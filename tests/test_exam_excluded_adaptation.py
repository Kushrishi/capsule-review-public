"""Reconcile all three case-excluded development comparisons without private data."""
import copy
import json
import math
from pathlib import Path
import pytest

from scripts.audit_exam_excluded_adaptation import SOURCE, audit

def _source():
    return json.loads(SOURCE.read_text(encoding="utf-8"))

def test_audit_reproduces_all_cases_and_rejects_model_promotion():
    a=_source()
    r=audit(a)
    m=r["macro"]
    assert r["clinical_model_promotion"] is False
    assert r["photometric_improved_auc_in_examinations"] == 1
    assert math.isclose(m["original_checkpoint"]["mean_auc"],0.492369229,abs_tol=1e-8)
    assert math.isclose(m["continued_no_augmentation"]["mean_auc"],0.513111641,abs_tol=1e-8)
    assert math.isclose(m["continued_photometric"]["mean_auc"],0.525825129,abs_tol=1e-8)
    assert m["original_checkpoint"]["pooled_positive_hits"]["51"] == 22
    assert m["continued_no_augmentation"]["pooled_positive_hits"]["51"] == 23
    assert m["continued_photometric"]["pooled_positive_hits"]["51"] == 22
    assert m["continued_photometric"]["mean_ap"] < m["original_checkpoint"]["mean_ap"]
    assert r["per_examination_auc_minus_original"]["25"]["continued_photometric"] < 0
    assert r["per_examination_auc_minus_original"]["27"]["continued_photometric"] < 0

@pytest.mark.parametrize(("field","value"),[
    ("status","Clinically validated"),
    ("source_images_checked",5631),
    ("private_preanalysis_design_sha256","changed"),
])
def test_metadata_integrity_required(field,value):
    a=_source();a[field]=value
    with pytest.raises(ValueError):audit(a)

def test_case_or_fold_leak_fails_closed():
    a=_source();a["per_examination"]["23"]["training_examinations"].append(23)
    with pytest.raises(ValueError):audit(a)
    b=_source();b["per_examination"]["61"]=copy.deepcopy(b["per_examination"]["23"])
    with pytest.raises(ValueError):audit(b)
    c=_source();c["per_examination"]["25"]["models"]["continued_photometric"]["roc_auc"]=0.99
    with pytest.raises(ValueError):audit(c)
    d=_source();d["per_examination"]["27"]["models"]["continued_photometric"]["positive_image_hits"]["51"]=50
    with pytest.raises(ValueError):audit(d)

def test_privacy_and_outcome_boundaries_are_enforced():
    for field in ("clinical_validation","model_promotion_approved",
                  "patient_independence_verified","authors_reserved_61_80_opened",
                  "locked_galar_11_20_reused"):
        a=_source();a["interpretation"][field]=True
        with pytest.raises(ValueError):audit(a)
    a=_source();a["evaluation"]["distinct_annotation_run_recall_evaluated"]=True
    with pytest.raises(ValueError):audit(a)
    a=_source();a["public_privacy"]["per_frame_predictions_included"]=True
    with pytest.raises(ValueError):audit(a)
    a=_source();a["per_examination"]["23"]["models"]["continued_photometric"]["average_precision"]=float("nan")
    with pytest.raises(ValueError):audit(a)
