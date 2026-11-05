"""Check private development images and disjoint fit/evaluation assignments.

Example:
    python scripts/check_development_cohort.py \
        --manifest /private/manifest.json \
        --source-root /private/original-images \
        --expected-sha256 0123456789abcdef...64hex

The digest must have been saved externally BEFORE dataset/result inspection.
This tool never writes private data or outputs source paths, names or hashes.
A structural PASS still requires human review of patient identity, reference
standards, permissions and study design.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from capsule_review.development_preflight import inspect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    repo = Path(__file__).resolve().parents[1]
    if source.is_relative_to(repo):
        parser.error("Private source images cannot be inside the public Git repository.")
    manifest_path = args.manifest
    if (manifest_path.is_symlink() or not manifest_path.is_file()
        or not 0 < manifest_path.stat().st_size < 32 * 1024 * 1024):
        parser.error("Manifest must be a small, regular private JSON file.")
    if manifest_path.resolve().is_relative_to(repo):
        parser.error("Private per-frame manifest cannot be stored in the public repository.")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = inspect(payload, source_root=args.source_root,
                         pinned_sha256=args.expected_sha256)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Exceptions can contain sensitive paths. Do not echo exception text.
        parser.error("Private preflight failed validation; inspect the local source separately.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
