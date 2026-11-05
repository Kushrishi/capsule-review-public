# Experimental contiguous-source temporal baseline

**November 5, 2026 | Algorithm implemented; NO real-image outcome experiment performed.**

## Purpose and boundary

The [current Galar primary study](GALAR_UNSEEN_11_20_RESULTS.md) failed at 10% distinct annotation-run recall. CNN score changes on the already-inspected 16-examination development pool have likewise not demonstrated reliable retrieval improvement. A new model fit on the same cases would be post-hoc development rather than new independent evidence.

The experimental module `src/capsule_review/temporal_baseline.py` offers a **training-free centred rolling maximum** of existing per-frame scores, before applying the unchanged exact-K `score_bin`, `score`, or `score_diverse` selection methods. It uses **no ground-truth labels**, has no new trained weights and is **not wired into the product or presented as clinically useful**. It does not alter the four frozen policies or the original study.

## Data prerequisite

Inputs must be two equally sized arrays: (1) every raw score for a **source-index-consecutive** published sequence, (2) an independently verified list of integer source frame IDs incrementing by exactly one, in order. The module fails closed for sampled 512-frame Galar references, gaps, duplicate indices, invalid/unscaled scores, or a non-odd window. Even adjacent published source IDs do not prove that no device exposures were lost, constant capture cadence or complete reference annotations.

`window=1` exactly reproduces raw model-score ranking. For `window=3`, the output at frame i is the maximum score among frames i-1, i, i+1 with truncated edges. This can distribute a narrow score peak over neighbours but **can also worsen localization and event coverage**. The operation takes linear time using a monotonic deque. It neither trains a temporal neural network nor calibrates predictions.

Example on **synthetic scores only**:

```python
from capsule_review.temporal_baseline import temporal_max_scores, temporal_selection
scores = [0.0, 0.9, 0.0, 0.0, 0.2]
indices = [100, 101, 102, 103, 104]  # fixture IDs, not patient frames
smooth = temporal_max_scores(scores, indices, window=3)
queue = temporal_selection(scores, indices, window=3, selected_count=2, policy="score_bin")
```

## Scientific decision

The method is currently a **software-only experimental control**, not new medical evidence and not a proposed product default. A trustworthy evaluation requires newly qualified source-consecutive, label-complete positive examinations, genuine examination/patient-group accounting, dataset rights, and precommitted comparisons at the same exact-K workloads. Select and lock the one temporal window on development-only material **before** any independent outcomes are opened; do not opportunistically sweep against the completed Galar 11–20 evaluation.

Positive image recall and distinct expert-annotated event/run recall must remain different endpoints. The 10% workload is a research comparison point, not a hard user-facing review limit. Preserve Galar 11–20 negative primary and leave authors' reserved 61–80 closed.

See [adaptive roadmap](ROADMAP.md), [source qualification blocker](PROJECT_STATUS.md) and [Stage 1 tracking](https://github.com/Kushrishi/capsule-review-public/issues/46).
