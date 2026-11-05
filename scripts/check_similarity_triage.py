"""Audit precomputed PRIVATE cross-examination resemblance measurements.

Only a small redacted numerical aggregate is printed. Never publish or
upload raw source images, per-pair records or frame/candidate identities.

Example:
  python scripts/check_similarity_triage.py \
    --private-pairs /private/PRIVATE_refined_similarity_candidates_20261105.json \
    --expected-sha256 51f8eee0795efc731a74a41f506a9b9b0fad374f65661d47a9cb998d48022f8b

Requires the completed separately executed, source-SHA-verified private
image-comparison script (and original private images for fresh generation).
This tool is NOT an exhaustive new image search or patient linker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capsule_review.similarity_triage import summarize_private_pair_scores


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-pairs", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    file = args.private_pairs
    if (file.is_symlink() or not file.is_file()
        or file.resolve().is_relative_to(root)
        or not 0 < file.stat().st_size < 50 * 1024 * 1024):
        p.error("Private source-score file missing, too large or located inside public repository.")
    if (len(args.expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in args.expected_sha256)):
        p.error("Expected an externally pinned lowercase SHA-256 digest.")
    try:
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.expected_sha256:
            raise ValueError("Private source-score commitment mismatch.")
        result = summarize_private_pair_scores(json.loads(data))
    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        # Do not expose source identities or paths through a raised exception.
        p.error("Private score integrity or schema verification failed.")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
