"""Synthetic counterexamples for the chronology diagnostic, no clinical data."""
import itertools

import pytest

from capsule_review.score_alignment import alignment_controls, summarize_alignment


def test_block_expectation_matches_exhaustive_allocation_matched_sampling():
    labels = [0, 1, 1, 0, 0, 0, 0, 1]
    scores = [.9, .8, .7, .6, .5, .4, .3, .2]
    result = alignment_controls(labels, scores, 3, "score", blocks=2)
    outcomes = [sum(labels[p] for p in chosen)
                for chosen in itertools.combinations(range(4), 3)]
    assert result["block_conditioned_expected_hits"] == sum(outcomes)/len(outcomes)
    assert result["circular_alignment"]["mean_hits"] == 3 * 3 / 8


def test_coarse_location_only_signal_is_removed_by_conditional_control():
    # Perfect pooled separation, no within-block information.
    y = [1]*4 + [0]*4
    r = alignment_controls(y, [.9]*4 + [.1]*4, 2, "score", blocks=2)
    assert r["positive_hits"] == 2
    assert r["global_random_expected_hits"] == 1
    assert r["block_conditioned_excess_recall"] == 0


def test_local_alignment_is_detected_but_inversion_is_negative():
    y = [0, 1, 0, 0, 0, 1, 0, 0]
    for scores, expected in [([.1, .9, .1, .1, .1, .9, .1, .1], .75),
                             ([.9, .1, .1, .1, .9, .1, .1, .1], -.25)]:
        r = alignment_controls(y, scores, 2, "score", blocks=2)
        assert r["block_conditioned_excess_recall"] == expected
        assert r["circular_alignment"]["inferential_p_value"] is False


@pytest.mark.parametrize("method", ["uniform", "score", "score_bin"])
def test_orbit_and_exact_k_for_flat_scores_and_full_review(method):
    y = [0, 1, 0, 0, 0, 0, 1, 0]
    r = alignment_controls(y, [.5]*8, 8, method, blocks=2)
    assert r["positive_hits"] == r["block_conditioned_expected_hits"] == 2
    assert r["block_conditioned_excess_recall"] == 0
    assert r["circular_alignment"]["fraction_offsets_at_least_observed"] == 1


def test_zero_positive_exams_are_undefined_not_perfect_and_not_in_macro():
    zero = alignment_controls([0]*8, [.5]*8, 2, "uniform", blocks=2)
    pos = alignment_controls([1]*8, [.5]*8, 2, "uniform", blocks=2)
    assert zero["positive_image_recall"] is None
    assert zero["block_conditioned_excess_recall"] is None
    s = summarize_alignment([zero, pos])
    assert s["examinations"] == 2 and s["positive_examinations"] == 1
    assert s["macro_positive_image_recall"] == .25
    assert s["leave_one_positive_exam_out_excess_range"] is None
    assert summarize_alignment([zero])["macro_positive_image_recall"] is None


def test_concentration_range_reveals_single_case_dependence():
    a = alignment_controls([0, 1, 0, 0]*2, [.1, .9, .1, .1]*2, 2, "score", blocks=2)
    b = alignment_controls([0, 1, 0, 0]*2, [.9, .1, .1, .1]*2, 2, "score", blocks=2)
    s = summarize_alignment([a, b])
    assert s["leave_one_positive_exam_out_excess_range"] == [-.25, .75]


@pytest.mark.parametrize("labels,scores,k,blocks", [
    ([0, None], [.1, .2], 1, 1), ([0, -1], [.1, .2], 1, 1),
    ([0, True], [.1, .2], 1, 1), ([0, 1], [.1], 1, 1),
    ([0, 1], [float("nan"), .2], 1, 1), ([0, 1], [.1, .2], 0, 1),
    ([0, 1], [.1, .2], 1, 3), ([0, 1, 0], [.1]*3, 1, 2),
    ([0, 1], [.1, .2], 1, True),
])
def test_invalid_inputs_fail_closed(labels, scores, k, blocks):
    with pytest.raises(ValueError):
        alignment_controls(labels, scores, k, "score", blocks=blocks)


def test_wrong_private_package_refused_before_member_access(tmp_path):
    pytest.importorskip("numpy")
    from scripts.audit_score_alignment import verified_reference_scores
    path = tmp_path / "fake.zip"
    path.write_bytes(b"x"*949542)
    with pytest.raises(ValueError, match="Wrong retained"):
        verified_reference_scores(path)
