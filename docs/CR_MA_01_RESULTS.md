# CR-MA-01: fixed three-category supervised comparison

**November 16, 2026 — completed; do not advance the fixed configuration.**

MobileNetV3-Small improved class-then-video macro recall by 3.60 percentage
points over the scratch compact CNN, but erosion recall fell by 22.58 points.
This fails the prespecified requirement that neither lesion category decline.
Retire this configuration on this split; do not tune against these test results.

## Study and execution

The previously qualified Kvasir-Capsule catalogue contains 5,560 labelled images
from 39 source videos. Video groups are disjoint across training, validation and
test; patient independence is not established. Training used 4,666 images from
34 videos; validation used 358 images from two videos; test used 536 images from
three videos. Test support is 74 angiectasia images from two videos, 78 erosion
images from two videos and 384 normal images from three videos. Only one
validation video supports each lesion category.

Exactly two CPU float32 fits completed, each with the same committed 512 batches
of 32 images. The scratch model was the existing 24,003-parameter
`AnatomyCNN(classes=3)`. The challenger was torchvision MobileNetV3-Small with
1,520,931 parameters, initialized from the preserved ImageNet checkpoint and a
fresh three-class final layer; all layers were trainable. AdamW learning rates
were 0.001 and 0.0001 respectively, with weight decay 0.0001. Preprocessing used
EXIF transpose, RGB, full-field bilinear padding to 224 × 224 and ImageNet
normalization, with no augmentation. No model settings changed after fitting
began. Full settings, common batch order and source identities are privately
bound by the existing commitment.

Validation selected maximum class-then-video macro recall, then minimum frame
log loss, then earliest update. All scheduled measurements were preserved:

| Update | Scratch validation recall | MobileNet validation recall |
| --- | ---: | ---: |
| 128 | 43.7121% | 37.0915% |
| 256 | 26.8450% | 46.6026% |
| 384 | 24.5965% | 42.8445% |
| 512 | 25.1619% | 41.6561% |

Selections were scratch update **128** and MobileNet update **256**. Selected
weights, all validation evidence, method identities and test logits were sealed
before the single test-metric evaluation. No replacement fits, post-result
selection or tuning occurred. No technical failure or frozen resource-limit
violation occurred.

## Sealed test results

Category recall averages recall across source videos containing that category;
the primary measure then averages the three category values. Macro-F1 and log
loss use the retained test frames. Higher recall/F1 and lower log loss are better.

| Measure | Scratch CNN | MobileNetV3-Small |
| --- | ---: | ---: |
| Class-then-video macro recall | 34.0928% | 37.6900% |
| Angiectasia video-macro recall | 2.5641% | 11.9780% |
| Erosion video-macro recall | 24.1935% | 1.6129% |
| Normal video-macro recall | 75.5208% | 99.4792% |
| Angiectasia pooled frame recall | 2.7027% | 12.1622% |
| Erosion pooled frame recall | 19.2308% | 1.2821% |
| Normal pooled frame recall | 75.5208% | 99.4792% |
| Frame macro-F1 | 0.324896 | 0.356424 |
| Mean multiclass log loss | 0.967940 | 1.003760 |

Confusion matrices: rows are source labels, columns are model predictions;
category order is Angiectasia, Erosion, Normal.

| Source label | Scratch → A / E / N | MobileNet → A / E / N |
| --- | --- | --- |
| Angiectasia | 2 / 29 / 43 | 9 / 11 / 54 |
| Erosion | 16 / 15 / 47 | 14 / 1 / 63 |
| Normal | 57 / 37 / 290 | 2 / 0 / 382 |

Per-video paired differences below are MobileNet minus scratch, in percentage
points. Aliases replace private source identities; “—” means no retained source
label of that category in that video.

| Video | Frames | Accuracy difference | Angiectasia recall difference | Erosion recall difference | Normal recall difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 167 | +12.5749 | +10.2564 | — | +13.2812 |
| V2 | 210 | +5.7143 | +8.5714 | 0.0000 | +7.0312 |
| V3 | 159 | +32.7044 | — | −45.1613 | +51.5625 |

The aggregate gain coincides with much stronger normal-category recall and
worse erosion recognition. Accuracy improvements do not satisfy the lesion
safeguard. Both models have low lesion recall on this small held-out sample.

## Verification, resources and evidence

A separate standard-library implementation, using `math` and exact `Fraction`
counts rather than the execution metric code, replayed all four validation
measurements, checkpoint choices and the sealed test logits. It verified both
512-batch traces, checkpoint/prediction hashes, confusion matrices, category and
video recalls, macro-F1, log loss, paired video differences and the advancement
decision. Numerical agreement passed at tolerance 1e-10. This is an independent
numerical implementation, not external researcher review or another inference
run.

| Resource | Scratch CNN | MobileNetV3-Small |
| --- | ---: | ---: |
| Fit wall time, including validation | 335.492 s | 681.650 s |
| CPU user time | 846.160 s | 2281.473 s |
| CPU system time | 182.757 s | 145.956 s |
| Peak process RSS | 639.574 MiB | 1113.809 MiB |

Four CPU threads were used. The complete fitting and sealed-prediction stage
took 1052.420 seconds. The limits were one hour and 4 GiB RSS per fit, two hours
total, with at least 4 GiB disk headroom checked before execution. Runtime:
Python 3.12.14, torch 2.15.0+cpu, torchvision 0.29.2+cpu, NumPy 2.3.5,
Pillow 12.3.0. Six synthetic execution tests and the published code's GitHub test
and privacy workflows passed.

Public pre-fit method commit: `24c4e9e93f5e295ee98df105c7248f3243e93863`.
Private source commitment SHA-256:
`ac9b6615c69d7f31a9f26ea8d114188fbc681885e0c74e7495ffec138f8e8a18`.
Pre-evaluation seal SHA-256:
`2bf8103d08f8edddf0aadda8502159f5290768b570bb80d1a682210792bb0077`.
Test result SHA-256:
`c44b936b8cf5bfc7a8169bac29823debcb835c00c83efbcecc8187d1b600c2ac`.

Selected checkpoint SHA-256 identities:

- Scratch: `dd4cf23b9d7787a0850d3a1a1a939160c1b387b38ac56f9311061b579a917c83`.
- MobileNet: `c334c9a68d959cdfe4ac947d731f107256a95a18f51c38832c3b32e4698d2418`.

The complete private evidence retains both selected checkpoints, all eight
scheduled snapshots, training traces, validation outputs, sealed test logits,
full numerical results, source commitments and replay verification. Medical
pixels, restricted weights and per-frame records are absent from public GitHub
and CI. Historical Galar results and all earlier FAIL decisions are unchanged.

This is a bounded comparison of two systems, not an isolated effect of
pretraining: architecture, capacity, normalization, dropout, learning rate and
initialization differ. Equal updates do not equalize FLOPs or convergence.
Three test videos provide imprecise estimates; there are no frame-independent
confidence intervals, clinical-validation claims or deployment conclusions.

Source: Smedsrud et al., *Kvasir-Capsule, a video capsule endoscopy dataset*,
Scientific Data 8, 142 (2021), [doi:10.1038/s41597-021-00920-z](https://doi.org/10.1038/s41597-021-00920-z).
Execution remained private noncommercial research under the qualified source-use
conditions; institutional ethics approval or exemption is not asserted.
