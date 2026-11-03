# Anatomy baseline

The application can now train a compact convolutional model, install it locally and run it from the viewer. **The companion real-data run package now includes a model fitted on verified Galar images.** It uses 4,095 training frames and 1,024 development frames. Its measured failures and evaluation limits are recorded in [REAL_DATA.md](REAL_DATA.md). Geometric fixtures remain software tests only.

This is an initial anatomical-region baseline, not a finding detector. The original product goal—reviewing potentially important intervals—still requires a separate model and evaluation. Building this baseline establishes a real training-to-viewer path first.

## Install the optional dependencies

From the extracted source folder, using your activated virtual environment:

```bash
python -m pip install -e ".[ml,dev]"
```

CPU is the default. CUDA or Apple MPS is used only when explicitly requested and available. The viewer still runs without the ML extra.

## Prepare real development data

Obtain the corrected Galar annotations and a manageable set of development examinations. See [DATA.md](DATA.md). Keep source images and downloaded annotations outside the source repository.

Expected layout:

```text
data/
  images/
    001/frame_000000.PNG
    001/frame_000001.PNG
    002/frame_000000.PNG
    ...
  labels/
    1.csv
    2.csv
    ...
```

Choose validation examinations before training. The following IDs are an **example configuration**, not downloaded data or an evaluated split:

```bash
capsule-review baseline prepare --images data/images --annotations data/labels --validation-exams 3 --output development.json --max-frames-per-exam 512
```

Use only IDs actually present, and include at least one separate training examination. A credible development study needs more than a single validation examination. The default classes are mouth, esophagus, stomach, small intestine and colon, matching the authors' section task. Every selected class must occur in the training sample. Increase the available data or explicitly specify a narrower task, for example:

```bash
capsule-review baseline prepare --images data/images --annotations data/labels --validation-exams 3 --output development-three-regions.json --classes stomach "small intestine" colon
```

The manifest records every selected image, both file and decoded-pixel hashes, annotation-file hashes, examination assignments, sampling and excluded rows. Sampling occurs uniformly in source order before labels are filtered. Unknown or all-zero anatomy annotations are not converted to normal findings. The manifest is never silently overwritten.

Examinations 61–80 are reserved by the authors' reference implementation and are not opened during preparation. Do not use them for exploratory development. Grouping is by examination unless a de-identified patient-group map is supplied through `--patient-groups`. A supplied mapping is not independently verified by this application. Without it, patient-independent performance must not be claimed.

Exact decoded-image overlap across training and validation is rejected. This does not detect every near-duplicate, shared patient or device-related shortcut.

## Train and inspect

```bash
capsule-review baseline train --manifest development.json --images data/images --output runs/anatomy-01 --epochs 10 --batch-size 32
```

The baseline uses three convolution blocks, group normalization and a classification head. Images are oriented, converted to RGB, padded to 96×96 while preserving aspect ratio, then scaled to [0,1]. The implementation does not download pretrained weights.

Training-class counts alone determine loss weights. Checkpoints are selected by validation loss. Therefore, the resulting validation metrics are **development results**, not a final test. The output includes:

- `weights.pt`, `model.json` and `status.json`: the completed model and its identity.
- `dataset.json`: the exact development manifest.
- `history.json` and `metrics.json`: training history, confusion matrix, per-class support, per-examination accuracy and a training-majority baseline.

An absent validation class has a null recall/F1, not a fabricated success score. Scores are uncalibrated. The model makes a forced choice among its selected classes; it does not detect out-of-distribution frames, lesions or a normal examination.

## Connect it to the viewer

Install only a model produced by this implementation and reviewed locally:

```bash
capsule-review baseline install runs/anatomy-01
capsule-review serve
```

Import a permitted **development examination not used for fitting**. Reload the page after installing a model. Select the model under **Model suggestions**, then click **Run local model**. Suggestions are saved separately from source annotations and reviewer notes.

Alternatively, run through the CLI:

```bash
capsule-review studies
capsule-review baseline predict runs/anatomy-01 --study ACTUAL_STUDY_ID
```

The predictor checks stored image and model hashes. Exact training-image overlap is rejected by default; the CLI can explicitly permit an in-sample demonstration with `--allow-training-overlap`, which labels the output accordingly. Passing this overlap check does not prove patient independence. Model loading uses tensor-only loading and checks the expected architecture, parameter names, shapes and finite values.

## Verification without clinical data

```bash
python -m pytest -q
python tests/browser_smoke.py --with-test-model
```

The model tests actually optimize neural-network weights and exercise prediction persistence using geometric fixtures. They do not establish endoscopy accuracy. Synthetic models require an explicit test flag and cannot be run on examinations marked as real. No test-model checkpoint is bundled as a medical model.
