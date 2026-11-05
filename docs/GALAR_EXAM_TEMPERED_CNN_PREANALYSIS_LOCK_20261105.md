# Pre-analysis lock: examination-tempered CNN training, retrospective 16-exam development

**Locked November 5, 2026 before the training/inference in this comparison.** This is NOT an independent, blind, patient-disjoint or clinical validation experiment. The 16 Galar examinations and their image-level outcomes were inspected in previous development work; the four partitions are deliberately based on these already known reference-positive counts. No model from this study is authorized for promotion.

## Question

Using the identical compact Capsule Review CNN, source images, seeds, optimization and evaluation, does **tempering the contribution of blood-positive images from dominant examinations** improve **examination-macro positive-image recall at exact K = 51 of 512 source-uniform reference images**, versus the existing globally class-balanced weighted cross-entropy fitting recipe? This tests one deliberate change in the fitting objective, not a new backbone, photometric alteration or selection heuristic.

## Data, grouping and excluded sources

Use only the previously SHA-256-verified **11,147 original selected PNG images** (16 permitted Galar examination IDs: 1–8, 21, 22, 23, 24, 25, 27, 29, 30). The **8,192 source-uniform reference rows** have 512 reference images per exam and 526 blood-positive labels. The other **2,955 enriched selected images** may be included in a fold's *training* source pool but NEVER in that fold's evaluation. The full pool has 1,663 selected positives. Check every original image against its private source manifest SHA-256 and recorded label/reference flag before preprocessing. Source archives are retained privately; the complete original Galar videos are not asserted available.

**Never access/reuse the already locked Galar 11–20 outcomes** for model fitting, thresholds or model selection; the source authors' reserved Galar 61–80 outcomes remain unopened. This experiment may use previously examined development images, so every result is exploratory. The available group unit is examination ID; patient independence, device/site diversity and full dense-video event labels are NOT established.

Four **fixed descriptive folds** from the November 5 reference-only feasibility design, four examination IDs held out per fold:

- Fold 1 evaluates 7, 8, 22, 24 (208 positive reference images).
- Fold 2 evaluates 29, 4, 2, 3 (125).
- Fold 3 evaluates 30, 23, 21, 5 (125).
- Fold 4 evaluates 27, 1, 25, 6 (68).

Each fold *trains from scratch* on all selected (reference + enriched) images from the other 12 examinations; no frames/labels from any held-out examination are used in training. Each fold evaluates exactly 4 × 512 = **2,048 held-out uniform-reference images**, never their enriched additions.

## Paired fixed CNN recipes

Model: existing `AnatomyCNN(2)` architecture (3 downsampling Conv2d/GroupNorm/ReLU blocks, 16/32/64 channels, average global pool and two logits); standard original aspect-preserving 96×96 RGB preprocessing and [0,1] scaling. Both arms use no augmentation, from-scratch identical initialization per fold with seed `1700 + fold_number`, identical shuffled training order per epoch and the same AdamW optimizer (learning rate **0.001**, weight decay **0.0001**), batch size **64**, exactly **6 epochs**, CPU deterministic algorithms and four threads, no checkpoint selection or learning-rate search. Always score the fixed final epoch (including failures).

For the same training rows with binary label `c`, exam `e`, let `N_c` be the global fitting count of class c and `n_ec` the fitting count of class c in exam e.

- **Control arm (pooled class balancing):** source image weight `w_i = 1/N_c`; normalize weights so their global mean is 1. The two classes therefore contribute equal total weight.
- **Single candidate arm (tempered examination-class weighting):** raw `w_i = 1/sqrt(n_ec)`; normalize **within each class** so each class contributes exactly half of total sample weight, then normalize overall weights to global mean 1. This reduces concentration on high-positive-count examinations without giving a single rare positive unbounded full inverse-frequency dominance. There is no parameter grid or choice of square-root exponent after results.

Use per-example cross-entropy, multiply by fixed per-example fitting weights and take the batch mean. The same batch order and learning-rate/epoch schedule is used for both arms. Validate finite, positive weights and class mass equality. This is a small CNN experiment, not the same as an ImageNet-pretrained MobileNet probe.

## Locked evaluation and decision

For each of the **16 held-out examinations**, record source-uniform image-positive support; both arms' ROC-AUC and AP **only when at least one positive and one negative image exist** (zero-positive exams have undefined AP/AUC for this purpose); and hits at **K=51**, **K=128**, **K=256**, each with deterministic decreasing-score rank and ascending source-frame-index ties.

**Primary descriptive comparison:** mean over the **11 positive-reference examinations** of `top51_positive_hits / reference_positive_count`, candidate minus control, in percentage points, examination-weighted equally (never pooled counts masquerading as independent exams). Secondary: mean AP, AUC over defined examinations; top51 positive-hit total; per-exam regressions/wins/ties; 25% and 50% retrieval; severe declines and zero-positive exam limitations. Report EVERY exam and no uncertainty CI that treats frames as independent patients.

**Exploratory signal threshold (not model promotion):** candidate primary improvement ≥ **+5 percentage points**, positive-reference-exam macro AP not worse, and no more than **2 of 11** positive-reference examinations worse at 10% workload. Record whether met, including the full per-exam table. Even if met, this is known data, and no checkpoint becomes a validated clinical model. If not met, explicitly reject the candidate and preserve the negative comparison.

No external-custodian contact, full-source redownload, clinical deployment, reader-time claim or retrospective modification of the Galar 11–20 negative primary is permitted. Original source pixels, individual labels/predictions, model checkpoints, training receipts and file hashes remain PRIVATE; public repository only gets code, synthetic tests, and non-identifying aggregate results/limitations.