"""Pin the source-grouping no-go and uniform-reference concentration values."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from scripts.audit_development_fold_readiness import audit, SOURCE

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/"experiments/galar-group-readiness-20261105/aggregate.json"


def test_group_audit_matches_canonical_original_selection():
    r=json.loads(RECORD.read_text(encoding="utf-8"))
    computed=audit(json.loads(SOURCE.read_text(encoding="utf-8")))
    assert r["available_examinations"] == computed["source_examinations"] == 16
    assert r["previously_sha256_verified_selected_images"] == computed["selected_images"] == 11147
    assert r["selected_images_with_uniform_reference_role"] == computed["uniform_reference_images"] == 8192
    assert r["uniform_reference_positive_images"] == computed["uniform_reference_positive"] == 526
    assert r["selected_positive_images_including_enriched_additions"] == 1663
    assert r["reference_top_four_positive_share"] == pytest.approx(
        computed["reference_concentration"]["top_four_positive_image_share"],abs=1e-9)
    assert r["reference_effective_positive_exam_count"] == pytest.approx(
        computed["reference_concentration"]["effective_positive_exam_count"],abs=1e-6)
    assert r["enriched_selected_top_four_positive_share"] == pytest.approx(
        computed["enriched_selection_concentration"]["top_four_positive_image_share"],abs=1e-9)


def test_illustrative_folds_show_imbalanced_reference_support_not_patients():
    r=json.loads(RECORD.read_text(encoding="utf-8"))
    folds=r["illustrative_reference_only_four_folds"]
    assert len(folds)==4
    assert [x["reference_positive_images"] for x in folds] == [208,125,125,68]
    assert all(x["exam_count"]==4 and x["reference_frames"]==2048 for x in folds)
    assert sum(x["reference_positive_images"] for x in folds)==526
    assert r["confirmed_independent_patients"] is False
    assert r["new_trained_model"] is False
    assert r["model_promoted"] is False
    assert r["original_galar_11_20_reopened"] is False
    assert r["authors_reserved_galar_61_80_opened"] is False


def test_missing_publisher_patient_id_and_domain_provenance_explicit():
    r=json.loads(RECORD.read_text(encoding="utf-8"))
    m=r["metadata_availability"]
    assert m["capsule_system_examinations_verified_from_existing_publisher_extract"]==8
    assert m["capsule_system_examinations_missing"]==8
    assert m["collection_site_examinations_authenticated"]==0
    assert m["patient_group_examinations_authenticated"]==0
    assert m["demographic_values_published"] is False
    assert r["source_paper_group_semantics"]["actual_published_fold_group_key"]=="video"
    assert r["source_paper_group_semantics"]["independent_patient_group_key_verified"] is False
    assert r["source_paper_group_semantics"]["study_id_alone_is_patient_id"] is False
    assert r["private_packet_contains_original_medical_pixels"] is False
    assert r["private_packet_contains_age_or_sex_values"] is False
    assert len(r["private_packet_sha256"])==64
