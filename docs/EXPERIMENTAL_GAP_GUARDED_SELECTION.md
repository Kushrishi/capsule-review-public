# Experimental uniform-gap-guarded score ranking

**Status: new exploratory selection algorithm; engineering property tested on generated inputs only. It has NOT been evaluated on the locked Galar 11–20 outcomes, an independent patient cohort or a real medical outcome.**

## Problem and technical objective

The four original policies compare image-model scores against source-chronological sampling at the same exact image count `K`. Highest-score ranking can concentrate on one high-scoring stretch and leave large unselected ordinal spans. Chronology bins improve spread but do not explicitly use *uniform's exact maximum skipped span* as a hard constraint.

This **fifth, optional product policy**, `score_guarded`, attempts to use useful scores while maintaining the following **technical invariants** for any valid imported sequence of length `N` and any integer `1 <= K <= N`:

1. **Exactly K** unique imported positions.
2. **Maximum skipped imported-position span <= maximum skipped span of deterministic uniform midpoints at the same N and K.**
3. **Sum of scores on selected positions >= sum of scores at uniform midpoints.**
4. The **original four policies, locked Galar evaluation and its primary/secondary results remain unchanged**. The new policy cannot silently enter a frozen four-policy replay.

These bounds are defined on **ordinal imported frames**. They do not imply temporal coverage, true pathology recall, clinically unique lesions, probability calibration, human reading efficiency or patient safety. A higher selected-score sum can come from a model shortcut or unrelated imaging artifact; the selected positions can still miss a real annotation that uniform would cover.

## Exact algorithm

- Compute the existing `uniform_midpoints(N, K)` source-position anchors and the maximum contiguous omitted ordinal span `G` between consecutive anchors, including head and tail.
- Partition the source sequence into K **nonoverlapping anchor-derived cells**. Each boundary is the integer midpoint *between adjacent uniform anchors*, not simply `floor(i*N/K)`. The latter partition can fail to contain its anchor when N/K is unfavorable.
- Apply exactly two coordinate-improvement sweeps, one forward and one backward.
- For each anchor, examine candidate positions inside its original cell that preserve the gap bound `G` to both current neighbors (using sentinels `-1` and `N` at endpoints).
- Move the anchor **only** when a candidate has a strictly higher score; deterministic equal-score tie resolution favors earlier positions for comparing candidate choices, but flat scores leave all original anchors untouched.
- Sort the selected positions by descending score for queue presentation, with ascending original position on ties.

**Complexity:** O(N) candidate-position examinations per sweep; O(K log K) to sort the final queue. Existing score-stream validation remains O(N). This is a fixed greedy, coordinate-descent-style **heuristic**, not a globally optimal medical or mathematical score-maximization solver. Scores must be present for every imported frame, in [0,1] and finite. No clinical annotations, reviewer notes or source pixels are read to choose positions.

**Why the gap bound holds:** At initialization each adjacent gap is at most G. A replacement anchor is accepted only if its **two changed adjacent gaps** are at most G. All other gaps remain unchanged. The invariant therefore holds inductively through all moves. Each accepted move strictly improves the selected score total, so the final sum is at least the initial uniform total. Nonoverlapping anchor-derived cells prevent collision and retain exact K.

## Critical counterexample (not a clinical result)

Suppose an artificial 24-frame sequence has K=6 and uniform midpoints include position 2. If generated score position 3 is higher, the guard may move that anchor from 2 to 3 without exceeding uniform's maximum omitted gap. If position 2 alone carries a hypothetical positive annotation, **uniform retrieves it but the guarded method misses it**. The selected-score sum and spacing bound still improve/hold. That is why these guarantees cannot be called pathology sensitivity or guaranteed evidence preservation.

Tests exercise this counterexample deliberately rather than concealing it.

## Engineering verification

`tests/test_gap_guarded.py` covers all K for N=1..95 (4,560 deterministic workload pairs), constant scores, clustered scores, invalid values, an artificially hidden positive interval, exact-K read-only API behavior, annotation/reviewer immutability, and a 200,000-position performance-sized case. The standard browser/local-model smoke tests additionally select the fifth method and verify the equal-workload comparison renders correctly. The existing `unseen_evaluation.LOCKED_METHODS` remains the **exact original four**; no new policy is permitted in replay of the November 4 Galar commitment.

Run engineering tests, not a medical assessment:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_gap_guarded.py tests/test_priority.py tests/test_priority_comparison.py tests/test_unseen_galar_synthetic_end_to_end.py
```

## Scientific next step, **not performed here**

The next exploratory evaluation should use **previously examined fitting/development examinations only**, with fixed saved original-CNN scores and source-verified annotations, and a versioned pre-analysis comparison specifying K and native run semantics before running. Show per-examination paired run recall, short-run failures, positive-image retrieval, maximum gaps, and cases where uniform is better. Do **not** use locked Galar 11–20 outcomes to choose or promote this post-hoc algorithm. Do **not** open authors' reserved Galar 61–80 cases. Any scientifically confirmatory claim requires a new independently qualified, outcome-concealed cohort and prespecified endpoints.

This is a working algorithmic candidate, **not an improved trained CNN**. The model's poor transfer between examinations and the negative Galar 10% primary result remain unresolved.
