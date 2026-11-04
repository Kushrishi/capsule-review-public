# Matched pretrained representation probe — real-image development result

**2026-11-04 · Completed on three *previously inspected* Galar examinations.** This is **not** external validation, a patient-independent estimate, clinical model selection or a replacement for the original blood CNN. The source-complete Galar 11–20 negative primary study remains unchanged; the source authors' reserved 61–80 cases remain unopened.

## Question

Does an ImageNet-pretrained full-field image representation fix the unstable performance of Capsule Review's compact CNN when tested with the **same excluded examination and exactly matched fitting-only reference images**?

We used a previously source-SHA-verified **frozen MobileNetV3-Small** feature bank from November 2, not a newly downloaded or trained backbone. Original PNG verification and its **10,123 × 576** feature-bank fingerprint were checked before fitting. Exactly **5,632** source-chronological reference images from Galar **1–8, 23, 25, 27** were selected; the rest of the feature cache was excluded. Each of three probes was fitted on **5,120** images from Galar 1–8 plus the other two development cases and scored only the excluded **512-image** case.

The classifier was **one predefined** training-fold-only `StandardScaler` + L2 `LogisticRegression` (C=0.1, `class_weight='balanced'`, `lbfgs`, max 300 iterations), with **no parameter search, no backbone fine-tuning and no outcome-driven threshold**. All three fits converged without warnings (134, 132, 125 iterations). A separate saved-coefficient replay reconstructed all 1,536 held-out prediction scores to at most **0.00000023** absolute difference and independently reproduced each case's ROC-AUC, average precision and top-K hits.

The exact pre-analysis parameters were committed first: [pre-analysis design](MATCHED_PRETRAINED_PROBE_LOCK_20261104.md), commit `b9be0f9f`.

## Actual outcomes

**ROC-AUC** · higher is better, but not the same as early positive-image retrieval.

| Excluded examination | Original CNN¹ | CNN continued without augmentation² | CNN + photometric continuation² | Pretrained frozen MobileNetV3 probe² |
| --- | ---: | ---: | ---: | ---: |
| 23 (4 positives) | 0.203 | 0.320 | 0.402 | **0.593** |
| 25 (14 positives) | 0.305 | 0.280 | 0.218 | **0.647** |
| 27 (26 positives) | **0.970** | 0.939 | 0.957 | 0.591 |
| **Equal-examination mean** | 0.492 | 0.513 | 0.526 | **0.610** |

**Positive reference images found at exactly K=51 of 512 positions per examination:**

| Metric | Original CNN¹ | Continued, no augmentation² | Continued, photometric² | Pretrained probe² |
| --- | ---: | ---: | ---: | ---: |
| Exam 23 / 4 | 0 | 0 | 0 | 0 |
| Exam 25 / 14 | 0 | 2 | 1 | **7** |
| Exam 27 / 26 | **22** | 21 | 21 | 8 |
| **Total / 44** | **22** | **23** | **22** | **15** |
| Mean examination average precision | **0.298** | 0.288 | 0.285 | 0.169 |

¹ The original checkpoint was historically fitted on the **4,096 Galar 1–8 images only**. ² The two CNN continuation arms and the frozen-pretrained probe were fitted on the **same 5,120 reference images per fold**. Consequently the original is a frozen historical reference, **not a fourth model trained with the matched pool**. In addition, the MobileNetV3 embedding extractor uses 160×160 full-field bicubic preprocessing whereas the original CNN uses 96×96 padded images, so this does **not** isolate backbone architecture as the sole causal variable.

At K=128 the four methods retrieved 28, 26, 27 and **19** positives respectively; at K=256 they retrieved 29, 28, 31 and **26**. The pretrained method achieved higher mean AUC but much lower mean AP and worse top-K image retrieval. Case 25 improved strongly while case 27 deteriorated substantially. Exam 23 remains **zero hits at the most restrictive workload** for all four methods.

The same result at K=51 across these three previously inspected references does **not** demonstrate a change in complete source-video blood-run recall. A blood-positive sampled image need not be an independently adjudicated lesion. The distributions are enriched and case counts small; patient independence remains unverified.

## Decision

**Do not promote the pretrained probe or any of the two CNN continuations.** This experiment provides useful negative evidence against the hypothesis that substituting an off-the-shelf pretrained representation, by itself, solves the examination-shift and limited-budget review problem.

The strongest next model-development question is whether **greater diversity of expert-labeled positive examinations and a training objective closer to distinct evidence-interval retention** can improve both high-AUC and difficult cases *without* sacrificing early retrieval. That requires a documented, development-only cohort-design decision; new external event-level claims still require complete annotations and independent data. The previous Galar 10% negative primary result must never be retrospectively reinterpreted or tuned away.

## Reproducibility and privacy

- [Full public non-identifying aggregate](../experiments/galar-matched-pretrained-probe-20261104/aggregate.json) includes every examination and all four reference models, including losses.
- [Reproducible probe implementation](../scripts/matched_pretrained_probe.py) validates the original feature bank and prior CNN reference package, enforces examination exclusion and saves fitted coefficients/predictions to a **private, non-repository directory**. It does not contain the original medical data.
- [Synthetic isolation tests](../tests/test_matched_pretrained_probe_synthetic.py) and [aggregate regression tests](../tests/test_matched_pretrained_probe_record.py) run without the original clinical images.
- The **private** package contains all three fitted scalers/linear probes, 1,536 source-associated predictions, audit receipts and independent replay, with SHA256 verification. Its image-derived features and labels are **never** part of public GitHub.
- The archived feature cache, original pretrained weights provenance and previous private CNN comparison are separate provenance dependencies; the newly created archive is not a copy of the full source-image archive.

**No new Galar images were acquired, no 11–20 inference or evaluation repeated, and no 61–80 outcomes opened.** The reader-facing viewer continues to use generated demonstration scores unless users provide their own scored research frames. This candidate is not installed as a medical model.
