# Frozen ImageNet feature-transfer baseline — Galar blood visibility

**Status:** completed exploratory experiment, November 2, 2026. **Not** an independently validated pathology detector, lesion-localization method or clinical review tool. Do not replace the existing CNN with this model: it performs worse on the historical development set.

## Question and method

We tested a stronger visual *representation* without adding new medical images or changing the historical Galar split. The source is the previously verified `capsule-blood-sparse-v1` private manifest: 512 sparse images from each of examinations 1–10. Examinations **1–8** supply 4,096 training frames (239 positive `blood` annotations, including 208 from examination 7). Examinations **9–10** supply 1,024 previously inspected development frames, with 213 positive annotations **all in examination 10**. These are **not** fresh held-out tests.

A frozen `torchvision` MobileNetV3-small pretrained on ImageNet (official `IMAGENET1K_V1`) extracts a 576-dimensional global-average-pooled representation from each image, using the standard 256-short-side resize/224-centre-crop/RGB ImageNet normalization. The backbone does **not** update. A train-only standardized linear logistic probe is optimized with inverse-frequency positive weighting and fixed L2=0.01 via deterministic LBFGS, maximum 100 steps. No architecture or hyperparameter search, and no checkpoint selection on examinations 9–10. The full setup was committed as [`PRETRAINED_BLOOD_SPEC.json`](PRETRAINED_BLOOD_SPEC.json) **before** the first feature-extraction run.

The official ImageNet backbone comes from `https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth` (SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`). The prior CNN comparator's unchanged metrics SHA-256 is `781b855c0e14278fb20cb45f25f2481bcf379182aa4dd9d8e9b9c93a12928d7a`. The complete frozen manifest hash is `4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb`.

## Measured result

| Historical development metric | Original small blood CNN | Frozen MobileNet features + logistic probe |
| --- | ---: | ---: |
| Combined ROC-AUC | **0.7262** | 0.6345 |
| Combined average precision | **0.6225** | 0.3537 |
| Examination 10 ROC-AUC | **0.7079** | 0.6678 |
| Examination 10 average precision | **0.7470** | 0.6275 |
| Exam 10 positives found among top 51/512 positions (10%) | **47 / 213** | 40 / 213 |

Examination 9 has zero positive `blood` labels; its within-examination ROC-AUC/AP are **undefined**, not perfect scores. At the same 10% sampled-frame budget in examination 10, the fixed redness score finds 26 positive frames and uniform sampling 21. A broader 5–100% budget curve is in the aggregate `pretrained_blood_probe_metrics.json`; **10% is an operating point, not a project-wide restriction**. Ranking results concern only the 512 available sparse images per examination, not the full video or lesion events.

**Interpretation:** merely freezing generic ImageNet features and learning a small blood-label head is inadequate here. This does *not* establish that all pretrained networks or fine-tuning would underperform. Possible explanations worth testing with proper fitting-only development include the image-centre crop, medical-domain shift, severely uneven positive-examination support and uncalibrated scores. **These explanations have not been causally tested.** Do not tune a new model repeatedly on the already-examined 9–10 results.

## Reproducibility and working viewer

No data or weights are committed to Git. Separate private companion files preserve the official pretrained weights, fitted linear head, all 1,024 score identities and the independent real-image replay. Each of the ten 512-image feature-cache shards was generated after original image and decoded-pixel SHA-256 checks against the frozen manifest. A fresh extraction of all 1,024 development images reproduced the saved probabilities **exactly**; a second training-only fit from the saved feature cache reproduced every fitted coefficient exactly. The private application also contains two separate prediction runs (old CNN and MobileNet) on examination 10, **512 scores each**, without touching the dataset annotations or human notes.

Install existing project dependencies, plus the matching official `torchvision` package:

```bash
python -m pip install -e '.[ml,dev]' 'torchvision>=0.24,<0.26'
```

Reproduce from permitted separately stored images, official weights, the original manifest and frozen spec. Extract by examination for resumability:

```bash
for exam in $(seq 1 10); do
  python scripts/pretrained_blood_probe.py --mode extract --exam "$exam" \
    --manifest /private/blood-manifest.json --images /private/galar/images \
    --weights /private/mobilenet_v3_small-047dcff4.pth \
    --spec docs/PRETRAINED_BLOOD_SPEC.json --cache-dir /private/probe-cache
done
python scripts/pretrained_blood_probe.py --mode fit \
  --manifest /private/blood-manifest.json --images /private/galar/images \
  --weights /private/mobilenet_v3_small-047dcff4.pth \
  --spec docs/PRETRAINED_BLOOD_SPEC.json --cache-dir /private/probe-cache \
  --existing-metrics /private/frozen-original-cnn/metrics.json \
  --output /private/pretrained-probe-run
python scripts/verify_pretrained_blood_probe.py \
  --manifest /private/blood-manifest.json --images /private/galar/images \
  --weights /private/mobilenet_v3_small-047dcff4.pth \
  --spec docs/PRETRAINED_BLOOD_SPEC.json --run /private/pretrained-probe-run
```

`import_pretrained_blood.py` imports the verified 512 examination-10 predictions into an **already imported** real Capsule Review study, as *separate model suggestions*. It is not a new medical inference server and cannot run the model without the external feature extractor and weights. The browser screenshot is a real stored-image demonstration (Playwright with intercepted in-process FastAPI transport, **not** proof of network-origin security).

## Decision

**Retain original CNN as the better historical baseline.** Don't promote the pretrained probe as a new best model. The next scientifically useful experiment needs (a) more blood-positive training examinations, (b) training-only internal selection of domain-adapted/fine-tuned models, and (c) genuinely new examination-level evaluation. With sufficient resources, a substantially larger Galar acquisition can be justified on its medical-data value rather than ruled out by an arbitrary cumulative file-size budget. No unapproved paid acquisition or large transfer was initiated in this run. Galar source-author holdout 61–80 remains unopened.
