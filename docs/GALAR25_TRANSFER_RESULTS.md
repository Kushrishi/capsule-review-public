# Galar 25 — fixed blood-CNN transfer: negative evidence across another examination

**Date:** November 2, 2026. **Decision: NO MODEL PROMOTION.** All three pretrained/fitted CNN checkpoints rank the 14 blood-labelled reference images poorly, including the expanded model that previously ranked strongly on examination 29. These are **fitting-pool development** observations, not independent patient/clinical validation.

## What was locked before new-image scoring

The [fixed Galar-25 transfer specification](GALAR_25_TRANSFER_SPEC.json) was committed **before acquiring any examination-25 pixels**. Three existing **unchanged** checkpoints (original CNN, continued original-only CNN, expanded-data continued CNN) were already trained without examination 25. No retraining, checkpoint selection, data-dependent threshold, changed preprocessing or review-budget optimization occurred. Galar exam 25 was selected as an acquisition candidate after its **training-pool annotation counts** had already been inspected, so this is **not a blind test**.

**Primary analysis:** 512 chronologically uniform, *label-blind* source-image positions from Galar examination **25**, with exactly **14** corrected `blood=1` annotations. Each 10% method chooses exactly **51** of the **same 512** images. The full 5–100% workload curve is reported. All metrics refer to *sparse annotated images*, not physician-adjudicated lesions or human reading-time savings.

## Comparison with previously examined fitting-pool case 29

| Reference examination | Explicit positives / 512 | Original CNN AUC | Original-only continued AUC | Expanded continued AUC |
|---|---:|---:|---:|---:|
| 29 (previously evaluated) | 122 | 0.859 | 0.834 | 0.882 |
| **25 (new here)** | **14** | **0.305** | **0.230** | **0.429** |

**These are two selected fitting-pool examination IDs, not independently verified patients or an unbiased prospective test.** The dramatic reversal is hypothesis-generating evidence of between-examination heterogeneity, not a population effect size; with only 14 positive reference images in exam25, exam-wise metrics are particularly fragile. The three model weights were identical between both comparisons.

## Primary observed result — no reliable transfer

| Method | ROC-AUC | Average precision | Top-51 positive hits |
|---|---:|---:|---:|
| Original CNN | 0.305 | 0.022 | 0 |
| Original-only continued | 0.230 | 0.025 | 2 |
| Expanded-data continued | 0.429 | 0.024 | 0 |
| Fixed redness | 0.167 | 0.016 | 0 |
| Uniform positional sampling | — | — | 1 |

**Interpretation:** all learned models have within-examination ROC-AUC **below 0.5**, and the expanded candidate retrieves **0** blood-positive reference images at 5% and 10%. The original-only continued model finds 2 at 10%, while deterministic uniform sampling finds 1. The slight ordering advantage of expanded by ROC-AUC is **not** a clinically useful operating-point result. With only 14 positives, all per-study estimates are unstable; we neither rescue the result by selecting a different operating point nor treat these outcomes as patient-independent evidence.

### Complete fixed reference workload curve

Each cell is the number of the **14** blood-positive reference images retrieved. A 10% review budget is a research operating point, **not a project or product constraint**.

| Budget | Source images reviewed | Original CNN | Original-only continued | Expanded continued | Redness | Uniform |
|---|---:|---:|---:|---:|---:|---:|
| 5% | 25 | 0 | 2 | 0 | 0 | 1 |
| 10% | 51 | 0 | 2 | 0 | 0 | 1 |
| 25% | 128 | 3 | 2 | 2 | 0 | 4 |
| 50% | 256 | 3 | 3 | 3 | 1 | 6 |
| 75% | 384 | 6 | 4 | 14 | 6 | 11 |
| 100% | 512 | 14 | 14 | 14 | 14 | 14 |

## Intentional pathology enrichment changes the apparent result

The secondary union of 1,013 images contains **265** blood-positive annotations, but those images were **deliberately selected** to represent positive runs in fitting data. They are **not** an unbiased exam sample, and their prevalence and AP are not population estimates.

| Method | ROC-AUC on enriched union | Average precision on enriched union |
|---|---:|---:|
| Original CNN | 0.693 | 0.389 |
| Original-only continued | 0.687 | 0.438 |
| Expanded-data continued | 0.605 | 0.334 |
| Fixed redness | 0.524 | 0.295 |

The original CNN's enriched-union ROC-AUC (~0.693) differs greatly from its **0.305** ranking on the label-blind reference. This contrast is a practical warning against evaluating pathology triage on positive-enriched convenience images.

## Real source acquisition and verification

The original Galar v2 (CC BY 4.0; Le Floch et al.) Figshare file **45258019** has a 31.99-GB original source archive. Examination 25's source frames span 7-Zip solid blocks 2, 3 and 4. A [bounded, staged GitHub Actions run](https://github.com/Kushrishi/capsule-review/actions/runs/41490010283) verified and extracted one source block at a time, deleting the compressed bytes before obtaining the next block. Exact compressed source transfer total **10,447,872,590 bytes**:

- Block **2**, offset **6,950,241,905**, length **3,470,070,406**, SHA-256 `793b010cd7ec383daabbafeb6852646cd791decbc31982976fb6ae64adb0fd34`, selected PNGs **98**.
- Block **3**, offset **10,420,312,311**, length **3,539,043,971**, SHA-256 `bac9b407b67f3a50314c696a4639df68265fb398b1977a60ed61eb10648f79f5`, selected PNGs **657**.
- Block **4**, offset **13,959,356,282**, length **3,438,758,213**, SHA-256 `eba4364d8ae1d239f86f356db8f0c6120caa9e0c1603a588e0cf54a5d48abbac`, selected PNGs **258**.

The official full-archive MD5 **was not verified**, because the full 31.99-GB archive was not downloaded. The independently downloaded retained artifact contains **1,013** original PNGs, **307,936,304** original image bytes and **265** blood-positive annotations. It is the union of 512 enriched fitting selections and 512 label-blind references with 11 overlaps. All 53 positive annotation runs are represented within the enriched fitting selection, but **annotation runs are not clinically confirmed distinct lesions**.

Every image's original byte length/SHA-256, PNG structure, source-frame ID, role and ZIP CRC passed an independent check; there were **zero internal decoded-pixel duplicates** and **zero exact file-byte duplicates against 9,129 previously acquired Galar source images**. Source ZIP SHA-256: `968e2abfe41d3c0ea628197390672a310357f879c25fd86b0da14a30002e45ef`; private identity manifest SHA-256: `911ec81835f7b23fb99cdfaed8c6a55595692014cfeeae66ca0ea9f59c0bf35e`. Raw medical images and per-image labels are stored **privately** in the Capsule Review Library, not Git.

## Post-hoc error characterization — appearance shift, not a new tuned model

A private, source-verified contact sheet was inspected for all **14** positive label-blind frames plus six high-scoring `blood=0` frames; it remains in Capsule Review Library and is **not** committed. The observed errors motivate an appearance/domain-shift hypothesis, **not** a diagnosis or clinician-adjudicated explanation.

In examination **25**, the expanded CNN's median score on the **14** blood-positive reference images was **0.361**, *below* the **0.520** median on the 498 blood-negative-label images. On the previously examined exam **29**, the same unchanged model's corresponding medians were **0.730** (122 positive) and **0.123** (390 negative). The fixed redness scores also ranked exam-25 positives poorly: positive median **0.040** versus negative median **0.099**. These values describe **uncalibrated ranking scores**, not probabilities of disease; exam-25 low positive support makes interpretations unstable. The scores are traceable to the private, SHA-256-locked per-image prediction CSV and are disclosed as **post-hoc descriptive failure analysis** only. They must not guide model/checkpoint selection on examination 25.

## Reproduction and limitations

The new read-only evaluation code was validated first by reproducing the completed examination-29 experiment's exact ROC-AUC/AP and 10% budget hits. Subsequently the examination-25 evaluation was repeated on all 1,013 original images in the same deterministic CPU environment: **private prediction CSV and aggregate JSON bytes were exactly identical** between runs. Independent scikit-learn calculations reproduced all ROC-AUC/AP values and every 5/10/25/50/75/100% budget hit. Aggregate JSON SHA-256 `47fac3d2b6821eb7c8d044a074b01dd9ff9b0d73b778105aae46afe614399fff`; private prediction CSV SHA-256 `285d3b14ab0f9e2cf45f4a7ca51205623e5694a17db0d55b9ba421e3023029c7`. The original checkpoint bytes were not modified.

Clinical caution: these are sparse frames from **one fitting-candidate examination**, not consecutive pathology-annotated video, unique patient IDs, diagnosed lesions, clinician reading time, model calibration, or independent external clinical sensitivity. `blood=0` does not prove absence of other findings. The author-reserved 61–80 and previously assigned 11–20 holdouts have **not** been used.

**Next scientific gate:** reproduce fixed model comparisons across *more* distinct positive-bearing fitting examinations (exam 27 is eligible but has only four positive annotation runs), then lock an evaluation policy before using any genuinely reserved cohort. Do not retrofit current models based on examination 25 and then advertise it as new test performance. Preserve this negative finding and investigate acquisition/device/appearance shifts in fitting-only analysis if future failures persist.
