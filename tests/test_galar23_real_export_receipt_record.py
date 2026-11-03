"""Public-only replay of the frozen, label-blind Galar23 selection positions.

No original source indices, source-label rows, patient data, images, or private
review export required to reproduce the *position-accounting* arithmetic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from capsule_review.evidence_receipt import _position_coverage, _uniform_at_equal_workload

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "experiments" / "galar23-interval-real-pilot-2026-11-03"
RECEIPT = DIR / "export_evidence_receipt.json"
PREVIOUS = DIR / "aggregate.json"


def _fixed_public_selection_plan():
    total = 512
    bookmarks = _uniform_at_equal_workload(total, 51)
    spans = [(32 * j, 32 * j + 16) for j in range(16)]
    endpoints = {p for start, end in spans for p in (start, end)}
    selected = bookmarks | endpoints
    covered = {p for start, end in spans for p in range(start, end + 1)}
    interior = {p for start, end in spans for p in range(start + 1, end)}
    return total, bookmarks, spans, endpoints, selected, covered, interior


def test_public_selection_arithmetic_matches_private_verified_real_export_counts():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prior = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    total, bookmarks, spans, endpoints, selected, covered, interior = _fixed_public_selection_plan()
    assert total == receipt["imported_images"] == prior["observations"]["verified_original_reference_pngs_imported"]
    assert len(bookmarks) == receipt["explicitly_saved_images"] == 51
    assert len(spans) == receipt["marked_image_intervals"] == 16
    assert len(endpoints) == receipt["interval_boundary_images"] == 32
    assert len(selected) == receipt["selected_export_images"] == prior["observations"]["unique_exported_boundary_or_bookmarked_images"] == 79
    assert len(bookmarks & endpoints) == receipt["images_both_saved_and_interval_boundary"] == 4
    assert len(endpoints - bookmarks) == receipt["images_only_selected_as_interval_boundary"] == 28
    assert len(covered) == receipt["unique_imported_positions_in_marked_spans"] == 272
    assert len(interior) == receipt["unique_imported_interval_interior_positions"] == 240
    assert len(interior - selected) == receipt["interval_interior_images_not_exported"] == 216
    assert total - len(selected) == receipt["imported_images_not_selected_for_export"] == 433
    assert receipt["selected_export_fraction_of_imported"] == pytest.approx(79 / 512, abs=1e-8)


def test_same_workload_uniform_distance_comparator_reproduces_report():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    n, _, _, _, selected, _, interior = _fixed_public_selection_plan()
    uniform = _uniform_at_equal_workload(n, len(selected))
    assert len(uniform) == len(selected) == 79
    assert _position_coverage(n, selected) == receipt["selected_position_coverage"]
    assert _position_coverage(n, uniform) == receipt["uniform_reference_position_coverage_at_exact_same_workload"]
    omitted = sorted(interior - selected)
    longest = run = 0
    prev = None
    for position in omitted:
        run = run + 1 if prev is not None and prev + 1 == position else 1
        longest = max(longest, run)
        prev = position
    assert longest == receipt["longest_consecutive_imported_position_gap_inside_intervals"] == 9
    assert receipt["selected_position_coverage"]["maximum_nearest_selected_imported_positions"] == 5
    assert receipt["uniform_reference_position_coverage_at_exact_same_workload"]["maximum_nearest_selected_imported_positions"] == 3


def test_public_receipt_privacy_no_clinical_or_full_source_claims():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prior = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    assert receipt["audit_passed"] is True
    assert receipt["selected_image_display_sha256_verified_by_zip_reader"] is True
    assert receipt["original_import_manifest_identity_digest_recomputed"] is True
    assert receipt["review_event_revisions_replayed"] == 51
    assert receipt["reviewer_interval_event_revisions_replayed"] == 16
    for key in ("clinical_validity", "pathology_labels_or_run_recall_evaluated",
                "reader_time_savings_measured", "all_imported_source_image_bytes_rehashed",
                "original_full_video_completeness_verified"):
        assert receipt[key] is False
    assert receipt["observed_source_index_assessment"] == "index-jumps"
    assert prior["source_run_evaluation_gate"]["completed"] is False
    assert all(prior["observations"][key] is None for key in (
        "original_source_annotation_positive_runs",
        "direct_selected_positive_annotation_runs",
        "numeric_span_overlapped_positive_annotation_runs"))
    # Never check in source-derived frame identifiers, per-image SHA values, notes,
    # original files, patient names, image paths or private reviewer history.
    public_text = RECEIPT.read_text(encoding="utf-8")
    forbidden = ('"study_id"', '"frames"', '"interval_history"', '"review_history"',
                 '"source_sha256"', '"display_sha256"', '"filename"', '"source_index"',
                 '"patient_id"', "Synthetic reviewer note", "frame_000")
    for value in forbidden:
        assert value not in public_text
    assert not any(isinstance(value, list) for value in receipt.values())
