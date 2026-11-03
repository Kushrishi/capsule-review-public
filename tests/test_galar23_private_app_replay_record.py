"""Verify nonidentifying public record of PRIVATE original-PNG app replay.

No source pixels, individual prediction values or original frame IDs in Git.
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "experiments/galar23-private-real-app-replay-2026-11-03/aggregate.json"
REPORT = ROOT / "docs/GALAR23_PRIVATE_APP_REPLAY.md"


def test_private_real_pixel_replay_record_is_scoped_and_complete():
    d = json.loads(RECORD.read_text(encoding="utf-8"))
    assert d["imported_original_source_pngs"] == 512
    assert d["rehashed_source_pngs_matching_prior_private_manifest"] == 512
    assert d["recomputed_normalized_display_pngs_matching_prior_private_manifest"] == 512
    assert d["original_exploratory_blood_cnn_scores_in_local_sqlite"] == 512
    assert d["persistent_score_values_matched_prior_verified_private_scores"]
    assert d["local_image_api_and_prediction_api_passed"]
    assert d["local_browser_image_and_prediction_display_passed"]
    assert d["private_browser_javascript_errors"] == 0
    assert not d["human_review_rows_changed"]
    assert not d["reference_labels_written_to_app"]
    assert not d["current_main_executed_on_real_images"]
    assert d["current_main_synthetic_ci_verified_separately"]
    assert d["private_workspace_archive_bytes"] == 110095614
    assert len(d["private_workspace_archive_sha256"]) == 64
    assert not d["model_validated"]
    assert not d["full_original_source_positive_annotation_runs_evaluated"]
    assert not d["independent_patient_or_examination_validation"]
    assert not d["clinical_validity"]


def test_public_research_record_has_no_private_individual_data():
    text = RECORD.read_text(encoding="utf-8")
    for private in (
        '"study_id"', '"source_index"', '"source_filename"', '"frame_000',
        '"model_score"', '"source_png_sha256"', '"display_png_sha256"',
        '"original_blood_label"', '"patient"', '"reviewer_note"',
        '"individual_predictions"', '"private_workspace_zip_bytes"',
        '"source_rows"',
    ):
        assert private not in text
    report = REPORT.read_text(encoding="utf-8")
    assert "older application snapshot" in report.lower()
    assert "not" in report.lower()
    assert "512" in report
    assert "no clinical" in report.lower()
    assert "previously inspected" in report.lower()
