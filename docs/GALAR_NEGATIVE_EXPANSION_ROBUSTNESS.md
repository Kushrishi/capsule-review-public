# Negative-training expansion: examination-level robustness audit

**November 3, 2026. Exploratory, post-hoc sensitivity analysis of already published aggregate data.** Not an independent experiment, confirmatory hypothesis test, validated patient-level confidence interval or medical-AI performance claim. This does **not** fit, retune, select, or promote any model.

## Question and source

The frozen [negative-examination fitting comparison](GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md) found that adding 1,024 source-verified, blood-negative-labelled images from fitting-only Galar 22 and 24 changed high-support macro ROC-AUC from **0.68655 to 0.70776**. But the evaluated examinations had been inspected, some were difficult, and the mean can hide heterogeneous outcomes.

This audit recomputes uncertainty **from the public nonidentifying per-exam aggregate only**, [paired comparison](../experiments/galar-negative-expansion-cv-2026-11-02/paired_comparison.json). No original image, individual label, private source identity, per-image score or checkpoint is downloaded/read. The training folds, original model results and evaluation cohort remain unchanged.

Only the previously specified six examinations with **at least ten positive-labelled reference images** are used for the AUC sensitivity analysis: 1, 7, 25, 27, 29 and 30. Each contains 512 label-blind reference images. They are treated as six observed examination summaries, **not six proven independent patients**.

## Recomputed descriptive findings

| Measure | Result |
| --- | ---: |
| Original pooled CNN macro ROC-AUC (six exams) | 0.68655 |
| Expanded pooled CNN macro ROC-AUC (same exams) | 0.70776 |
| Mean paired change | **+0.02121** |
| Examinations with positive paired change | **5/6** |
| Smallest / largest examination-level change | **−0.02774 / +0.05852** |
| Exhaustive 6^6 examination-resampling draws | **46,656** |
| Descriptive 2.5th to 97.5th percentile of resampled mean changes | **−0.00269 to +0.04415** |
| Leave-one-examination-out means | +0.01375 to +0.03100 |
| Leave-one-fitting-fold-out means | +0.01397 to +0.04140 |
| Top-51 positive-labelled image hits across all 14 held-out exams, original → expanded | **151 → 153** |
| Top-51 positive-labelled image hits on hard exams 23 and 25 | **0 → 0, both exams** |

The six paired changes, in order 1/7/25/27/29/30, were **−0.02774, +0.05281, +0.05852, +0.00142, +0.02940, +0.01286**. The benefit is not universal; examination 1 deteriorated. The mean improvement is small compared with examination-to-examination variation, and the resampled interval includes zero.

The **K=51** comparison is a *fixed experimental workload* of 51 selected images out of 512 label-blind reference candidates per examined case. It is not an application limitation, not actual reading time, not selected distinct lesions, and not full-source annotation-run sensitivity.

## Exactly how the resampling works

We enumerate every ordered six-draw sequence drawn *with replacement* from the **six paired examination-level AUC differences**, equally weighted; there are exactly 6^6 = 46,656 combinations. For each draw, the arithmetic mean of the six differences is recorded. The interval reports the linearly interpolated empirical percentiles at 0.025 and 0.975, with **no Monte Carlo randomness**. We also recalculate the mean after dropping each individual examination and, separately, after dropping all high-support examinations belonging to each **pre-existing CNN-fitting fold** (A: 1/27/29, B: 25/30, C: 7).

This examination bootstrap is a **descriptive stress test only**. Its usual statistical interpretation would require sampling/exchangeability assumptions not demonstrated here. Examinations share three fitted fold models, so outcomes are not independent even if patients were; there are only **three training folds**, too few for a reliable fold-cluster interval. The protocol, cohort and model development were already explored, and neither the bootstrap interval nor the leave-out ranges may be marketed as a prospective, patient-level or clinical confidence interval. Bootstrap resampling does not create new examinations.

## Decision

**No model promotion.** Preserve both the modest average improvement and the failure cases. The next scientific step is a sufficiently diverse and independently locked evaluation with verified source identities and a coverage endpoint based on directly selected annotated image/run evidence. Do not optimize from this post-hoc analysis against held-out studies, presume source-positive runs equal distinct lesions, or treat blood=0 as clinically normal. Galar 11–20 and the authors' 61–80 remain unopened.

## Reproduce without private inputs

From the repository root, run:

    python scripts/analyze_galar_negative_expansion_robustness.py
    python -m pytest -q tests/test_galar_negative_expansion_robustness.py

To save the aggregate to a new local file, add --output /path/to/new-result.json. The CLI refuses overwrites, refuses changed evaluation examination IDs, requires exact paired metric agreement, and rejects any file larger than 256 KiB. The result contains only previously public examination-level counts/differences and method metadata.

Source: corrected Galar v2, Le Floch et al., *Scientific Data* (2025); dataset licence CC BY 4.0. This is a reproducibility/interpretation addendum, not a new clinical evaluation.
