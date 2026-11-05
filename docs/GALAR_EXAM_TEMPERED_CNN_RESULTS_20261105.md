# Examination-tempered blood CNN: completed 16-exam retrospective development comparison

**November 5, 2026. Decision: NEGATIVE PRIMARY; NO MODEL PROMOTION.** This research directly trained and tested eight compact neural-network checkpoints on **original source-SHA-verified Galar image pixels**, not synthetic scores or reused feature-bank predictions. It is **exploratory on previously inspected examinations**, not independently blinded, patient-disjoint, clinical or source-complete event evaluation.

## Precommitted question and design

See the [pre-analysis lock](GALAR_EXAM_TEMPERED_CNN_PREANALYSIS_LOCK_20261105.md), committed **before fitting** at `eeafd155f4ddf5f2beef5d7b383f41159cded5ef`. The question was whether reducing the influence of examinations with large numbers of blood-positive selected images improves **mean positive-examination positive-image recall at the exact 10% reference-image review workload**, versus ordinary global class balancing.

- **Source:** the 16 previously acquired development examinations **1–8, 21, 22, 23, 24, 25, 27, 29, 30**; each of their **11,147 selected original PNGs** rechecked against the private image/source SHA-256 manifest before resizing. There were **8,192 uniform-reference positions** (512 per examination), 526 positive, and 2,955 extra outcome-enriched source positions. **All** added enrichment for a held-out examination was excluded from both its fitting and evaluation. All selected images from the other 12 examinations were allowed in fitting.
- **Four fixed examination-exclusive retrospective folds**, each with 4 held-out examinations × 512 source-uniform reference images. Fold fitting sizes: **9,099, 8,602, 7,635, 8,105** selected images. Source labels from earlier development were already inspected, including when selecting fold groups. These are **not new independent test examinations**.
- **Same model/optimization:** both arms train the original `AnatomyCNN(2)` architecture **from scratch**, with identical per-fold seed, original RGB 96×96 aspect-preserving preprocessing, shuffled batch sequence, AdamW at `0.001`, weight decay `0.0001`, batch 64, **six fixed epochs** and final-epoch scoring. No augmentation, hyperparameter search, epoch selection or tuning on this comparison's outcomes.
- **Control:** sample loss weights are inverse global class counts, normalized for equal blood-positive and blood-negative class contribution.
- **Single candidate:** weight each training sample inversely proportional to the *square root* of the number of images of that label in its examination; normalize separately within each class, preserving the identical overall positive/negative loss mass. This tempers dominance without making a single positive image carry a full inverse-examination-frequency weight.

## Main outcome: a negative primary

| Measure (11 positive-reference examinations) | Pooled class-balanced CNN | Examination-tempered CNN | Candidate change |
| --- | ---: | ---: | ---: |
| **Mean per-examination positive-image recall @ 51/512 (10%)** | **17.7815%** | 17.6516% | **−0.1299 percentage points** |
| Total blood-positive reference images retrieved @ 51 | **151 / 526** | 148 / 526 | −3 images |
| Mean examination average precision | **0.2809** | 0.2794 | −0.00146 |
| Mean examination ROC-AUC | 0.6242 | **0.6425** | +0.0183 |
| Positive examinations improved / worse / tied @ 51 | — | 1 / 2 / 8 | Not a consistent improvement |

The **predeclared exploratory signal** required at least **+5 pp** mean 10% recall, non-worse mean AP and no more than two worse positive examinations. It **was not met**. The small macro ROC-AUC improvement does not compensate for lower AP and lower early retrieved-positive support. The candidate remains **unpromoted**.

### Case-level evidence (no favorable-case selection)

| Source examination | Positive uniform-reference images | Control blood-positive @ 51 | Tempered blood-positive @ 51 |
| --- | ---: | ---: | ---: |
| 1 | 22 | 5 | 5 |
| 2 | 1 | 0 | 0 |
| 4 | 2 | 0 | 0 |
| 6 | 6 | 0 | 0 |
| 7 | 208 | **50** | 47 |
| 21 | 1 | 0 | 0 |
| 23 | 4 | 0 | 0 |
| 25 | 14 | 0 | 0 |
| 27 | 26 | 23 | 23 |
| 29 | 122 | **34** | 33 |
| 30 | 120 | 39 | **40** |

Zero-positive cases **3, 5, 8, 22 and 24** had **undefined** positive recall, average precision and ROC-AUC for this study; they were included in selection workload and fitting where appropriate, but never scored as perfect-negative pathology successes. The public [per-examination aggregate](../experiments/galar-exam-tempered-cnn-20261105/aggregate.json) also preserves both models' exact K=128/K=256 hits, AP and AUC.

### Secondary review workloads did not rescue the primary

| Measure | Control | Tempered |
| --- | ---: | ---: |
| Mean exam positive-image recall @ 128/512 (~25%) | **43.34%** | 38.00% |
| Total positive hits @ 128 | 298 | 299 |
| Mean exam positive-image recall @ 256/512 (50%) | 57.35% | **69.95%** |
| Total positive hits @ 256 | 436 | 439 |

The disproportionate macro 50% difference reflects small-support cases: finding one or two more positives in an examination with only two or six annotated positives changes its *examination-normalized* recall greatly. That is **not** an independent confirmed benefit, lesion retention, event-run coverage or a reason to overturn the negative 10% result.

## Verification and privacy

The original selected-frame metadata SHA-256 matched its private commitment; all eleven separately retained source packages and every one of their **11,147 original PNGs** were rehashed and their source-frame IDs, byte lengths and labels aligned before model preprocessing. Results are archived as **eight independent final-epoch checkpoints and eight held-out prediction streams**. A separate score-level replay recomputed ROC-AUC, AP and exact-K retrieval for **all 8,192 reference images per arm**, checking every previously saved metric and label. Checkpoint-level *re-inference* from original images was **not** independently performed and is not claimed.

There were **two receipt-writing interruptions** after some complete training/inference. Both are recorded in the private run log. The preserved original checkpoints and prediction arrays for fold 1 (both arms) and fold 2 (control arm) were recovered without retraining those finished models or rerunning their inference. The unsaved original training-loss floating-point values for those recovered arms were reconstructed from **six-decimal console logs**. Model training recipe, predictions, source frames, metrics and outcomes were not altered.

The **private** 949,542-byte, 26-file research archive has SHA-256 `9dd1cca41d07299191cd867886ddfa7c1d84d8b188a9ff349b8067ca541f1ea1` and was saved in the user's access-controlled Library. It holds fitting/replay scripts, receipts, the 8 checkpoints and 8 prediction arrays, an individual source-record/label manifest and source-dependency hashes; **no original medical PNG or cached image pixel tensor**. The temporary rescaled-image bank was deleted after packaging; original source-image archives remain separate private dependencies.

Public Git contains only the [source-free weighting and split implementation](../src/capsule_review/exam_balance.py), its [synthetic tests](../tests/test_exam_balance.py), the [auditable aggregate](../experiments/galar-exam-tempered-cnn-20261105/aggregate.json), and [aggregate integrity regression tests](../tests/test_exam_balance_record.py). No private per-frame score, label or checkpoint is promoted to Git or the viewer.

## Scientific decision and next highest-value task

**Do not promote the candidate or use these 16 already inspected examinations as an independent success test.** Examination-tempered class weighting redistributes loss mass as intended, but it did not improve the prespecified early-reference retrieval endpoint. Further varying that exponent, training epochs or fold assignments after seeing this comparison would be posthoc optimization. A stronger next model study requires **genuinely more diverse positive examinations and authenticated patient/device/site grouping**, plus a frozen development protocol and a new qualified independent cohort for any generalization claim.

The selected 512-source-reference frames are NOT complete videos; their positive-image retrieval is not distinct clinically reviewed blood-lesion recall. The original locked **Galar 11–20** source-complete evaluation's **negative 10% primary** remains unchanged, and authors' Galar **61–80** outcomes remain unopened. No clinical reader time or patient safety measure was observed.
