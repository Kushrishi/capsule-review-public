"""Synthetic tests ensure coarse dHash collisions aren't called patient matches."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest

from capsule_review.similarity_triage import summarize_private_pair_scores

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"experiments/galar-visual-similarity-triage-20261105/aggregate.json"


def synthetic_pair(structure=.65,mae=.03,centre=.04, a=(1,11),b=(2,23)):
    return {"a":list(a),"b":list(b),"dh":"0f0f0f0f0f0f0f0f",
            "gray_ssim":structure,"rgb_mae":mae,"center_mae":centre,
            "rgb_rmse":max(mae,0.05),"high":structure>=.95 and mae<=.06 and centre<=.07}


def test_coarse_collision_not_automatically_a_duplicate():
    result=summarize_private_pair_scores([synthetic_pair()])
    assert result["candidate_pairs_scored"]==1
    assert result["candidate_original_image_identities"]==2
    assert result["strict_pixel_aligned_close_copy_pairs"]==0
    assert result["near_duplicates_globally_ruled_out"] is False
    assert result["clinical_patient_linkage_proven"] is False
    assert result["source_groups_independent_proven"] is False


def test_strict_very_close_pair_is_only_a_candidate_not_clinical_identity():
    row=synthetic_pair(structure=.97,mae=.03,centre=.03)
    result=summarize_private_pair_scores([row])
    assert result["strict_pixel_aligned_close_copy_pairs"]==1
    assert result["human_adjudication_complete"] is False
    assert result["safe_to_promote_medical_model"] is False


@pytest.mark.parametrize("mutation",[
    lambda r:r.update(gray_ssim=float("nan")),
    lambda r:r.update(gray_ssim=1.01),
    lambda r:r.update(rgb_mae=-.01),
    lambda r:r.update(high=True),
    lambda r:r.update(a=r["b"]),
    lambda r:r.update(b=[1,99]),
    lambda r:r.update(dh="not-a-dhash"),
    lambda r:r.update(private_frame_label=1),
])
def test_reject_bad_or_misclassified_private_pair(mutation):
    row=synthetic_pair()
    mutation(row)
    with pytest.raises(ValueError):
        summarize_private_pair_scores([row])


def test_identity_only_stays_in_memory_and_duplicate_pairs_fail_closed():
    one=synthetic_pair()
    report=summarize_private_pair_scores([one])
    assert "image_path" not in str(report)
    assert "source_index" not in str(report)
    assert "[1, 11]" not in str(report)
    b=copy.deepcopy(one)
    b["a"],b["b"]=b["b"],b["a"]
    with pytest.raises(ValueError):
        summarize_private_pair_scores([one,b])


def test_actual_public_aggregate_is_numerically_explicit_about_remaining_risks():
    a=json.loads(SOURCE.read_text(encoding="utf-8"))
    assert a["schema_version"]==1
    assert a["prior_source_selected_images"]==11147
    assert a["source_images_reverified_in_second_stage"]==499
    assert a["cross_examination_candidate_pairs"]==5293
    assert a["original_source_png_sha256_duplicate_count"]==0
    m=a["metrics"]
    assert m["strict_close_copy_candidate_pairs"]==0
    assert m["grayscale_ssim_at_least_0_90_pairs"]==0
    assert m["grayscale_ssim_at_least_0_70_pairs"]==44
    assert m["grayscale_ssim_max"]==pytest.approx(.7902994)
    assert m["grayscale_ssim_mean"]==pytest.approx(.4942104)
    assert a["strict_pixel_aligned_close_copy_rule"]=={
        "grayscale_ssim_min":.95,
        "full_rgb_mae_max":.06,
        "center_rgb_mae_max":.07,
    }
    for key,value in a["limits"].items():
        if key in ("pixel_aligned_only","candidate_set_only"):
            assert value is True
        else:
            assert value is False
    assert a["reproducibility"]["source_images_or_pairwise_identity_data_published"] is False
    for f in ("private_candidate_scores_sha256","private_second_stage_archive_sha256",
              "prior_private_source_audit_sha256"):
        assert len(a["reproducibility"][f])==64
