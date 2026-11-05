"""Tests are synthetic metadata only; no original medical records are loaded."""
from __future__ import annotations

import copy
import pytest

from capsule_review.cohort_gate import REQUIRED, assess


def worksheet(status="pass"):
    return {
        "schema_version": 1,
        "candidate": "Synthetic eligible cohort",
        "checks": {
            key: {"status": status, "evidence_ref": "synthetic-test-evidence"}
            for key in REQUIRED
        },
    }


def test_all_pass_still_requires_independent_human_and_protocol_approval():
    result = assess(worksheet()).public_summary()
    assert result["decision"] == "HUMAN_REVIEW_REQUIRED"
    assert result["passed"] == result["total"] == len(REQUIRED)
    assert result["issues"] == []
    assert result["approved_for_outcome_access"] is False
    assert result["clinical_validation"] is False


def test_sparse_labels_and_missing_patient_identity_block_kvasir_like_case():
    data = worksheet()
    data["candidate"] = "Kvasir-like sparse annotations, not confirmed exhaustive"
    data["checks"]["exhaustive_target_annotation"]["status"] = "unknown"
    data["checks"]["independent_patient_exam_grouping"]["status"] = "unknown"
    result = assess(data).public_summary()
    assert result["decision"] == "BLOCKED"
    assert result["passed"] == len(REQUIRED) - 2
    assert {issue["check"] for issue in result["issues"]} == {
        "exhaustive_target_annotation", "independent_patient_exam_grouping",
    }


def test_missing_and_claimed_pass_without_evidence_are_blocked():
    data = worksheet()
    del data["checks"]["source_integrity_and_duplicates"]
    data["checks"]["exhaustive_target_annotation"]["evidence_ref"] = ""
    result = assess(data).public_summary()
    assert result["decision"] == "BLOCKED"
    assert result["passed"] == len(REQUIRED) - 2
    assert all(issue["status"] == "unknown" for issue in result["issues"])


def test_gate_does_not_echo_private_text_or_evidence_refs():
    data = worksheet()
    sensitive = "PRIVATE-PATIENT-FRAME-REFERENCE-DO-NOT-PRINT"
    data["checks"]["research_use_permission"]["status"] = "fail"
    data["checks"]["research_use_permission"]["reason"] = sensitive
    data["checks"]["research_use_permission"]["evidence_ref"] = sensitive
    result = assess(data).public_summary()
    assert sensitive not in str(result)


@pytest.mark.parametrize("change", [
    lambda x: x.update(schema_version=2),
    lambda x: x["checks"].update(typo_instead_of_verified={"status": "pass"}),
    lambda x: x["checks"]["complete_source_chronology"].update(status="approved"),
    lambda x: x["checks"]["complete_source_chronology"].update(reason="A"*801),
    lambda x: x.update(candidate=""),
])
def test_invalid_data_fails_closed(change):
    data = worksheet()
    change(data)
    with pytest.raises(ValueError):
        assess(data)


def test_documenting_nonclinical_kvasir_like_candidate_is_not_approval():
    data = worksheet()
    for k in (
        "exhaustive_target_annotation", "independent_patient_exam_grouping",
        "clinician_approved_label_mapping",
    ):
        data["checks"][k]["status"] = "unknown"
        data["checks"][k]["reason"] = "Not verified in published dataset"
    assert assess(data).decision == "BLOCKED"
