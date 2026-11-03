"""Verify a local Capsule Review export and produce an aggregate-only evidence receipt.

Example:
    python scripts/audit_review_evidence.py --review-zip private-review.zip \
      --study-manifest private-study.json --output new-local-receipt.json

Never upload medical images, full source manifests, exported notes or this
private review ZIP to public CI or a hosted review service.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from capsule_review.evidence_receipt import audit_review_export_zip


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-zip", type=Path, required=True)
    parser.add_argument("--study-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh local aggregate JSON; cannot exist")
    args = parser.parse_args(argv)
    receipt = audit_review_export_zip(
        review_zip=args.review_zip,
        study_manifest_path=args.study_manifest,
        output=args.output,
    )
    print("Verified selected-image bytes, complete importer manifest identity, "
          "final reviewer history, interval history and exact selected union.")
    print(
        f"{receipt['selected_export_images']} selected images from "
        f"{receipt['imported_images']} imports; "
        f"{receipt['interval_interior_images_not_exported']} imported interior "
        "images inside marked intervals were NOT included in the export."
    )
    print("Aggregate-only engineering receipt created locally. "
          "No pathology labels, lesion sensitivity or reader-time benefit assessed.")


if __name__ == "__main__":
    main()
