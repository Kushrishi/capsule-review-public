# Examination-excluded adaptation: fixed development comparison

**2026-11-04 · Exploratory, previously inspected data · No model promotion**

## The experiment

The original fitted Galar blood CNN was used to initialize two matched continued-training arms. For each evaluated examination among **23, 25 and 27**, fitting used the **4,096** previously verified Galar 1–8 training images plus **512 uniform-reference images from each of the other two** development examinations. Exactly **5,120 training images** per fold, 2 epochs, batch 64, AdamW at 0.0001, identical initialization and training order. The experimental difference was photometric augmentation (brightness, contrast, saturation) on the training input only.

All **5,632 unique original image inputs** across the source fitting and development reference pools were verified against saved SHA-256 identities. Original-model scores on all three evaluation examinations were reproduced with maximum absolute error below 0.000003. The candidate models were frozen before their own fold's evaluation, but the cases had been studied previously; this is **not untouched or patient-independent evaluation**.

The locked Galar 11–20 experiment was not reused. The original researchers' 61–80 holdout was not opened. All model checkpoints, individual source-frame labels and per-image predictions remain private.

## Actual image-level ranking results

| Excluded examination | Original ROC-AUC | No-augmentation continuation | Photometric continuation |
| --- | ---: | ---: | ---: |
| 23 (4 positives / 512) | 0.203 | 0.320 | 0.402 |
| 25 (14 positives / 512) | **0.305** | 0.280 | 0.218 |
| 27 (26 positives / 512) | **0.970** | 0.939 | 0.957 |
| Equal-examination mean | 0.492 | 0.513 | 0.526 |

At exactly **51** selected images per examination, positive-image hits were **22** total for the original model, **23** for no-augmentation continuation, and **22** for the photometric continuation. Mean examination average precision fell from **0.298** (original) to **0.288** (no augmentation) and **0.285** (photometric). With augmentation, ROC-AUC improved in only **one of three** examinations. Exam 23 still had **zero top-51 hits** under all methods.

The 25%/50% fixed-K positive-image retrieval results and full-precision case metrics are in [the public nonidentifying aggregate](../experiments/galar-exam-excluded-adaptation-20261104/aggregate.json). Reconcile every published comparison using `python scripts/audit_exam_excluded_adaptation.py`, which requires no private images or model weights.

## Interpretation and decision

**Neither adaptation is an established improvement. Do not promote either model.** The small macro ROC-AUC rise does not demonstrate consistent examination benefit, positive-image enrichment at the 10% workload, or better annotated-event preservation. These three small, previously inspected, possibly patient-dependent sparse reference samples cannot support clinical sensitivity, full-video run recall or confidence claims.

This result strengthens the evidence that **photometric augmentation and brief continuation alone do not solve examination/domain generalization**. The fitting positives remain concentrated in the original examination 7, and the newly supplied positive examples are few. A scientifically stronger next study requires greater diversity of original positive examinations, fixed examination/patient grouping and a new independent qualified outcome cohort. An alternative architecture or representation should first be compared under the same held-out training-only protocol, not selected using the completed 11–20 outcomes.

The fixed pre-analysis design, exact executed program, independent score-level replay and six private model checkpoints were retained in a checksum-verified, access-controlled research archive. The private archive contains **no source image pixels**; the original source archives are separate dependencies. No new clinical application capability or model was activated by this experiment.
