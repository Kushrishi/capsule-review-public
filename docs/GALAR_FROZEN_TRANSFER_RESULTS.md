# Original blood CNN: frozen transfer to new Galar fitting examinations

**Date:** 2 November 2026. **Scientific role:** descriptive, post-acquisition examination-separated *training-candidate* transfer. **Decision:** retain unchanged original CNN as an exploratory baseline; **do not promote or optimize it on these examined results.** Galar source is CC BY 4.0 (Le Floch et al.).

## What was frozen before scoring

The protocol [`GALAR_FROZEN_TRANSFER_SPEC.json`](GALAR_FROZEN_TRANSFER_SPEC.json) was committed at [`8b56abc`](https://github.com/Kushrishi/capsule-review/commit/8b56abc7e67e261df2d4cf1b2ff9ece231b03a41) **before the first new score computation** (later merged via PR #17). The original `capsule-cnn-v1` blood checkpoint, SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, had been trained on examinations **1–8** and selected using already inspected historical development **9–10**. No training, checkpoint selection, architecture adjustment, calibration or hyperparameter search was performed here.

The comparison evaluated exactly **512 label-blind source-chronological reference positions in each of exams 21, 23 and 30**, using the original full-field 96x96 aspect-preserving padded RGB preprocessing, a fixed untrained redness heuristic (which uses an ImageOps centre crop), and label-blind uniform selection. These imaging studies were selected for *fitting-cohort acquisition* after their blood labels had been inspected; this is **not a prospective, patient-independent or blinded test**. The experimental unit remains examination (unique patients cannot be confirmed).

## Primary results — label-blind reference frames

| Examination | Positives | CNN ROC-AUC | CNN AP | Redness ROC-AUC | Redness AP | Blood hits at 10%: CNN / redness / uniform |
|---|---:|---:|---:|---:|---:|---:|
| 21 | 1/512 | 0.828 | 0.011 | 0.965 | 0.053 | 0 / 1 / 1 |
| 23 | 4/512 | 0.203 | 0.006 | 0.417 | 0.008 | 0 / 0 / 0 |
| 30 | 120/512 | 0.891 | 0.732 | 0.726 | 0.431 | 40 / 28 / 13 |

At 10%, each method selects **51 of the same 512 reference frames** per examination. A blood-positive frame is **not a distinct lesion**. With only **one** positive reference image in exam 21 and **four** in exam 23, ROC-AUC/AP and budgeted hits are highly unstable. Exam 23 is a *negative transfer observation* for both the CNN and the red-excess heuristic; it must not be hidden by pooled metrics. Exam 30 has markedly better within-exam CNN ranking, but that does not establish clinical sensitivity or reader-time benefit.

### Full reference workload curve

Each cell shows **blood-positive reference images selected** in the order **CNN / redness / uniform**, at the same frame budget. All budgets up to 100% are included; **10% is not a limit on the product or project**.

| Review budget | Per-exam images | Exam 21 CNN / red / uniform | Exam 23 CNN / red / uniform | Exam 30 CNN / red / uniform |
|---|---:|---:|---:|---:|
| 5% | 25 | 0 / 1 / 0 | 0 / 0 / 0 | 21 / 13 / 7 |
| 10% | 51 | 0 / 1 / 1 | 0 / 0 / 0 | 40 / 28 / 13 |
| 25% | 128 | 1 / 1 / 0 | 0 / 0 / 1 | 91 / 55 / 28 |
| 50% | 256 | 1 / 1 / 1 | 0 / 2 / 1 | 108 / 86 / 62 |
| 75% | 384 | 1 / 1 / 1 | 1 / 3 / 4 | 118 / 114 / 91 |
| 100% | 512 | 1 / 1 / 1 | 4 / 4 / 4 | 120 / 120 / 120 |

### What the pooled results can and cannot say

The 1,536 label-blind reference images contain **125 blood-positive annotations** (1 + 4 + 120). Combined CNN ROC-AUC / average precision are **0.871 / 0.487** and redness **0.496 / 0.089**. These pooled statistics are confounded by very different *between-examination positive prevalences* and possible score shifts. They must **not** be advertised as external discrimination estimates. The three examination-level comparisons above are the principal findings.

## Secondary — intentionally pathology-enriched selection

For completeness, the **3,000-image union** (512 enriched plus 512 label-blind reference images in each exam, minus overlap) contains **514** explicitly blood-positive annotations. CNN pooled ROC-AUC / AP are **0.695 / 0.459** versus redness **0.470 / 0.155**. Because the acquisition deliberately selected blood-positive rows, **neither AP, apparent prevalence nor positive-image retrieval is representative of natural case mix**. This secondary analysis is descriptive only.

## Provenance and independent checks

- Each of **3,000** original PNGs was rechecked against its frozen private source-file SHA-256, correct source-frame ID and byte length; **no exact decoded-image duplicates** were found against the original 1–10 image cohort or across the three newly acquired examinations.
- Private original model weights remained byte-identical to the frozen pilot (`f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`).
- All **1,024 original historical development predictions** were independently replayed on the saved real images: maximum absolute CNN score error **4.99e-10**; historical ROC-AUC and AP reproduced at **0.726189** and **0.622538**.
- All **3,000 new scores** reproduced exactly in a separate CPU inference pass (maximum absolute score difference **0.0**); independently computed scikit-learn ROC-AUC/AP and all **six review budgets** agree with the committed aggregate.
- Original scores are archived **privately**, alongside image identities, source manifests and provenance. No medical images, per-image scores/labels, private manifest or model weights are committed to GitHub. Public machine-readable data are in [`../experiments/galar-frozen-transfer-2026-11-02/aggregate.json`](../experiments/galar-frozen-transfer-2026-11-02/aggregate.json) and [`../experiments/galar-frozen-transfer-2026-11-02/verification.json`](../experiments/galar-frozen-transfer-2026-11-02/verification.json).

## Research interpretation and decision

**We have evidence of examination-dependent transfer, not universal model improvement.** The CNN's strong results on exam 30 do not cancel out its low rankings on exam 23. Exam 21 and 23 have too few reference positives to support robust generalization estimates. Neither this sparse sample nor the positive-label runs identify independent physician-adjudicated lesions or complete video intervals, so no lesion sensitivity, diagnostic accuracy, population performance or review-time savings is claimed.

**Next scientific action:** use *training-only* examination-held-out fitting to investigate generalization with additional pathology-positive studies while preserving these exploratory negative results. Prefer diverse positive-bearing source examinations such as 25, 27 and 29; prespecify the training/validation protocol before fitting, and keep the previously reserved **11–20** and original author **61–80** groups unopened. Do not tune the existing CNN against these 21/23/30 transfer outcomes and call a later comparison independent.
