# Frozen CNN scores versus chronological selection geometry

**November 6, 2026. Executed mechanistic development experiment; no training, inference, image acquisition or model promotion.**

[Analysis contract](SCORE_GEOMETRY_CONTROL_PLAN_20261106.md) · [Aggregate](../experiments/score-geometry-controls-20261106/aggregate.json) · [Independent replay](../experiments/score-geometry-controls-20261106/independent-check.json) · [Private-only runner](../scripts/audit_score_geometry.py)

## Answer

**The original CNN scores contain useful local selection information beyond one-per-bin chronological coverage on both already-inspected complete-source examinations.** The score-bin advantage on Galar35/36 cannot be explained by the tested bin geometry alone. This does **not** establish generalizable pathology discrimination: the original model still has strong between-examination ranking failures, short-run omissions and negative historical results. No weights or product behavior changed.

The new analysis contract was committed at `74d8586ebc4e626068669ee688a9dfe36f3ca4a6` before computing these randomized outcomes. Prior outcomes and examinations were already inspected. This is prospective specification of a **retrospective exploratory analysis**, not newly blinded validation or a registered trial.

## What executed and was verified

Reused frozen original-CNN snapshots for all **9,643 + 13,326 published original images**, verified snapshot SHA-256, original checkpoint identity and score/queue commitments, and joined only corrected **35.csv / 36.csv** from the pinned official corrected-label archive. Exact source membership, explicit binary labels, native +5 stride, historical denominators and **all 50 historical policy/workload count comparisons** replayed. The new score-only analysis did not rehash image pixels or rerun inference. Historical image-byte verification and private retention remain separate evidence, with current recovery status in the private handoff.

At each of the fixed 10% / 25% workloads, executed **10,000 within-bin score randomizations**, **1,000 coarse16-block circular-score-shift controls**, and **100 fixed systematic phases**. Total: **40,000 + 4,000 + 400** controls. Seeds and algorithms are fixed in the contract/code. Preserved uniform, raw score-bin, global score, score-diverse and window3 policies. No selection parameter was tuned against these outcomes.

An independent script importing no production selector/evaluator reproduced every primary randomization count, short/medium/long stratum, coarse-shift draw and phase selection. Independent direct bin/run intersection arithmetic matched exact expected counts. Simulated means agreed with exact expectations within **1.72 Monte Carlo standard errors** across reported count endpoints. Synthetic exhaustive combinations verify the earliest-maximum tie distribution and runs crossing multiple bins.

## Controlled run-preservation results

The geometry control permutes scores **inside each original K chronological bin**, retaining its boundaries, score multiset, one selected image per bin and exact workload. A uniquely maximal score has a uniformly random position under this permutation. All bins at these four operating points had unique maxima, so literal score permutation and independent uniform-one-per-bin selection have the **same exact null distribution**. No full-score permutation is necessary to simulate the winning position. Code also handles tied maxima using the original earliest-tie rule, independently tested on synthetic data.

| Examination | Budget; exact K | Uniform runs | Real score-bin runs | Geometry-only expected runs | Real minus geometry, run-recall pp | Randomized run-count 95% reference interval |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 35; 29 runs | **10%; 964** | 16 | **23** | 16.690 | **+21.76** | 13–20 |
| 36; 59 runs | **10%; 1,333** | 15 | **28** | 18.510 | **+16.08** | 13–24 |
| 35; 29 runs | 25%; 2,411 | 25 | **28** | 23.271 | **+16.31** | 20–26 |
| 36; 59 runs | 25%; 3,332 | 36 | **41** | 32.625 | **+14.19** | 27–39 |

Expected distinct-run counts sum `1 − product(1 − bin_hit_probability)` over runs, so a run spanning several bins counts once. Fractional expected counts do not represent fractional observed events.

At 10%, the **equal-examination mean** run recall is **63.38% real**, **40.30% deterministic uniform** and **44.46% geometry-only expectation**. Thus real score-bin exceeds deterministic uniform by **23.09 pp**, and the geometry-matched expectation by **18.92 pp**. The two conditional score-information contrasts differ by **5.67 pp**. At 25%, the corresponding real score-bin advantage is **9.41 pp versus uniform** and **15.25 pp versus geometry**. The baseline choice matters: deterministic uniform is below the geometry expectation at 10% but above it at 25%.

Within-bin randomized upper-tail reference fractions (plus-one correction) for run counts are **0.00070 / 0.00130** at 10% for35/36, and **0.00320 / 0.00470** at25%. The paired macro fraction is **0.00010** at both budgets. These are exploratory, conditional randomization summaries, **not** confirmatory clinical p-values; no multiplicity-adjusted claim is made. They assume exchangeability inside short bins, which capsule chronology does not guarantee.

The paired macro real-minus-randomized **95% reference range** is **11.10–26.56 pp** at10%, **7.71–23.06 pp** at25%; Monte Carlo SE of the null macro mean is **0.0405 / 0.0382 pp**. These ranges describe fixed-examination randomization variability, **not a confidence interval for future patients**. With only two outcome-inspected examinations, reliable population uncertainty is unavailable. The aggregate gives the three-value two-examination bootstrap support explicitly, without treating it as a population CI. Do not pool 22,969 correlated images into an artificial independent sample size or describe a causal percentage of benefit.

## Sensitivity controls

| Examination; budget | Real runs | Coarse16-block shift mean; 95% reference interval | Mean across100 fixed systematic phases; 95% phase interval |
| --- | ---: | --- | --- |
| 35;10% | 23 | 16.525;13–20 | 17.30;16–19 |
| 36;10% | 28 | 18.300;13–24 | 19.41;15–24.525 |
| 35;25% | 28 | 23.015;20–26 | 24.00;22–26 |
| 36;25% | 41 | 32.396;27–39 | 33.75;30–39 |

Circular shifts preserve coarse score location and most within-block score autocorrelation, while breaking fine score/label alignment. Real scores remain favourable under this control. Block boundaries introduce discontinuities, and16 blocks is a fixed sensitivity choice, not an authenticated anatomy stratification. The100-phase grid is deterministic sensitivity: its interval is neither a Monte Carlo SE nor a patient CI, and no best phase was selected. Phase interpolation can give fractional quantiles even though every actual count is integer.

## Positive images are a different endpoint

| Examination; budget | Positive images available | Uniform hits | Real score-bin hits | Geometry expected hits |
| --- | ---: | ---: | ---: | ---: |
| 35;10% | 1,534 | 151 | 163 | 153.400 |
| 36;10% | 209 | 16 | 33 | 20.900 |
| 35;25% | 1,534 | 385 | 397 | 383.583 |
| 36;25% | 209 | 52 | 67 | 52.250 |

At10%, real score-bin's positive-image recall is **10.63% on35** and **15.79% on36**, despite run recalls79.31% and47.46%. The conditional image-recall lifts are only **0.63 pp on35** versus **5.79 pp on36**. A few selected positives spread across runs can improve run preservation with modest overall positive-image enrichment. Neither endpoint is lesion sensitivity.

Global ranking remains a separate failure mode: at10% it reaches **22/29 runs on35 versus6/59 on36**; on36 its first5% finds no positive image. At25% on36, global ranking retrieves79 positive images but only27 runs, versus score-bin67 images across41 runs. The new conditional result does not erase this heterogeneity or rehabilitate global ranking.

## Short-run failures remain substantial

| Examination; budget | Short runs: uniform / real / geometry expectation | Medium: uniform / real / geometry | Long: uniform / real / geometry |
| --- | --- | --- | --- |
| 35;10% | 4 / **9** /3.860 of14 | 8 / **10** /8.830 of11 | 4 /4 /4 of4 |
| 36;10% | 4 / **14** /7.570 of44 | 11 / **14** /10.940 of15 | none |
| 35;25% | 10 / **13** /8.333 of14 | 11 /11 /10.938 of11 | 4 /4 /4 of4 |
| 36;25% | 21 / **26** /17.625 of44 | 15 /15 /15 of15 | none |

Local score information particularly helps short runs relative to geometry, but **35.7% /68.2% of short runs still go unselected at10% on35/36**, versus9.1% /6.7% of medium runs. Even25% misses18 of44 short runs on36. Four long runs in only one examination cannot establish long-event reliability. These length strata count positive published positions, not seconds or independent lesions.

The frozen temporal-window3 score-bin retains only **17/29 and20/59 runs at10%**, versus raw23/29 and28/59; at25% it reaches24/29 and35/59 versus raw28/29 and41/59. The prior temporal harm remains unchanged. This rejects that fixed max-filter comparator on these cases, not every possible temporal model.

## Multi-examination extension: evaluated, acquisition deferred

The full31–40 index is already verified: **381,787 images; six positive and four zero-blood examinations;605 annotation runs;18 solid blocks totaling69,215,688,770 bytes**. Shared blocks mean per-exam costs cannot simply be summed. Expanding beyond the retained35/36 blocks would require **62,331,483,800 additional compressed bytes**, before original-image retention, predictions and any duplicate transport wrappers. This execution recovered missing backup ranges only; it did not acquire a new examination.

| Exam | Images | Previously inspected blood runs | Required blocks | Total block bytes for complete export |
| --- | ---: | ---: | --- | ---: |
| 31 | 24,919 | 162 | 0,1 | 7,094,259,360 |
| 32 | 23,421 | 0 | 1,2,3 | 10,803,629,651 |
| 33 | 13,297 | 0 | 3,4 | 7,091,985,967 |
| 34 | 10,867 | 9 | 4,5 | 6,963,285,731 |
| 35 | 9,643 | 29 | 5 | 3,453,334,016 |
| 36 | 13,326 | 59 | 5,6 | 6,884,204,970 |
| 37 | 18,125 | 0 | 6,7 | 6,892,487,867 |
| 38 | 6,209 | 0 | 7,8 | 7,555,919,684 |
| 39 | 130,776 | 286 | 8–13 | 25,510,343,310 |
| 40 | 131,204 | 60 | 13–17 | 19,833,541,469 |

The closest bounded resource-defined extension, all34–37, needs **6,971,568,628 new compressed bytes** (blocks4/7) in addition to restored5/6. It adds only **one blood-positive examination with9 runs and one zero-blood examination**. It would be a defensible convenience/resource development extension if explicitly specified and fully verified, but is not enough new positive-domain diversity to resolve the observed generalization question. Selecting only its easiest partial neighbours would be invalid. No new source transfer is justified here merely to inflate examination count; the requested existing-data mechanistic analysis is complete.

**Prespecified future eligibility:** screen all ten in fixed numerical order and report every exclusion; require complete original membership against corrected explicit-binary labels, original-byte/source checksums and durable private retention, verified permitted use/version, fixed original checkpoint/preprocessing/policies/budgets, and no use of CNN outcomes to select cases. Zero-positive cases remain in cohort accounting, with positive-run recall undefined. Link device/site and patient identities only through authenticated source metadata; do not infer them from export stride, filenames or appearance. Conduct leakage checks against1–8 fitting material; unknown patient overlap prevents patient-independent claims. Previously inspected31–40 remain development even after qualification. Group-level uncertainty must use genuine examination or authenticated patient units. A complete published-label study can measure annotation-run preservation; clinically adjudicated event preservation needs a stronger reference standard.

The source index does **not** authenticate patient grouping, full clinical event completeness, site/device labels or a study-specific rights review. No new patient mapping or permissions were established in this execution. Do not treat a metadata index or checksum as those qualifications. The full current69 GB archive MD5 remains unverified; authors'61–80 stay unopened.

## Decision: what needs to improve

The limitation is a combination. Chronological selection geometry limits clustering; the CNN supplies useful **local** ranking on35/36, yet **global discrimination/domain transfer is unstable**. Short-run omissions remain the clearest evidence-preservation failure. Training positives remain concentrated in few examinations, and patient/domain grouping and clinically meaningful event labels remain unresolved. The frozen11–20 primary stays **−1.2668765 pp**, and the16-examination chronology-conditioned result still fails to show consistent CNN advantage. Different checkpoints, source sampling and endpoints prohibit pooling those studies with this one as if they were a common test.

**Next major investment:** qualify a broader source-diverse evaluation/development cohort and its reference standard before another model fit. Freeze a resource-bounded multi-examination cohort using the eligibility rules above, authenticate patient/device/site grouping, retain complete source exports and unchanged predictions, then repeat these controls with the **equal-positive-examination10% run-recall contrast** primary and25%/short-run results secondary. Include all eligible negative examinations in accounting. Seek clinician adjudication of sampled missed short runs before interpreting them as missed lesions. This execution sends no custodian/clinician messages.

Only after that benchmark is qualified should a single fixed **training-diversity** comparison be considered, with group-excluded fitting and identical evaluation sources. A bigger CNN, architecture sweep, score-bin/window tuning on35/36, or a claimed clinical promotion is not supported. The existing AI became **better understood**, not improved.
