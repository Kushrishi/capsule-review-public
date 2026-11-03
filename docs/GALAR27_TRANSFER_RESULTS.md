# Frozen blood-visibility CNN transfer — new Galar examination 27

**Date:** 2 November 2026. **Scientific role:** descriptive, examination-separated *fitting-pool* transfer. **Decision:** retain all three unchanged CNN checkpoints as exploratory baselines; **do not promote the expanded model**. No diagnostic, lesion-sensitivity, independent-patient or reader-time claim.

## Why this case was selected — and what was frozen

The official corrected Galar v2 (Le Floch et al., CC BY 4.0) training-pool audit had already shown **762** `blood=1` annotated positions within **four** positive annotation runs in examination **27**. The selection was therefore **informed by its pathology annotations**, and this is **not a prospective blind or independent clinical test**. Individual runs are not independently confirmed lesions.

The locked [Galar-27 source and transfer protocol](GALAR27_TRANSFER_SPEC.json) was committed at [`b670cc9`](https://github.com/Kushrishi/capsule-review/commit/b670cc9657398a5b26d2a895548f8f1ec8795f20) **before first access to examination-27 original pixels and before the first score**. It fixed:

- The official image source ID **45258019**, corrected-annotation ZIP SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`, and exact prior source-frame request SHA-256 `1aedfcdecbb270687a660acd50f312803ed0884308ea9a0973102aac242409f1`.
- The **1,005-image union**, comprising exactly 512 enriched fitting images and 512 label-blind uniform reference positions with 19 overlaps. The enriched subset contains **256** explicitly blood-positive images; the uniform reference subset has **26**. The unique union actually contains **273** blood-positive images.
- Three **unchanged** historical checkpoints: original CNN `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, original-only continued `ae88ccfedc53d8f419b3da8c0c01ca6b61361ef29858b6a536e25408ba99eefb`, and expanded continued `2534d3b7982ee8c557cadc5ad3fcc4c7c4c557f899fa013e881d8655eab97111`.
- The original aspect-preserving, padded 96×96 RGB preprocessing, unmodified red-excess heuristic, deterministic uniform comparator, rank tie rules and exactly **5, 10, 25, 50, 75, 100%** review budgets. No training, calibration, checkpoint selection, threshold tuning or architecture search could use examination-27 results.

The **primary** analysis below is confined to the 512 label-blind reference images. The intentionally pathology-enriched union is strictly secondary.

## Actual source-image acquisition and provenance

The [successful one-time GitHub Actions run](https://github.com/Kushrishi/capsule-review/actions/runs/41502991021) used the already validated single-solid-block streaming engine to fetch only original 7z blocks **5** and **6** at exact HTTP 206 source offsets:

| Original 7z block | Starting offset | Transferred bytes | SHA-256 |
|---|---:|---:|---|
| 5 | 17,398,114,495 | 3,489,830,304 | `1533108c5f5f414106c34aee1573423e7f415610352682e29302e47b2457e0bc` |
| 6 | 20,887,944,799 | 3,455,329,610 | `4b6adb70089791fd14f7a81a6d21bb13c81a304221777460e5b2daeafbdc22e6` |

Combined original compressed transfer: **6,945,159,914 bytes**, not the full 31.99-GB publisher archive. Both blocks' selection members were decoded and verified **before releasing the compressed block for the next transfer**. The actual original archive inventory listed all **14,796** examination-27 PNG members (10,842 in block 5; 3,954 in block 6).

A separate, independent local audit downloaded the resulting private artifact and checked **all 1,005 selected original PNGs** against their recorded SHA-256 and byte lengths, PNG validity, ZIP CRC, unique original source-frame identities and the exact frozen label/selection role counts. All passed. Their original file bytes total **291,862,996**. **Zero original-file SHA-256 duplicates** were found against the **10,142** earlier acquired Galar images. The private original-image source ZIP SHA-256 is `13b9b087686985d5e8521df727534bef53eca4d050abf117e459e4229fdec093`; the original private image manifest SHA-256 is `8d1ac2f533dce6f33ef56ba1136d8187ac96379c790137c88b69a48d3007244c`.

The image package is retained **only** in the private Capsule Review Library; no image pixels, exact source-frame IDs, individual annotations or model scores are committed to Git.

### Entire archive's *range receipts*, not whole-file checksum

Examination 27's successful block-5 and block-6 transfer means all **ten** official original compressed-block ranges have now been fully transferred and SHA-256-accounted for in separate acquisition runs for studies 21, 23, 25, 27, 29 and 30. Including the separately verified 1,342,072 bytes of original 7z signature/index data, their byte lengths reconcile to the published **31,989,399,751-byte** archive. Block 8's independently repeated source SHA-256 also agrees across acquisitions.

This establishes **separate source-block transfer provenance**, **not** the publisher's full-archive MD5: the original 31.99 GB archive was never reassembled and hashed as a single file, and most nonselected PNG images were not individually decoded. See the nonidentifying [source block coverage manifest](../experiments/galar27-2026-11-02/source-block-coverage.json).

## Primary outcome — 512 label-blind reference frames

Only **26/512** source-annotated blood-positive images are present in this particular preselected reference. A selected positive frame is **not** an independent lesion or physician diagnosis. The 26 positives may cluster within only four known positive annotation runs; uncertainty is much larger than image-level sample size might suggest.

| Fixed method | ROC-AUC | Average precision | Blood-positive hits at 10% (51 images) |
|---|---:|---:|---:|
| **Unchanged original CNN** | **0.96985** | **0.86558** | **22** |
| Original-only continued CNN | 0.94911 | 0.84794 | 21 |
| Expanded-data continued CNN | 0.95719 | 0.82323 | 21 |
| Fixed red-excess heuristic | 0.86254 | 0.38997 | 15 |
| Label-blind uniform position selection | — | — | 2 |

**The unchanged original CNN ranks highest here.** More fitting data did not improve this examination's ROC-AUC/AP or its 10% positive-image retrieval relative to the historical checkpoint. This is not an assertion that it is the best model generally.

### All prespecified review workloads

Each entry is the **number of blood-labelled reference images retrieved** at exactly the same number of selected sample images.

| Budget | Selected reference images | Original CNN | Original-only continued | Expanded continued | Redness | Uniform |
|---|---:|---:|---:|---:|---:|---:|
| 5% | 25 | **21** | **21** | 20 | 9 | 1 |
| 10% | 51 | **22** | 21 | 21 | 15 | 2 |
| 25% | 128 | **25** | 23 | 24 | 19 | 7 |
| 50% | 256 | 26 | 26 | 26 | 25 | 14 |
| 75% | 384 | 26 | 26 | 26 | 26 | 19 |
| 100% | 512 | 26 | 26 | 26 | 26 | 26 |

**The 10% budget is an experimental operating point, not a fixed product constraint.** We measured all six workloads, and none represents verified complete-video lesion sensitivity, temporal coverage or specialist time savings.

### Secondary: pathology-enriched 1,005-image union

This union contains **273/1,005** positive annotations, deliberately inflated by source-label-driven acquisition. Consequently, its average precision and apparent prevalence are not representative of a natural clinical cohort:

| Fixed method | ROC-AUC | Average precision |
|---|---:|---:|
| Unchanged original CNN | 0.97055 | 0.94131 |
| Original-only continued | 0.92860 | 0.88386 |
| Expanded continued | 0.92537 | 0.87897 |
| Fixed red-excess heuristic | 0.87001 | 0.69616 |

Do **not** replace the primary reference analysis with the more favorable enriched-union numbers.

## Independent reproducibility

The actual source package, every original PNG hash and role, and all three model checkpoint SHA-256s were verified before inference. A **second CPU replay**, decoding the original image files afresh rather than reusing the preprocessed tensor cache, reproduced **all 1,005 saved predictions for each CNN exactly** (maximum difference **0.0**). Independent scikit-learn ROC-AUC and average-precision computations agree with the repository's tie-aware metric implementation. All 512 reference identities and all six budget result tables recompute exactly from the saved private prediction CSV.

Reproducibility fingerprints:

- Public aggregate report SHA-256: `565bd226ad4adc01d678cfaf1df4ef55346fc0f876990eca43a947b2c414308b`.
- Private 1,005-image predictions CSV SHA-256: `4bd6bb1f605c10c1e1749f3c9d69238951de866c0b72009326923644ca927fe8`.
- Source original-image ZIP SHA-256: `13b9b087686985d5e8521df727534bef53eca4d050abf117e459e4229fdec093`.
- Private manifest SHA-256: `8d1ac2f533dce6f33ef56ba1136d8187ac96379c790137c88b69a48d3007244c`.

Only aggregate results, code and checks are committed. Scores and images remain privately preserved.

## Interpretation across different examinations

The CNN scores vary dramatically between examinations:

| Exam | Blood-positive reference frames | Unchanged original CNN AUC | Expanded continued CNN AUC |
|---|---:|---:|---:|
| 23 | 4 | **0.203** | Not held out: fitting data |
| 25 | 14 | 0.305 | 0.429 |
| 27 | 26 | **0.970** | 0.957 |
| 29 | 122 | 0.859 | **0.882** |
| 30 | 120 | 0.891 | Not held out: fitting data |

The expanded candidate ranks better than the unchanged original on **25 and 29**, but worse on **27**; even on exam 25, **all methods perform poorly**. On exam 27, the original checkpoint is strongest. These case-level contrasts are **descriptive only**: cases were chosen after consulting training-pool pathology support, the positive counts differ, the model's original checkpoint was selected using previously inspected exams 9–10, and patient independence has not been established.

**Decision:** no promotion, checkpoint/threshold selection, or clinical claims. The immediate research need is **examination-level failure analysis and a fixed training methodology evaluated on a sufficiently broad, appropriately independent cohort**, not chasing a favorable score at any one review budget. Cases 11–20 and the original authors' 61–80 holdout are still unopened. Continue to develop the working Capsule Review interface separately from model validity claims.
