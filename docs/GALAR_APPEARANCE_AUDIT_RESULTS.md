# Galar image-ranking failures: verified descriptive appearance audit

**Date:** November 2, 2026. **Scientific role:** explicitly **post-hoc error characterization** on Galar fitting-pool examinations with previously inspected model scores. **Decision:** neither model promotion nor an input normalization change is justified. Source: corrected Galar v2, Le Floch et al., CC BY 4.0.

## Why this investigation was necessary

The unchanged original blood CNN has very different examination-level rankings: reference ROC-AUC was **0.305** in examination **25**, **0.970** in **27**, and **0.859** in **29**. The expanded CNN yielded **0.429**, **0.957**, and **0.882**. We therefore measured a **fixed set of eight appearance characteristics** in each study, rather than fitting or optimizing another classifier to already-known failures.

The [protocol](GALAR_APPEARANCE_AUDIT_SPEC.json) was committed **before computing any new appearance features**. This is **not blinded preregistration**: all source labels and model outcomes were already examined. It prespecifies eight features, four score streams, 512 label-blind reference positions per exam, robust by-label summaries, and strict source identity checks. No statistical significance tests, feature selection or new training were performed.

## Exact source verification and reference support

All three original medical-image ZIPs and saved per-frame score CSVs were matched to their previously recorded SHA-256 hashes. **Every one of the 1,536 source-reference PNGs** was separately rehashed, checked against its original frame ID, `blood` label and reference flag, opened as a valid PNG and processed with the original CNN's EXIF-oriented padded 96x96 RGB transform. The unchanged historic red-excess comparator was also recomputed from the original image and matched to the archived result. No future evaluation or authors' reserved holdout frames were accessed.

| Galar examination | Reference images | `blood=1` | `blood=0` | Original CNN positive hits at 10% |
| --- | ---: | ---: | ---: | ---: |
| 25 | 512 | 14 | 498 | 0 |
| 27 | 512 | 26 | 486 | 22 |
| 29 | 512 | 122 | 390 | 33 |

## Prespecified appearance measurements

Each table cell shows **median blood-positive / median blood-negative-labelled** image measurements within that same examination. The complete aggregate preserves counts, means, medians, and 25th/75th percentiles for **every** feature and model score. These are image-level statistics, not independent lesions or clinical probabilities.

| Fixed image feature | Exam 25: positive / negative | Exam 27: positive / negative | Exam 29: positive / negative |
| --- | ---: | ---: | ---: |
| Padded red excess | 0.040 / 0.099 | 0.169 / 0.103 | 0.126 / 0.136 |
| Color saturation | 0.402 / 0.584 | 0.701 / 0.582 | 0.650 / 0.589 |
| Mean luminance | 0.331 / 0.221 | 0.248 / 0.278 | 0.266 / 0.318 |
| Mean edge difference | 0.0335 / 0.0214 | 0.0167 / 0.0200 | 0.0153 / 0.0181 |
| Near-white pixels | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 |
| Very-dark pixels | 0.106 / 0.231 | 0.238 / 0.150 | 0.163 / 0.107 |
| All-black pixels (includes padding) | 0.083 / 0.081 | 0.081 / 0.082 | 0.082 / 0.081 |
| Original aspect ratio | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |

**Exam 25:** blood-positive reference images are *less red* (0.040 vs 0.099) and *less saturated* (0.402 vs 0.584) than blood-negative-labelled images. Their median luminance is higher and their edge difference is also higher. In **exam 27**, the blood-positive images are distinctly redder (0.169 vs 0.103) and more saturated (0.701 vs 0.582), while the unchanged original CNN ranks them well.

**Exam 29 is an important counterexample:** its blood-positive images do **not** have a higher median simple red-excess score than its negative-labelled images, yet CNN discrimination remains substantially better than in exam 25. Therefore neither redness nor saturation alone can establish a causal explanation for the model failure. Source aspect ratio is 1.00 throughout these reference samples, which also does not support an aspect-ratio explanation here.

### Frozen CNN score reversal — not clinical probabilities

These are medians of the archived **uncalibrated class-1 softmax scores**; each cell again shows positive / negative-labelled frames:

| Exam | Original CNN | Expanded continued CNN |
| --- | ---: | ---: |
| 25 | 0.074 / 0.168 | 0.361 / 0.520 |
| 27 | 0.912 / 0.073 | 0.886 / 0.213 |
| 29 | 0.530 / 0.067 | 0.730 / 0.123 |

Both models invert the expected median score ordering on **exam 25**: positive-labelled images receive lower scores than negative-labelled frames. Exam 27 shows the opposite, with much stronger separation. This is **descriptive compatibility** between image appearance and model behavior, not proof of the cause. There has been no independent expert adjudication of images, inflammation, artifacts, hematin or bleeding findings.

## Independent reproducibility and interpretation limits

The identical source and score packages were processed **twice**, including fresh PNG decoding and all eight fixed image features. The two runs produced **byte-identical** aggregate JSON and individual private-feature CSVs:

- Aggregate SHA-256: `09a467b518b74eb89162b4c2fece9619486de617fd6a52523d6aa9548848db9d`
- Private per-image CSV SHA-256: `c07db3c66d027d730eaef82566e1c3a4d210a312e4b5926ee871381f5d608597`

The public [aggregate](../experiments/galar-appearance-audit-2026-11-02/aggregate.json) reports all preselected measurements, including uninformative ones. Individual scores, images, frames, source labels, private feature vectors and original model weights **remain in Capsule Review Library** and are not checked into Git.

The study contains only **three examination IDs**, without verified patient independence, with 14 / 26 / 122 source blood-positive reference frames. Positive images can occur within correlated annotation runs and are not independently adjudicated lesions. No pooled diagnostic sensitivity, p-value, confidence interval, physician reading time, device robustness or causal mechanism is established.

**Next scientific action:** if exploring domain robustness, prespecify variations such as color/illumination augmentation on **fitting-only** examinations before any optimizer updates, compare methods across more entire examination holdouts (including negative studies), preserve unfavorable cases and keep the reserved Galar 11–20 and authors' 61–80 cohorts unopened until a final model and clinical evaluation protocol are locked. Complete-video evidence preservation additionally requires consecutive pathology-annotated recordings and appropriate specialist review.
