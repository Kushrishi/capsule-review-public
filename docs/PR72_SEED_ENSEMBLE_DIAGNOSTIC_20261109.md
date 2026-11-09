# PR72 three-seed ensemble diagnostic — exploratory only

**9 November 2026 · Development-only retrospective analysis of the completed PR72 experiment. No models retrained, no new original images, and no candidate or selector promoted.**

## Fixed question

PR72 demonstrated an unstable local-ranking effect on 69 distinct short annotated blood-positive runs across fitting-source examinations 23/25/29/30. A later error-persistence audit found extensive seed-level disagreement. We therefore tested two simple, fixed, source-agnostic combinations of the three PR72 held-out seed predictions for each training objective: (a) majority vote of whether the positive boundary endpoint outranks the negative one and (b) ordering by the arithmetic mean of the three **raw** positive-minus-negative class-logit margins. Both combinations use the original paired seeds 17/29/43; no weights, thresholds, folds or models are selected using outcomes.

The comparison was declared locally before ensemble outputs were calculated, **but the examinations and single-seed outcomes were already inspected**. This is not new independent validation or a registered blinded test.

## Observed equal-examination pair ordering

| Model/objective | Existing mean across individual seeds | Three-seed majority vote | Three-seed arithmetic mean margin |
|---|---:|---:|---:|
| Compact CNN, classification | 63.7720% | 61.4262% | 67.0965% |
| Compact CNN, fixed local-ranking loss | 72.2908% | 75.2292% | **78.9150%** |

### Per-examination ordering, local-ranking arm

| Excluded examination | Distinct short runs | Individual-seed mean | Three-seed majority | Three-seed mean margin |
|---|---:|---:|---:|---:|
| 23 | 23 | 55.07% | 56.52% | **52.17% (12/23)** |
| 25 | 20 | 78.33% | 85.00% | **95.00% (19/20)** |
| 29 | 11 | 75.76% | 72.73% | **81.82% (9/11)** |
| 30 | 15 | 80.00% | 86.67% | **86.67% (13/15)** |

These are 69 original distinct annotated short runs, not 69 patients or lesions. Averaging three seed checkpoints does not create new independent examinations; the macro values equally weight the four examination units.

## Singleton ordering

| Model/objective | Mean over individual seeds | Three-seed majority | Three-seed mean margin |
|---|---:|---:|---:|
| Classification | 52.78% | 50.00% | 51.67% |
| Local ranking | 62.22% | 64.17% | **85.00%** |

The mean-margin local-ranking ensemble orders 15/21 distinct singleton pairs correctly, but results remain heterogeneous: **Galar23 is only 4/10 (40%)**, versus 6/6 in25, 2/2 in29 and 3/3 in30. The 85% statistic is equal-examination averaging of those four rates, **not** pooled 85% of singleton events.

## Scientific interpretation and advancement decision

This is a potentially useful **ensemble-stability signal**, not proof of better abnormality detection. The fixed ranking mean-margin ensemble improves equal-examination ordering descriptively from 72.29% to 78.92%, but performs worse in Galar23 and still misses six of its ten singletons. Its advantage over mean single-seed performance could partly reflect how raw logit magnitudes weight the three models, since the models are not calibrated. Majority voting is less dramatic. The classification ensemble shows no consistent analogous gain. No new image-level or whole-sequence exact-K model inference was performed.

The prespecified PR72 data-transfer/singleton gate already failed, and this posthoc diagnostic does **not** override that decision. The 10% exact-K distinct-run recall performance against uniform selection remains unproven for these ensembles. No candidate is integrated into the research viewer.

A future **independently chosen, still-uninspected fitting-source examination with genuine source-complete boundary labels**, and a separate pre-outcome commitment, would be needed to test whether this behaviour transfers. Do not choose a favorable source case after viewing current errors, and do not open reserved 61–80 for this retrospective comparison. Where independent data are unavailable, report the evidence limit rather than an accuracy claim.

## Reproduction and privacy

The script `scripts/exploratory_seed_ensemble.py` requires the private PR72 `Short_Event_Foundation_Private_Final_Evidence_20261109.zip`, with its nested sealed pre-outcome checkpoint/logit package. It checks the 24 logit-file hashes and recorded source-run identities, calculates only predefined ensemble strategies, and writes an **aggregate-only** JSON result. A separate local independent implementation reproduced the 24 individual PR72 score cells exactly, read-back-verified the 24 sealed prediction vectors, and independently matched the eight objective/examination ensemble cells. Synthetic-only tests cover voting/margin ties, magnitude reversal and invalid seed counts.

All original images, individual source/run identities, annotations, model weights, endpoint logits and full private source manifests remain outside public Git. Nothing from a private medical package is embedded in this report or public tests; patient linkage remains unverified.