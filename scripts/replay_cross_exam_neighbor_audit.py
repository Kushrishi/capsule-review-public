"""Replay the private cross-examination embedding-neighbour score audit.

This is a SCORE replay, not a repeat of source-pixel decoding, the full
embedding-nearest-neighbour search, or a patient-identity verification.

Example:
  python scripts/replay_cross_exam_neighbor_audit.py \
    --private-archive /private/Capsule_Review_Private_Cross_Examination_Neighbor_Audit_20261105.zip \
    --expected-sha256 5e43c1a39422ece4a3b1549f47ec397d14f2c6fddd58146b5492e4443ab6e53d

Never place original frames, per-image scores, private archives or frame IDs
inside the public source repository. Only aggregate counts are printed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from capsule_review.similarity_triage import summarize_private_embedding_neighbors

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RECORD = ROOT / "experiments/galar-cross-exam-neighbor-audit-20261105/aggregate.json"
PRIVATE_MEMBER = "PRIVATE_verified_top_embedding_neighbors.json"
MAX_ARCHIVE = 20 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-archive", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    source = args.private_archive
    if (source.is_symlink() or not source.is_file()
        or source.resolve().is_relative_to(ROOT)
        or not 0 < source.stat().st_size <= MAX_ARCHIVE
        or len(args.expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in args.expected_sha256)):
        parser.error("A small, pinned private archive outside the public repository is required.")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != args.expected_sha256:
        parser.error("Private research archive does not match the externally pinned SHA-256.")
    try:
        with zipfile.ZipFile(source) as archive:
            if PRIVATE_MEMBER not in archive.namelist():
                raise ValueError("Required source-score member missing.")
            rows = json.loads(archive.read(PRIVATE_MEMBER))
        summary = summarize_private_embedding_neighbors(rows)
        public = json.loads(PUBLIC_RECORD.read_text(encoding="utf-8"))
        expected = public["original_image_pretrained_embedding_screen"]["private_original_pixel_followup"]
        if (summary["candidate_pairs_scored"] != expected["candidate_pairs"]
            or summary["unique_original_source_frames"] != expected["fresh_original_png_sha256_reverified"]
            or summary["strict_pixel_aligned_close_copy_pairs"] != expected["strict_pixel_aligned_close_copy_pairs"]
            or summary["ssim_at_least_0_90"] != expected["ssim_at_least_0_90_pairs"]
            or summary["maximum_gray_ssim"] != expected["maximum_grayscale_ssim"]):
            raise ValueError("The current published source audit no longer matches saved private metrics.")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError, zipfile.BadZipFile):
        # Never echo source paths, frame/group IDs or other private records.
        parser.error("Private score replay or public aggregate verification failed.")
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
