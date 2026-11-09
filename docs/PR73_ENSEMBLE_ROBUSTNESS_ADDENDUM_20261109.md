# PR72 fixed-seed ensemble — scale, omission and aggregation robustness

**9 November 2026; retrospective development-only sensitivity analysis, building on PR #73.** No new CNN fits, original medical images, source transfers, new model scores, or benchmark inference. This report tests whether the previously reported short-event pair-ordering improvement depends strongly on a specific aggregation or the magnitude of one seed's logits. **No model or review policy is promoted.**

## Scope and source verification

We independently re-read all 24 saved PR72 model prediction vectors (four held-out fitting examinations × two objectives × three fixed seeds), checked their pre-outcome SHA-256 seals and reconstructed 69 distinct genuine short annotation-run positive/negative pairs, including 21 singletons. A separate implementation reproduced every original PR73 majority/raw-mean ensemble count and all eight training-normalized ensemble cells. Only aggregate counts and code appear publicly. All four development examinations and their outcomes have already been inspected; this cannot be confirmatory evaluation.

## Robustness comparison

The original PR73 result averaged three **raw positive-minus-negative class-logit pair margins**, scoring a run as correctly ordered when the mean margin was positive. We measured three diagnostics without fitting models or looking for a favourable replacement:

1. **Training-RMS normalization.** For each held-out examination and seed, divide the model's pair margins by the root mean squared positive-minus-negative margin on **training-examination pairs only**. This rescales each seed without accessing held-out labels for normalization. It is a retrospective sensitivity check, not a promoted selector.
2. **One-seed omission.** Compute the mean margin from each of the three possible two-seed subsets, retaining every examination. This is not permission to select a favourable subset.
3. **Artificial seed-score scaling.** Multiply each seed in turn by 0.25, 0.5, 2 or 4 before averaging. These 12 perturbations are illustrative sensitivity probes, not fitted ensemble weights, confidence intervals or competing candidates.

| Original objective | Individual-seed mean | Three-seed majority | Raw three-seed mean | Training-RMS normalized mean |
|---|---:|---:|---:|---:|
| Classification: equal-examination ordering | 63.7720% | 61.4262% | 67.0965% | 67.0965% |
| Local ranking: equal-examination ordering | 72.2908% | 75.2289% | **78.9147%** | **78.9147%** |
| Local ranking: equal-examination singleton ordering | 62.2222% | 64.1667% | **85.0000%** | **85.0000%** |

For local-ranking models, **omitting one seed yields 72.2480–75.1647%** equal-examination ordering; the full-three-seed result is therefore not replicated by any of the three two-seed subsets. The 12 arbitrary score-rescaling probes yield **69.241–80.418%**. Thus an order-of-magnitude change in one model's relative logit scale can materially change the conclusion, although training-RMS normalization did *not* change any binary pair-ordering outcomes in these data. These are **not** confidence intervals.

Ranking mean-margin singleton ordering was **15/21 distinct runs = 71.43% pooled**, while its previously reported 85% figure is an equal-examination macro average. It was **4/10 in Galar 23**, **6/6 in 25**, **2/2 in 29**, and **3/3 in 30**. The tiny singleton denominators in 29 and 30 explain much of the high macro figure. The 85% should never be described as 85% of the 21 singleton runs.

## Exactly what changed relative to majority voting

Across the 69 original short runs, the local-ranking raw-margin ensemble corrected **three** pair orderings missed by three-seed majority voting, but also lost **one** pair majority voting had ordered correctly—a **net two-run gain**. The candidate examination 23 contributes one such loss and no such rescue; this examination remains a substantial failure case. Thirty-one of 69 ranking runs show disagreement in binary ordering among the three seeds, so model variability is genuine, but averaging does not remove the remaining examination shift.

These are outcomes of correlated prediction rules on four development examinations, not independent samples of patients or adjudicated lesions. The score-scale sensitivity does not prove overfitting, calibration failure or any specific causal mechanism. The PR72 rules that blocked downstream advancement still apply.

## Decision

Keep the ensemble as an **exploratory diagnostic only**. Do not select a favourable pair of seeds, rescaling factor, examination subset or normalized outcome to obtain a positive development claim. No new CNN trained here. No end-to-end **10% exact-K distinct-run recall** has been measured for the PR72 ensemble; PR72 and the historical negative primary findings remain unchanged.

The next justified development task remains a frozen visual-representation comparison using the retained 69-run fitting cohort (or a separately prespecified, legitimately independent event-preservation evaluation once data and eligibility permit). The original pinned MobileNetV3-Small weights are required to complete the 180 missing embeddings. Inability to retrieve those weights is a compute/data-access blocker, not a positive/negative experiment result.

## Reproducibility and privacy

`ensemble_robustness_audit.py` verifies all private inputs, computes every predefined probe and writes the full internal aggregate. `independent_robustness_verify.py` independently reads the sealed score package, verifies its 24 hashes, and cross-checks the original PR73 counts and normalized cells. Five synthetic tests exercise source exclusions, scale sensitivity, normalization invariance, scoring ties and singleton weighting. `make_public_robustness_record.py` emits only non-identifying aggregate tables. Private source manifests, logits, individual score margins, images and model weights remain outside Git and CI. This report is not clinical validation.