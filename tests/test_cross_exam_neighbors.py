"""Synthetic-only tests for a private-image similarity audit."""
import json
from pathlib import Path
import pytest
from capsule_review.similarity_triage import summarize_private_embedding_neighbors

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = ROOT / "experiments/galar-cross-exam-neighbor-audit-20261105/aggregate.json"


def record():
    return dict(a=[1, 10], b=[2, 20], cosine=.94,
                gray_ssim=.73, rgb_mae=.12, center_mae=.10,
                high_pixel_aligned_close_copy_candidate=False)


def test_private_records_yield_redacted_aggregate():
    result = summarize_private_embedding_neighbors([record()])
    assert result["candidate_pairs_scored"] == 1
    assert result["unique_original_source_frames"] == 2
    assert result["strict_pixel_aligned_close_copy_pairs"] == 0
    assert result["source_groups_independent_proven"] is False
    assert "[1, 10]" not in str(result)


@pytest.mark.parametrize("field,value", [
    ("cosine", .3), ("cosine", float("nan")),
    ("gray_ssim", 1.2), ("rgb_mae", -1),
    ("high_pixel_aligned_close_copy_candidate", True),
    ("b", [1, 22]), ("a", [1, -2]),
])
def test_bad_private_scores_are_rejected(field, value):
    item = record()
    item[field] = value
    with pytest.raises(ValueError):
        summarize_private_embedding_neighbors([item])


def test_public_record_preserves_full_search_scope_and_limits():
    record = json.loads(AGGREGATE.read_text())
    h = record["full_population_coarse_dhash"]
    e = record["original_image_pretrained_embedding_screen"]
    p = e["private_original_pixel_followup"]
    assert record["original_selected_images"] == 11147
    assert h["all_cross_examination_pairs_compared"] == 57789904
    assert h["coarse_exact_equal_hash_pairs"] == 5293
    assert h["coarse_hamming_distance_at_most_six_pairs"] == 704222
    assert sum(h["distance_histogram_zero_through_six"].values()) == 704222
    assert e["source_images"] == 10123
    assert e["source_examinations"] == 14
    assert e["excluded_from_feature_bank_examinations"] == [22, 24]
    assert p["candidate_pairs"] == 551
    assert p["fresh_original_png_sha256_reverified"] == 451
    assert p["strict_pixel_aligned_close_copy_pairs"] == 0
    assert p["maximum_grayscale_ssim"] == pytest.approx(.7915423)
    assert record["limitations"]["patient_to_examination_uniqueness_authenticated"] is False
    assert record["limitations"]["all_57789904_pairs_evaluated_by_original_pixel_ssim"] is False
    assert record["limitations"]["source_authors_reserved_61_80_outcomes_unopened"] is True
