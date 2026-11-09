# Fixed redness baseline on the 69 short-run boundary pairs — 9 November 2026

**Result: A fixed handcrafted red-versus-green image score does not explain the higher local-pair ordering of the retained CNNs.** Its equal-examination ordering is **54.1156%**, compared with PR72's **72.2908%** individual-ranking-model seed mean and PR73's **78.9147%** raw three-seed mean-margin ensemble. These are previously inspected fitting-source *development* comparisons, not patient-independent validation, clinician performance or the 10% exact-K evidence-preservation endpoint. No model or policy is promoted.

## Question and audit boundary

The first-order interpretation of short-event CNN performance might be that blood-associated images simply appear redder than their immediately neighbouring explicitly blood-negative images. To test that narrow hypothesis without additional model fitting, a local, human-readable contract was saved before any new redness endpoint calculation. The contract SHA-256 is `acdd319f4e692ade3eed2d082a58bdb99357f272de99ea21d74fac8f37317277`. It was **locally fixed, not independently preregistered**, and PR69–74 development outcomes were already known. The analysis is accordingly retrospective and exploratory.

The benchmark uses the unchanged PR72 **69 original, genuine adjacent positive–negative boundary pairs** representing 69 distinct short positive annotation runs across four development examinations 23/25/29/30 (23/20/11/15). A pair uses one expressly labelled positive and one source-native immediately adjacent expressly labelled negative image; an unknown annotation is not a negative. Exactly 21 runs are singletons (10/6/2/3). The unit is an annotated run, not a unique lesion or patient. Patient linkage remains unverified.

All **137 distinct original PNG endpoints** were recovered privately and checked byte-for-byte against the frozen PR72 source manifest (file length and full SHA-256). Fifty-nine endpoints came from the previously recovered 21- and 159-original packages; 78 came from four earlier privately retained examination source snapshots. All source images were previously authorized. No original publisher bytes were downloaded, no historical training or inference was rerun, and no reserved examinations were touched. The 137 private image scores were saved with SHA-256 `10400636e2d3214e1d85bfcece27e6533076549f7410071c141a4745e6e973c5` outside public Git.

## Frozen simple image score

For each original PNG: EXIF transpose and RGB conversion; full-field bicubic resize to 160×160; central circular aperture centered on pixel (79.5,79.5) with radius 70; discard nearly black pixels with RGB sum below 45; calculate for remaining pixels `clip((R-G)/(R+G+20), -1, 1)` and take the arithmetic mean. Higher scores indicate greater red-channel intensity relative to green within the aperture. There is **no fitted threshold, score weight, model, image selection, objective search or outcome-based crop**. No clinical pathology discrimination is inferred from the pixel statistic.

For each boundary pair the positive-minus-negative score >0 contributes one correct order, <0 contributes zero, and an exact tie contributes 0.5. Every examination contributes equally to the macro mean, and singleton macro ordering follows the same examination weighting. Pooled counts are reported separately and are not uncertainty estimates.

## Every held-out fitting-source result

| Exam | Distinct runs | Correct orderings | Singleton runs | Correct singleton orderings |
|---|---:|---:|---:|---:|
| 23 | 23 | 11 | 10 | 4 |
| 25 | 20 | 13 | 6 | 5 |
| 29 | 11 | 7 | 2 | 1 |
| 30 | 15 | 6 | 3 | 2 |
| **Pooled** | **69** | **37 (53.62%)** | **21** | **12 (57.14%)** |
| **Equal-examination mean** | — | **54.1156%** | — | **60.0000%** |

This fixed baseline performs poorly, especially on examination 30 (6/15). Its performance cannot establish that every apparent positive is visually obvious or that the label is clinically adjudicated bleeding.

## Comparison to existing learned models

The historical PR72 ranking objective averaged **72.2908%** pair ordering across seed/examination cells; PR73's three-seed unweighted raw-margin ensemble achieved **78.9147%**, with an equal-examination singleton average of **85.0000%** and **15/21 (71.43%) pooled singleton correct**. The 85% macro result must not be described as 85% of the 21 singleton examples.

A source-aligned retrospective overlap of the new redness rule and the **frozen PR73 ranking ensemble** gives **32** pairs correct under both, **5** correct only under redness, **21** correct only under the CNN ensemble and **11** missed by both. For singleton runs, corresponding counts are **10 / 2 / 5 / 4**. This overlap is hypothesis-generating; it does **not** authorize fitting a favourable hybrid score on inspected outcomes or assuming that the 5 additional cases transfer to independent patients.

The CNNs outperform *this precise red-versus-green formula* on these local pairs. This does **not** isolate what the CNNs learned, rule out other color/brightness heuristics, show temporal understanding, establish calibrated blood probabilities, or imply improved 10% review-budget distinct-run recall. PR72's failed advancement gates and historical negative 10% results are unchanged.

## Independent verification and privacy

Two separate implementations evaluated the original PNG pixels: a vectorized NumPy implementation and an independent scalar pixel loop using PIL. All **137 image scores** agreed to maximum absolute difference **5.56×10⁻¹⁷**; they independently reproduced the 69 pair decisions, four examination counts, macro ordering and singleton counts exactly. The audit checks source-original byte lengths and full SHA-256 on all 137 PNGs, rather than assuming correspondence from filenames. Synthetic image/scoring/aggregation tests validate the sign, neutral images, black-field handling, source-label integrity and run-count denominators. All clinical source images, individual labels, per-image scores and exact source membership remain in private storage only. The public record contains explanatory code, this aggregate and synthetic tests.

**Scientific decision:** retain the CNN ensemble and redness comparison as development diagnostics only; no model, policy, patient-level sensitivity or clinical claim advances. The higher-value next model experiment remains the frozen MobileNet representation comparison, which needs the exact pinned weights to generate the 180 remaining features from already-retained originals. No new publisher-image acquisition is justified here.
