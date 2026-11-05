"""Structural preflight for an external capsule-endoscopy dataset.

Input is a local PRIVATE metadata worksheet, not a public Git artifact.
An all-pass result still requires independent human/clinical review and a
separately frozen pre-outcome study protocol; it is NOT study approval.

Usage: python scripts/check_cohort_gate.py /private/worksheet.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from capsule_review.cohort_gate import assess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path, help="Private metadata worksheet JSON")
    args = parser.parse_args()
    path = args.worksheet
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 64 * 1024:
        parser.error("Expected an existing small, regular local JSON worksheet.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = assess(payload)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.public_summary(), indent=2, sort_keys=True))
    return 0 if result.decision == "HUMAN_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
