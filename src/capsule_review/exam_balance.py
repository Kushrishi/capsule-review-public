"""Fixed examination-balanced image-CNN fitting utilities (research only).

The high-level experiment is frozen in
docs/GALAR_EXAM_TEMPERED_CNN_PREANALYSIS_LOCK_20261105.md.

Never infer patient independence from Galar examination numbers. The caller
must verify original *private* pixel SHA256s, source-reference/enrichment roles
and group assignments before constructing model input arrays. These helpers do
not access the file system or network, and do not promote a clinical model.
"""
from __future__ import annotations

import numpy as np

ARMS = ("pooled_class_balanced", "tempered_examination_balanced")
HELDOUT_FOLDS = (
    (7, 8, 22, 24),
    (29, 4, 2, 3),
    (30, 23, 21, 5),
    (27, 1, 25, 6),
)
ALLOWED_EXAMINATIONS = frozenset(e for fold in HELDOUT_FOLDS for e in fold)
EPOCHS = 6
BATCH_SIZE = 64
LEARNING_RATE = .001
WEIGHT_DECAY = .0001
EXACT_K = (51, 128, 256)


def split_masks(examinations, is_reference, fold: int):
    """A held-out exam contributes ONLY its 512 original reference frames.

    Enriched samples of a held-out exam are discarded; no fitting or evaluation
    on their reference labels. Return train and evaluation masks in *input order*.
    """
    exams = np.asarray(examinations)
    refs = np.asarray(is_reference)
    if (fold not in (1, 2, 3, 4) or exams.ndim != 1
        or refs.shape != exams.shape or refs.dtype != np.bool_
        or not np.issubdtype(exams.dtype, np.integer)):
        raise ValueError("Invalid fixed fold or source-role arrays.")
    if set(int(x) for x in exams) != ALLOWED_EXAMINATIONS:
        raise ValueError("Study population changed or protected examinations included.")
    for exam in ALLOWED_EXAMINATIONS:
        if int(np.sum((exams == exam) & refs)) != 512:
            raise ValueError("Exactly 512 original uniform-reference frames required per examination.")
    heldout = np.isin(exams, HELDOUT_FOLDS[fold - 1])
    fit = ~heldout
    evaluate = heldout & refs
    if int(evaluate.sum()) != 2048 or np.any(fit & evaluate):
        raise ValueError("Non-disjoint fitting/reference evaluation.")
    return fit, evaluate


def fitting_sample_weights(labels, examination_ids, arm: str):
    """Return per-sample weights with equal global mass per blood class.

    Control: inverse global class frequency. Candidate: within each class,
    1/sqrt(per-exam class count), normalized to half the total class mass.
    Both have mean weight 1 and equal class mass. Rare positives are tempered,
    not assigned their full inverse-frequency group mass.
    """
    y = np.asarray(labels)
    exam = np.asarray(examination_ids)
    if (arm not in ARMS or y.ndim != 1 or exam.shape != y.shape
        or len(y) < 2 or not np.issubdtype(y.dtype, np.integer)
        or not np.issubdtype(exam.dtype, np.integer)
        or set(int(z) for z in np.unique(y)) != {0, 1}
        or not set(int(z) for z in np.unique(exam)) <= ALLOWED_EXAMINATIONS):
        raise ValueError("Invalid prequalified binary fitting population.")
    n = len(y)
    weights = np.empty(n, dtype=np.float64)
    for label in (0, 1):
        cls = (y == label)
        if arm == "pooled_class_balanced":
            weights[cls] = n / (2 * int(cls.sum()))
        else:
            values, counts = np.unique(exam[cls], return_counts=True)
            by_exam = dict(zip(values.tolist(), counts.tolist()))
            unnormalized = np.array(
                [1 / np.sqrt(by_exam[int(e)]) for e in exam[cls]], dtype=np.float64
            )
            weights[cls] = unnormalized * n / (2 * unnormalized.sum())
    if (not np.isfinite(weights).all() or not np.all(weights > 0)
        or not np.isclose(weights.sum(), n, rtol=0, atol=1e-4)
        or not all(np.isclose(weights[y == c].sum(), n/2, atol=1e-4)
                   for c in (0, 1))):
        raise ValueError("Sample weight budget failed.")
    return weights.astype(np.float32)


def exact_k_positive_hits(reference_labels, scores, source_indices, budgets=EXACT_K):
    """Deterministic score rank with earliest original-source-frame tie break."""
    y = np.asarray(reference_labels)
    p = np.asarray(scores)
    idx = np.asarray(source_indices)
    if (y.shape != p.shape or idx.shape != p.shape
        or y.ndim != 1 or len(y) != 512
        or not set(np.unique(y).tolist()) <= {0, 1}
        or not np.isfinite(p).all() or not np.isfinite(idx).all()
        or len(np.unique(idx)) != len(idx)
        or tuple(budgets) != EXACT_K):
        raise ValueError("Expected 512 aligned original source-reference rows and fixed K.")
    rank = np.lexsort((idx, -p))
    return {str(k): int(y[rank[:k]].sum()) for k in budgets}
