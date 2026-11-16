"""Route sealed-sequence-only changes to synthetic, non-fitting CI checks.

This is a test-scope decision, not a scientific or privacy authorization. The
complete branch diff must match an explicit allowlist. Other changes, empty
diffs, and default-branch pushes retain the existing full CI route. Missing
history or malformed event data fail the routing job instead of guessing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess


SEQUENCE_ONLY_PATHS = frozenset({
    ".github/workflows/tests.yml",
    "docs/SEALED_SEQUENCE_INFERENCE.md",
    "scripts/ci_scope.py",
    "scripts/run_frozen_sequence.py",
    "src/capsule_review/sequence_pipeline.py",
    "tests/test_ci_scope.py",
    "tests/test_sequence_pipeline.py",
})


def scope_for_paths(paths: list[str]) -> str:
    return "sequence" if paths and set(paths) <= SEQUENCE_ONLY_PATHS else "full"


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
    ).stdout


def _sha(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Expected a complete commit SHA")
    return value


def changed_paths(root: Path, base: str, head: str) -> list[str]:
    """Use the cumulative branch diff, including both sides of any rename."""
    common = _sha(_git(root, "merge-base", _sha(base), _sha(head)).decode().strip())
    raw = _git(root, "diff", "--name-only", "--no-renames", "-z", common, head, "--")
    return [os.fsdecode(path) for path in raw.split(b"\0") if path]


def event_scope(root: Path, event_name: str, event: dict) -> str:
    if event_name == "pull_request":
        base = _sha(event["pull_request"]["base"]["sha"])
        head = _sha(event["pull_request"]["head"]["sha"])
    elif event_name == "push":
        head = _sha(event["after"])
        default_branch = event["repository"]["default_branch"]
        if not isinstance(default_branch, str) or not default_branch:
            raise ValueError("Missing default branch")
        if event["ref"] == f"refs/heads/{default_branch}":
            return "full"
        # Tags and other references keep the full route. Feature branches must
        # include all changes since their default-branch ancestor, not just the
        # last pushed commit, which could hide an earlier unrelated change.
        if not isinstance(event["ref"], str) or not event["ref"].startswith("refs/heads/"):
            return "full"
        base = _sha(_git(
            root, "rev-parse", "--verify", f"refs/remotes/origin/{default_branch}^{{commit}}",
        ).decode().strip())
    else:
        raise ValueError("Unsupported CI event")
    if _git(root, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("Checkout does not match event head")
    return scope_for_paths(changed_paths(root, base, head))


def main() -> int:
    try:
        root = Path(__file__).resolve().parents[1]
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        mode = event_scope(root, os.environ["GITHUB_EVENT_NAME"], event)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"mode={mode}\n")
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError):
        print("CI scope failed: cannot verify the complete change scope; no route selected.")
        return 1
    print(f"CI test scope: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
