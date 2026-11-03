# Fixed-update blood CNN expansion — fitting-cohort examination 29

**Date:** November 2, 2026. **Decision:** retain all three CNN checkpoints as exploratory research candidates. Do **not** replace the application default or claim independent clinical benefit. The expanded-fitting arm ranks highest by ROC-AUC on this single training-candidate examination, but its review-budget advantages are mixed.

## Why this comparison matters

The initial Galar fitting set had only **239 blood-positive images across exams 1–8**, of which 208 came from one examination. Galar 21, 23 and 30 provided 3,000 additional verified sparse source images with 514 blood-positive annotations. The initial frozen CNN subsequently transferred poorly to the four-positive reference cohort of exam 23, despite stronger rankings in exam 30. We needed a controlled *training-data* comparison, not another architecture search tuned to those observed cases.

The fixed training/evaluation protocol was committed as [`4dfc23e`](https://github.com/Kushrishi/capsule-review/commit/4dfc23e188aba0cba63ff5d9902baab19c7879e4) **before the first new optimization update**, merged through [PR #19](https://github.com/Kushrishi/capsule-review/pull/19). Frozen spec Git blob: `ac042de43b22d33a2860df06fbac03e80a1cb331`. Examination 29's corrected-label support and source acquisition value were already known from fitting-pool audits, so this is **not blinded preregistration**. Neither the 1,009 newly acquired exam-29 images nor their predictions were used during optimization or model selection.

## What actually ran

Original checkpoint: two-class `capsule-cnn-v1`, SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, historically selected on previously inspected exams 9–10.

Two deterministic continued-training arms started from that *same* original checkpoint, with identical 666 minibatch updates, batch size 32, seed 37, AdamW learning rate 0.0001, weight decay 0.0001, exact 96×96 padded RGB preprocessing, and class weights based solely on each arm's fitting labels. Neither used augmentation, early stopping or test-based checkpoint selection. Data were sampled with replacement, so this is an equal-**updates** comparison, not identical seen-image counts.

| Arm | Allowed fitting exams | Images | Blood-positive | Fixed updates |
|---|---|---:|---:|---:|
| Original checkpoint (no new fitting) | 1–8, historical | 4,096 | 239 | 0 additional |
| Original-only continued | 1–8 | 4,096 | 239 | 666 |
| Expanded continued | 1–8 + 21, 23, 30 | 7,096 | 753 | 666 |

Additional data were intentionally pathology-enriched and differ in label prevalence from original fitting examples. The two fitted arms also have different class weights because their training prevalences differ. This study isolates optimization-step count, but **does not isolate the causal effect of adding data from all accompanying sampling and weighting differences**.

## Primary outcome — label-blind Galar examination 29 reference

Exactly **512** preselected source-chronological uniform reference images, containing **122** corrected `blood=1` annotations. Source examination 29 was not used in any arm's fitting. These are sparse reference images, not dense video or unique lesion events.

| Fixed method | ROC-AUC | Average precision | Blood-positive hits among top 51/512 (10%) |
|---|---:|---:|---:|
| Unchanged original CNN | 0.8594 | 0.6452 | 33 |
| Original-only continued | 0.8338 | 0.5825 | 31 |
| **Expanded-data continued** | **0.8817** | **0.6511** | **35** |
| Untrained red-excess heuristic | 0.4394 | 0.2930 | 19 |
| Uniform sampling | — | — | 10 |

The expanded candidate improved ROC-AUC by approximately **0.0223** and average precision by **0.0059** over the untouched original CNN on this one examination. These are descriptive differences, **not evidence of statistically reliable improvement across independent patients**.

### All review budgets — number of blood-positive sampled images retrieved

| Budget | Frames reviewed | Original CNN | Original-only continued | Expanded continued | Redness | Uniform |
|---|---:|---:|---:|---:|---:|---:|
| 5% | 25 | **19** | 14 | 16 | 14 | 6 |
| 10% | 51 | 33 | 31 | **35** | 19 | 10 |
| 25% | 128 | **81** | 80 | 78 | 25 | 29 |
| 50% | 256 | 109 | 107 | **117** | 52 | 63 |
| 75% | 384 | 119 | 115 | **120** | 78 | 91 |
| 100% | 512 | 122 | 122 | 122 | 122 | 122 |

The best ranking **changes by budget**: the original CNN wins at 5% and 25%; the expanded candidate wins at 10%, 50% and 75%. A 10% setting is a comparison point, never a project-wide scientific or product constraint.

### Secondary intentionally enriched union

On all **1,009** acquired exam-29 images (including deliberate positive enrichment; 372 blood-positive annotations), the original / original-only continued / expanded CNN ROC-AUCs are approximately **0.862 / 0.839 / 0.887**, respectively. These are descriptive, **not representative case-mix or population performance**, and their average precision cannot be directly compared with naturally sampled examinations.

## Source and computational verification

- The official 7z source index and two approved compressed blocks (7 and 8) were verified. Exact archive-member identity, all **1,009** PNG hashes, byte lengths and valid decoding were independently checked. No exact decoded-pixel duplicates were found against the earlier 8,120 Galar frames. The original full-archive MD5 remains unverified because only selected blocks were transferred.
- All **7,096** fitting images were independently rehashed before training. No exams 9–10, 11–20, 29 or 61–80 entered the optimization inputs.
- The portable training implementation reproduced both **new checkpoint files byte-for-byte**, including SHA-256 `ae88ccfedc53d8f419b3da8c0c01ca6b61361ef29858b6a536e25408ba99eefb` (original-only) and `2534d3b7982ee8c557cadc5ad3fcc4c7c4c557f899fa013e881d8655eab97111` (expanded).
- The portable evaluation implementation reproduced all **1,009** source prediction rows and their aggregate metrics **byte-for-byte** in a fresh CPU pass. Aggregate SHA-256 `b4fbcbf6c2546b8bb79169489920a3e6ff51c4bdb50466c1d166f5ac22f27b0e`; private prediction CSV SHA-256 `f27a410a75cdf51bc726b181083fee3f89e9f71f0bed567c04223c1aebf51e79`. Independent scikit-learn ROC-AUC and average precision agreed with the repository's tie-aware metric implementation.
- All original source images, private image identities and labels, individual prediction records and checkpoint weights are stored separately in the **Capsule Review Library** and were never committed to GitHub. Public repository artifacts include only code, tests and nonidentifying aggregate records.

## Decision and next scientific milestone

**Do not promote either fitted model.** We have one new examination-level fitting-cohort evaluation and a previously observed failure on exam 23; outcome heterogeneity remains unresolved. Exam 29 was chosen with knowledge of its training-cohort annotation support, and examination IDs do not establish distinct patients. Sparse image ranking is not lesion sensitivity, prospective diagnostic accuracy or measured physician review time.

Next: acquire and evaluate at least another fitting-candidate blood-positive examination (e.g. 25 or 27), preserving examination separation and frozen checkpoint/model-selection rules. A truly independent study then requires the already reserved cases **11–20** or another appropriately authorized, source-independent cohort **only after the model and analysis are locked**. The original author 61–80 holdout remains unopened. Before moving from image ranking to review-interval prioritization, obtain verified consecutive pathology-annotated sequences and define clinically meaningful events with appropriate expert input.
