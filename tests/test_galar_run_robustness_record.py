"""Protect the case-weighted, equal-workload Galar robustness audit.

Uses ONLY previously published source-locked aggregate counts; no medical pixels,
source annotation CSVs, per-frame predictions or private file manifests.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.audit_galar_run_robustness import (
    BUDGET_IMAGES, EXAMS, LABELS_SHA256, SOURCE_SHA256, audit,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/galar-run-coverage-2026-11-02/aggregate.json"
REPORT = ROOT / "experiments/galar-run-robustness-2026-11-03/aggregate.json"


def _source():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_exact_source_provenance_and_checked_output_is_reproducible(tmp_path):
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    assert audit(_source()) == stored
    assert stored["corrected_source_archive_sha256_from_prior_verified_audit"] == LABELS_SHA256
    assert stored["scientific_design"]["exam_ids_previously_inspected"] == list(EXAMS)
    assert not stored["scientific_design"]["independent_holdout_or_blinded_test"]
    assert not stored["scientific_design"]["patient_independence_verified"]
    assert not stored["scientific_design"]["clinical_validation"]
    assert not stored["scientific_design"]["selection_model_promoted"]
    assert stored["source_run_coverage_ceiling"] == {
        "full_source_annotation_runs": 283,
        "runs_reachable_by_all_512_reference_images": 110,
        "unreachable_even_at_full_reference_workload": 173,
        "short_1_to_5_source_runs": 124,
        "short_1_to_5_reachable_runs": 13,
    }

    script = ROOT / "scripts/audit_galar_run_robustness.py"
    out = tmp_path / "verified.json"
    command = [sys.executable, str(script), "--input", str(SOURCE), "--output", str(out)]
    run = subprocess.run(command, text=True, capture_output=True, check=True)
    assert "exploratory" in run.stdout
    assert json.loads(out.read_text(encoding="utf-8")) == stored
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0


def test_every_budget_equal_k_and_alternative_macro_micro_readouts():
    d = json.loads(REPORT.read_text(encoding="utf-8"))
    assert d["scientific_design"]["fixed_review_workload_each_exam"] == BUDGET_IMAGES
    assert d["scientific_design"]["positive_source_exam_count"] == 7
    assert d["scientific_design"]["blood_negative_label_exam_ids"] == ["9"]
    assert set(d["review_budgets"]) == set(BUDGET_IMAGES)
    for percentage, k in BUDGET_IMAGES.items():
        result = d["review_budgets"][percentage]
        assert result["selected_imported_images_per_exam"] == k
        assert set(result["methods"]) == {"original_checkpoint", "red_excess", "uniform"}
        assert set(result["paired_against_uniform"]) == {"original_checkpoint", "red_excess"}
        for method in result["methods"].values():
            assert method["selected_image_count_in_blood_negative_label_exams"] == k
            assert method["sum_distinct_source_annotation_runs_hit"] <= 110
            assert (method["short_1_to_5_run_hits"] + method["medium_6_to_25_run_hits"]
                    + method["long_26_plus_run_hits"] ==
                    method["sum_distinct_source_annotation_runs_hit"])
            assert 0 <= method["macro_per_exam_source_run_recall"] <= 1
            assert 0 <= method["micro_source_run_recall"] <= 1
        for compare in result["paired_against_uniform"].values():
            assert (compare["positive_exam_wins"] + compare["positive_exam_ties"] +
                    compare["positive_exam_losses"]) == 7
            assert len(compare["leave_one_exam_out_difference_by_exam"]) == 7
            assert compare["minimum_leave_one_exam_out_difference"] <= compare["maximum_leave_one_exam_out_difference"]
            assert "not 95% CIs" in compare["variance_warning"]

    ten = d["review_budgets"]["10"]
    assert ten["methods"]["original_checkpoint"]["sum_distinct_source_annotation_runs_hit"] == 28
    assert ten["methods"]["uniform"]["sum_distinct_source_annotation_runs_hit"] == 31
    assert ten["paired_against_uniform"]["original_checkpoint"]["positive_exam_wins"] == 2
    assert ten["paired_against_uniform"]["original_checkpoint"]["positive_exam_ties"] == 2
    assert ten["paired_against_uniform"]["original_checkpoint"]["positive_exam_losses"] == 3
    assert ten["paired_against_uniform"]["original_checkpoint"]["cases_whose_removal_changes_effect_direction"] == ["27"]
    assert ten["paired_against_uniform"]["original_checkpoint"]["macro_source_run_recall_difference"] > 0
    assert ten["paired_against_uniform"]["original_checkpoint"]["leave_one_exam_out_difference_by_exam"]["27"] < 0

    twentyfive = d["review_budgets"]["25"]
    assert twentyfive["methods"]["original_checkpoint"]["sum_distinct_source_annotation_runs_hit"] == 69
    assert twentyfive["methods"]["uniform"]["sum_distinct_source_annotation_runs_hit"] == 55
    assert twentyfive["paired_against_uniform"]["original_checkpoint"]["positive_exam_wins"] == 5
    assert twentyfive["paired_against_uniform"]["original_checkpoint"]["cases_whose_removal_changes_effect_direction"] == []
    assert d["review_budgets"]["100"]["methods"]["original_checkpoint"] == d["review_budgets"]["100"]["methods"]["uniform"]


@pytest.mark.parametrize("mutation", [
    lambda d: d["examinations"].update({"11": deepcopy(d["examinations"]["10"])}),
    lambda d: d.update({"source_corrected_release_sha256": "0" * 64}),
    lambda d: d["examinations"]["10"]["budgets"]["10"].update({"selected_reference_images": 50}),
    lambda d: d["examinations"]["10"]["budgets"]["10"]["methods"].pop("uniform"),
    lambda d: d["examinations"]["10"]["budgets"]["10"]["methods"]["uniform"].update({"source_annotation_runs_hit": 999}),
    lambda d: d["examinations"]["10"]["reference_ceiling_by_length"].update({"1-5": 999}),
    lambda d: d["examinations"]["9"].update({"reference_blood_positive": 1}),
    lambda d: d["examinations"]["29"]["budgets"]["100"]["methods"]["uniform"].update({"source_annotation_runs_hit": 0}),
])
def test_corrupted_or_reserved_source_fail_closed(mutation):
    data = _source()
    mutation(data)
    with pytest.raises(ValueError):
        audit(data)


def test_public_output_is_aggregate_only_and_retain_unfavorable_evidence():
    report = REPORT.read_text(encoding="utf-8")
    assert "private" not in json.loads(report)["source_data_access"].lower() or "no new" in report.lower()
    for private_key in (
        '"source_index"', '"filename"', '"image_sha256"', '"note"', '"review_history"',
        '"frame_ids"', '"individual_predictions"', '"per_frame_scores"', '"original_png"',
    ):
        assert private_key not in report
    data = json.loads(report)
    assert data["source_run_coverage_ceiling"]["unreachable_even_at_full_reference_workload"] == 173
    assert data["review_budgets"]["50"]["paired_against_uniform"]["original_checkpoint"]["macro_source_run_recall_difference"] < 0
    assert data["review_budgets"]["75"]["paired_against_uniform"]["original_checkpoint"]["cases_whose_removal_changes_effect_direction"]
    assert data["scientific_design"]["no_significance_tests"]
