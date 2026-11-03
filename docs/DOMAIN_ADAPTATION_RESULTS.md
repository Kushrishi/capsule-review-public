# Galar blood domain-adaptation experiment — November 2, 2026

**Decision: retain the existing compact CNN as the better historical development baseline.** A fixed full-field, partly fine-tuned pretrained MobileNetV3-small candidate improved over the previous *frozen-feature* MobileNet probe on both deliberately selected training-only positive-bearing holdouts and on the previously explored development cases, but did not outperform the compact CNN or a redness heuristic consistently. This is **not** new independent examination/patient-level validation, dense video, lesion sensitivity, a diagnosis, or evidence of reduced physician review time.

## Why this experiment

The original Galar sparse-image fitting data include **4,096 images from examinations 1–8**, of which only **239** are explicitly `blood` positive. These are concentrated in examination 7 (**208** positive); examination 1 contributes 22 and examinations 2/4/6 contribute 1/2/6. The previously trained ImageNet-frozen feature probe achieved development ROC-AUC 0.635, compared with 0.726 from the original compact CNN. The next justified *engineering* attempt was limited, fixed-schedule supervised endoscopy adaptation, not an unlimited checkpoint search over the already-inspected cases.

The **frozen, pre-fit** specification is [`DOMAIN_ADAPTATION_SPEC.json`](DOMAIN_ADAPTATION_SPEC.json), SHA-256 `cbbf7f2724d5ca0ab03a676775fcb74556bd0a889af35124d9068b93e32d7f65`. It was committed to the private GitHub research branch **before** the first optimization step. Source manifest hash `4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb`; official ImageNet MobileNet weights SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.

## Exact method and examination isolation

- Early MobileNetV3-small visual layers frozen; final two feature blocks and a 576-to-1 classification head trained for **exactly three epochs**, 160×160 RGB full-field bicubic resize, deterministic ImageNet normalization, fixed AdamW rates and train-only loss weighting. No early stopping, checkpoint selection, augmentation sweep or changes prompted by evaluation outcomes.
- **Fold A:** train on examinations 2–8, evaluate only 1 (**22** positive / 512). **Fold B:** train on 1–6 and 8, evaluate only 7 (**208** positive / 512). The fold IDs were chosen using **training-cohort label support** (each has at least 20 positives); this is not unbiased all-examination cross-validation, and exams may not be independent patients.
- In each fold compare the fixed domain-adapted candidate with the official ImageNet-frozen feature logistic probe **refitted solely on the same fitting examinations** and a fixed, untrained red-excess image score. Uniform positional sampling is a fixed-budget workload comparator.
- Finally, refit the same three-epoch candidate on **all training examinations 1–8**; evaluate once on previously used **9–10** solely as a *historical* development comparison. Do not select a checkpoint or modify settings based on those results. The source authors' 61–80 holdout remains unopened.
- The comparison to the old frozen MobileNet is **not a single-variable ablation**: the new model uses full-image resizing rather than the frozen baseline's ImageNet centre crop. Any gain could reflect adaptation, cropping or their interaction.

## Held-out fitting-examination findings

| Held-out fitting exam | Positive blood frames | Fixed method | ROC-AUC | Average precision | Positives among top 51/512 |
| --- | ---: | --- | ---: | ---: | ---: |
| 1 | 22 | **Domain-adapted MobileNet** | 0.710 | 0.131 | 8 |
| 1 | 22 | Frozen MobileNet feature + refitted logistic | 0.600 | 0.079 | 5 |
| 1 | 22 | Untrained red excess | **0.827** | **0.226** | **11** |
| 7 | 208 | **Domain-adapted MobileNet** | **0.751** | **0.709** | **46** |
| 7 | 208 | Frozen MobileNet feature + refitted logistic | 0.741 | 0.674 | 43 |
| 7 | 208 | Untrained red excess | 0.558 | 0.474 | 24 |

With only **two deliberately selected positive-bearing examination holdouts**, these are descriptive comparisons, not a stable population estimate. Average precision changes with the dramatically different positive prevalences. For the same 10% sampled-frame budget, fixed uniform sampling would capture one of 22 positive images in exam 1 and 21 of 208 in exam 7; this benchmark does not estimate lesion or interval recall.

## Previously examined development cases: 9–10

| Method | Combined ROC-AUC | Combined average precision | Exam 10 ROC-AUC | Exam 10 AP | Exam 10 positives among top 51/512 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Original compact blood CNN** | **0.726** | **0.623** | **0.708** | **0.747** | **47** |
| Newly domain-adapted MobileNet | 0.686 | 0.475 | 0.687 | 0.692 | 44 |
| Prior frozen-feature MobileNet | 0.635 | 0.354 | 0.668 | 0.628 | 40 |
| Uniform source sampling | — | — | — | — | 21 |

All **213** positive development `blood` annotations come from examination 10; examination 9 has zero positives. Exam-9-only ROC-AUC and average precision are undefined. Review budgets of **5, 10, 25, 50, 75 and 100%** are included in the private full-results HTML; **10% is not a constraint** on the project. Any original-CNN 50/75/100% points in that report were computed *post hoc* from its unchanged saved scores; its frozen 5/10/25% metrics were independently matched first.

## Exact replay and actual application

- The frozen original manifest and actual image-file/pixel SHA-256 checks were enforced before fitting. The original weights and fit-only per-examination feature-cache receipts were independently validated.
- A separate verifier reconstructed each candidate from the official ImageNet backbone and its saved adapted final blocks. **All 2,048 saved candidate evaluation predictions** (512 + 512 + 1,024) were exactly reproduced after original-image rehashing (max probability deviation **0.0** in the same CPU environment). This checks numeric provenance, **not** medical validity.
- The final candidate was imported as **512 additional model suggestions** into a separate copy of the actual Galar examination-10 Capsule Review review, alongside 512 original CNN predictions and 512 previous MobileNet feature-probe predictions. It is a model **comparison**, not a promoted default. Original 512 source frames and reference labels, prior 1,024 predictions and reviewer-note rows were unchanged (SQLite identity/digest checks). A Playwright in-process browser test confirmed all three models visible, frame navigation and zero JS exceptions. This does **not** establish external browser-origin deployment security.
- The GitHub repository contains only this source, tests, fixed spec and aggregate record. **Medical image files, original manifests with per-image identifiers, official weights, trained checkpoints, saved per-image scores and research workspace DB remain in the separate private companion package/Library.**

## What needs to improve next

The limiting resource is **multiple pathology-positive training examinations and genuinely new examination-level data**, not an arbitrarily fixed 10% review budget. Keep this candidate, but do not call it superior without evaluation on new patients/exams and without stronger relevant baselines. For expanded Galar data, plan cloud storage, permitted acquisition and practical compute; the earlier 512 MiB limit is no longer the *scientific* definition of feasible research. Do not incur substantial unapproved transfer/compute costs. The authors' 61–80 designated holdout must not be silently used during development.

Source: [Le Floch et al., *Galar*, Scientific Data (2025)](https://doi.org/10.1038/s41597-025-05112-7). An explicit `blood=0` is **not** proof that an image contains no other pathology. Not intended for patient-care decisions.
