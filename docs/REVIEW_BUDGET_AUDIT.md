# Sparse-image ranking versus annotated evidence coverage

**Exploratory historical development result — November 1, 2026.** This study reuses the previously selected epoch-8 blood-label classifier and its frozen 1,024 per-image scores. **No retraining, new image acquisition, or independent evaluation occurred.** The chronology-stratified comparison was conceived after seeing historical development results; it is a *post-hoc hypothesis*, not proof of superiority.

## Research question

If a fixed fraction of a capsule examination's *available sampled images* are prioritized for inspection, does selecting the highest-scoring images cover many different blood-positive **annotation runs**, or repeatedly select images from one prolonged run?

This is deliberately different from the original image-retrieval objective. **A contiguous run of Galar `blood=1` annotation rows is not necessarily a separate lesion or a clinical event.** Galar is a pathology-enriched dataset; the outcome `blood=0` does not establish a normal examination. The [source paper](https://www.nature.com/articles/s41597-025-05112-7) provides frame-level labels, not independent lesion identities.

## Data and integrity

- **Development examinations:** Galar v2 IDs **9** and **10**, with 512 uniformly sampled, independently rehashed source PNG files per examination. The images and all 1,024 saved scores match the original private experiment's SHA-256 identities.
- **Full corrected annotation sequences:** 4,339 rows in exam 9; 9,745 rows in exam 10, with source frame IDs increasing in exact steps of five. The corrected December 2025 ZIP and each used CSV are checked against their known SHA-256 values before use.
- **Exam 9:** no `blood=1` annotation rows. No positive-run recall can be estimated; every selected image consumes budget but has `blood=0`.
- **Exam 10:** 3,983 positive annotation rows forming **41** contiguous positive runs. Of those, **31** contain a positive frame from the existing sparse sample; 10 are intrinsically unreachable from those 512 images. Twenty-two runs contain at most 25 annotated positions, and only 12 of those short runs are reachable from our sample.
- **Source-image spacing:** consecutive *retained* images are 40–45 original frame indices apart in exam 9 and 95–100 apart in exam 10. The code explicitly disallows treating these as consecutive frames for dense temporal inference.

All budgets below are measured **per examination out of the 512 already sampled images**, *not* as a percentage of the original complete video. The 41-run denominator comes from the complete corrected **label timeline**, not from the 512-image sample. This is an exploratory data-limited measurement.

## Fixed selection comparisons

The evaluator never reads `blood` labels to **select** images; it uses them only after a set of positions has been selected. Every method spends exactly `floor(512 × budget / 100)` positions per examination. Ties favor earlier sampled source frames.

- **CNN top:** choose the globally highest scores from the original pretrained-on-fitting-data blood image model (frozen epoch 8, fitted on Galar 1–8).
- **CNN time-stratified:** divide the 512 candidate images into exactly *k* consecutive, approximately equal-size chronological bins and choose the highest CNN score from **each bin**. The bin count is the review budget; no label-based selection and no temporal neural network. This policy was designed *post hoc*.
- **Redness top:** choose highest values from the original fixed, untrained red-excess score.
- **Uniform:** choose the deterministic midpoint index of each of *k* evenly spaced candidate-image bins.
- **Random:** 100 fixed-seed independent *algorithm draws* per examination/budget (not 100 patients). Report mean and range; do not cherry-pick the best draw.

## Actual outcomes on examination 10

| 512-image budget | Policy | Positive sampled images | Distinct positive annotation runs / 41 | Short runs (≤25 annotated positions) |
| ---: | --- | ---: | ---: | ---: |
| 5% (25 images) | CNN top | 25 | 2 | 0 |
| | CNN time-stratified | 10 | 5 | 0 |
| | Redness top | 16 | 6 | 3 |
| | Uniform | 9 | 4 | 0 |
| | Random mean (100 draws) | 10.56 | 5.00 | — |
| 10% (51 images) | CNN top | **47** | 3 | 0 |
| | CNN time-stratified | 24 | **11** | 0 |
| | Redness top | 26 | 9 | **4** |
| | Uniform | 21 | 10 | 2 |
| | Random mean (100 draws) | 21.07 | 8.84 | — |
| 25% (128 images) | CNN top | **115** | 10 | 3 |
| | CNN time-stratified | 59 | **21** | 5 |
| | Redness top | 64 | 20 | **7** |
| | Uniform | 51 | 17 | 2 |
| | Random mean (100 draws) | 52.84 | 16.02 | — |

At 10%, **44 of the 47 positive images chosen by CNN top ranking belong to one prolonged annotation run**. The model excels at selecting individual positive images from the sampled set, but that is not the same as covering many different annotated regions. Time-stratification reaches 11 runs instead of 3 at the same budget, yet selects only 24 versus 47 positive images. It still reaches **none** of the short positive runs at 10%; even this alternative does not solve the rare/brief-evidence problem.

The *maximum possible* run coverage using only these 512 images is **31/41 = 75.6%**, even at 100% of the available sampled-image budget. The ten unreachable annotated runs demonstrate the structural information loss introduced by sparse image acquisition. This is **not** a measured model error.

## Reproduce without downloading an entire frame archive

Use the previously saved private blood-pilot bundle and the existing official corrected annotation ZIP. Extract the private manifest, scores and model metrics into a directory outside Git, and optionally extract the 512 exam-9 and 512 exam-10 PNGs from their original verified image checkpoint for another image hash check:

```bash
python scripts/review_budget_audit.py \
  --corrected-label-zip /private/20251215_Labels_Updated.zip \
  --manifest /private/blood-manifest.json \
  --predictions /private/predictions.csv \
  --historical-metrics /private/model-metrics.json \
  --images /private/images \
  --output /private/reproduced-review-budget.json
```

`--images` is optional, but omitting it means the script verifies the saved source-image hashes against the frozen manifest **without re-reading PNG bytes**. The audit always validates the exact official corrected source ZIP/CSV checksums, frozen 5,120-frame manifest, all 1,024 prediction identities, full annotated source ordering, and original frame-budget results. It refuses to overwrite an existing result. The aggregate checked into Git is [`review_budget_audit.json`](../experiments/galar-v2-2026-11-01/review_budget_audit.json); it contains **no individual frame IDs, labels, predictions, images, or weights**.

## What this result does *not* establish

- There is **one** positive development examination. Neither confidence intervals across patients nor generalization to different equipment, clinics or demographics can be estimated reliably.
- The CNN checkpoint was selected using the historical development set and the new stratified policy was designed after seeing that set; the 11-versus-3 run difference is exploratory and must not be optimized or promoted as independently tested.
- Discontinuous sampled images cannot support contiguous-video interval localization, temporal CNN inference, artifact transition analysis, a review-time measurement, or detection of unsampled events.
- Annotation-run count is not a unique-lesion count. Very short runs may be noise, repeatedly separated annotation segments, or different disease manifestations; clinical interpretation requires independent adjudication.
- The model's high-ranked images are research suggestions, not a basis for hiding unchecked frames or declaring a study normal.

**Next scientifically justified gate:** secure several additional outcome-blind examination assignments and consecutive images, then compare prespecified interval policies on *truly dense sequences*, with independent positive examinations and explicit review-unit costs. Do not select new examinations by looking at their labels, and keep authors' reserved examinations 61–80 unopened. The [MICCAI 2026 CapsuleAudit paper](https://papers.miccai.org/miccai-2026/0188-Paper0867.html) already studies temporally informed capsule classification; simply adding time bins or smoothing is not a novelty claim.

Data attribution: Le Floch et al., [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2), **CC BY 4.0**.
