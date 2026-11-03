# Frozen full-field pretrained MobileNetV3: examination-separated blood-label transfer

**2 November 2026 — completed, independently replayed exploratory research. Decision: NO MODEL PROMOTION.**

## Scientific question and locked design

The earlier six from-scratch compact blood CNNs were trained on fitting-only Galar data with whole-examination separation. Even the better pooled weighted CNN still failed on several source examinations. This experiment tests a **single, prespecified stronger visual representation**—a frozen ImageNet MobileNetV3-small feature extractor with a fold-trained, regularized logistic blood-label head—rather than running another open-ended architecture search.

The exact [protocol](GALAR_FROZEN_MOBILENET_CV_SPEC.json) was committed in [`89433ea`](https://github.com/Kushrishi/capsule-review/commit/89433ea2df89d6a8438c26cf2753d53bcf992082), Git blob `2440eae552535e62e1824cff6fd6437d2641e565`, **before any new feature extraction or model fitting**. The prior CNN outcomes, positive-case counts, and several individual Galar transfer results were already examined. This is a *predeclared post-hoc development comparison*, **not** independent/blinded preregistration, patient-level generalization, or clinical validation.

The input is **10,123 source-verified original Galar PNGs**, including 1,663 explicit `blood=1` labels, from previously inspected fitting examinations **1–8, 21, 23, 25, 27, 29, 30**. Earlier Galar 9–10 and the reserved 11–20 and authors' 61–80 cohorts were **not accessed**. The three held-out folds and every per-examination validation image are **identical** to the previously completed pooled CNN comparison. In every fold, training uses only *other* examination IDs, and evaluation uses exactly **512 label-blind reference images** from each held-out examination. The fitted training unions in the newer studies are intentionally pathology-enriched and do **not** reflect natural blood prevalence. Distinct examination IDs do not prove different patients.

## Methods

- **ImageNet backbone:** official torchvision `mobilenet_v3_small`, weights SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`, kept in the private research archive. Original PNG → EXIF orientation correction → full-field 160×160 bicubic RGB resize (no center crop) → ImageNet normalization. Extract 576 global-average-pooled features in inference mode; **no backbone updates**. Original PNG bytes, exact source IDs, reference roles and SHA-256s reverified against the previous 14-examination development manifest and original archives. A verified source cache contains exactly 10,123 feature rows, not data from any reserved cohort.
- **Classifier:** one fresh `StandardScaler` + scikit-learn `LogisticRegression` per fold; standardized **only using the fitting examinations**. Fixed solver LBFGS, L2 regularization C=0.1, balanced class weights, max 300 iterations, tolerance 1e-6 and seed 37. No checkpoint, threshold, crop, hyperparameter or post-hoc case selection. All **three classifiers converged without warnings**, in 168/166/196 solver iterations in folds A/B/C.
- **Comparison:** the earlier, immutable *pooled-weighted compact CNN* trained from scratch using the exact same examination folds and 512-reference selections. Both candidate models are uncalibrated; **do not** compare their raw probability values as calibrated clinical risks. Fixed workloads: exactly **51, 128, 256 and 512 images selected per examination**, with the existing deterministic source-order tie-break. A 51-image budget is a research measurement, **not** a product restriction.
- **Primary descriptive endpoint:** mean examination ROC-AUC on the same six held-out studies with at least ten positive reference images (**1, 7, 25, 27, 29, 30**). Secondary: all 11 positive examinations (including unstable 1–6-positive studies), examination-wise average precision, blood-positive image hits at fixed K, and the three `blood=0`-only reference examinations 3/5/8. Negative-only ROC-AUC/AP are **undefined**, not zero or perfect. No source annotation-run or distinct-lesion recall is inferred from image hits.

## Primary outcome: the frozen pretrained probe does not outperform pooled fitting

| Metric | Previous pooled-weighted CNN | Frozen MobileNetV3 + logistic probe |
| --- | ---: | ---: |
| Macro ROC-AUC, 6 positive examinations with ≥10 reference positives | **0.6865** | 0.6154 |
| Macro ROC-AUC, all 11 blood-positive examinations | **0.6332** | 0.5896 |
| Macro average precision, all 11 blood-positive examinations | **0.2702** | 0.1732 |
| Blood-positive reference image hits among 51 selected images/examination (14 exams summed) | **151** | 115 |
| Hits among 128 selected/examination | **286** | 201 |
| Hits among 256 selected/examination | **398** | 321 |
| Hits among all 512 reference images/examination | 526 | 526 |
| Uniform comparator hits at 51/examination (same data) | 50 | 50 |

All 14 studies contribute an equal **fixed number of selected reference images** at each K. The total 526 positive reference images across the 14 studies cluster within examinations; these are **correlated labelled frames, not independent lesions or patients**. We report no frame-wise inferential confidence intervals.

## The important heterogeneity: some previously difficult exams improve, others worsen

| Held-out exam | `blood=1` reference frames / 512 | Pooled CNN ROC-AUC | Frozen pretrained ROC-AUC | Pooled top-51 hits | Pretrained top-51 hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 22 | 0.635 | 0.625 | 3 | 4 |
| 2 | 1 | 0.153 | 0.241 | 0 | 0 |
| 3 | **0** | undefined | undefined | 0 | 0 |
| 4 | 2 | 0.817 | 0.800 | 0 | 1 |
| 5 | **0** | undefined | undefined | 0 | 0 |
| 6 | 6 | 0.514 | 0.726 | 0 | 0 |
| 7 | 208 | **0.827** | 0.516 | 48 | 25 |
| 8 | **0** | undefined | undefined | 0 | 0 |
| 21 | 1 | **0.945** | 0.350 | 1 | 0 |
| **23** | **4** | 0.417 | **0.676** | 0 | **2** |
| **25** | **14** | 0.166 | **0.535** | 0 | **5** |
| 27 | 26 | **0.981** | 0.603 | 24 | 7 |
| 29 | 122 | **0.768** | 0.680 | 40 | 35 |
| 30 | 120 | **0.742** | 0.733 | 35 | 36 |

The fixed pretrained features produce **better image ranking on known difficult examinations 23 and 25** than the previous pooled CNN, but performance drops on 7, 21, 27 and 29, and the primary six-examination macro score is lower overall. Exam23 has **only four positives** and exam25 **14**, so their AUC and top-K results are highly unstable. This is **a model trade-off**, not evidence that either representation is ready for clinical use. It does not establish a future ensemble will help; any ensemble and its evaluation would require a separately locked methodology, not a post-hoc successful blend chosen on these cases.

All three `blood=0`-only source examinations 3/5/8 remain in their assigned held-out folds. Forced-K ranking spends **153 review selections across these studies at K=51**, with no blood-positive labelled images by definition. Their model score distributions are preserved in the full aggregate, but uncalibrated scores **must not be called clinical false positives or absence of other pathology**.

## Source integrity, reproducibility and privacy

The official pretrained weights were rehashed against the previously saved genuine torchvision file. All **10 original source archive groups** were independently SHA-256-verified and every original PNG image hash, byte length and study/frame identity was checked again; the original metadata fingerprint stayed `78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2`. The extraction was resumed at a completed, reverified archive boundary after an execution timeout; the model parameters and comparison protocol never changed. The resulting **10,123×576** private feature cache has SHA-256 `611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae`.

An independent verification script **refitted all three probes** from the saved frozen features and reproduced all **7,168 source-aligned held-out class-1 scores** to maximum absolute error **1.11×10⁻¹⁶**, independently reconstructed all **56 examination×K selections**, and freshly extracted **42 original PNG features** (three per examination) to a maximum absolute feature difference **4.05×10⁻⁶**. The full nonidentifying public aggregate has SHA-256 `d0afc63060bb3d963bd3e4f15bdcc3797bb56c2b84fd27c5b6c117eee5772a82`. Local synthetic and integrity tests: **12 passed** including the public-record checks.

Source images, study-specific original frame identity records, model coefficients, original pretrained weights, full feature bank, and individual predictions are retained **privately**, outside Git. The public [aggregate](../experiments/galar-frozen-mobilenet-2026-11-02/aggregate.json) contains only nonidentifying examination-level statistics and comparison metadata. Reproducibility scripts: [feature/fit](../scripts/galar_frozen_mobilenet_cv.py) and [independent replay](../scripts/verify_galar_frozen_mobilenet_cv.py). This model was **not** installed as a clinical default or exposed as a diagnostic recommendation.

## Decision and next scientifically meaningful work

**No model promotion.** Frozen pretrained full-field features plus a linear probe did not improve the primary examination-level metric over the existing pooled CNN, although it performed differently on several failed cases. A single frozen pretrained backbone, one fixed C, and limited deliberately enriched source examinations do **not** establish the ceiling of pretrained models or medical-domain adaptation. The earlier balancing-plus-jitter comparison likewise did not show universal improvement.

The most useful next gap is **additional negative and positive fitting examination diversity** (especially unacquired corrected-source blood-negative exams 22, 24, 26, 28), followed by a genuinely fixed, sufficiently varied model selection and a completely separate protocol before touching any still reserved Galar 11–20 or original authors' 61–80. If subsequent work explores a pretrained *fine-tuned* backbone or score-combination method, explicitly label that work post-hoc development and preserve all failures. No current model has established full-video evidence preservation, clinician adjudicated lesion sensitivity, specialist reading-time benefit, independent patients or clinical readiness.
