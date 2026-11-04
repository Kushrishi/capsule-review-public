# Locked Galar 11–20 annotation-run evaluation

**November 4, 2026. Completed research evaluation; no model promoted.**

The original CNN did **not demonstrate an improvement at the prespecified primary operating point**. At equal 10% review workload, score per bin averaged **49.35%** positive annotation-run recall versus **50.62%** for uniform: a paired examination-level difference of **−1.27 percentage points** across the six examinations with positive runs. It won in two, lost in two and tied in two. Four zero-positive examinations have undefined run recall and remain in the source/workload record.

This is prespecified examination-level evidence under an explicitly disclosed outcome-concealed eligibility amendment. It is not independent-patient or clinical validation, an adjudicated-lesion study, or a measured reading-time benefit.

## Source and pre-outcome integrity

- All **163,161 eligible original PNGs** were acquired privately from official Figshare file **44725302**, CRC/byte-hash/decode-verified, and aligned to all corrected binary-annotation rows. There were **zero missing eligible images** and no duplicate PNG bytes within an examination.
- All **12** solid blocks were required: **40,041,927,480 compressed bytes**, plus the previously verified index/header. The reconstructed complete archive matched publisher MD5 `fdc88663514f5691a14c08dff13c667e`. The PNGs total **48,757,425,342 bytes**.
- Examination 15’s inferred filename-grid gap has **no corrected annotation row**. The case remained included with **11,510** eligible images; the source gap was preserved. No image was interpolated and runs were not bridged across it.
- [Amendment A1](GALAR_ELIGIBILITY_AMENDMENT_20261104.md) and its synthetic-tested worker were committed at `1231f6113aa1ce9a56d398b914da3b7b0f2723f6` before corrected CSV processing. Raw cells entered transient worker memory, but only frame identifiers and binary-label availability were exposed; `0` and `1` mapped identically. **Do not describe this as CSV payloads remaining entirely unprocessed or as independent-human blinding.**
- The original checkpoint `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3` and original RGB/96×96 aspect-preserving preprocessing were reused. No training, tuning, calibration, checkpoint selection or policy change used 11–20 outcomes.
- All scores, source hashes and all four policies at **5/10/25/50/100%** were sealed and privately retained before analyst outcome access. Master SHA-256: `6944ce6348c76ee69ec06138aa10f926a0632710c089222dd7a765c803e90068`. [Immutable commitment](https://github.com/Kushrishi/capsule-review-public/commit/d9516cff6e296570bd6dbfc3a4b75139106c032e) and [server-timestamped record](https://github.com/Kushrishi/capsule-review-public/issues/24#issuecomment-6637642856) were read back before outcome release.
- Every original PNG and snapshot was rehashed/decoded/replayed after that commitment and **before the first outcome CSV read**. Only 11–20 outcomes were then read; authors’ **61–80 CSV payloads remain unopened**.
- A separate implementation reproduced all **200** examination × workload × policy combinations, including exact selections, run/image hits, run-length strata and ordinal omission/coverage metrics. The independent oracle passed 240 synthetic queue comparisons and three synthetic run cases before outcome access. Concurrent original-model scoring matched serial scoring bit-for-bit on generated inputs. Interrupted execution tasks were rerun with unchanged inputs/model before outcomes; exclusive-create guards prevented snapshot overwrites.

## Primary result: equal 10% workload

The cohort contains **1,742 blood-positive annotated images** in **154 annotation runs**. Each run is a maximal corrected `blood=1` stretch at a +5 source-index stride, not a confirmed distinct lesion. Exact K is the original integer half-up rule; all four policies select the same K within each examination.

| Exam | Eligible images | Positive images | Positive runs | K | Uniform runs hit | Score-bin runs hit | Difference, pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 24,351 | 34 | 9 | 2,435 | 4 | 3 | -11.11 |
| 12 | 17,744 | 30 | 3 | 1,774 | 1 | 1 | +0.00 |
| 13 | 4,056 | 0 | 0 | 406 | 0 | 0 | Undefined |
| 14 | 5,375 | 0 | 0 | 538 | 0 | 0 | Undefined |
| 15 | 11,510 | 196 | 7 | 1,151 | 3 | 4 | +14.29 |
| 16 | 17,451 | 0 | 0 | 1,745 | 0 | 0 | Undefined |
| 17 | 27,747 | 150 | 8 | 2,775 | 6 | 5 | -12.50 |
| 18 | 12,044 | 0 | 0 | 1,204 | 0 | 0 | Undefined |
| 19 | 29,384 | 601 | 11 | 2,938 | 8 | 8 | +0.00 |
| 20 | 13,499 | 731 | 116 | 1,350 | 41 | 43 | +1.72 |

The prespecified mean uses the six defined examination-level paired differences. Zero-positive cases **13, 14, 16 and 18** are reported as undefined, not zero recall or excluded source failures. Their complete technical outputs remain in the [aggregate](../experiments/galar-unseen-11-20-20261104/aggregate.json). Zero blood-positive annotations do not establish normal anatomy.

| Policy at 10% | Mean recall, six defined exams | Pooled runs hit / 154 | Positive images hit / 1,742 | Worst omitted imported-position span across ten exams |
| --- | ---: | ---: | ---: | ---: |
| Uniform | 50.62% | 63 | 170 | 10 |
| Highest score | 24.74% | 28 | 305 | 9,129 |
| Score + separation | 43.30% | 62 | 199 | 3,566 |
| Score per bin | 49.35% | 64 | 174 | 18 |

Every policy reviewed **16,316 images** across the ten examinations. Highest-score ranking reached more positive images but fewer distinct runs than uniform, including **zero** positive runs on examinations **11 and 17** at this workload. Frame hits therefore cannot substitute for run retrieval. Imported-position spans are not elapsed time or clinical safety estimates.

Score-bin reached **64** pooled runs versus **63** for uniform. Examination 20 contributes **116 of 154** reference runs, so the prespecified equally weighted examination-level mean remains the primary result. Its leave-one-defined-examination-out mean differences range from **−4.38 to +0.98 pp**; this is descriptive heterogeneity, not a confidence interval or evidence of patient independence.

## Prespecified secondary workloads

| Workload | Total images reviewed per policy | Uniform mean run recall | Score-bin mean run recall | Score-bin minus uniform, pp |
| --- | ---: | ---: | ---: | ---: |
| 5% | 8,159 | 42.36% | 42.45% | +0.09 |
| 10% | 16,316 | 50.62% | 49.35% | -1.27 |
| 25% | 40,792 | 72.16% | 81.67% | +9.51 |
| 50% | 81,583 | 88.77% | 90.09% | +1.32 |
| 100% | 163,161 | 100.00% | 100.00% | +0.00 |

All four policies at every workload are retained in the aggregate. The higher descriptive score-bin recall at 25% is a prespecified **secondary** finding and does not replace the negative 10% primary result. Queues are recomputed at each K and are not necessarily nested. At 100%, every policy reaches all 154 source runs and 1,742 positive images; this is an input/accounting check. The application supports arbitrary exact K, including all imported images; 10% is not a product cap.

At 10%, pooled source-run length support and retrieval were:

| Annotated rows per run | Source runs | Uniform hits | Highest-score hits | Score + separation hits | Score-bin hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1-5 | 108 | 21 | 14 | 30 | 28 |
| 6-25 | 33 | 29 | 8 | 21 | 23 |
| 26+ | 13 | 13 | 6 | 11 | 13 |

## Every worse-than-uniform case

The table lists examinations with fewer distinct positive runs reached than equal-K uniform. Exact counts/differences for each failure are in `worse_than_uniform` in the aggregate.

| Workload | Highest score | Score + separation | Score per bin |
| --- | --- | --- | --- |
| 5% | 11, 12, 15, 17, 19, 20 | 12, 17 | 12, 20 |
| 10% | 11, 17, 19, 20 | 11, 17 | 11, 17 |
| 25% | 11, 12, 17, 19, 20 | 11, 12, 17 | 17, 20 |
| 50% | 12, 17, 19 | 17 | 15 |
| 100% | None | None | None |

## Reproducibility and limits

The [non-identifying aggregate](../experiments/galar-unseen-11-20-20261104/aggregate.json), [pre-outcome commitment](../experiments/galar-unseen-11-20-20261104/prelabel_commitment.json), original JSON lock, amendment, production selector and synthetic tests are public. Original images, corrected per-frame records, checkpoint, per-frame scores and complete execution proofs remain private. A separate durable full image archive could not be retained; the official pinned source and private hashes permit reacquisition. The retained original model/pre-outcome package permits authorized replay.

The pure accounting module’s `*_verified_by_this_module=false` fields refer to that module alone; the separate end-to-end source gates above performed the byte/checkpoint/ZIP validation. Original frozen protocol/model metadata retain their historical initial status; this report records completed execution.

Patient independence and cross-patient generalization are unverified. Runs are not adjudicated lesions; reference annotations are not clinical truth; ordinal gaps are not time. No human-reader sensitivity, actual clinician-time benefit, diagnostic validity, novelty or publication readiness is established. Four zero-positive cases and only six defined paired observations limit interpretation. No model is promoted. The earlier sparse-reference results and negative findings remain unchanged.
