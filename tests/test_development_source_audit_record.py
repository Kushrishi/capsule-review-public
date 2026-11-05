"""Protect the independently checked non-identifying 11,147-image source audit."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NEW=ROOT/"experiments/galar-development-source-audit-20261105/aggregate.json"
OLD=ROOT/"experiments/galar-negative-expansion-cv-2026-11-02/aggregate.json"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def test_full_selected_pool_accounting_and_private_archive_boundary():
    j=read(NEW)
    old=read(OLD)
    assert j["original_image_sha256_reverified"]==11147
    assert j["selected_frame_identities_verified"]==11147
    assert j["source_original_png_bytes_rehashed"]==3374503965
    assert j["independently_checked_private_source_packages"]==11
    assert j["source_byte_mismatch_count"]==0
    assert j["source_manifest_label_or_role_mismatch_count"]==0
    assert j["exact_original_png_sha256_duplicate_count"]==0
    assert j["examination_count"]==16
    assert len(j["per_examination"])==16
    assert sum(x["selected_images"] for x in j["per_examination"].values())==11147
    assert sum(x["blood_positive_selected_images"] for x in j["per_examination"].values())==1663
    assert j["selected_explicit_blood_negative_images"]==9484
    assert j["selected_unknown_labels"]==0
    assert j["reference_images"]==8192
    assert j["reference_positive_images"]==526
    assert j["additional_enriched_images"]==2955
    assert j["four_largest_positive_examinations"]==[29,30,27,25]
    assert j["four_largest_positive_share"]==1276/1663
    assert j["zero_selected_positive_examination_ids"]==[3,5,8,22,24]
    assert old["source"]["original_image_count"]==11147
    assert old["source"]["blood_positive_annotations"]==1663
    assert j["privacy"]["original_pixels_published"] is False
    assert j["privacy"]["frame_identifiers_published"] is False
    assert j["privacy"]["per_image_labels_published"] is False
    assert j["privacy"]["source_hashes_published"] is False
    assert len(j["privacy"]["private_receipt_sha256"])==64

def test_every_examination_reconciles_with_frozen_reference_manifest():
    old=read(OLD)["source"]
    new=read(NEW)["per_examination"]
    assert set(new)==set(old["exam_reference_images"])
    for exam,row in new.items():
        assert row["reference_images"]==old["exam_reference_images"][exam]==512
        assert row["reference_blood_positive_images"]==old["exam_reference_positive"][exam]
        assert row["selected_images"] == row["reference_images"]+row["additional_enrichment_images"]
        assert row["blood_positive_selected_images"]+row["explicit_blood_negative_selected_images"]==row["selected_images"]
        assert row["source_examination_id_is_patient_id"] is False

def test_visual_screen_is_not_confused_with_identity_or_source_completeness():
    j=read(NEW)
    visual=j["visual_similarity_screen"]
    assert visual["decoded_image_count"]==11147
    assert visual["cross_examination_matching_dhash_groups"]==106
    assert visual["images_with_cross_exam_matching_dhash"]==499
    assert visual["private_cross_exam_candidate_pairs"]==5293
    assert visual["near_duplicate_status"]=="not ruled out"
    assert j["patient_independence_verified"] is False
    assert j["source_complete_original_video_coverage_verified"] is False
    assert j["unimported_positions_have_verified_negative_labels"] is False
    assert j["independent_external_event_recall_eligible"] is False
    assert j["external_research_study_readiness"]=="BLOCKED"
    assert j["original_locked_11_20_result_unchanged"] is True
    assert j["authors_reserved_61_80_unopened"] is True
