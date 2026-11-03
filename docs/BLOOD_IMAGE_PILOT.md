# Sparse blood-label image pilot — 2026-11-01

**Status:** exploratory, examination-separated *development* experiment. This is neither lesion detection nor independent clinical evaluation. The frozen anatomy study and its original metrics remain unchanged.

## Question and data

Can a compact model rank individual images with an explicit Galar `blood` label above other sampled images, more effectively than a fixed redness score and label-blind sampling?

- Source: verified Galar v2 (Le Floch et al.), corrected December 2025 labels, **CC BY 4.0**. The already acquired image checkpoints supply **512 uniformly selected PNGs per examination**; no additional full recordings were obtained.
- Fit: examinations **1–8**, 4,096 sampled frames, **239** with `blood=1`. Examination 7 supplies **208/239** positives; remaining classes and study-specific confounding require caution.
- Historical development: examinations **9–10**, 1,024 frames, **213** positives, **all in examination 10**. Both examinations were already examined during prior research; they are **not blind/confirmatory test data**.
- Future **unopened** evaluation assignment: examinations **11–20**. This assignment precedes accessing those examinations' labels/images; access and case-mix suitability are not established. The Galar authors' reserved **61–80** remain untouched.
- No verified patient-group identifiers. Examination separation alone does not prove patient independence. `blood=0` means absence of the **blood annotation**, not absence of all disease or a clinically normal recording.

## Fixed comparators and methods

The pre-fitting settings, research question and known feasibility limitations were recorded before the model run in a private `blood-pretrain-plan.json`. This was **not a preregistered blinded trial**, and the eventual model checkpoint is selected on the already-known historical development set.

1. **Untrained redness comparator:** mean positive difference between image red and its strongest green/blue channel after a fixed 96×96 center crop. This is a visual score, not a clinical threshold.
2. **Compact CNN:** the existing three-block `capsule-cnn-v1` architecture with two outputs, 96×96 RGB aspect-preserving padded input, seed 17, CPU, batch size 32, AdamW learning rate 0.001, 10 epochs, training-only inverse-frequency class weights. Best checkpoint by *unweighted historical-development cross entropy*. No pretrained weights or model search.
3. **Label-blind controls:** deterministic uniform and 100 seeded random draws at per-examination sampled-frame budgets of **5%, 10%, 25%**. Image-score selection ranks within each examination and spends exactly the same selected-frame budget as sampling.

Primary outputs are binary ROC-AUC and average precision when class support allows, plus **blood-positive sampled-frame recall** at a fixed fraction of the 512 available images. All comparisons report examination-specific scores; undefined metrics stay null when an examination has no positives. Scores are uncalibrated; this is not continuous-video interval coverage, lesion sensitivity or a measurement of specialist time.

## Completed results — fixed ten-epoch run

Independent replay of all 1,024 development scores reproduced both recorded metric tables and source-frame identities. **Epoch 8** had the lowest development cross-entropy; epoch 10 was not selected. No separate independent test was run.

| Historical development measure | Compact CNN | Fixed red-excess comparator |
| --- | ---: | ---: |
| ROC-AUC, examinations 9–10 pooled | **0.7262** | 0.5453 |
| Average precision, pooled | **0.6225** | 0.2122 |
| ROC-AUC, examination 10 only | **0.7079** | 0.6887 |
| Average precision, examination 10 only | **0.7470** | 0.5309 |

Examination 9 contains zero blood-positive annotations, so its ROC-AUC and average precision are **undefined**, not zero or one. Examinations 9–10 have different disease prevalence; pooled discrimination can reflect this case difference. **Examination 10 is the only positive development examination**, which is insufficient for reliable examination-level generalization estimates.

At the **10%** sampled-image budget, we select **51 of 512 frames per examination**. In examination 10, the CNN selects **47 of 213** positive frames, the red-excess comparator selects **26**, deterministic uniform selection finds **21**, and the mean of 100 seeded random selections finds **21.07**. The corresponding CNN 5% and 25% budgets select **25/213** and **115/213** positive sampled frames. Every selection in blood-negative examination 9 is non-positive for this task; these 51 slots still count toward review burden.

These are **sparse-frame hits within an existing preselected image sample**. The 47 hits are not 47 independent lesions or 47 full-video events; there is no claim of clinical sensitivity, reader-time reduction, patient independence or efficacy on a new site/device. Data were previously inspected and the checkpoint was chosen using development loss.

Frozen aggregate results: [`blood_image_pilot_metrics.json`](../experiments/galar-v2-2026-11-01/blood_image_pilot_metrics.json); fixed pre-fitting plan: [`blood_image_pilot_plan.json`](../experiments/galar-v2-2026-11-01/blood_image_pilot_plan.json). The accompanying **private** result package contains the real trained weights, exact manifest, per-frame development predictions and independent replay evidence. No raw data or image-identity records were committed.

## Reproduce with existing permitted local checkpoints

Install the optional ML extras: `python -m pip install -e ".[ml,dev]"`. Extract the five previously verified image checkpoints outside the repository as `images/001/...` through `images/010/...`. Put the corrected source CSVs at `labels/1.csv` through `labels/10.csv`. Reuse the trusted corrected-source receipt and frozen `requested_frames.csv` from the prior private development run.

```bash
python scripts/blood_image_pilot.py prepare \
  --selection /data/requested_frames.csv \
  --labels /data/labels --images /data/images \
  --receipt /data/label-integrity.json \
  --output /data/blood-development-manifest.json

python scripts/blood_image_pilot.py train \
  --manifest /data/blood-development-manifest.json \
  --images /data/images --output /data/blood-cnn-01

python scripts/verify_blood_image_pilot.py \
  --manifest /data/blood-development-manifest.json \
  --images /data/images --run /data/blood-cnn-01
```

The private run folder contains `weights.pt`, `metrics.json`, `history.json`, `predictions.csv` and `verification.json`. The manifest contains individual image identities and is **not** committed to Git. The Git record retains only aggregate scientific results and source-reproduction instructions. Do not add image archives, corrected CSVs, weights or individual-frame predictions to the repository.

### View the actual saved suggestions

Import a permitted development examination into the existing local viewer with its Galar annotations. Then run:

```bash
python scripts/save_blood_predictions.py \
  --data-dir /local/capsule-workspace --study-id ACTUAL_IMPORTED_STUDY_ID \
  --examination 10 --run-dir /data/blood-cnn-01
```

This checks every source-frame number and original SHA-256 and saves **model suggestions separately** from reference annotations and reviewer notes. The original images are not modified, and the score does not replace the human interpretation.

## Interpretation boundary

Positive frames are temporally correlated, the fitting positives are dominated by one examination, and there is only one positive development examination. Therefore a favorable aggregate score is **not** enough to establish generalization. Uniform sampling here operates on the frozen **512 snapshots**, not dense annotated sequences. Dense chronological evidence and more independent positive examinations are required before studying interval coverage or reduction in real review effort.

If the pilot fails or merely reproduces a redness heuristic, retain that negative result and reassess whether the next 30–40 GB archive is justified. Do not choose new cases by their unseen pathology labels to rescue the model score. Compare directly with Galar/CapsuleAudit methods only after reconciling labels, splits and evaluation units.

Dataset and attribution: [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2), [Scientific Data article](https://www.nature.com/articles/s41597-025-05112-7), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
