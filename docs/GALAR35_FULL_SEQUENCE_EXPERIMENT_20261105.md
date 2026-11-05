# Galar 35 — full original-source CNN and temporal experiment

**November 5, 2026. Executable two-stage research workflow; original Galar 35 PNG acquisition and full-image inference NOT performed.** Galar 35 labels were previously examined, so all future results from this examination are **descriptive development evidence**, not blinded independent validation.

## Scientific question

On **all 9,643 complete published original PNG positions** in Galar 35 (verified native source-index stride **5**), does a fixed 3-position temporal rolling maximum of the **unchanged original blood CNN score** improve coverage of distinct corrected-label-positive annotation runs relative to the original score-bin and uniform review queues at the *same exact-K workload*? Previous corrected label audits found **1,534 blood-positive rows across 29 source annotation runs**; neither run is necessarily one lesion or one clinically adjudicated event.

**Fixed methods:** uniform, original descending score, original score+separation and original score-bin; plus a *single non-promoted* temporal window-3 score-bin comparator. Workloads: **5%, 10%, 25%, 50%, 100%** with exact historical integer half-up K. The 10% descriptive comparison is highlighted for continuity with previous negative results; that does **not** re-open or replace Galar 11–20's immutable 10% primary result. No new training, threshold tuning, calibration, additional model selection, or product default changes.

## Private inputs and safe execution

All paths here are on a private permitted machine, **outside public Git**, with its own available disk and licensed Figshare access. See [Galar 35 acquisition](GALAR35_PRIVATE_ACQUISITION_AND_EXPERIMENT_20261105.md) for obtaining `/private/galar35-original-pngs.zip` from **only** verified 7z block 5 (3,453,334,016 compressed source bytes). The original source ZIP must have been fully checksum/CRC/image-verified with the pinned original labels before further analysis. Do **not** run private medical-data acquisition or inference in public GitHub Actions.

The original model is the durable private `capsule-blood-real-pilot.zip`, SHA-256 `5e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc`, containing `model/weights.pt` SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`. Input is original PNG bytes; preprocessing **EXIF-transpose, RGB, 96×96 aspect-preserving bilinear pad, float32 / 255**. Scores are uncalibrated softmax outputs, not clinical probabilities.

1. **Score and seal BEFORE reading outcomes.** The first stage reads ONLY the 9,643 image member bytes, not the outcome-bearing manifest, label ZIP or source-block receipt. It validates exact source positions and source package SHA, rehashes every original PNG, runs the pinned CNN and freezes the original four selection queues and the fixed temporal queue. It writes an *exclusive-create private JSON* snapshot with individual source frame identifiers, image hashes and raw scores.

```bash
python scripts/run_galar35_full_sequence_private.py --score \
  --source-originals /private/galar35-original-pngs.zip \
  --expected-originals-sha256 <private-package-SHA256> \
  --model-zip /private/capsule-blood-real-pilot.zip \
  --score-snapshot /private/galar35-frozen-original-scores.json
```

Record the **private score snapshot SHA-256** printed by this step and preserve the snapshot on durable private storage. It contains confidential original-image identifiers/predictions and must not enter public Git.

2. **Audit separately.** This stage refuses to read outcomes if the private snapshot or any saved queues have changed. It then rehashes and byte-compares every original PNG to both the frozen scoring record and private manifest, checks the pinned block receipt, opens **only `35.csv`** from the SHA-verified official corrected label ZIP, checks all labels and counts, and uses the existing source-run evaluator for original fixed methods. It adds the fixed temporal baseline and produces an aggregate-only descriptive report.

```bash
python scripts/run_galar35_full_sequence_private.py --audit \
  --source-originals /private/galar35-original-pngs.zip \
  --expected-originals-sha256 <private-package-SHA256> \
  --score-snapshot /private/galar35-frozen-original-scores.json \
  --score-snapshot-sha256 <private-score-snapshot-SHA256> \
  --corrected-labels-zip /private/20251215_Labels_Updated.zip \
  --output /private/galar35-development-aggregate.json
```

These are **separate deliberate local commands**, not an automated public action. Both fail closed for incorrect source/model identity, missing frames, source-grid gaps, untrusted unknown labels or altered frozen queues; neither overwrites a prior private result. The audit returns only aggregate review budgets, positive image counts, distinct corrected annotation-run coverage, and omission metrics. The output may be reviewed for non-identification before selective public release, but must not automatically be uploaded.

## What will and will not be established

A successful run can test fixed heuristics on a **complete exported Galar 35 source-position sequence**, avoiding previous sparse-reference adjacency failure. It will not prove complete device video exposure, clinically distinct lesions, independent patient grouping, human-review time savings or diagnostic safety. The labels were already inspected. The historical Galar 11–20 primary remains **−1.2668765 percentage points** at 10% score-bin versus uniform; the 25% secondary observation is not a substitute primary. Authors' Galar 61–80 are reserved.

**Current gate:** original Galar 35 block 5 has not been acquired; the local runtime lacks official Figshare DNS access and an installed 7z command. Until verified original PNGs arrive on private storage, only synthetic end-to-end software tests can run. No model improvement has yet been measured.
