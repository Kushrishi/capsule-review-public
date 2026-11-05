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

from capsule_review.cohort_gate import REQUIRED, assess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", nargs="?", type=Path, help="Private metadata worksheet JSON")
    parser.add_argument("--template", action="store_true", help="Print a blocked, all-unknown worksheet template")
    args = parser.parse_args()
    if args.template:
        if args.worksheet is not None:
            parser.error("Choose either --template or a worksheet file.")
        print(json.dumps({
            "schema_version": 1,
            "candidate": "REPLACE_WITH_DATASET_NAME",
            "checks": {key: {"status": "unknown", "reason": "", "evidence_ref": ""}
                       for key in REQUIRED},
        }, indent=2, sort_keys=True))
        return 0
    if args.worksheet is None:
        parser.error("Provide a private worksheet path or use --template.")
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
