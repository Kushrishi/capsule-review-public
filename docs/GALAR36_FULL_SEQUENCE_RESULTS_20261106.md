# Galar 36: complete-source fixed-policy development replication

**November 6, 2026. Real original-image acquisition, unchanged CNN inference and independently reproduced outcomes. No model trained or promoted.**

[Aggregate](../experiments/galar36-full-source-20261106/aggregate.json) · [Independent replay](../experiments/galar36-full-source-20261106/independent-check.json) · [Omission analysis](../experiments/galar36-full-source-20261106/omission-mechanism.json) · [Executed design/programs](GALAR36_PRIVATE_INCREMENTAL_ACQUISITION_20261106.md)

## What executed

The existing PR #64 acquisition and evaluation programs ran unchanged at `cb25a284606dcfd7c83334d6c3fbdb8d6911406a`. All 35 retained block-5 parts were restored and their complete 3,453,334,016 bytes matched the original SHA-256. The source-index/header pins, official corrected-label ZIP and original model ZIP were verified. The offline `--check-only` preflight passed before acquisition.

Exactly **3,430,870,954 new compressed source bytes** were acquired from official Figshare file 44755700, inclusive range **21255343165–24686214118**, using the existing strict HTTP206, Content-Range, length and redirect checks. A sparse original archive held only the verified index and blocks 5/6; no full 69 GB source archive was downloaded or publisher-wide MD5 verified.

The index matched **3,098 study36 PNGs in block 5 and 10,228 in block 6**. All **13,326 original PNGs** passed extraction/7z CRC, PNG verification, source identity, original-byte hashing, exact corrected-label membership and native +5 grid checks. There were **209 positive images**, **59 positive annotation runs**, no unknown target labels or internal published-grid gaps. This is the complete **published export**, not proof of every device exposure or elapsed capture time.

The original 96×96 RGB/padded CNN scored every PNG once. Its source hashes, scores, four original queues and the fixed window-3 comparator were sealed before the separate outcome audit. Snapshot SHA-256: `a636cb9c74f5019a58bc03414a6e428298eb833bb5cf69066dc4a78cf4d6dd90`. The image package and snapshot were privately retained and their remote payloads SHA-256 verified before `--audit`. Thirty-five image-package parts plus two half-parts replaced a repeatedly timed-out transport part; the complete package bytes/hash did not change.

Scoring did not decode outcome annotations. Acquisition preflight and earlier work had already inspected study36 labels: stage separation is reproducible computation, **not newly blinded validation**. All original images, individual labels/scores, weights and source identities remain private. The audit rechecked all original PNG hashes, source receipts, frozen selections and corrected `36.csv`. An independent implementation imported no production selector, temporal processor or evaluator and reproduced all 25 policy/workload outcomes, saved queues, run strata and spacing metrics.

## Equal exact-K outcomes

Cells are **positive images / positive annotation runs reached**, denominators **209 / 59**. K is historical integer half-up; budgets are selected independently, not guaranteed nested queues.

| Budget | K | Uniform | Global score | Score with separation | Raw score-bin | Window-3 score-bin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5% | 666 | 15 / 15 | **0 / 0** | 19 / 18 | 17 / 17 | 15 / 15 |
| 10% | 1,333 | 16 / 15 | 12 / 6 | 32 / 29 | 33 / 28 | 25 / 20 |
| 25% | 3,332 | 52 / 36 | 79 / 27 | 67 / 37 | 67 / 41 | 60 / 35 |
| 50% | 6,663 | 105 / 48 | 133 / 44 | 107 / 46 | 117 / 50 | 109 / 46 |
| 100% | 13,326 | 209 / 59 | 209 / 59 | 209 / 59 | 209 / 59 | 209 / 59 |

At **10%**, raw score-bin covers **47.46% of runs**, versus uniform **25.42%**: **+22.03 percentage points**. Score with separation reaches one more run (29/59), but raw score-bin reaches more at 25% (41 versus 37). No method is a universal winner and none was selected or promoted using these outcomes.

Global score ranking has a material failure: the entire first 666-image queue contains **zero blood-positive annotated images**. At 10% it reaches fewer positive images and runs than uniform. At 25% it reaches more positive images (79 versus 52) but fewer runs (27 versus 36). Image enrichment and distinct evidence preservation remain different objectives. A negative blood annotation is not proof that an image is clinically normal.

Supporting raw-score ROC-AUC is **0.57853**, average precision **0.01893**, against positive prevalence **0.01568**. An independent scikit-learn calculation agreed to 1e-12. These score diagnostics do not rescue poor early retrieval, establish calibration or measure clinical sensitivity.

## Short runs and temporal losses

There are **44 short runs (1–5 positive positions), 15 medium (6–25), and no 26+ runs**. Length is published-position count, not duration or adjudicated lesion size.

| Budget | Raw-covered runs lost by temporal | Previously missed runs gained | Net run change |
| --- | ---: | ---: | ---: |
| 5% | 6 | 4 | −2 |
| 10% | 12 | 4 | −8 |
| 25% | 10 | 4 | −6 |
| 50% | 6 | 2 | −4 |
| 100% | 0 | 0 | 0 |

At 10%, losses comprise **10 short and 2 medium runs**; all four gains are short. Every raw positive selection in the 12 lost runs is replaced by a same-bin **label-negative** temporal selection. Eight replacements move one published position earlier with equal smoothed scores and a lower original score. This directly supports the same max-spreading/earliest-tie displacement mechanism seen on Galar35. Other displacements also contribute; this is not a clinical adjudication of neighbours.

At 25%, all ten lost runs are short. The fixed temporal heuristic again has lower run coverage than raw score-bin at every budget below 100%. Preserve the negative result; no smoothing window or tie rule was retuned.

## Model scores versus selection geometry

The CNN and scores are identical inputs to the original four policies. At 10%, score-bin reaches **24 runs missed by global score**, while global score reaches two missed by score-bin. At 25%, these counts are 18 and four. Thus policy allocation, not a new model, explains much of the improvement in run retention. The global ranking failure also shows that these image scores are unreliable as a stand-alone early triage queue on this examination.

The post-outcome union of all five queues would reach 39 runs at 10%; it is **not an equal-K selector** and is not a deployable or valid comparative result. It only identifies complementary omissions. Do not combine queues without charging every extra selected image to the budget.

## Comparison with completed Galar35

No Galar35 acquisition, inference or completed evaluation was repeated; this table reads its preserved aggregate.

| Measure | Galar35 | Galar36 |
| --- | ---: | ---: |
| Positive image prevalence | 15.91% | 1.57% |
| Short / medium / long annotation runs | 14 / 11 / 4 | 44 / 15 / 0 |
| 10% uniform run coverage | 16/29 (55.17%) | 15/59 (25.42%) |
| 10% raw score-bin run coverage | 23/29 (79.31%) | 28/59 (47.46%) |
| 10% global score positive-image recall | 583/1,534 (38.01%) | 12/209 (5.74%) |
| 10% temporal versus raw run change | −6 | −8 |
| 25% uniform / raw score-bin runs | 25/29 / 28/29 | 36/59 / 41/59 |

**What repeated:** raw score-bin's run-coverage advantage over deterministic uniform at 10% and 25%, and the net harm of fixed temporal processing. **What did not transfer:** strong positive-image enrichment by global score ranking. Absolute run retention is substantially lower on the short-run-heavy study36.

Lower prevalence changes precision's baseline, but these are two different examinations. Appearance, location, annotation practice, event length, sampling phase and patient/device/site differences are confounded. The experiment cannot establish that prevalence *caused* the model failure. At equal percentage review, random expected positive-image recall is approximately the same percentage regardless of prevalence; weak observed early recall is not explained by base rate alone.

Both cases are previously inspected **development** examinations with unauthenticated patient linkage. Their favourable score-bin comparisons do not override the stronger historical Galar11–20 **negative 10% primary: −1.2668765 pp**. That evaluation remains unchanged and unopened for new analysis; authors' 61–80 remain reserved. No human time savings, diagnosis, clinical validity or novelty was measured.

## Decision and single highest-value next experiment

Do not promote global ranking or the fixed temporal heuristic. Retain raw score-bin as an experimental comparator, not a clinically effective default. The completed replication strengthens evidence about policy-dependent evidence retention and examination heterogeneity; **the CNN itself did not improve**.

The next experiment should be a **locked, multi-examination complete-source replication of unchanged score-bin versus uniform**, with 10% equal-examination positive-run recall difference as the primary endpoint, 25% and short-run strata secondary, and global score/separation as fixed supporting controls. Qualify patient/examination grouping, complete labels, source rights and source retention before selecting the cohort; choose eligibility without favourable CNN outcomes. Previously inspected 21–60 must remain labelled development, and a genuinely external claim needs a separately authenticated cohort. Do not reopen 11–20 or authors' 61–80.

This outranks another architecture or smoothing sweep: two favourable inspected cases coexist with a locked multi-examination primary failure, and early ranking changes sharply by case. First determine where the fixed policy benefit survives complete, group-defensible replication; then a distinct model-development hypothesis can be evaluated under a new lock.
