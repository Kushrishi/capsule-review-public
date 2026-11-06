# Galar 35: complete-source CNN inference and negative temporal result

November 5, 2026 experiment. **Descriptive development only; no model promoted.**

[Measured aggregate](../experiments/galar35-full-source-20261105/aggregate.json) · [Independent numerical replay](../experiments/galar35-full-source-20261105/independent-check.json) · [Missed-run explanation](../experiments/galar35-full-source-20261105/temporal-misses-aggregate.json) · [Fixed experiment](GALAR35_FULL_SEQUENCE_EXPERIMENT_20261105.md)

## What actually ran

All **9,643 original published PNGs** from the approved official Galar v2 block 5 were verified, privately retained and scored with the **unchanged original CNN and original 96×96 preprocessing**. No training, model substitution, threshold tuning, window tuning or product default change occurred. Original-image identities, hashes, weights, labels, scores, queues and detailed missed-run records remain private.

The scoring stage accepted no outcome annotations. Its exact-K queues and score snapshot were durably deposited and downloaded back with identical SHA-256 **before the separate label audit**. The snapshot commitment is `b22bd37ffa08bdace73a4cb8b3f785772f9565cdcf7b0303632ebb1ad10ef4e7`. This preserves a reproducible separation of computation stages; **35's labels were already inspected, including acquisition preflight**, so it is not a newly blinded or independent test.

The audit reconciled every PNG and private manifest entry with the official SHA-verified corrected `35.csv`: **1,534 positive annotated images, 29 positive annotation runs**, no unknown labels, native source-index stride **5**. A separate implementation reconstructed all five queues and independently checked every positive-image count, run count, run-length stratum, recall, paired difference and ordinal-spacing metric. It imported no production selector, temporal processor or outcome evaluator.

## Equal-workload results

Cells contain **positive images reached / distinct positive annotation runs reached**. Denominators are **1,534 images / 29 runs**. K uses the fixed integer half-up rule, not a ceiling or a retuned budget.

| Workload | Exact K | Uniform | Raw CNN score-bin | Fixed temporal window-3 score-bin |
| --- | ---: | ---: | ---: | ---: |
| 5% | 482 | 78 / 13 | 83 / 16 | 77 / 10 |
| 10% | 964 | 151 / 16 | 163 / 23 | 156 / 17 |
| 25% | 2,411 | 385 / 25 | 397 / 28 | 387 / 21 |
| 50% | 4,822 | 768 / 28 | 774 / 28 | 769 / 27 |
| 100% | 9,643 | 1,534 / 29 | 1,534 / 29 | 1,534 / 29 |

At **10%**, raw score-bin run coverage is **79.31%**, versus **55.17%** for uniform and **58.62%** for temporal processing. Temporal processing loses **6/29 runs (−20.69 percentage points)** relative to raw score-bin, with no newly reached runs. Positive-image retrieval is **10.63% raw**, **9.84% uniform** and **10.17% temporal**. These are different endpoints.

The two prespecified supplementary controls are also retained in the aggregate. At 10%, global score ranking reaches **583 images / 22 runs**; score with separation reaches **200 / 26**. Their observed ranking is descriptive, not permission to select a new winning policy on this case. No policy is promoted.

## Missed runs and why the temporal heuristic failed here

The 29 runs comprise **14 short (1–5 positive positions), 11 medium (6–25), and 4 long (26+)**. Runs are defined from annotations, not adjudicated lesions or durations.

At 10%, raw score-bin misses **6 runs**: five short and one medium. Temporal misses **12**: eleven short and one medium. All **six additional losses** are short runs of lengths **1, 1, 2, 3, 5 and 5**; it gains no run that raw score-bin misses. In four losses, the selected position moves **one published position earlier** onto a negative annotation. In the other two, the same-bin selections move seven positions later and four earlier, also onto negative annotations. These are directly verified selection displacements, not a clinical explanation of the images.

The fixed rolling maximum spreads a high score to neighbouring positions; earliest-position tie breaking can then select a neighbour rather than the positively annotated position. It does not imply the selected neighbour shares the annotation. Across 5/10/25/50%, temporal processing loses **6/6/7/1** raw-covered runs and gains **0/0/0/0**. At 25%, all seven additional misses are short runs; at 50%, the added miss is a one-position run. Full 100% review is the completeness control, not a favourable temporal result.

**Decision:** reject this fixed window-3 score-bin heuristic as an improvement on Galar 35. Preserve the failure. Do not retune the window on these outcomes. The unchanged raw CNN score-bin performs favourably against uniform on this development case at 5–25%, but no CNN improvement or generalization has been established.

## Boundaries, verification and next experiment

This is one already-inspected examination and a complete **published export**, not necessarily every device exposure or a timestamped video. Positive annotation runs are not distinct lesions; examination identity does not establish patient independence. No clinician time, diagnostic safety or calibrated clinical probability was measured. The authors' **61–80 remain unopened**. The frozen Galar 11–20 **negative 10% primary remains −1.2668765 percentage points**; these results do not revise it.

The local suite passed **908 tests / 1 skipped**; focused acquisition/full-sequence/temporal checks passed **85**. The new scientific results are independently replayed, not inferred from passing software tests. Public CI uses synthetic data only.

**Single highest-value next experiment:** a separately authorized, fixed-policy complete-source replication on **Galar 36**, preserving the same model, window and five workloads. The already-inspected public index records **13,326 positions / 209 positive images / 59 annotation runs** and requires blocks 5 and 6; with block 5 retained, block 6 adds **3,430,870,954 compressed bytes**. This offers a different, shorter-run-heavy development examination without selecting a new window on 35. It still would not be independent clinical validation. No block 6 acquisition is authorized or performed by this experiment.
