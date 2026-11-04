"""Aggregate-only regression for already inspected pretrained CNN comparison."""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"experiments/galar-matched-pretrained-probe-20261104/aggregate.json"
METHODS=("original_checkpoint","continued_no_augmentation",
         "continued_photometric","frozen_mobilenet_v3_linear_probe")
EXAMS=(23,25,27)
K=("51","128","256")


def verify(data: dict):
    assert data["status"] == "Exploratory development; not independent validation"
    assert data["preanalysis_git_design_commit"] == "b9be0f9f0fe16e4bf5de32257995693ec05ee021"
    assert data["feature_source"]["feature_sha256"] == (
        "611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae"
    )
    assert data["feature_source"]["metadata_sha256"] == (
        "78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2"
    )
    assert data["feature_source"]["feature_bank_source_images"] == 10123
    assert data["feature_source"]["reference_entries_used"] == 5632
    assert data["fitting"]["original_checkpoint_historical_fitting_only_original_1_to_8"] is True
    assert set(data["fitting"]["matched_fitting_pool_only_methods"]) == set(METHODS[1:])
    assert data["pretrained_probe"]["hyperparameter_search"] is False
    assert data["pretrained_probe"]["backbone_finetuned"] is False
    assert data["pretrained_probe"]["scaler_fitted_only_training_fold"] is True
    assert data["pretrained_probe"]["convergence_warnings_total"] == 0
    for safety in ("clinical_validity","model_promoted","clinical_review_time_measured",
                   "galar_locked_11_20_reused","galar_reserved_61_80_opened"):
        assert data[safety] is False
    assert set(data["privacy"]) == {
        "individual_frames_included","per_image_labels_included",
        "per_frame_predictions_included","trained_coefficients_included",
        "clinical_pixels_included","original_features_included"
    }
    assert all(v is False for v in data["privacy"].values())
    assert data["evaluation"]["patient_independence_verified"] is False
    assert data["evaluation"]["full_video_event_ground_truth"] is False
    assert data["evaluation"]["budgets"] == [51,128,256]
    rows=data["case_results"]
    assert set(rows)=={str(i) for i in EXAMS}
    for ex in EXAMS:
        row=rows[str(ex)]
        assert row["evaluated_exam"]==ex
        assert row["training_reference_images"]==5120
        assert row["training_examinations"]==[*range(1,9),*(i for i in EXAMS if i!=ex)]
        assert row["positive_reference_images"]=={23:4,25:14,27:26}[ex]
        assert row["training_reference_blood_positive"]=={23:279,25:269,27:257}[ex]
        assert set(row["methods"])==set(METHODS)
        for name in METHODS:
            record=row["methods"][name]
            for key in ("roc_auc","average_precision"):
                assert type(record[key]) in (float,int) and math.isfinite(record[key])
                assert 0<=record[key]<=1
            hits=record["positive_reference_images_hit"]
            assert set(hits)==set(K)
            assert all(type(hits[k]) is int and
                       0<=hits[k]<=min(int(k),row["positive_reference_images"]) for k in K)
    for method in METHODS:
        values=[rows[str(ex)]["methods"][method] for ex in EXAMS]
        mean_auc=sum(x["roc_auc"] for x in values)/3
        mean_ap=sum(x["average_precision"] for x in values)/3
        hits={k:sum(x["positive_reference_images_hit"][k] for x in values) for k in K}
        public=data["aggregate"][method]
        assert abs(mean_auc-public["mean_examination_roc_auc"])<1e-12
        assert abs(mean_ap-public["mean_examination_average_precision"])<1e-12
        assert hits==public["total_positive_images_hit"]
    return data["aggregate"]


def test_fixed_pretrained_results_include_negative_transfer():
    metrics=verify(json.loads(SOURCE.read_text(encoding="utf-8")))
    original=metrics["original_checkpoint"]
    pretrained=metrics["frozen_mobilenet_v3_linear_probe"]
    assert pretrained["mean_examination_roc_auc"] > original["mean_examination_roc_auc"]
    assert pretrained["mean_examination_average_precision"] < original["mean_examination_average_precision"]
    assert pretrained["total_positive_images_hit"]["51"] == 15
    assert original["total_positive_images_hit"]["51"] == 22
    assert metrics["continued_no_augmentation"]["total_positive_images_hit"]["51"] == 23
    assert metrics["continued_photometric"]["total_positive_images_hit"]["51"] == 22


def test_casewise_difficult_win_and_strong_case_regression():
    d=json.loads(SOURCE.read_text(encoding="utf-8"))["case_results"]
    assert d["23"]["methods"]["frozen_mobilenet_v3_linear_probe"]["positive_reference_images_hit"]["51"] == 0
    assert d["25"]["methods"]["frozen_mobilenet_v3_linear_probe"]["positive_reference_images_hit"]["51"] == 7
    assert d["27"]["methods"]["frozen_mobilenet_v3_linear_probe"]["positive_reference_images_hit"]["51"] == 8
    assert d["27"]["methods"]["original_checkpoint"]["positive_reference_images_hit"]["51"] == 22
    assert d["25"]["methods"]["original_checkpoint"]["roc_auc"] < .5


def test_original_locked_experiment_not_rewritten():
    locked=ROOT/"experiments/galar-unseen-11-20-20261104/aggregate.json"
    previous=ROOT/"experiments/galar-exam-excluded-adaptation-20261104/aggregate.json"
    assert locked.is_file() and previous.is_file()
    assert set(json.loads(previous.read_text())["per_examination"])=={"23","25","27"}
    assert "score_bin" in locked.read_text()
