"""Synthetic-only tests of exam-balanced learning and strict reference evaluation."""
from __future__ import annotations
import numpy as np
import pytest

from capsule_review.exam_balance import (
    ALLOWED_EXAMINATIONS, ARMS, EXACT_K, HELDOUT_FOLDS,
    exact_k_positive_hits, fitting_sample_weights, split_masks,
)


def synthetic_source():
    # Every exam has precisely 512 uniform source-reference rows;
    # a few fit-only enriched rows are included to test evaluation exclusion.
    exams = np.repeat(sorted(ALLOWED_EXAMINATIONS), 512).astype(np.int16)
    reference = np.ones(len(exams), dtype=bool)
    enriched_exam = np.array([7, 7, 23, 23, 23], dtype=np.int16)
    exams = np.concatenate((exams, enriched_exam))
    reference = np.concatenate((reference, np.zeros(len(enriched_exam), dtype=bool)))
    return exams, reference


def test_all_four_fixed_folds_keep_exams_and_enrichment_out_of_eval():
    e, refs = synthetic_source()
    evaluated = []
    for fold in range(1, 5):
        train, evaluation = split_masks(e, refs, fold)
        assert not np.any(train & evaluation)
        assert int(evaluation.sum()) == 2048
        assert np.all(refs[evaluation])
        assert len(np.unique(e[evaluation])) == 4
        assert len(np.unique(e[train])) == 12
        assert all(int(x) not in e[train] for x in HELDOUT_FOLDS[fold - 1])
        evaluated.extend(np.unique(e[evaluation]).tolist())
    assert set(evaluated) == ALLOWED_EXAMINATIONS


def test_heldout_enriched_images_are_not_leaked_into_training():
    e, refs = synthetic_source()
    train, evaluation = split_masks(e, refs, 1)
    assert not train[-5] and not train[-4]  # enriched held-out exam 7
    assert not evaluation[-5] and not evaluation[-4]
    assert train[-1] and not evaluation[-1]  # enriched fit exam 23


def test_invalid_group_set_and_reference_counts_rejected():
    e, refs = synthetic_source()
    with pytest.raises(ValueError):
        split_masks(e, refs, 5)
    changed = e.copy()
    changed[0] = 61
    with pytest.raises(ValueError):
        split_masks(changed, refs, 1)
    modified = refs.copy()
    modified[0] = False
    with pytest.raises(ValueError):
        split_masks(e, modified, 1)


def test_paired_arms_have_equal_total_class_mass_but_differ_by_examination():
    exams = np.array([1] * 30 + [2] * 20 + [7] * 50, dtype=np.int16)
    labels = np.array([1] * 1 + [0] * 29 +
                      [1] * 4 + [0] * 16 +
                      [1] * 25 + [0] * 25, dtype=np.int64)
    pooled = fitting_sample_weights(labels, exams, ARMS[0])
    tempered = fitting_sample_weights(labels, exams, ARMS[1])
    for w in (pooled, tempered):
        assert np.all(np.isfinite(w)) and np.all(w > 0)
        assert float(np.sum(w)) == pytest.approx(len(labels), abs=2e-5)
        assert w[labels == 0].sum() == pytest.approx(len(labels) / 2, abs=2e-5)
        assert w[labels == 1].sum() == pytest.approx(len(labels) / 2, abs=2e-5)
    # Highest-positive-count exam 7 loses relative positive-class dominance.
    fraction_pooled = pooled[(exams == 7) & (labels == 1)].sum() / pooled[labels == 1].sum()
    fraction_tempered = tempered[(exams == 7) & (labels == 1)].sum() / tempered[labels == 1].sum()
    assert fraction_tempered < fraction_pooled
    assert not np.allclose(tempered, pooled)


def test_tiny_negative_only_group_is_safe_but_no_positive_global_fails():
    labels = np.array([1,0,0,0,0,0,0,0], dtype=np.int64)
    exams = np.array([1,1,2,2,3,3,4,4],dtype=np.int16)
    balanced = fitting_sample_weights(labels,exams,"tempered_examination_balanced")
    assert np.all(np.isfinite(balanced))
    with pytest.raises(ValueError):
        fitting_sample_weights(np.zeros(8,dtype=np.int64),exams,"pooled_class_balanced")


def test_fixed_k_ties_earliest_original_source_position():
    labels = np.zeros(512,dtype=np.int64)
    labels[3] = 1
    scores = np.zeros(512,dtype=np.float64)
    frames = np.arange(512,dtype=np.int64) * 5
    result = exact_k_positive_hits(labels,scores,frames)
    assert result == {"51":1,"128":1,"256":1}
    labels[300] = 1
    result = exact_k_positive_hits(labels,scores,frames)
    assert result == {"51":1,"128":1,"256":1}
    scores[300] = 0.7
    assert exact_k_positive_hits(labels,scores,frames)["51"] == 2
    assert set(result) == {str(k) for k in EXACT_K}


def test_malformed_prediction_or_source_rejected():
    labels = np.zeros(512,dtype=np.int64)
    scores = np.zeros(512)
    frames = np.arange(512)
    scores[17] = np.nan
    with pytest.raises(ValueError):
        exact_k_positive_hits(labels,scores,frames)
    scores[17] = 0
    frames[17] = frames[18]
    with pytest.raises(ValueError):
        exact_k_positive_hits(labels,scores,frames)
    with pytest.raises(ValueError):
        exact_k_positive_hits(labels[:-1],scores[:-1],frames[:-1])
