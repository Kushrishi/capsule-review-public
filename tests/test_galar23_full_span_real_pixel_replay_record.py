"""Public safeguards for private Galar23 source-PNG retention aggregate.

No source images, private image-level rows or original frame identifiers.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "experiments" / "galar23-full-span-real-pixel-replay-2026-11-03" / "aggregate.json"
REPORT = ROOT / "docs" / "GALAR23_FULL_SPAN_REAL_PIXEL_REPLAY.md"


def test_real_image_retention_counts_are_consistent_with_frozen_selection():
    d = json.loads(AGG.read_text(encoding="utf-8"))
    s = d["selection_policy"]
    p = d["source_provenance"]
    labels = d["previous_verified_reference_blood_image_labels"]
    assert s["imported_reference_images"] == 512
    assert s["predeclared_scripted_bookmarks"] == 51
    assert s["predeclared_scripted_intervals"] == 16
    assert s["standard_boundary_only_export_images"] == 79
    assert s["full_span_export_images"] == 295
    assert s["additional_images_retained_by_full_spans"] == 216
    assert 79 + 216 == 295
    assert s["strict_interior_imported_positions"] == 240
    assert s["imported_images_inside_marked_spans"] == 272
    assert s["imported_images_still_absent_from_full_span_archive"] == 217
    assert s["imported_images_still_absent_from_full_span_archive"] + 295 == 512
    assert p["original_source_reference_pngs_rehashed"] == 512
    assert p["original_source_image_sha256_passed"] == 512
    assert p["normalized_display_png_sha256_recomputed_for_selected_full_span"] == 295
    assert p["previously_exported_boundary_only_display_pngs_matched_byte_for_byte"] == 79
    assert p["full_span_archived_display_png_sha256_reverified"] == 295
    assert labels["explicit_blood_positive_imported_reference_images"] == 4
    assert labels["blood_positive_reference_images_in_standard_boundary_export"] == 0
    assert labels["blood_positive_reference_images_in_full_span_export"] == 2
    assert labels["blood_positive_reference_images_outside_full_span_export"] == 2


def test_source_run_claims_and_credential_gates_not_overstated():
    d = json.loads(AGG.read_text(encoding="utf-8"))
    f = d["frozen_scientific_gate"]
    p = d["source_provenance"]
    labels = d["previous_verified_reference_blood_image_labels"]
    assert not p["current_main_route_executed_byte_for_byte"]
    assert p["importer_identity_digest_recomputed_and_matched"]
    assert p["previously_saved_reviewer_and_interval_histories_reconciled"]
    assert p["private_original_archive_and_receipt_preserved_in_capsule_review_library"]
    assert labels["full_original_source_positive_annotation_runs"] is None
    assert labels["direct_retained_source_positive_annotation_runs"] is None
    assert labels["clinical_lesions"] is None
    assert not f["official_corrected_source_verified_in_this_session"]
    assert f["protected_exams_11_through_20_and_61_through_80_unopened"]
    assert not f["model_promoted"]
    assert not d["selection_policy"]["original_source_video_completeness_verified"]
    assert "different numbers of retained images" in d["interpretation"]
    assert "NOT AI model detection" in d["interpretation"]
    report = REPORT.read_text(encoding="utf-8")
    for phrase in (
        "295", "216", "79", "512", "0", "two",
        "not a byte-identical execution",
        "not superior", "not distinct lesions",
        "source-run recall remain unavailable",
    ):
        assert phrase.casefold() in report.casefold()


def test_public_aggregate_contains_no_private_per_frame_rows_or_archive():
    d = json.loads(AGG.read_text(encoding="utf-8"))
    encoded = AGG.read_text(encoding="utf-8")
    assert not any(isinstance(item, list) for item in d.values())
    assert "PRIVATE" not in encoded or "private" in encoded.lower()
    forbidden_keys = (
        '"study_id"', '"frames"', '"filename"', '"source_index"', '"review_history"',
        '"interval_history"', '"individual_labels"', '"source_image_sha256"',
        '"reviewer_note"', '"patient"', '"per_frame_predictions"',
    )
    for key in forbidden_keys:
        assert key not in encoded
    assert "No original images" in d["privacy"]
