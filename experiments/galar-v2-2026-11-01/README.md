# Galar v2 anatomy pilot — 2026-11-01

**Status:** frozen examination-separated *development* benchmark, not a clinical validation or an independent final test. This is a reproduction record, not a promoted model release.

## Protocol

- Corrected official Galar v2 labels (December 2025), five anatomical regions, 512 source-order sampled frames per examination.
- Fit examinations **1–8** (4,095 eligible frames); development examinations **9–10** (1,024 frames). Examination 6 frame 0 was excluded because all anatomy flags are zero.
- `capsule-cnn-v1`, 10 epochs, seed 17, CPU, batch size 32, learning rate 0.001. Best epoch **5** by development cross-entropy. No pretrained weights or hyperparameter search.
- Examinations 61–80 were not opened. Patient independence cannot be established. The two development examinations were used to select the checkpoint.

## Measured performance

| Measure | Model | Training-majority baseline |
| --- | ---: | ---: |
| Frame accuracy | 68.36% (700/1,024) | 70.31% (720/1,024) |
| Balanced accuracy | 53.12% | 20.00% |
| Macro F1 | 0.4811 | 0.1651 |

| Examination | Mouth | Esophagus | Stomach | Small intestine | Colon | Model accuracy | Majority accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 11 | 2 | 41 | 330 | 128 | 75.98% | 64.45% |
| 10 | 0 | 0 | 0 | 390 | 122 | 60.74% | 76.17% |

The model **never predicts esophagus** (0/2), and stomach precision is **15.69%**. The strong examination-level shift and concentration of rare classes in examination 9 make the aggregated scores particularly unstable. They are not evidence of patient-independent generalization. The majority baseline beats the model in total frame accuracy.

## Recorded artifacts

- [`configuration.json`](configuration.json): frozen experiment settings and dataset identifiers.
- [`history.json`](history.json): training and development loss by epoch.
- [`metrics.json`](metrics.json): original machine-readable confusion matrices, class scores and per-examination accuracy.
- [`../../tests/test_real_data_record.py`](../../tests/test_real_data_record.py): independent arithmetic checks on the frozen result tables.
- [`error_audit.json`](error_audit.json): post-hoc examination-specific error audit. All 1,024 Galar frames were re-read, their SHA-256 digests checked and model outputs independently regenerated against the stored weights, reproducing the original confusion matrix exactly. See [`scripts/audit_validation.py`](../../scripts/audit_validation.py) for the reproducible command.

Full image/CSV hashes, manifest, weights and the real viewer verification are preserved in the companion run package **outside Git**. This repository deliberately does not distribute dataset frames, source labels, image-identity records, model weights or clinical observations.

**Post-hoc error patterns:** examination 10 misclassifies 116 small-intestine frames as colon and 38 colon frames as stomach; its single sampled anatomy transition has 10/10 neighbouring sample frames misclassified (using a fixed ±5 sampled-frame window). Examination 9 has 14/32 errors in analogous transition windows, versus 109/480 away from them. The window analysis was conceived after seeing the baseline and is **hypothesis-generating**, not a new independent performance result. These counts do not locate anatomical transitions precisely or establish a clinical defect.

To reproduce from the separately retained images and model files:

```bash
python scripts/audit_validation.py \
  --manifest /data/anatomy-01/dataset.json \
  --images /data/images \
  --run-dir /data/anatomy-01 \
  --expected-metrics experiments/galar-v2-2026-11-01/metrics.json \
  --output /tmp/validation-error-audit.json
```

**Next evaluation gate:** acquire sufficiently diverse *new development examinations*, preregister a larger examination-separated split, report per-examination and per-class uncertainty, and only then compare model changes. Avoid tuning to improve the existing two-examination headline score.

Dataset attribution: Le Floch et al., [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2), **CC BY 4.0**. This is a derived development selection, not an official Galar benchmark split.

## Training-only pathology feasibility (separate from the anatomy benchmark)

The [protocol proposal](../../docs/RESEARCH_PROTOCOL.md) and [aggregate audit](pathology_feasibility.json) were created **without training a pathology detector or inspecting new held-out data**. The source script is [`scripts/pathology_feasibility.py`](../../scripts/pathology_feasibility.py), and [`tests/test_pathology_feasibility.py`](../../tests/test_pathology_feasibility.py) uses synthetic annotations only. The tool analyzes full corrected annotation CSVs for examinations 1–8 and compares their source-frame IDs with the original 512-image-per-exam sampling plan, retaining no raw labels or individual image identities in Git. It also confirms each CSV SHA-256 against the **separately preserved, previously source-verified** Galar v2 correction receipt (`galar-run/label-integrity.json`). The receipt itself must be trusted; an arbitrary self-issued hash list is not proof of official provenance.

| Training-only pathology label | Full annotated positive rows | Existing sampled positives | Positive annotation runs hit / total |
| --- | ---: | ---: | ---: |
| blood | 11,143 | 239 | 32 / 76 |
| active bleeding | 84 | 0 | 0 / 4 |
| angiectasia | 313 | 17 | 17 / 58 |
| polyp | 254 | 4 | 3 / 10 |
| ulcer | 11 | 0 | 0 / 4 |

Of 76 blood-positive annotation runs, **57 contain at most 25 annotated rows**, while the longest contains **7,415**; counting positive frames as independent lesions would be severely misleading. Original equal-size sampling spans unequal examination fractions; do not use it as a fixed-percentage review-budget comparison. The separate, purely **label-only visibility** reference uses uniform sampling at 5%, 10% and 25% of annotated positions per examination and 100 seeded random selections. Runs are contiguous *annotated positives*, **not confirmed separate lesions**. Galar is pathology-enriched, patient independence is unknown, and no patient/clinical review-time performance follows from these counts.

Run against the independently retained data and corrected-label receipt (paths shown are placeholders):

```bash
python scripts/pathology_feasibility.py \
  --labels-dir /private/galar-plan/labels \
  --sample-plan /private/galar-plan/requested_frames.csv \
  --exams 1-8 \
  --label-integrity-receipt /private/galar-run/label-integrity.json \
  --output /tmp/training-only-feasibility.json
```

If the trusted receipt is omitted the script explicitly marks its output **unverified**. Never replace an existing result in place.

## Exploratory blood-label image pilot (additional run, not the anatomy baseline)

See [the study record](../../docs/BLOOD_IMAGE_PILOT.md), [fixed pre-fitting plan](blood_image_pilot_plan.json) and [aggregate results](blood_image_pilot_metrics.json). The 10-epoch, 2-output CNN was fitted to the existing 512 snapshots from each of examinations 1–8 (239 blood positives) and selected on previously inspected examinations 9–10 (213 positives, all from 10). Best epoch 8.

The CNN's historical development ROC-AUC/AP is 0.7262/0.6225 pooled, and 0.7079/0.7470 within examination 10, compared with a fixed redness comparator of 0.5453/0.2122 pooled and 0.6887/0.5309 within examination 10. At 10% sampled-frame review budget in examination 10: CNN 47/213 annotated positives, redness 26/213, uniform 21/213. The per-examination absence of positives in examination 9 prevents across-positive-examination generalization claims. These are not continuous-video or lesion-level results.

Images, original CSVs, trained weights, individual predictions and workspace data stay outside Git. The independently replayed real experiment is retained in the companion run package. Future evaluation examinations 11–20 were assigned without opening their labels or pixels; the authors' reserved 61–80 remain untouched.

## Historical sparse-image annotation-run budget audit

The separate [aggregate results](review_budget_audit.json) and [detailed limitations](../../docs/REVIEW_BUDGET_AUDIT.md) compare score ranking, outcome-blind chronological-bin selection and sampling on the **existing** 512 scored frames each from examinations 9–10. Official corrected source annotation runs are counted separately: exam 10 has 41 blood-positive annotation runs, only 31 reachable from this sparse sample. At a 10%-of-sampled-images budget, CNN top ranking reaches 3 runs across 47 positive images, whereas one CNN-best-per-time-bin reaches 11 runs across 24 positive images. These are **post-hoc** historical development findings, not new independent model validation, dense-frame interval detection or separate lesion sensitivity. Source SHA-256, saved score identities and all 1,024 source image hashes were rechecked; the frozen model and prior metrics are unchanged.

## Independent real-image sequence-readiness gate

[`sequence_readiness.json`](sequence_readiness.json) is the aggregate result of rehashing the 5,120 original retained PNG files against the exact private blood-pilot manifest using [`scripts/sequence_readiness.py`](../../scripts/sequence_readiness.py). No within-examination saved-image pair is within five source-frame indices of the next, so the saved sample is **not** a consecutive video clip and cannot validate temporal interval selection. The private image identities and source files remain outside Git. This is a negative data-feasibility result, not an additional trained model.
