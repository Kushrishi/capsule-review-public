# Blood-CNN examination-separated training-only comparison

**November 2, 2026. Status: completed, independently replayed, exploratory. Scientific decision: no model promotion.**

## Question

The prior compact blood CNN and fixed continued-training candidates performed inconsistently between Galar examinations, notably 23 and 25. A previous source-verified 4,608-image experiment demonstrated that simply increasing the image candidate pool did not rescue an untrained redness ranking.

This experiment asks whether **sampling examinations and positive/negative classes more evenly, with fixed modest photometric augmentation**, improves examination-level transfer compared with ordinary pooled weighted training. It is a **two-component training recipe comparison**, not an isolated test of augmentation alone.

The immutable [methodology](GALAR_EXAM_CV_SPEC.json) was committed at [`cc93ec3`](https://github.com/Kushrishi/capsule-review/commit/cc93ec3704c3117ebbb3de3084c97b2e7b6524aa) **before new optimization**. Existing image labels, former development outcomes and the earlier exam23/25 failures had already been examined. This is not newly blinded independent validation or preregistration.

## Exact source, separation and computation

All **10,123 original source PNGs**, across 14 fitting examinations **1–8, 21, 23, 25, 27, 29, 30**, were reconstructed from ten previously verified private source archives, with original outer ZIP SHA-256 and **each individual original image SHA-256, byte length, PNG decode and source ID** checked. All original 1–8 images follow the unchanged historical blood-pilot manifest (SHA-256 `0f1cec23f43023788428c0fa694f6f00f42b367fd2ed2f539b97a57443080f59`). Six additional source examination packages have separately verified manifests and original source-image hashes. The **1,663 explicit `blood=1` images** include intentionally pathology-enriched fitting images from the new examinations; pooled sample prevalence is not natural examination prevalence.

**Every examination was evaluated only in a fold where the entire examination was excluded from model fitting.** All held-out results use **exactly 512 source-chronological, label-blind reference images per examination** (14 × 512 = 7,168 unique evaluated reference positions per arm). Fitting uses all approved training images of the other examinations, including their fitting-enriched images; test labels never enter preprocessing, sampling or model fitting. The three frozen whole-examination held-out folds:

| Fold | Held-out examination IDs |
| --- | --- |
| A | 1, 3, 21, 27, 29 |
| B | 2, 5, 23, 25, 30 |
| C | 4, 6, 7, 8 |

Models use the *same unchanged compact `AnatomyCNN(2)` architecture*, freshly initialized from fixed seed 37 for **each arm and each fold**, with original 96×96 aspect-preserving padded RGB preprocessing. We did **not** initialize from the historically fitted CNN: that would leak information into original fitting examinations now used as held-out cases. Both arms use exactly **384 AdamW updates, batch size 32, learning rate 0.0002, weight decay 0.0001** and select the final checkpoint; no model/epoch/threshold search or early stopping.

- **Pooled weighted:** uniform sampling with replacement across all permitted fitting images and training-only inverse-frequency class-weighted cross entropy; no augmentation.
- **Examination-balanced plus jitter:** sample fitting examinations uniformly, then classes 50/50 when both labels exist (blood-negative-only exams stay negative). Use unweighted cross entropy and pre-fixed per-image brightness/saturation multipliers in [0.75, 1.25], applied **only in training**.

All three entirely blood-negative-labelled fitting examinations **3, 5 and 8** are represented as whole held-out cases in the designated folds. No examination 9–10 or reserved Galar 11–20 or original authors' 61–80 was used for training or evaluation. Distinct study identifiers **do not establish unique patients**.

## Full held-out results

Each examination has 512 *label-blind* reference frames. The AUC values refer to explicitly annotated blood-positive versus blood-negative frames, **not physician-adjudicated lesions**. Positive support of 1–6 images makes many individual ROC-AUC and AP values highly unstable; negative-only examination ROC-AUC is **undefined** rather than zero or one.

| Exam | Positive / 512 | Pooled AUC | Balanced+jitter AUC | Pooled blood hits at 51 | Balanced blood hits at 51 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 22 | 0.635 | 0.218 | 3 | 0 |
| 2 | 1 | 0.153 | 0.229 | 0 | 0 |
| 3 | 0 | — | — | 0 | 0 |
| 4 | 2 | 0.817 | 0.545 | 0 | 0 |
| 5 | 0 | — | — | 0 | 0 |
| 6 | 6 | 0.514 | 0.130 | 0 | 0 |
| 7 | 208 | 0.827 | 0.803 | 48 | 50 |
| 8 | 0 | — | — | 0 | 0 |
| 21 | 1 | 0.945 | 0.033 | 1 | 0 |
| **23** | **4** | **0.417** | **0.292** | **0** | **0** |
| **25** | **14** | **0.166** | **0.095** | **0** | **0** |
| 27 | 26 | 0.981 | 0.445 | 24 | 2 |
| 29 | 122 | 0.768 | 0.681 | 40 | 12 |
| 30 | 120 | 0.742 | 0.533 | 35 | 18 |

The **six examinations with at least ten positive reference frames** (1, 7, 25, 27, 29, 30) had descriptive **macro ROC-AUC 0.687 for pooled versus 0.463 for balanced+jitter**. Including all eleven blood-positive exams, with many tiny numerators, yields **0.633 versus 0.364**. Mean examination-level average precision across the eleven positive examinations was **0.270 versus 0.140**. These are not estimated performance on an unselected population or evidence of a robust patient-generalization advantage. The cases and candidate recipes were chosen with earlier results known.

At exactly **51 selected frames per examination** (14×51 = 714 review selections, including 153 forced `blood=0` selections in the three negative-only studies), pooled CNN selected **151 blood-positive images** versus **82** for the balanced+jitter CNN and **50** for deterministic uniform selection. At K=128: **286 / 197 / 130**; at K=256: **398 / 331 / 265**. At K=512 all inspect all 526 reference-positive frames, so the 100% ceiling is identical. These are **positive images, not unique clinical lesions or original positive annotation runs**.

The pooled model improves over balanced+jitter in all six higher-support held-out examinations by ROC-AUC, but **does not solve the most consequential negative-transfer cases**. In examination 25, pooled ROC-AUC is **0.166** and zero positive images appear among the top 51; in exam23, ROC-AUC is **0.417** and top-51 is also zero. It would be scientifically incorrect to call either candidate reliable, calibrated or ready to replace the application's existing research suggestions.

## Independent numeric replay and provenance

The experiment was run on CPU float32 with deterministic PyTorch, two threads, fixed seeds, no tuning from held-out outcomes. The full output SHA-256 is **`1c06c72f97bf67c5d51f24d32c93213743b1fec484a01441a5ba107c7653608f`**. The source-image metadata fingerprint is **`78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2`**.

A **separate checkpoint loader and independently implemented inference loop** reloaded all six actual training checkpoints and replayed all **14,336 held-out class-1 scores** with **maximum absolute difference 0.0**. All **112** examination × arm × fixed-review-K comparisons and examination-level ROC-AUC/AP calculations reproduced. The verification receipt's SHA-256 is **`1216a89951be6ae3f002569d3575f244b77fa9bca5f20ddeb18abe51fa61fc88`**.

The actual script run at training time is preserved privately with exact SHA-256 **`6b19c0c372fbf2b9cb9f792f44047616636d0fc95fa41e1d6ef328c398905adc`**. The [repository implementation](../scripts/galar_exam_cv.py) differs only by an environment-configurable data root and removal of a redundant overwritten constant, not by its algorithm. The original exact script, six checkpoints, private per-frame predictions, private source roles, complete aggregate and independent replay live in **Capsule Review Library / Examination CV 2026-11-02**; the private bundle SHA-256 is **`a927ff8253476da8b691f9bc7025ec9a76845edbb3f11efb06798eb658c8da9d`**. The public [nonidentifying full per-examination aggregate](../experiments/galar-exam-cv-2026-11-02/aggregate.json) contains all outcomes, including negative cases and unfavorable budgets. No original medical images, individual frame labels/scores, source identities or trained weights enter Git.

**Scientific decision:** retain this as a meaningful controlled *negative* result for the examined balancing-plus-photometric-jitter recipe. Neither candidate should be promoted. Future experiments should increase genuine negative-examination and positive-examination diversity, investigate model features more broadly than a compact from-scratch CNN, and lock a completely separate evaluation before opening a new cohort. A review-budget percentage is not a product constraint. No clinical lesion sensitivity, physician reading-time benefit, patient independence, source capture timing or full-video evidence preservation was established.
