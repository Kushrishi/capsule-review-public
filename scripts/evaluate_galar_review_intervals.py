"""Offline Galar source-run audit of a privately exported Capsule Review review.

Never run this on a public hosted runner or publish inputs/predictions. Reads
only the exact corrected CSV for the permitted fitting examination and emits
aggregate statistics without private frame IDs or original annotation values.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from capsule_review.interval_evidence import evaluate_private_galar_export


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exam", type=int, required=True, help="Original Galar fitting examination ID 21–30 only")
    parser.add_argument("--review-zip", type=Path, required=True, help="Private Capsule Review export ZIP")
    parser.add_argument("--study-manifest", type=Path, required=True, help="Private full local study manifest JSON")
    parser.add_argument("--verified-source-manifest", type=Path, required=True, help="Private source-verified original PNG receipt JSON")
    parser.add_argument("--corrected-labels-zip", type=Path, required=True, help="Official corrected Galar v2 labels ZIP")
    parser.add_argument("--output", type=Path, required=True, help="Private aggregate output JSON; must not exist")
    args = parser.parse_args(argv)
    result = evaluate_private_galar_export(
        review_zip=args.review_zip, study_manifest_path=args.study_manifest,
        verified_source_manifest_path=args.verified_source_manifest,
        corrected_labels_zip=args.corrected_labels_zip, exam=args.exam,
        output=args.output,
    )
    print("Completed private Galar reviewer interval evidence audit for one permitted fitting examination.")
    print(f"Selected exported images: {result['selected_export_images']}; "
          f"direct source-positive annotation runs: {result['direct_selected_positive_annotation_runs']}; "
          f"interval-only overlap without direct evidence: {result['span_overlapped_without_direct_selected_evidence']}.")
    print("No source image IDs, per-image labels, reviewer notes or clinical findings were published.")


if __name__ == "__main__":
    main()
