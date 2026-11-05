"""Privacy-safe source-device and group-aware fold feasibility regression tests.

All fold outcomes use the nonidentifying, already examined public aggregate.
Optional group rows are generated fiction; never import clinical metadata in CI.
"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.audit_development_fold_readiness import SOURCE, audit


def source():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def fake_metadata():
    return [
        {
            "exam_id": str(e),
            "capsule_system": "synthetic-device",
            "collection_site": None,
            "patient_group": None,
            "patient_mapping_evidence_sha256": None,
        } for e in (1, 2, 3, 4, 5, 6, 7, 8)
    ]


def test_reference_only_concentration_and_fold_feasibility():
    j = audit(source())
    assert j["source_examinations"] == 16
    assert j["selected_images"] == 11147
    assert j["uniform_reference_images"] == 8192
    assert j["uniform_reference_positive"] == 526
    assert j["selected_positive_including_enrichment"] == 1663
    assert j["enriched_positive_images_excluded_from_reference_metrics"] is True
    assert j["reference_concentration"]["positive_examinations"] == 11
    assert j["reference_concentration"]["top_four_positive_image_share"] == pytest.approx(476/526)
    assert j["reference_concentration"]["effective_positive_exam_count"] == pytest.approx(3.740786,abs=1e-6)
    assert j["enriched_selection_concentration"]["top_four_positive_image_share"] == pytest.approx(1276/1663)
    folds = j["proposed_illustrative_folds"]
    assert [f["heldout_positive_reference_images"] for f in folds] == [208,125,125,68]
    assert sum(f["heldout_positive_reference_images"] for f in folds) == 526
    assert all(f["heldout_exam_count"] == 4 for f in folds)
    assert all(f["heldout_uniform_reference_images"] == 2048 for f in folds)
    assert all(not f["patient_disjoint_confirmed"] for f in folds)
    assert j["new_prospective_holdout_created"] is False
    assert j["clinical_model_promotion_allowed"] is False
    assert j["independent_event_coverage_allowed"] is False


def test_partial_capsule_metadata_does_not_claim_independent_patients():
    j = audit(source(), fake_metadata())
    assert j["studies_with_device_information"] == 8
    assert j["studies_with_site_information"] == 0
    assert j["studies_with_patient_mapping"] == 0
    assert j["distinct_reported_devices"] == 1
    assert j["patient_independence_proven"] is False
    assert "patient_group_mapping_missing" in j["critical_blockers"]
    assert "device_metadata_partial" in j["critical_blockers"]
    assert "collection_site_metadata_missing" in j["critical_blockers"]
    assert "synthetic-device" not in str(j)


def test_patient_group_equals_study_id_still_not_verified():
    metadata = fake_metadata()
    for record in metadata:
        record["patient_group"] = record["exam_id"]
        record["patient_mapping_evidence_sha256"] = "a"*64
    j = audit(source(), metadata)
    assert j["patient_independence_proven"] is False
    assert j["group_id_equals_study_id_seen"] is True
    assert "patient_group_copied_from_study_id" in j["critical_blockers"]
    assert "a"*64 not in str(j)


def test_duplicate_patient_group_straddling_fold_is_flagged():
    metadata = fake_metadata()
    # Source examinations 7 and 29 initialize distinct folds.
    metadata.append({
        "exam_id":"29", "capsule_system":None, "collection_site":None,
        "patient_group":"fictional-shared", "patient_mapping_evidence_sha256":"b"*64,
    })
    for record in metadata:
        if record["exam_id"] == "7":
            record["patient_group"] = "fictional-shared"
            record["patient_mapping_evidence_sha256"] = "b"*64
    j = audit(source(), metadata)
    assert j["cross_fold_group_id_collisions"] == 1
    assert "cross_fold_group_leakage" in j["critical_blockers"]
    assert "fictional-shared" not in str(j)


def test_unknown_group_mapping_cannot_be_self_certified():
    metadata = fake_metadata()
    metadata[0]["patient_group"]="anonymous-a"
    with pytest.raises(ValueError,match="without source evidence"):
        audit(source(), metadata)
    metadata[0]["patient_mapping_evidence_sha256"] = "unverified"
    with pytest.raises(ValueError,match="fingerprint"):
        audit(source(), metadata)


def test_demographic_rows_must_not_be_passed_to_public_audit():
    metadata = fake_metadata()
    metadata[0]["patient_age"] = 63
    with pytest.raises(ValueError,match="Unrecognized"):
        audit(source(), metadata)


def test_reject_extra_examinations_or_invented_positive_rows():
    changed = deepcopy(source())
    changed["per_examination"]["61"] = deepcopy(changed["per_examination"]["1"])
    with pytest.raises(ValueError):
        audit(changed)
    changed = deepcopy(source())
    changed["per_examination"]["1"]["reference_blood_positive_images"] += 5
    with pytest.raises(ValueError):
        audit(changed)
    changed = deepcopy(source())
    changed["patient_independence_verified"] = True
    with pytest.raises(ValueError):
        audit(changed)


def test_four_folds_are_exploratory_not_prespecified_clinical_study():
    j=audit(source())
    assert j["readiness"] == "EXAMINATION_ONLY_EXPLORATORY_DESIGN"
    assert j["fold_generation_used_inspected_development_outcomes"] is True
    assert "all_development_labels_previously_inspected" in j["critical_blockers"]
    assert "complete_source_event_labels_unavailable" in j["critical_blockers"]
