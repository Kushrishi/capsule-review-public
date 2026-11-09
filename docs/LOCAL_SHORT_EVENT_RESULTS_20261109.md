# Local short-event objective comparison — 9 November 2026 UTC

## Recovery and scope

The resumed audit found main still at PR69 merge
`31fbe74a6463768bb15be69dba9e6180d653c5d5`, with no newer completed short-event
experiment. The private PR69 evidence, source audit, fitting packages and retained
benchmark blocks were recovered and verified. PR69's six fits were not repeated;
the historical CNN was not rescored. Its negative training-diversity result and
the historical locked Galar 11–20 negative 10% primary remain unchanged.

This experiment tests one training objective on already-inspected development
examinations. It cannot establish patient-independent or clinical validation.
No Galar 11–20 or reserved 61–80 sources were acquired for this experiment; no external
outreach or Google Drive copying/sharing was performed.

## Exact feasibility result

The permitted retained fitting assets contained 10,123 original PNGs. Full fitting
labels and native archive membership were checked, without treating sparse
uniform references as sequences. Only 14 genuine adjacent opposite-label pairs
were retained, ten touching short positive runs. The original 1–8 fitting subset
supplied no such retained pairs. Unknown labels and native gaps were preserved.

Before new pixels, the [acquisition lock](LOCAL_SHORT_EVENT_ACQUISITION_LOCK_20261109.md)
fixed an engineering gate of 32 distinct short runs, at least four examinations,
and at most 16 runs from one examination. This is a feasibility threshold, not a
power calculation. A complete-solid-block cost enumeration rejected 14 cheaper
block sets. The smallest qualifying verified block required 3,514,256,456
compressed bytes; only 21 new original PNGs (4,871,891 bytes) were extracted.
This minimum is conditional on the fixed gate and complete verified solid blocks.

Rights were checked against Galar v 2 CC BY4.0 (Le Floch et al.). The selected block
matched its prior SHA256; each extracted original passed archive CRC, byte length,
SHA256 and decoding checks. The full publisher archive MD 5 was not verified.
Capacity was checked before acquisition with 8 GB reserved headroom. New originals
were durably saved and read back with matching SHA256.

The resulting 32 pairs represent 32 short annotation runs across five permitted
examinations. Every pair has a positive boundary image and its immediate native
±5 explicitly negative neighbour; no gaps or unknowns bridge a pair. Run length
means 1–5 annotated published positions, not seconds or distinct lesions. The
five-examination pair counts are 1/4/1/11/15. Shared endpoints remain visible in
the private manifest:63 distinct pair images, with one negative shared by two
runs. The exact 4,096 PR69 diverse references remain the common background.
The combined fitting union has 4,156 distinct originals.

All 10 source ZIPs and 10,123 retained image identities were rechecked. A separate
source audit rehashed pair endpoints and reproduced adjacency and labels. No
exact PNG-byte or 96×96 preprocessed-image overlap was found with the 53,911
evaluation originals. Near duplicates and cross-examination patient linkage
remain unverified.

## Frozen intervention and actual execution

The [experiment lock](LOCAL_SHORT_EVENT_EXPERIMENT_LOCK_20261109.md), JSON contract,
and executable code were committed at
`9dfce9ba6a9d83cf13847604c64195f9ba8157d3` before fitting. Six new fits completed:
classification and local-ranking arms for paired seeds 17/29/43. These matched
controls are necessary because pair-enriched exposures differ from PR69.

Both arms use unchanged capsule-cnn-v 1, EXIF/RGB black-padded bilinear 96×96
preprocessing, deterministic CPU execution, AdamW(lr 0.001, weight_decay 0.0001),
and 1,024 updates. Each batch contains 16 background references and eight pairs;
each fit has 32,768 image presentations (9,148 positive/23,620 negative). Every
pair appears 256 times. Initial tensors, schedules, image exposures and final
checkpoint rule match within each seed.

The control uses inverse-exposure-weighted two-class cross entropy. The candidate
adds 0.5×mean softplus(z_negative−z_positive), with z the blood-minus-other logit.
There was one fixed weight, no architecture sweep, stopping rule, seed selection,
or benchmark-based parameter search.

An ancillary fitting-only diagnostic, added after fitting and before benchmark
outcomes, found all six models ordered 32/32 fitting pairs correctly. Ranking
increased their margins. These are repeated training examples and do not prove
transfer or improved event preservation.

The retained benchmark transports were restored privately:388 wrappers and raw
parts were byte-verified. All 53,911 original PNGs passed prior frozen SHA256 and
source-index checks. Cached tensors matched PR69 identities. Only the six new
models were scored; all 18 vectors were sealed before outcomes.


## Results and scientific decision

**The controlled comparison did not demonstrate reliable improvement.** The 10%
primary mean changed from 50.0000% to 50.3086% (+0.3086 pp), with one improving seed
and two worsening seeds. The paired-effect standard deviation was 11.6182 pp;
the range was−8.0247 to+13.5802 pp. The prespecified all-seed consistency criterion
failed. Mean short-run recall was exactly unchanged. No model is promoted.

All primary values below are equal-positive-examination means for 31/34, with
unchanged exact-K score-bin selection. Positive runs are 162/9 respectively.

| Seed | Classification 10% | Ranking 10% | Paired change(pp) | Classification 25% | Ranking 25% | Paired change(pp) |
|---|---:|---:|---:|---:|---:|---:|
| 17 | 50.0000% | 41.9753% | -8.0247 | 83.9506% | 77.4691% | -6.4815 |
| 29 | 43.5185% | 57.0988% | +13.5802 | 75.3086% | 82.7160% | +7.4074 |
| 43 | 56.4815% | 51.8519% | -4.6296 | 77.7778% | 78.3951% | +0.6173 |

| Comparison |10% mean run recall |25% mean run recall |
|---|---:|---:|
| Matched classification |50.0000% |79.0123% |
| Local ranking |50.3086% |79.5267% |
| Historical unchanged CNN |59.2593% |76.2346% |
| Deterministic uniform |78.0864% |79.6296% |
| Exact geometry expectation |51.2932% |76.8904% |

Ranking's 10% mean is 27.7778 pp below uniform and 0.9846 pp below geometry.
Classification is 28.0864 pp below uniform and 1.2932 pp below geometry. No new model
exceeded uniform at 10%. Tie-aware score-permutation expectations equal geometry:
there were no tied bin maxima. Every model's conditional geometry reference
interval includes zero; these conditional randomization references are not
patient-population confidence intervals.

The 25% secondary mean effect is+0.5144 pp (seed SD 6.9450 pp; two positive seeds),
with ranking still 0.1029 pp below uniform. It cannot rescue the primary failure.
Galar 31's seed-mean primary change is+0.6173 pp; Galar 34's is exactly zero apart
from floating-point rounding. One Galar 34 run changes recall by 11.1111 pp,
illustrating the instability of a nine-run examination.

### Every seed and examination

Cells show score-bin run hits, short-run hits, singleton hits and positive-image
hits, in that order. Denominators are shared within an examination: Galar 31 has
162 runs/83 short runs/14 singleton runs/3,310 positive images; Galar 34 has
9/4/2/49. Full medium/long strata, all four policies and exact null expectations
are preserved in the [public aggregate](../experiments/local-short-event-20261109/aggregate.json).

| Workload | Examination | Seed | Classification: runs/short/singletons/images | Ranking: runs/short/singletons/images |
|---|---|---|---|---|
| 10% | 31 | 17 | 90/19/1/331 | 82/14/0/322 |
| 10% | 31 | 29 | 87/18/0/319 | 95/21/1/329 |
| 10% | 31 | 43 | 93/23/0/330 | 96/25/0/328 |
| 10% | 34 | 17 | 4/1/0/4 | 3/1/0/4 |
| 10% | 34 | 29 | 3/0/0/6 | 5/1/0/7 |
| 10% | 34 | 43 | 5/2/1/5 | 4/1/0/4 |
| 25% | 31 | 17 | 128/49/3/830 | 125/47/3/824 |
| 25% | 31 | 29 | 118/39/2/812 | 124/45/3/823 |
| 25% | 31 | 43 | 126/47/4/827 | 128/49/3/825 |
| 25% | 34 | 17 | 8/3/2/13 | 7/2/1/12 |
| 25% | 34 | 29 | 7/2/0/13 | 8/3/1/14 |
| 25% | 34 | 43 | 7/2/1/13 | 7/2/1/12 |

Exact K values at 10%/25% are 2,492/6,230 (31),1,087/2,717 (34), and 1,813/4,531
(37). Galar 37 has 18,125 explicitly negative images and zero positive runs;
all six models and all policies use those exact workloads, with positive recall
undefined. It is not assigned a perfect score or included in the positive macro.

### Short-event failures and other policies

At 10%, mean equal-examination short-run recall is 24.5482% in both arms, versus
uniform 69.8795%. Ranking harms Galar 31 short hits in seed 17 (19→14), helps in 29
(18→21) and 43 (23→25); Galar 34 changes 1→1,0→1,2→1. Therefore an unchanged mean
conceals seed/examination regressions. Across three seeds, singleton omissions
are 46/48 available seed-run opportunities for classification and 47/48 for ranking;
these repeated opportunities are not independent samples. Uniform misses 12/16
singleton runs per queue. No singleton-preservation improvement is demonstrated.

At 25%, short-run mean recall changes 56.2751%→57.4799% (+1.2048 pp), again with
regressions in individual seed/examination cells. Singleton hits summed over
seeds remain 12/48 in both arms.

Mean positive-image recall at 10% is 10.0366%→10.0315%; at 25% it is 25.6973%→25.3723%.
More positive images and more distinct runs are different outcomes. Global score
ranking's 10% run recall worsens 46.1934%→41.9753%; score-diverse worsens
59.0535%→55.5556%. At 25% they change 68.2099%→66.9753% and 77.4691%→75.0000%.
Neither alternate policy supplies a consistent rescue, and no selector was chosen
from these outcomes.

## Interpretation and single next experiment

The objective increased fitting margins but did not transfer reliably to
short-event preservation. A+0.3086 pp mean amid 11.6182 pp seed variation, unchanged
short-run recall, worse singleton omissions and a large uniform deficit does not
establish a better AI. Selecting seed 29 would be a selection effect prohibited
by the lock. Three seeds are too few to estimate training variability precisely.

Only 32 boundary pairs, repeated 256 times each, supported this intervention.
The perfect fitting ordering with weak development transfer is consistent with
memorization or fitting-source specificity; it does not by itself prove either
mechanism. The engineering data gate was deliberately bounded, not evidence
that 32 pairs suffice statistically. Pair enrichment differs from PR69, so poorer
absolute 10% performance versus PR69 cannot be attributed to the ranking term.
The within-seed matched comparison isolates that term for this schedule only.
Selection geometry explains much of coverage; inadequate transferable model
discrimination remains evident. Patient linkage, exhaustive near-duplicate
clearance, clinical event identity and temporal duration remain unresolved.
Galar 35/36 and all earlier results are unchanged contextual evidence, not pooled
new evaluation. Already-inspected 31/34/37 provide development outcomes, not
independent confirmation. No new untouched benchmark was consumed.

**Single next experiment:** a prespecified fitting-only examination-held-out
local-pair transfer test using these verified originals, with the held-out
examination removed from both background references and pair training. Compare
classification and the same fixed ranking objective on held-out pair ordering
and margin, using fixed paired seeds and budget. This directly tests whether the
training-margin benefit transfers between fitting examinations before spending
another complete-source benchmark cycle or acquiring more data. Do not tune
against 31/34/37 or claim patient independence. Freeze eligibility and the transfer
criterion before running it; it has not been executed in this experiment.

## Reproduction and private retention

Public scripts reproduce planning, input preparation, fixed training/scoring,
evaluation and an independent scalar outcome replay. Private inputs must be
provided by an authorized holder; public CI uses synthetic data only. The replay
imports neither production selectors nor the production evaluator and verifies
42 examination/budget/model records, 168 policy sets, 84 exact null expectations,
and all seed macro changes. A separately implemented model/preprocessing canary
checks 144 new-model predictions; maximum absolute score difference was zero.
Source-level independent checks verified 32 local boundaries and rehashed 63 pair
endpoints. These are independent implementations, not an external research team.

All six checkpoints and 18 vectors were retained and readback-verified before
outcome evaluation. The pre-outcome package is 13,899,293 bytes, SHA256
`4822bd2001490e6e2373f5ab3fe189ea76ea276d6336c440895869e202e36c8d`.
The 21-new-originals package is 4,879,916 bytes, SHA256
`50954e19e64f4102ea3a8022a8278fcd6d234f0f220f2d9e6231ef48d0ffae22`.
Private source packages, image/prediction records, membership, audit receipts and
checkpoints remain private. Public Git contains aggregates and reproducible code.
The large reconstructed sparse archive and image tensors are temporary caches;
no claim is made that a complete publisher archive was newly retained.
