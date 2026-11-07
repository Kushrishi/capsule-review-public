# Galar 31/34/37 complete-source unchanged-CNN results

Executed November 6–7, 2026 UTC, from merged PR67. **The earlier score-bin advantage did not replicate consistently.** At the fixed 10% workload, equal-positive-examination run recall was 59.26% for raw score-bin versus 78.09% for deterministic uniform (−18.83 percentage points). Score information relative to matched geometry was negative on31 and positive on34; its two-examination mean was inconclusive. No model was trained, retuned or promoted.

This is exploratory, already-inspected, examination-separated **development** evidence. Patient-repeat linkage and per-examination site/device provenance are unverified. Annotation runs are not independent lesions, and blood annotations are not clinical sensitivity, active-bleeding diagnoses or reader-time measurements. Galar37 is a zero-blood comparator, not a clinically normal examination.

## Execution and frozen design

The [A2 contract](GALAR313437_EXPERIMENT_LOCK_20261106.md) was committed as bd59b4936770d8d782df0e29df5cf8a9df1af15d before new source acquisition. It explicitly amended the earlier8GiB operator cap to14,065,827,988 distinct new compressed bytes for these three cases. [A2.1](GALAR313437_RETENTION_AMENDMENT_A21_20261106.md) froze durable publisher-block retention instead of duplicate extracted ZIP retention. [A2.2](GALAR313437_INTERRUPTION_RECOVERY_A22_20261107.md) authorized exact missing-range recovery after a cloud interruption, before replacement inference and outcomes. No substitute examinations, full-archive fallback or reserved61–80 payloads were opened.

Official source: [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2), CC BY4.0; original image source and corrected labels are attributed to the Galar dataset authors. See the frozen contract for exact official ranges, rights and capacity preflight. Source blocks0/1/4/7 plus previously retained5/6 reconstructed only the target complete published exports. All membership, native+5 grids without internal gaps, source CRCs, PNG decoding and SHA256 identities were verified, including independent rechecking of all53,911 PNG hashes. Published stride-five exports do not imply continuous device exposures or known elapsed time.

| Examination | Complete originals | Original PNG bytes | Blood-positive images | Positive annotation runs | K10 | K25 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|31|24,919|8,181,689,551|3,310|162|2,492|6,230|
|34|10,867|3,223,269,590|49|9|1,087|2,717|
|37|18,125|5,065,721,113|0|0|1,813|4,531|
|Total|53,911|16,470,680,254|3,359|171|5,392|13,478|

All final snapshots use the original compact capsule-cnn-v1, checkpoint SHA256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, original EXIF/RGB96×96 padded bilinear preprocessing, softmax and fixed policies. Exact K uses the pre-existing integer rounding rule. No calibration, parameter selection or training occurred. There were zero exact PNG-byte overlaps with the4,096 original fitting images; this does not rule out repeat patients, near-duplicates or domain leakage.

The frozen31 snapshot was recovered unchanged.34 required replacement inference after its first unretained snapshot was lost;37 restarted after interruption.34's replacement digest differed from its recorded first digest despite matched source bytes/checkpoint/code/runtime versions. Its first scores were unavailable, so exact queue concordance cannot be asserted. A prespecified, label-free128-image technical canary on31 (no full31 rescore or snapshot replacement) found maximum absolute score variation1.19e−7 and no difference above1e−4; this is consistent with floating-point variation, not proof of original34 equivalence. Final replacement snapshots were sealed before outcomes; independent replay uses those final sealed scores.

All image hashes, final scores and75 queues (3cases×5policies×5historical budgets), original checkpoint, source receipts and raw corrected-label archive were remotely readback-verified in a14,805,804-byte pre-audit package at03:31:48UTC November7. SHA256 `fb2dece8f6ba8f1748d009f4ed7d102fb2563a4dd480e746507b4ed5bf9e92dd`. Only then did the separate31/34/37 CSV audit run; all53,911 labels joined one-to-one. This is auditable computational separation, not new blinding. The private launch record transparently notes an initially failed timestamp helper, corrected after launch; the independently verified pre-audit seal already preceded the audit.

## Joint primary and uncertainty

At10%, report both raw-bin contrasts jointly. Each positive examination receives weight1/2 regardless of its image or run count.37 remains in accounting but has undefined positive-image/run recall and contributes no positive-recall denominator. The25% endpoint is secondary.

Geometry controls reuse PR66:10,000 within-floor-bin score permutations per case/budget, PCG64 SeedSequence([20261106,exam,percent,1]), coupled uniform-within-bin geometry draws;1,000 fixed16-block circular shifts with stream2;100 fixed systematic phases. There were no tied score maxima in the evaluated floor bins, so permutation and geometry distributions coincide. Exact bin/run expectations supply the score-information point contrast. The66,600 newly executed randomization/phase controls exclude the already-completed35/36 controls.

| Budget | Raw-bin run recall | Uniform run recall | Raw − uniform (pp) | Raw − exact geometry (pp) | Conditional95% reference for score effect (pp) | Upper-tail randomization fraction |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
|10%|59.26%|78.09%|-18.83|+7.97|[-6.17, +20.99]|0.1379|
|25%|76.23%|79.63%|-3.40|-0.66|[-10.19, +9.57]|0.5766|

These are conditional randomization reference ranges from observed-minus-null draws, **not patient-population confidence intervals**. Null-mean Monte Carlo SE is0.06985pp at10% and0.05308pp at25%. Two-examination resampling support for score-information effects is [−4.62,+7.97,+20.56]pp at10% and[−4.78,−0.66,+3.47]pp at25% (weights1/4,1/2,1/4); it cannot establish population uncertainty. Neither joint endpoint establishes an advantage over both baselines.

## Per-examination policies and positive-image retrieval

Cells below separate distinct annotation runs from positive images. Positive-image percentages use3,310 and49 denominators respectively; no pooled-image weighting substitutes for the primary comparison. Full aggregate uncertainty and spacing summaries are in the [machine-readable results](../experiments/galar313437-full-source-20261107/aggregate.json).

| Exam | Budget/K | Policy | Runs reached | Run recall | Positive images reached | Positive-image recall |
| --- | --- | --- | ---: | ---: | ---: | ---: |
|31|10% / 2,492|Uniform|109/162|67.28%|343/3310|10.36%|
|31|10% / 2,492|Raw score-bin|84/162|51.85%|322/3310|9.73%|
|31|10% / 2,492|Global score|60/162|37.04%|1000/3310|30.21%|
|31|10% / 2,492|Score diversity|78/162|48.15%|399/3310|12.05%|
|31|10% / 2,492|Window3 score-bin|82/162|50.62%|324/3310|9.79%|
|31|25% / 6,230|Uniform|132/162|81.48%|829/3310|25.05%|
|31|25% / 6,230|Raw score-bin|121/162|74.69%|821/3310|24.80%|
|31|25% / 6,230|Global score|82/162|50.62%|1647/3310|49.76%|
|31|25% / 6,230|Score diversity|101/162|62.35%|1040/3310|31.42%|
|31|25% / 6,230|Window3 score-bin|124/162|76.54%|828/3310|25.02%|
|34|10% / 1,087|Uniform|8/9|88.89%|9/49|18.37%|
|34|10% / 1,087|Raw score-bin|6/9|66.67%|7/49|14.29%|
|34|10% / 1,087|Global score|0/9|0.00%|0/49|0.00%|
|34|10% / 1,087|Score diversity|6/9|66.67%|8/49|16.33%|
|34|10% / 1,087|Window3 score-bin|3/9|33.33%|4/49|8.16%|
|34|25% / 2,717|Uniform|7/9|77.78%|13/49|26.53%|
|34|25% / 2,717|Raw score-bin|7/9|77.78%|14/49|28.57%|
|34|25% / 2,717|Global score|4/9|44.44%|13/49|26.53%|
|34|25% / 2,717|Score diversity|8/9|88.89%|22/49|44.90%|
|34|25% / 2,717|Window3 score-bin|6/9|66.67%|11/49|22.45%|

37: every policy retrieved zero annotated blood images/runs at both budgets; positive recall remains undefined. Without non-blood pathology adjudication, an all-zero blood comparator cannot measure specificity, normality or false clinical alerts for exact-K ranking.

| Exam | Budget | Raw runs | Geometry exact expected runs | Raw − geometry (pp) | Permutation95% run reference | Coarse16 shift mean runs |100-phase mean runs [95% grid range] |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
|31|10%|84|91.4900|-4.62|[83.0, 100.0]|90.367|94.91 [89.0, 109.0]|
|31|25%|121|128.7500|-4.78|[121.0, 136.0]|127.933|132.00 [125.475, 136.0]|
|34|10%|6|4.1500|+20.56|[2.0, 7.0]|4.061|4.50 [4.0, 8.0]|
|34|25%|7|6.6875|+3.47|[5.0, 8.0]|6.563|6.75 [5.0, 8.0]|

31 is worse than geometry at both budgets;34 is better. The10% score-information contrast spans25.18pp between cases; the uniform contrast is−15.43pp on31 and−22.22pp on34. Deterministic uniform is itself phase-sensitive, especially34: its8/9 run result is near the upper end of the fixed phase grid, while the phase mean is4.5/9. Systematic phases are sensitivity analyses, not independent patients or an identical floor-bin randomization family.31 raw-bin falls below its systematic-phase reference range at both workloads. No favourable phase or baseline replaced the prespecified comparison.

## Short-event coverage and temporal comparator

Run lengths count published positive positions, not elapsed time. Short=1–5, medium=6–25, long=26+. Counts below are reached/available.

| Exam | Budget | Policy | Short | Medium | Long | Singletons |
| --- | --- | --- | --- | --- | --- | --- |
|31|10%|Uniform|33/83|42/45|34/34|2/14|
|31|10%|Raw score-bin|17/83|33/45|34/34|2/14|
|31|10%|Global score|21/83|23/45|16/34|5/14|
|31|10%|Score diversity|20/83|27/45|31/34|3/14|
|31|10%|Window3 score-bin|18/83|30/45|34/34|0/14|
|31|25%|Uniform|53/83|45/45|34/34|3/14|
|31|25%|Raw score-bin|42/83|45/45|34/34|4/14|
|31|25%|Global score|33/83|25/45|24/34|6/14|
|31|25%|Score diversity|40/83|28/45|33/34|6/14|
|31|25%|Window3 score-bin|45/83|45/45|34/34|2/14|
|34|10%|Uniform|4/4|4/5|0/0|2/2|
|34|10%|Raw score-bin|1/4|5/5|0/0|1/2|
|34|10%|Global score|0/4|0/5|0/0|0/2|
|34|10%|Score diversity|1/4|5/5|0/0|1/2|
|34|10%|Window3 score-bin|0/4|3/5|0/0|0/2|
|34|25%|Uniform|2/4|5/5|0/0|0/2|
|34|25%|Raw score-bin|2/4|5/5|0/0|1/2|
|34|25%|Global score|0/4|4/5|0/0|0/2|
|34|25%|Score diversity|3/4|5/5|0/0|2/2|
|34|25%|Window3 score-bin|1/4|5/5|0/0|0/2|

At10%, raw-bin reaches18/87 short runs versus37/87 for uniform, missing69 versus50. At25%, it reaches44/87 versus55/87, missing43 versus32. These pooled run counts are descriptive; primary inference still weights examinations equally. Of16 singletons, raw-bin reaches3 versus uniform4 at10%; at25% raw reaches5 versus uniform3. Thus the short-run deficit does not mean every subgroup or operating point favours uniform. All34 long runs occur in31 and both raw-bin and uniform reach all34 at both budgets.

Window3 changes coverage rather than simply preserving adjacent evidence. On31@10 it loses10 raw-reached runs and gains8; on34@10 it loses3 and gains0. On31@25 it loses11 and gains14, an important positive exception (124 versus121 raw runs);34@25 loses2 and gains1. Window3 misses every singleton at10%. In an ancillary post-outcome mechanism check,3/5 lost short runs on31@10 and1/1 on34@10 include an earlier adjacent negative position winning an exact temporal-max plateau tie; at25% the counts are3/11 and1/2. This characterizes one failure mechanism, not all temporal losses. No new window or tie policy was fitted.

The pre-outcome [fixed-bin oracle diagnostic](GALAR313437_ORACLE_DIAGNOSTIC_20261106.md) bounds geometry's restriction with label-informed maximum matching; it is not an executable label-free selector.31@10 can reach at most150/162 runs with one image per fixed bin; actual raw reaches84. Geometry forces at least12 misses but leaves66 additional runs reachable in principle.31@25 and34 at both budgets can theoretically reach every run.31@25's41 raw misses are all short. These ceilings show that geometry alone cannot explain the observed failures; they do not prove a learnable classifier can attain the oracle.

## Ranking and spacing failures

31 global ranking retrieves1,000 positive images at10%, versus343 for uniform, but reaches only60 runs versus109. At25% the comparison is1,647 versus829 positive images but82 versus132 runs. At10%,791/1,000 global positive hits lie in long runs, and its most-selected run supplies136 hits. Positive-image discrimination therefore does not imply preservation of distinct events.34 global ranking retrieves **zero of49 blood-positive images and zero of9 runs** at10%, increasing to13 images/four runs at25%. This cross-case failure supports concern about score transfer, but unverified device/site records prevent attribution to a particular domain.

| Exam | Budget | Largest unselected imported-image span: uniform | Raw bin | Global | Score diversity | Window3 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
|31|10%|9|18|5876|2284|18|
|31|25%|3|6|3167|1996|6|
|34|10%|9|18|2945|497|18|
|34|25%|3|6|612|482|6|
|37|10%|9|18|2177|675|18|
|37|25%|3|6|1926|171|6|

At10%, the95th-percentile distance to a selected imported image is5 for uniform and7 for raw-bin on31/34, versus2,600 for31 global ranking. At25% uniform/raw values are2/3. These are source-order coverage quantities, not time or lesion visibility. Raw-bin prevents very large gaps but its within-bin maxima often select the wrong positions for short events.

## Independent reproduction and durability

A separate Python/NumPy/csv implementation imports no production selector or geometry module. It independently rechecked53,911 PNG hashes, all75 policy queues, six examination/budget audits, exact expectations, all66,600 randomization/phase controls and both joint macro comparisons. A separate augmenting-path matching algorithm reproduced the oracle ceilings. [Replay proof](../experiments/galar313437-full-source-20261107/independent-check.json); script SHA256 `528aa3db4bec39bb9a99a907107068b6ea32b46a191b3e1272d8d5cc1ca5eac1`. Local full suite:1,015 passed,1 skipped; final-head CI must additionally pass Python3.11–3.13, local-model/browser and public-source privacy gates before merge.

All6 required publisher blocks are privately retained as388 logical transports, **20,950,032,958 original compressed bytes**, with actual remote wrapper/raw SHA256 readback and restore verification. Of these,14,065,827,988 bytes are distinct newly required blocks0/1/4/7;6,884,204,970 reuse retained5/6. Interruption required recovery of71 exact pinned ranges (3,467,448,522 bytes), bringing cumulative publisher compressed payload to17,533,276,510 bytes. Two optional split transport backups are redundant copies, not extra source coverage. No required compressed-source gap remains. The full69,219,317,963-byte archive was not downloaded and its full-file MD5 is **not verified**.

Original images are durable through verified publisher blocks plus retained headers/index/approved membership and extraction code. The three extracted PNG ZIPs are temporary working conveniences, not separately uploaded originals. Their combined bytes total16,478,078,414 including ZIP overhead. The final private evidence package retains checkpoint, raw corrected-label archive, image hashes, final predictions/queues, one-to-one outcome joins, repetition arrays, source receipt maps and pre-/post-audit proofs. Exact locations, byte counts and checksums remain in the private inventory; no pixels, individual annotations/scores, source IDs or weights are published here.

## Historical comparison, interpretation and next experiment

Frozen35/36 data are read descriptively without rerunning inference or their44,400 controls: at10%, raw/uniform runs were23/16 of29 and28/15 of59; their equal-examination raw-minus-geometry effect was+18.92pp and raw-minus-uniform+23.09pp. New31/34 effects are+7.97pp (inconclusive and heterogeneous) and−18.83pp respectively. At25%, old score-information effect+15.25pp contrasts with−0.66pp now. These selected, already-inspected examinations should not be pooled post hoc into an allegedly confirmatory success. The locked11–20 negative10% primary result, failed16-examination chronology-conditioned advantage, and historical negative temporal findings remain unchanged.

The AI became **better understood, not improved**.31 ranking has positive-image enrichment yet loses event coverage;34's global ranking fails badly; both lose short runs under raw-bin versus fixed uniform. The oracle and geometry controls implicate score alignment and event-selection objectives as well as source heterogeneity. Training positives were highly concentrated:208/239 fitting positives came from examination7. That makes training diversity a stronger next controlled hypothesis than a larger architecture, while it does not establish the cause. Labels still do not distinguish independent lesions, blood/hematin/active bleeding reliably enough for clinical claims. Patient linkage, authenticated site/device provenance and clinical adjudication remain essential for eventual validation.

**Single next proposed experiment (not run): matched-budget training-examination-diversity ablation.** Keep capsule-cnn-v1,96×96 preprocessing, optimizer/loss and fixed selectors. Compare original1–8 fitting population with a broader permitted fitting pool1–8 plus21/23/25/27/29/30, using existing privately retained uniform references only. Exclude9/10 and all benchmark cases from fitting; never use reserved61–80. Before training, verify asset hashes/rights/labels, exact original-image overlap, obtainable class counts and examination distribution, then freeze source membership. Each arm targets4,096 distinct fitting images with239 blood-positive/3,857 other images, identical class weights, batch32 and1,024 updates (eight epochs), fixed final checkpoint rather than benchmark-selected stopping; paired seeds17/29/43. If matched counts/diversity are infeasible, stop and amend before outcomes rather than silently changing the comparison. Prefer a frozen constrained sampler that spreads positives across eligible fitting examinations without inspecting benchmark outcomes.

Cost: six compact CPU fits,24,576 fitting-image exposures per epoch across arms, and323,466 benchmark forward passes (six checkpoints×53,911), plus the unchanged private evaluation/control replay. No additional publisher-original acquisition is required **if** the existing14-examination reference packages qualify and are durable; this is a prerequisite, not an assumed verification. Freeze10% equal-positive-examination run-recall change versus the original checkpoint and score-information/uniform contrasts jointly;25%,short strata, all seeds and per-exam effects secondary; prohibit seed/model selection on benchmark results.31/34/37 would remain inspected development targets, not independent confirmation. A successful ablation would motivate separately grouped, clinically adjudicated confirmation; it would not itself demonstrate patient generalization. Do not launch training until that data/matching preflight and explicit experiment lock are complete.

