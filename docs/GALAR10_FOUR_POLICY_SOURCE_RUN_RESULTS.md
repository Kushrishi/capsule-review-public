# Capsule Review — Real Galar10 evidence-diversity audit

**November 3, 2026 · Retrospective scientific engineering result · Not clinical validation**

## Research question

Can an AI-assisted review queue retain **more distinct original blood-positive annotation stretches** at the same review workload? Counting more positive images is not the same as finding more separate evidence stretches.

## Input verification

This case uses **Galar10**, an already examined development case. A prior private corrected-annotation packet and archived original-CNN score stream were rehashed; 512 sorted reference-score rows matched source frame IDs and binary blood labels. The source file contains **9,745 corrected annotation rows**, **3,983 annotated blood-positive rows** and **41 separate blood-positive annotation runs**. Only **31 of those 41 runs** are represented by any of the saved 512 reference images.

Two separately implemented fixed selection algorithms reproduced every image/run count and imported-position coverage statistic across **24 policy × workload comparisons**. The original CNN and uniform outcomes also reconcile with the previously published independent Galar source-run audit at **all six workloads**.

**Terminology:** a source-positive run is a maximal stretch of corrected source rows with `blood=1` and original source-frame index step exactly five. It is **not a pathologist-confirmed separate lesion, a distinct clinical event, diagnosis, or continuous video duration**.

## All six exact-K workloads

| K / 512 images | CNN score only (images / runs) | Score + separation | Score / chronology bin | Uniform baseline |
|---|---:|---:|---:|---:|
| 25 | 25 / **2** | 13 / **4** | 10 / **5** | 9 / **4** |
| 51 | 47 / **3** | 24 / **9** | 24 / **11** | 21 / **10** |
| 128 | 115 / **10** | 56 / **19** | 59 / **21** | 51 / **17** |
| 256 | 141 / **13** | 129 / **23** | 109 / **27** | 107 / **26** |
| 384 | 164 / **21** | 164 / **21** | 163 / **30** | 157 / **28** |
| 512 | 213 / **31** | 213 / **31** | 213 / **31** | 213 / **31** |

Each method chooses **exactly K** original reference images. No policy can retrieve a positive source run absent from all 512 reference images.

## The critical 10% finding

At **K=51**, the globally highest-CNN-score policy selects **47 positive images but reaches only 3 of 41** positive source annotation runs. In fact **44 of its 47 positive selected images (93.6%) come from one original positive annotation run**. Its maximum nearest-selected imported-position distance is 111 positions, versus five under uniform.

By contrast, the **chronology-bin** method selects 24 positive images spread across **11 positive annotation runs**, and uniform selects 21 across **10 runs**. The score + separation policy selects 24 across **9 runs**. The chronology-bin method's worst imported-position gap is nine; the score + separation method's is 25.

At **K=128 (25%)**, the top-score CNN reaches just **10** positive source runs; chronology-bin reaches **21**, score + separation reaches **19**, and uniform reaches **17**. At 100%, all four recover **31/41 (75.6%)**, the sparse-input ceiling. An apparent image-retention advantage for the CNN can therefore conceal substantial evidence-diversity loss.

## Engineering implication

The currently shipped **chronology-bin** policy is a sensible transparent *coverage-first default*, and this historical case explains why. It is **not** proof that the method generalizes better to other examinations or should be used for clinical triage. This case is not a held-out test; no patient independence, lesion sensitivity, physician reading time, or confidence interval is demonstrated.

The score + separation heuristic also degenerates into score-only behavior at high K when the ordinal suppression radius becomes zero (here K=384). This is a documented algorithm property, not a reason to retroactively tune the policy against an inspected case.

## Data limitations and next evidence gate

The original whole publisher-corrected ZIP could **not** be reacquired in this run. The saved original-source label copy and score records passed exact saved-file hash checks and multiple historical result reconciliations, but the six-examination four-policy extension remains **gated** until the exact publisher archive is available. Reserved independent examination groups remain unopened, and no new pathology model has been promoted.

The useful next step is to evaluate the frozen four-policy algorithm against **denser original imagery** and an untouched examination-separated cohort, with source annotation-run retrieval as the primary endpoint. Do not substitute image count, inspection of sparse samples, or new metrics selected after seeing results.

**Reproducibility:** The private original-label and score inputs, the complete Python replay, an independently written verifier and exact hashed aggregate are preserved in the user's private Capsule Review Library. The accompanying JSON is a non-identifying derivative safe for sharing after review.