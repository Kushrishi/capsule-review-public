"""Run an authenticated local scoring adapter, or verify a sealed sequence.

Adapters are trusted, reviewed Python code supplied by the study owner. A hash
authenticates that code; it does not make arbitrary Python safe to execute.
No model, dataset download, event evaluator, or external submission is included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

from capsule_review.sequence_pipeline import run_sequence, verify_seal


def load_adapter(method: dict, files: dict[str, Path]):
    """Import only the exact adapter already checked by run_sequence."""
    path = files.get("adapter")
    if path is None or path.suffix != ".py":
        raise ValueError("The method must authenticate one Python file named adapter.")
    expected = next(row["sha256"] for row in method["files"] if row["name"] == "adapter")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Adapter changed after authentication.")
    # Compile the authenticated bytes directly, never an unverified .pyc file.
    name = "_capsule_frozen_adapter_" + expected
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
        factory = getattr(module, "create_scorer", None)
        if not callable(factory):
            raise ValueError("The adapter must expose create_scorer(method, files).")
        scorer = factory(method, files)
        if not callable(scorer):
            raise ValueError("The adapter factory must return a batch scorer.")
        return scorer
    finally:
        sys.modules.pop(name, None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Score one complete manifest with a reviewed local adapter.")
    run.add_argument("--source-manifest", type=Path, required=True)
    run.add_argument("--source-sha256", required=True)
    run.add_argument("--method-manifest", type=Path, required=True)
    run.add_argument("--method-sha256", required=True)
    run.add_argument("--source-root", type=Path, required=True)
    run.add_argument("--asset-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="Check a bundle against an independently retained seal hash.")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--seal-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_seal(args.bundle, expected_seal_sha256=args.seal_sha256)
            summary = {key: result[key] for key in
                       ("seal_sha256", "method_id", "frame_count")}
            summary["budgets"] = [{"percent": row["percent"], "k": row["k"]}
                                  for row in result["budgets"]]
        else:
            result = run_sequence(
                args.source_manifest, args.method_manifest, args.source_root,
                args.asset_root, args.output,
                expected_source_sha256=args.source_sha256,
                expected_method_sha256=args.method_sha256,
                scorer_factory=load_adapter,
            )
            summary = {"seal_sha256": result["seal_sha256"]}
            summary.update({key: result["receipt"][key] for key in (
                "status", "method_id", "frame_count", "wall_seconds",
                "frames_per_second_including_preflight", "process_peak_rss_bytes",
            )})
    except KeyboardInterrupt:
        parser.exit(130, "Sequence execution interrupted; no successful output is claimed.\n")
    except Exception:
        parser.exit(1, "Sequence operation failed. Inspect local inputs or the private failure receipt.\n")
    print(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
