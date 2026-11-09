# Frozen pretrained representation: short-event comparison (9 November 2026)

## Decision

**Negative development result; neither candidate advances.** The exact ImageNet1K_V1 MobileNetV3-Small 576-D frozen representation plus a fixed affine head underperformed the paired historical compact CNN on the same **69 source-native positive/negative short-event run comparisons**, across examinations 23/25/29/30 and seeds 17/29/43. This is neither patient-independent testing nor a 10% image-review-workload experiment. **No clinical model or queue policy is promoted.**

## Immutable source, provenance and timing

The public preparation merged in [PR #76](https://github.com/Kushrishi/capsule-review-public/pull/76), main `5d39c8d9e252d0d756391ec55d60ea618fe0f311`, before fitting. The source-safe preparation included matching pinned weights, 19 synthetic tests, exact source-ID guards, a historical three-image canary, fixed 4-fold×3-seed×2-objective training, and a mandatory prefit lock. This execution recovered the exact official checkpoint (SHA256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`), with all five retained private source archive hashes verified. Three historically cached canaries reproduced **exactly (max absolute difference 0.0)** at the original full-image 160px preprocessing; no original PNGs were acquired. **4,232** rows of the 10,123-image old feature cache were copied byte-identically; exactly **180** new embeddings were extracted, for **4,412×576** feature rows (SHA256 `6a4495ce0c64e1fff9c66a26afed4fb24c1a81989e4ba5d913c291853f9dff69`).

A private `PREFIT_LOCKED.json` (SHA256 `812839a49a2e604863b6a8a79128c6e91a38c88ed34eeb78219928e2df798ced`) and exact feature array were **uploaded to private Library and verified after readback before any fit**. All **24/24** heads completed 1,024 fixed AdamW updates with matched core/pair schedules and identical initial parameters for the paired objectives. The original complete prediction receipt (SHA256 `c21612b3a92a7caeaa67197715f3fbcca71e72851ab20e2ae4eddc4be83d4747`) binds 24 heads and 24 score files. All 48 files, paired initialization/schedule controls and the full private sealed ZIP (SHA256 `6b254b3b3e736672863bca49d3f3367fc0a3eadb14ecbe9f398dc156aa5c693b`) were preserved and independently read back **before** outcomes were inspected.

The first evaluation attempt stopped before writing or exposing outcomes because `build()` returned a pair list but the evaluator attempted `m['pairs']`. A **two-expression evaluation-only source correction** was documented and uploaded to Library before inspection; no model weights, training, metric definitions, or prefit lock changed. Original fit code SHA256 `8b9f5be6e46f5f11ec52ae494865696c0b979bf2148227b60a45625ba36a21d7` remains available at PR #76; corrected evaluator SHA256 `f2e252cfee0431fba049aabe34fffd9ed3c6d0496c804dc9740197b4a02d4af1`. The independent verification module was unchanged.

## Prespecified held-out 69-run results

All values below are **equal-examination, equal-seed means**. Tie policy: a strict positive-minus-negative blood-logit margin wins; an exact tie contributes 0.5. An annotation run is not a unique lesion or patient.

| Representation package | Classification pair ordering | Local-ranking pair ordering | Classification singleton ordering | Ranking singleton ordering |
| --- | ---: | ---: | ---: | ---: |
| Historical PR #72 compact CNN (96px padded) | **63.77%** | **72.29%** | **52.78%** | **62.22%** |
| Frozen ImageNet MobileNetV3-Small (160px full field) | 50.94% | 49.08% | 33.89% | 31.11% |

The matched new-classification-minus-historical-classification contrast is **-12.83 pp**; new-ranking-minus-historical-ranking is **-23.21 pp**. Within the frozen encoder, ranking-minus-classification is **-1.86 pp**. These are descriptive paired-development differences, not patient-level confidence intervals.

### Examination heterogeneity (seed means)

| Examination | Runs | CNN class. | MobileNet class. | CNN ranking | MobileNet ranking |
| --- | ---: | ---: | ---: | ---: | ---: |
| Galar 23 | 23 | 53.62% | 40.58% | 55.07% | 40.58% |
| Galar 25 | 20 | 68.33% | 65.00% | 78.33% | 66.67% |
| Galar 29 | 11 | 57.58% | 51.52% | 75.76% | 42.42% |
| Galar 30 | 15 | 75.56% | 46.67% | 80.00% | 46.67% |

For Galar 30, **all three singleton runs were missed by both MobileNet objectives in all three seeds**. On Galar 25 the new ranking arm was slightly higher than new classification; on 23 both tied, on 29 ranking was lower. None of these observations justifies selecting an exam or seed to rescue the result.

**Pooled (over all 3 seeds: 69 runs × 3 = 207 pair assessments; 21 singleton runs × 3 = 63 singleton assessments):** MobileNet classification ordered 105/207 pairs and 26/63 singleton presentations; MobileNet ranking ordered 103/207 pairs and 26/63 singleton presentations. These are *not* independent run or patient counts and differ from macro percentages because examinations have different run and singleton denominators.

### Prespecified advancement gates

For each representation/control contrast, advancement required positive macro difference, **every seed** positive, **every examination** seed-mean nonnegative, and no macro singleton regression. The independent verifier confirmed:

- MobileNet classification vs matched historical CNN classification — **FAIL**.
- MobileNet ranking vs matched historical CNN ranking — **FAIL**.
- Within-MobileNet ranking vs classification — **FAIL**.
- New classification eligibility for downstream full-source benchmark — **NO**.
- New ranking eligibility for downstream full-source benchmark — **NO**.

Independent replay reproduced **all 24** held-out run/singleton count cells, verified all **48 checkpoint/score file hashes** and reconstructed all **24** saved linear-head predictions from stored normalization and checkpoint tensors. It matched the primary evaluator's macro metrics and within-encoder consistency decision.

## Scientific interpretation and limitations

This refutes the specific, prespecified idea that replacing the compact CNN package with this fixed ImageNet-pretrained 160px MobileNetV3-Small representation plus fixed linear head would improve same-task, examination-held-out local pair ordering. It **does not refute all self-supervised, endoscopy-domain pretrained, fine-tuned or temporal representations**, nor isolate model architecture causally: source-image preprocessing and model capacity differ. Weakness could reflect domain mismatch, nonlinearity of the local boundary task, or fitting support; these are *hypotheses*, not established causes. There is no independent patient grouping and only four development examinations. No new 10% exact-K distinct-annotation-run recall, real clinical reading time, lesion sensitivity, or external validation was measured.

Keep the locked historical 11–20 negative 10% result unchanged, never treat inspected 31/34/35/36/37 as untouched, and do not open reserved 61–80. The correct next step is to reassess feature-domain and short-event support using existing development evidence and obtain defensible independent source/group support **before** committing to another new model fit, not to tune MobileNet on these observed failures.

## Privacy and reproduction

Public Git receives only this report, source-only evaluator erratum/test and nonidentifying aggregates. Private Library retains the original source archives, pinned public pretrained weights privately stored in Google Drive, source canaries, locked 4,412×576 features, all model and prediction files, independent replay and the evaluation erratum. No pixels, per-frame source rows, individual predictions, or model weights are published. Historical fitted code is pinned to PR #76; the evaluation-only bugfix is separate and has the recorded SHA above.
