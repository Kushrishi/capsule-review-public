# Capsule Review

A local image-sequence viewer with bookmarks, reviewer notes and illustrated exports.

**Public software repository:** [Kushrishi/capsule-review-public](https://github.com/Kushrishi/capsule-review-public). This source-only release contains reproducible software and nonidentifying aggregate research records. Original medical images, individual source annotations/predictions, research workspaces and trained weights are **not bundled**; the historical research archive remains private. See [public-release safeguards](docs/PUBLIC_RELEASE_SAFETY.md).

This repository currently has **no software licence**. Dataset attribution (including the Galar source's CC BY 4.0) does not grant a separate licence to the application code.

**Working now:** import frames, navigate and preview the sequence, save and reopen a review, and export selected images with notes. Reference annotations and imported model outputs are kept separate from reviewer entries.

**New in 0.2:** a local anatomy-model training pipeline, checked development splits, bounded Galar downloads, and a browser action for running an installed model.

**Real-data milestone completed:** a compact anatomy model has been trained on verified Galar images and its predictions saved in the viewer. The companion first-real-run package contains weights, measured results and a small runnable demonstration. The source-only ZIP retains geometric software fixtures. Clinical validation and a hosted service remain outside this release. See [the actual result and limitations](docs/REAL_DATA.md).

## Current research state — 2 November 2026

Capsule Review is a **working, localhost-only capsule-image research viewer**: verified image import and navigation, reviewer bookmarks and notes, saved sessions, illustrated exports and separate source annotation versus model-suggestion layers. The application is **not a clinical decision-support device**.

**Verified source-image inventory:** the original **5,120-image** Galar pilot spans examinations 1–10 (historical 9–10 are development-only); an additional **7,051 original PNGs** from fitting-candidate examinations **21, 22, 23, 24, 25, 27, 29 and 30** have been individually source-verified. The additional selection has **1,424** explicit `blood=1` annotations; some images from positive-bearing cases were deliberately pathology-enriched. New examinations **22 and 24** contribute 512 label-blind images each, with **zero explicit blood-positive annotations**—not proof of absence of other pathology. **The current fitting-image pool therefore comprises 11,147 images across 16 examinations** (original 1–8 plus these eight new exams), with 1,663 explicitly blood-positive images; historical 9–10 are excluded from this fitting-pool count. Images, individual annotations/predictions and model checkpoints remain in private Library storage. Source block SHA-256s were verified individually; the 31.99-GB publisher's whole-file MD5 was **not** independently verified. See [original acquisition](docs/GALAR_21_30_ACQUISITION.md), [verified 22/24 acquisition](docs/GALAR_NEGATIVE_22_24_RESULTS.md), and [block receipts](experiments/galar27-2026-11-02/source-block-coverage.json).

**Models and results:** the initial compact blood CNN, pretrained/fine-tuned MobileNet candidates, and two fixed continued-training CNNs have reproducible sparse-image experiments. The new CNNs were compared with equal optimizer-update budgets. On label-blind 512-image reference selections, the expanded CNN was best on **exam 29**, but all three CNNs performed poorly on **exam 25**, and the **unchanged original CNN** performed best on **exam 27**. The transfer outcome is inconsistent across examinations. Read the [fixed fitting comparison](docs/GALAR_EXPANDED_FIT_RESULTS.md), [exam-25 negative result](docs/GALAR25_TRANSFER_RESULTS.md), and [exam-27 complete result](docs/GALAR27_TRANSFER_RESULTS.md). **No model was promoted, and no clinical lesion sensitivity or specialist time savings have been demonstrated.**

**Quantitative failure analysis (post-hoc):** verified original PNG appearance features on **1,536 label-blind reference frames** across examined cases 25/27/29 show that blood-labelled exam-25 frames have *lower median redness and saturation* than its negative-labelled frames, whereas exam 27 shows the opposite. Exam 29 remains a counterexample to a redness-only explanation. These observations are descriptive, not a new calibrated classifier or a causal mechanism. See [prespecified feature definitions and all results](docs/GALAR_APPEARANCE_AUDIT_RESULTS.md).

**New annotation-run coverage ceiling:** an independent replay of the original corrected Galar labels and saved CNN scores across eight already examined studies found that **only 110 of 283** positive annotation runs are represented in the 512-image-per-exam reference samples (including **13 of 124 short runs**). At a 10% workload on exam 10, the CNN selected 47 positive *images* from only 3 annotated runs, whereas uniform selected 21 images from 10 runs. This is a **post-hoc data coverage finding, not lesion sensitivity**: even 100% of an already sparse sample can omit source evidence. See the [full run-coverage audit and all six budgets](docs/GALAR_RUN_COVERAGE_RESULTS.md).

**New source-density feasibility result:** using the original corrected Galar labels for all fitting-pool examinations 21–30, increasing label-blind candidate positions from 512 to 4,096 per exam increased representable positive annotation runs from **79/242** to **201/242**, including short-run coverage from **10/117** to **76/117**. But with **51 actual reviewed frames per exam**, uniform sampling reached only **21** versus **25** positive runs. This is an exploratory *label-only* counterfactual; no additional medical pixels were decoded or scored. See [frozen protocol and real-source results](docs/GALAR_DENSITY_CEILING_RESULTS.md).

**Actual source-PNG follow-up completed:** 4,608 original Galar23 images (512 and 4,096 label-blind candidates) were checksum-verified and scored by the **unchanged original redness heuristic**, plus uniform and chronology-bin selection. The 4,096 candidates contained **21/28** source blood-positive annotation runs versus **4/28** at 512, but **all three selection policies found zero runs at 51 reviewed images**. At 512 reviewed images, chronology-bin redness reached **6** runs, uniform **3**, global redness **0**; at 256, uniform outperformed both other policies. **No reliable winner or clinical benefit was established.** The new research candidate data are not independent. Read the [full original-pixel negative/result record](docs/GALAR23_PIXEL_DENSITY_RESULTS.md).

**Completed examination-separated training comparison:** after rehashing **10,123** real source PNGs across **14** previously explored fitting examinations, we trained **six compact CNNs from scratch**, two fixed training recipes across three disjoint examination folds. On the six held-out examinations with at least 10 positive label-blind reference images, pooled weighted training reached descriptive macro ROC-AUC **0.687**, versus **0.463** with examination/class-balanced sampling plus photometric jitter. Yet both fail on exam25; neither was promoted. A separate verifier matched **all 14,336** saved held-out scores exactly. See [the complete real-data and negative-outcome report](docs/GALAR_EXAM_CV_RESULTS.md).

**Completed frozen pretrained-image comparison:** official ImageNet MobileNetV3-small 576-dimensional full-field features were extracted from all **10,123 SHA-256-verified original fitting images**, and three fixed linear blood-label probes were fitted using only the other examinations in each fold. On the six held-out studies with at least ten positive reference images, macro ROC-AUC was **0.615**, below the previous pooled from-scratch CNN's **0.687**. Top-51 positive-image hits summed across 14 exams were **115 versus 151**. Previously difficult exams 23 and 25 improved in isolation, but cases 7 and 27 deteriorated; no model was promoted. **7,168 predictions were independently replayed**, with 42 original-image feature checks. See [the full pretrained-feature results](docs/GALAR_FROZEN_MOBILENET_CV_RESULTS.md).

**Completed new fitting-data comparison (November 2 local / November 3 UTC):** from the same frozen 3-fold, examination-separated 384-update pooled-CNN recipe, adding only **1,024 original `blood=0`-annotated fitting images** from exams 22/24 to the 14-examination training pool increased descriptive macro ROC-AUC from **0.6865 to 0.7078** across six higher-support, previously inspected reference examinations. Positive image hits at **K=51** per examination increased only **151 → 153** over 14 evaluated exams; examinations **23 and 25 still had zero top-51 positives**. The source images, three trained checkpoints and per-image predictions remain private. See the [frozen protocol](docs/GALAR_NEGATIVE_EXPANSION_CV_SPEC.json) and [full mixed/negative results](docs/GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md). No clinical model was promoted.

**Next research objective:** improve between-examination generalization with more diverse *private* fitting data and an independently locked evaluation protocol; improve the viewer's honest source-coverage/evidence-review workflow without assuming a diagnostic model. Do not run private medical-data acquisition through public Actions, reinterpret `blood=0` as normality, or open reserved Galar 11–20 and authors' 61–80 before appropriate protocol controls. These exploratory results show no clinical validity, distinct lesion detection, or measured physician time savings. Review-budget percentages are experiments, not product restrictions.

## Run

Upgrading from 0.1: install this version from a new source folder. Your existing workspace and reviewer notes remain in `~/.capsule-review`; no review-table migration is required.

Use Python 3.11 or later. The real-data run and current checks used Python 3.12.14 on Linux.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\capsule-review serve
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
capsule-review serve
```

Open **http://127.0.0.1:8765**. Choose **Open test sequence** to try the workflow, or **Import frames** to select permitted research images. No account or cloud connection is needed after installation. The server binds to localhost only.

## Review an examination

1. Import PNG, JPEG or WebP images. Filenames are sorted naturally: `frame_2` before `frame_10`.
2. Use the filmstrip, position slider or arrow keys. The preview rate is not acquisition timing. The **source-index audit** distinguishes a consistent observed index stride (for example, every +5) from unusual jumps, without inventing missing image content or assuming complete footage.
3. Bookmark an individual frame or write a note. Navigation saves the draft first. Ctrl/Command+S saves directly.
4. For a **reviewer-selected image interval**, choose **Mark start** at the current imported frame, navigate to a later frame, optionally add an interval note, and choose **Save end**. Marked intervals persist after reopening and can be removed; interval creation and removal are recorded separately from individual frame notes and model suggestions.
5. Reopen the app to continue at the last position and revisit marked interval boundaries.
6. Export a ZIP containing an illustrated `review.html`, structured `review.json`, and selected frame images.

Exports include manually saved frames and **only the start/end boundary images** of reviewer-marked intervals, deduplicated within the existing 250-frame/128-MiB limits. Interval notes and creation/removal history are included in the JSON. Intermediate images are **not automatically exported or presumed reviewed**, and imported image positions/source IDs do not indicate verified original recording times, lesions or diagnostic findings. Dataset labels and predictions are never automatically reported as findings.

### Larger folders and Galar reference labels

Browser import supports up to 1,000 frames and 512 MiB. Use the CLI for larger image folders:

```bash
capsule-review import "/path/to/001" --title "Galar 001 - development" \
  --source "Galar v2; Le Floch et al.; CC BY 4.0" \
  --labels "/path/to/labels/1.csv"
```

On Windows, use the same command on one line. The `--labels` option is optional. It expects a per-examination CSV with a `frame` column and image filenames such as `frame_000001.PNG`. Empty reference values remain unknown rather than being converted into negatives.

The adapter follows the authors' schema and has now been exercised on the exact verified development sample from ten Galar examinations. Original source frame numbers are preserved. See [data notes](docs/DATA.md).

## Storage and limits

Data is stored in `~/.capsule-review`: SQLite reviews and owned image copies. Choose another location with `capsule-review --data-dir PATH serve` (place the global option before the command). Original and display-image hashes are recorded. Display copies are lossless PNG after orientation/RGB conversion; original metadata is not retained. The original source files are not modified.

The local database is not encrypted and there is no multi-user authentication. Use de-identified research data only. Do not expose this application to a network or use it for patient-care decisions.

Exports are limited to 250 selected frames and 128 MiB of image data. Images must be non-animated PNG/JPEG/WebP, at most 32 MiB and 24 megapixels each. Imports fail atomically if a supplied image is invalid; no silent partial examination is created.

## Model training and inference

Install the optional ML extra with `python -m pip install -e ".[ml]"`. Prepare examination-separated data, train the compact anatomy baseline, install the completed model, and use **Run local model** in the viewer. The [model guide](docs/MODEL.md) contains the commands, split rules and evaluation limits.

The first real-data training-to-viewer run is complete. Its overall accuracy is 68.36%, below the 70.31% majority comparator; balanced accuracy and macro F1 are higher. See [the full development result](docs/REAL_DATA.md). The anatomy model is an early software/data-integration baseline. Separate exploratory blood-visibility models exist, but clinically validated lesion detection remains future work.

### External prediction imports

The viewer accepts JSON predictions from an external model run. Each record must identify the examination, sequence position and original image hash. Mismatched images, duplicate entries and invalid scores are rejected. Importing predictions does not alter reviewer notes or source annotations.

The source-only ZIP does not automatically download a model. Real trained weights and saved predictions are distributed in the companion run package. See [prediction format](docs/PREDICTIONS.md).

## Check the software

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m playwright install chromium
python tests/browser_smoke.py
```

The browser check exercises import, navigation, persistence and export against a temporary local server. It writes screenshots and results under `test-results/browser/`. A separate `--transport in-process` mode tests UI logic with a FastAPI test client where browser network access is unavailable; that does not test real-origin browser security.

[Recorded verification](docs/VERIFICATION.md) distinguishes the checks actually performed from those still outstanding.

## Research record and limits

- [Original Galar anatomy model and software integration](docs/REAL_DATA.md), including a measured majority-baseline failure.
- [Original sparse blood CNN](docs/BLOOD_IMAGE_PILOT.md), [pretrained feature probe](docs/PRETRAINED_BLOOD_PROBE.md) and [train-only domain adaptation](docs/DOMAIN_ADAPTATION_RESULTS.md).
- [Verified Galar training-source audit](docs/GALAR_TRAINING_POOL_RESULTS.md), [expanded fitting protocol/results](docs/GALAR_EXPANDED_FIT_RESULTS.md) and [new examination-27 transfer](docs/GALAR27_TRANSFER_RESULTS.md).
- [Real complete Rhode Island sequence and replication](docs/RHODE_REPLICATION_RESULTS.md), and [dense pathology-sequence data gate](docs/DENSE_SEQUENCE_DATA_GATE.md).
- [Reviewer interval evidence audit](docs/INTERVAL_EVIDENCE_AUDIT.md) and its [frozen evaluation protocol](docs/INTERVAL_EVIDENCE_AUDIT_SPEC.json): a **local, private-input** tool that distinguishes directly selected blood-positive annotated images/runs from source-positive rows merely numerically overlapped by reviewer intervals. Public tests use synthetic images and source annotations only; no lesion or clinical sensitivity is claimed.

Image-ranking experiments use sparse source positions and limited source annotations. They cannot establish complete-video interval sensitivity, independent lesion detection, independent patients, clinical diagnostic accuracy or measured review-time savings. Negative results and unresolved limitations are retained rather than selectively promoted. The current software does not automatically hide source frames or make medical findings for reviewers.
