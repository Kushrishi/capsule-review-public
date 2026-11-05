"""Read-only scientific reconciliation of the negative 16-exam CNN result.

No private source images, labels, individual predictions or checkpoints are
needed. These tests must not promote or relabel this retrospective result.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/"experiments/galar-exam-tempered-cnn-20261105/aggregate.json"
SOURCE=ROOT/"experiments/galar-development-source-audit-20261105/aggregate.json"
METHODS=("pooled_class_balanced","tempered_examination_balanced")
BUDGETS=("51","128","256")


def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_preanalysis_design_and_all_16_case_outcomes_are_still_present():
    a=record()
    source=json.loads(SOURCE.read_text(encoding="utf-8"))
    assert a["preanalysis_git_commit"]=="eeafd155f4ddf5f2beef5d7b383f41159cded5ef"
    assert a["verified_original_selected_png_images"]==11147
    assert a["verified_uniform_reference_images"]==8192
    assert a["verified_selected_blood_positive_images"]==1663
    assert a["positive_uniform_reference_images"]==526
    assert a["n_examinations"]==16
    assert set(a["per_examination"])==set(source["per_examination"])
    assert a["training"]["epochs"]==6
    assert a["training"]["batch_size"]==64
    assert a["training"]["early_stop_or_checkpoint_selection"] is False
    assert a["training"]["augmentation"]=="none"
    assert a["evaluation"]["fixed_image_budgets"]==[51,128,256]
    assert a["evaluation"]["source_uniform_reference_only"] is True
    assert a["evaluation"]["heldout_examination_enrichment_used_for_fitting_or_scoring"] is False
    assert a["evaluation"]["positive_examination_count"]==11
    assert len(a["folds"])==4
    assert sorted(int(e) for fold in a["folds"] for e in fold["heldout_exams"])==sorted(
        int(e) for e in a["per_examination"]
    )
    assert [fold["fit_selected_images"] for fold in a["folds"]]==[9099,8602,7635,8105]
    for eid,row in a["per_examination"].items():
        assert row["reference_images"]==512
        assert row["positive_reference_images"]==source["per_examination"][eid][
            "reference_blood_positive_images"
        ]
        for arm in METHODS:
            r=row["methods"][arm]
            assert set(r["hits"])==set(BUDGETS)
            assert all(type(r["hits"][k]) is int and
                       0 <= r["hits"][k] <= min(int(k),row["positive_reference_images"])
                       for k in BUDGETS)
            if row["positive_reference_images"]==0:
                assert r["average_precision"] is None
                assert r["roc_auc"] is None
            else:
                assert all(0<=r[k]<=1 and math.isfinite(r[k])
                           for k in ("roc_auc","average_precision"))


def test_full_aggregate_reconciliation_including_unfavorable_primary():
    data=record()
    pos=[r for r in data["per_examination"].values()
         if r["positive_reference_images"]>0]
    assert len(pos)==11
    for method in METHODS:
        metrics=data["aggregate"][method]
        assert metrics["mean_defined_examination_average_precision"]==pytest.approx(
            sum(r["methods"][method]["average_precision"] for r in pos)/11,abs=1e-12
        )
        assert metrics["mean_defined_examination_roc_auc"]==pytest.approx(
            sum(r["methods"][method]["roc_auc"] for r in pos)/11,abs=1e-12
        )
        for k in BUDGETS:
            hits=sum(r["methods"][method]["hits"][k] for r in pos)
            recall=sum(r["methods"][method]["hits"][k]/r["positive_reference_images"]
                       for r in pos)/11
            assert hits==metrics["pooled_positive_reference_hits_at_k"][k]
            assert recall==pytest.approx(
                metrics["mean_positive_examination_recall_at_k"][k],abs=1e-12
            )
    control=data["aggregate"][METHODS[0]]
    candidate=data["aggregate"][METHODS[1]]
    delta=100*(candidate["mean_positive_examination_recall_at_k"]["51"]
               -control["mean_positive_examination_recall_at_k"]["51"])
    assert delta==pytest.approx(-.12987695364744534,abs=1e-9)
    assert data["primary_candidate_minus_control_pp"]==pytest.approx(delta,abs=1e-12)
    assert control["pooled_positive_reference_hits_at_k"]["51"]==151
    assert candidate["pooled_positive_reference_hits_at_k"]["51"]==148
    assert candidate["mean_defined_examination_roc_auc"]>control["mean_defined_examination_roc_auc"]
    assert candidate["mean_defined_examination_average_precision"]<control["mean_defined_examination_average_precision"]
    assert (data["top51_cases_improved"],data["top51_cases_deteriorated"],data["top51_cases_tied"]) == (1,2,8)
    assert data["exploratory_signal_rule"]["met"] is False
    assert data["decision"].startswith("REJECT_CANDIDATE_FOR_PROMOTION")


def test_zero_positive_cases_and_hidden_evaluation_boundaries():
    data=record()
    assert sorted(int(e) for e,r in data["per_examination"].items()
                  if r["positive_reference_images"]==0)==[3,5,8,22,24]
    boundaries=data["data_boundary"]
    assert all(value is False for value in boundaries.values())
    private=data["private_reproducibility"]
    assert private["saved_checkpoints"]==8
    assert private["saved_prediction_streams"]==8
    assert private["verified_predictions_per_arm"]==8192
    assert private["score_level_metric_replay_completed"] is True
    assert private["source_checkpoint_reinference_independently_completed"] is False
    assert private["temporary_preprocessed_pixel_cache_deleted"] is True
    assert len(private["private_archive_sha256"])==64
    assert private["recording_only_resume_events"]==2


def test_new_candidate_does_not_rewrite_locked_negative_study():
    j=json.loads((ROOT/"experiments/galar-unseen-11-20-20261104/aggregate.json").read_text())
    a=j["budget_summary"]["10"]["policies"]
    d=100*(a["score_bin"]["mean_defined_examination_run_recall"]
          -a["uniform"]["mean_defined_examination_run_recall"])
    assert d==pytest.approx(-1.2668765,abs=1e-6)
    assert j["authors_reserved_61_to_80_opened"] is False
