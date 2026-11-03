"""Only public-safe aggregate invariants; no original medical images are used in CI."""
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AGGREGATE=ROOT/"experiments"/"galar23-interval-real-pilot-2026-11-03"/"aggregate.json"
REPORT=ROOT/"docs"/"GALAR23_REAL_INTERVAL_PILOT_RESULTS.md"


def test_public_pilot_counts_reproduce_report_without_source_identifier_leakage():
    data=json.loads(AGGREGATE.read_text(encoding="utf-8"))
    a=data["observations"]
    assert a["verified_original_reference_pngs_imported"]==512
    assert a["blood_positive_reference_image_labels_from_prior_verified_manifest"]==4
    assert a["simulated_explicit_bookmarks"]==51
    assert a["simulated_interval_spans"]==16
    assert a["unique_exported_boundary_or_bookmarked_images"]==79
    assert a["exported_directly_source_blood_positive_images"]==0
    assert a["source_blood_positive_reference_images_in_strict_interval_interiors_not_exported"]==2
    assert a["source_blood_positive_reference_images_outside_all_marked_spans"]==2
    text=REPORT.read_text(encoding="utf-8")
    for number in ("512", "51", "16", "79", "two"):
        assert number in text.lower()
    assert "not a human reader session" in text.lower()
    assert "not" in data["interpretation"].lower()


def test_full_source_run_metrics_remain_explicitly_null_when_official_source_absent():
    data=json.loads(AGGREGATE.read_text(encoding="utf-8"))
    assert data["source_run_evaluation_gate"]["completed"] is False
    for key in ("original_source_annotation_positive_runs",
                "direct_selected_positive_annotation_runs",
                "numeric_span_overlapped_positive_annotation_runs"):
        assert data["observations"][key] is None
    assert data["source_run_evaluation_gate"]["protected_exams_11_through_20_and_61_through_80_unopened"]
    assert data["source_run_evaluation_gate"]["official_Galar_corrected_archive_SHA256_required"]=="2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
    assert data["verification"]["original_source_png_bytes_verified_against_private_SHA256_manifest"]==512
    assert data["verification"]["exported_display_PNG_SHA256_and_ZIP_CRC_replayed_independently"]==79


def test_public_record_contains_no_private_frame_level_source_content():
    aggregate=AGGREGATE.read_text(encoding="utf-8")
    data=json.loads(aggregate)
    assert set(data["observations"])=={
        "verified_original_reference_pngs_imported",
        "blood_positive_reference_image_labels_from_prior_verified_manifest",
        "simulated_explicit_bookmarks","simulated_interval_spans",
        "unique_exported_boundary_or_bookmarked_images",
        "exported_directly_source_blood_positive_images",
        "source_blood_positive_reference_images_in_strict_interval_interiors_not_exported",
        "source_blood_positive_reference_images_outside_all_marked_spans",
        "original_source_annotation_positive_runs","direct_selected_positive_annotation_runs",
        "numeric_span_overlapped_positive_annotation_runs",
    }
    assert "private_artifacts_location" in data
    forbidden=('private_source_manifest.json','review.json','frame_0000','source_frame_index',
               'individual_annotations','raw_image_base64','reviewer_note_text','prediction_rows')
    for value in forbidden:
        assert value not in aggregate
    assert "no original images" in data["privacy"].lower()
