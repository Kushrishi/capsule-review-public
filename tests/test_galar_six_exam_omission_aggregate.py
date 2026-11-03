"""Public nonidentifying cross-check of six previously inspected Galar cases.

This validates a previously run private replay's *aggregates*, not the
underlying publisher corrected-source blood annotation intervals or a new
medical model. All per-frame records stay outside the public repository.
"""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "experiments/galar-six-exam-omission-2026-11-03/aggregate.json"
OLDER = ROOT / "experiments/galar-priority-score-2026-11-03/aggregate.json"
REPORT = ROOT / "docs/GALAR_SIX_EXAM_OMISSION_SPAN_RESULTS.md"
CASES = ("21", "23", "25", "27", "29", "30")
METHODS = {"uniform", "score", "score_diverse", "score_bin"}
BUDGETS = (25, 51, 128, 256, 384, 512)


def audit():
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_each_actual_score_replay_matches_previously_published_baselines():
    d = audit()
    previous = json.loads(OLDER.read_text(encoding="utf-8"))
    assert d["schema_version"] == 1
    assert d["comparison_count"] == 144
    assert set(d["case_ids"]) == set(CASES)
    assert set(d["methods"]) == METHODS
    assert d["fixed_exact_workloads"] == list(BUDGETS)
    assert not d["source_run_metrics_from_this_replay"]
    assert not d["clinical_validation"]
    assert not d["patients_independent"]
    assert not d["model_promoted"]
    assert not d["source_images_labels_predictions_committed"]
    assert d["comparison_reconciles_prior_original_score_replay"]
    assert sum(d["per_exam"][ex]["positive_reference_images"] for ex in CASES) == 287
    for k in BUDGETS:
        across = d["by_workload"][str(k)]
        assert set(across) == METHODS
        assert set(previous["workloads"][str(k)]) == METHODS | {"selected_images_per_exam"}
        for method in METHODS:
            expected_hits = previous["workloads"][str(k)][method]["blood_positive_reference_images_retained"]
            row = across[method]
            assert row["sum_positive_reference_images_hit"] == expected_hits
            case_hit_total = 0
            for exam in CASES:
                case = d["per_exam"][exam]
                record = case["workloads"][str(k)][method]
                assert record["selected_count"] == k
                assert 0 <= record["positive_reference_images_hit"] <= min(k, case["positive_reference_images"])
                assert 0 <= record["largest_consecutive_omitted_imported_images"] <= 512 - k
                assert 0 <= record["max_nearest_selected_imported_positions"] <= 511
                assert 1 <= record["occupied_16_equal_ordinal_bins"] <= min(k, 16)
                if k == 512:
                    assert record["largest_consecutive_omitted_imported_images"] == 0
                    assert record["max_nearest_selected_imported_positions"] == 0
                    assert record["occupied_16_equal_ordinal_bins"] == 16
                case_hit_total += record["positive_reference_images_hit"]
            assert row["sum_positive_reference_images_hit"] == case_hit_total
            assert 0 <= row["worst_case_largest_omitted_span"] <= 512 - k
            assert 0 <= row["mean_largest_omitted_span"] <= row["worst_case_largest_omitted_span"]
            assert 0 <= row["exam_count_largest_gap_gt_2x_uniform"] <= 6


def test_case_mix_and_adverse_research_result_retained():
    d = audit()
    k = d["by_workload"]["51"]
    assert k["score"]["sum_positive_reference_images_hit"] == 95
    assert k["uniform"]["sum_positive_reference_images_hit"] == 27
    assert k["score_bin"]["sum_positive_reference_images_hit"] == 31
    assert k["score_diverse"]["sum_positive_reference_images_hit"] == 43
    assert k["score"]["mean_largest_omitted_span"] == 239.6667
    assert k["uniform"]["mean_largest_omitted_span"] == 10.0
    assert k["score_bin"]["mean_largest_omitted_span"] == 17.1667
    assert k["score_diverse"]["mean_largest_omitted_span"] == 68.8333
    assert k["score"]["mean_occupied_16_equal_ordinal_bins"] == 7.1667
    assert k["uniform"]["mean_occupied_16_equal_ordinal_bins"] == 16
    for case, positive in (("21", 1), ("23", 4), ("25", 14)):
        assert d["per_exam"][case]["positive_reference_images"] == positive
        assert d["per_exam"][case]["workloads"]["51"]["score"]["positive_reference_images_hit"] == 0
    body = REPORT.read_text(encoding="utf-8").lower()
    assert "previously examined" in body
    assert "not clinical validation" in body
    assert "144/144" in body
    assert "not original video frames" in body


def test_no_individual_medical_data_or_unsafe_interpretation_in_public_record():
    d = audit()
    forbidden = {
        "patient_id", "source_frame", "frame_index", "image_sha256",
        "prediction_score", "source_annotations", "source_run_locations",
        "individual_labels", "source_filename", "original_image",
    }
    def walk(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                assert key not in forbidden
                walk(inner)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(d)
    assert "not original frames" in d["metric_definition"]
    assert not d["source_run_metrics_from_this_replay"]
