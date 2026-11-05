"""Synthetic-only temporal score regression tests; no clinical images or labels."""
from __future__ import annotations

import math
import random

import pytest

from capsule_review.temporal_baseline import temporal_max_scores, temporal_selection
from capsule_review.priority import select_positions


def naive(seq, width):
    h = width // 2
    return [float(max(seq[max(0, i-h):min(len(seq), i+h+1)])) for i in range(len(seq))]


@pytest.mark.parametrize("n", [1, 3, 7, 20, 103])
@pytest.mark.parametrize("w", [1, 3, 5, 7])
def test_exact_rolling_max_matches_reference(n, w):
    if w > n:
        return
    rng = random.Random(123 + n * 7 + w)
    values = [rng.randrange(9) / 8 for _ in range(n)]
    indices = list(range(10000, 10000+n))
    assert temporal_max_scores(values, indices, window=w) == naive(values, w)
    assert temporal_max_scores(values, indices, window=w) == temporal_max_scores(values, indices, window=w)


def test_window_one_matches_raw_selection_and_flat_scores_are_not_invented():
    raw = [0.02, .04, .92, .01, .07, .1, .05]
    for policy in ("score", "score_diverse", "score_bin"):
        assert temporal_selection(raw, list(range(7)), window=1, selected_count=3, policy=policy) == (
            select_positions(raw, 3, policy))
    assert temporal_max_scores([.2]*7, list(range(7)), window=3) == [.2]*7


def test_exact_k_and_deterministic_for_all_supported_policies():
    scores = [((i*7)%13)/12 for i in range(41)]
    for k in (1, 2, 4, 10, 40, 41):
        for policy in ("score", "score_diverse", "score_bin"):
            chosen = temporal_selection(scores, list(range(41)), window=3,
                                        selected_count=k, policy=policy)
            assert len(chosen) == len(set(chosen)) == k
            assert chosen == temporal_selection(scores, list(range(41)), window=3,
                                                selected_count=k, policy=policy)
            assert all(0 <= x < 41 for x in chosen)


@pytest.mark.parametrize("source", [
    [100, 102, 103], [100, 101, 101], [102, 101, 100],
    [100, 101, 103], [100, True, 102], [100, -1, 0],
])
def test_source_missing_duplicates_and_malformed_order_fail_closed(source):
    with pytest.raises(ValueError):
        temporal_max_scores([.1, .8, .2], source, window=3)


@pytest.mark.parametrize("scores", [
    [.1, float("nan"), .3], [.1, float("inf"), .3],
    [.1, -0.1, .3], [.1, 1.01, .3], [.1, True, .3],
])
def test_invalid_scores_rejected(scores):
    with pytest.raises(ValueError):
        temporal_max_scores(scores, [100, 101, 102], window=3)


@pytest.mark.parametrize("w", [0, -1, 2, 4, 9, True, 3.0])
def test_invalid_window_rejected(w):
    with pytest.raises(ValueError):
        temporal_max_scores([.1, .9, .3], [0, 1, 2], window=w)


@pytest.mark.parametrize("policy", ["uniform", "score_guarded", "", "new_method"])
def test_unapproved_policy_rejected(policy):
    with pytest.raises(ValueError):
        temporal_selection([.1, .9, .2], [0,1,2], window=3, selected_count=1, policy=policy)


def test_model_scores_not_reference_labels_and_no_source_mutation():
    scores = [0.0, 0.8, 0.0, 0.0, 0.0]
    indices = [901, 902, 903, 904, 905]
    before_scores, before_indices = scores.copy(), indices.copy()
    assert temporal_max_scores(scores, indices, window=3) == [0.8,0.8,0.8,0.0,0.0]
    assert scores == before_scores and indices == before_indices


def test_synthetic_spread_can_reduce_peak_localization_not_guarantee_gain():
    scores = [.0]*9
    scores[4] = 1
    smoothed = temporal_max_scores(scores, list(range(9)), window=3)
    assert smoothed[3:6] == [1., 1., 1.]
    assert smoothed[2] == smoothed[6] == 0
    # Deliberately do not assert pathology/run recall improvements.
