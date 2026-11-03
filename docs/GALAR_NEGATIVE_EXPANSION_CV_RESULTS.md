# Adding two blood-negative-labelled Galar fitting examinations: completed matched CNN comparison

**November 2, 2026 local time (November 3 UTC). Status: completed, independently replayed. Decision: retain as exploratory data-diversity evidence, do not promote a model.**

## Scientific question

Our existing compact blood-image CNN produced widely different rankings across capsule-endoscopy examinations, with particularly poor results on Galar 23 and 25. The project independently acquired and preserved **512 original Galar PNGs from each of examinations 22 and 24**, both with no explicit `blood=1` annotation in the corrected source. The source acquisition and independent replay are documented in [GALAR_NEGATIVE_22_24_RESULTS.md](GALAR_NEGATIVE_22_24_RESULTS.md).

The question is whether adding those **1,024 blood-negative-labelled fitting images** improves the prior fixed, **three-fold examination-separated** pooled weighted CNN when the model architecture, initialization, optimization budget, preprocessing and originally held-out reference examinations remain fixed.

The exact [prespecified experiment protocol](GALAR_NEGATIVE_EXPANSION_CV_SPEC.json) was committed **alone at [`90c707b`](https://github.com/Kushrishi/capsule-review/commit/90c707b5b2763ea25217ed0f6e5f46171a693d10)** (Git blob SHA-1 `aa15f1ffaba381bb663a2ef3f0e1c578b4fd56c9`) *before* the three new optimization runs. The old case labels, prior model outcomes, and severe failures were already inspected. This is **not a new blinded cohort**, independent patient test or clinical validation.

## Exactly what changed

| Design feature | Original pooled CNN | Negative-examination expansion |
| --- | --- | --- |
| Fitting-source examination IDs available | 14 | **16** (adds 22 and 24) |
| Verified original source images available | 10,123 | **11,147** |
| Explicit `blood=1` labels in fitting pool | 1,663 | **1,663** |
| Sample-positive fraction (intentionally enriched source pool) | 16.4% | 14.9% |
| Original reference examination IDs evaluated | Exactly the same 14 | **Exactly the same 14** |
| Reference positions per evaluated examination | 512 label-blind | **The identical 512 source frames and blood labels** |
| Model architecture | From-scratch 3-conv `AnatomyCNN(2)` | **Unchanged** |
| Fitting protocol | CPU float32, seed 37, AdamW, 384 steps, batch 32, LR 0.0002, decay 0.0001, train-fold inverse-frequency class-weighted loss | **Unchanged** |

The 512 reference positions in **Galar 22 and 24 are training-only in all three folds**, not new validation rows. The fixed held-out examination folds remain **A: 1/3/21/27/29; B: 2/5/23/25/30; C: 4/6/7/8**. An entire held-out examination was removed from that fold's fitting images. The saved prior CNN checkpoints/scores were not altered or refitted.

One important qualification: expanding the data pool also changes the available sample distribution and **train-only class weights**; an identically seeded sampler draws different individual images once the pool changes. The result is therefore a controlled **training-source addition**, not a single-variable causal isolation of disease status, image variety, class weights or negative prevalence. Blood-negative annotation is not proof of absence of other pathology.

## Primary result — small descriptive improvement, unresolved hard cases

| Same previously examined cohort and metric | Original pooled CNN | Pooled CNN with 22/24 training-only |
| --- | ---: | ---: |
| Macro ROC-AUC, six exams with ≥10 positive reference images | **0.6865** | **0.7078** |
| Macro ROC-AUC, all eleven positive-reference exams (including very low positive support) | **0.6332** | **0.6397** |
| Positive images among exactly 51 selected per exam, summed over 14 exams | **151** | **153** |
| Positive images among exactly 128 selected per exam | **286** | **287** |
| Positive images among exactly 256 selected per exam | **398** | **416** |
| Positive images among exactly 512 selected per exam | 526 | 526 |

The six higher-support exams are **1, 7, 25, 27, 29, 30**. The 0.0212 macro-AUC increase is modest and descriptive, not a statistically validated or externally generalizable effect. At the tight K=51 workload, the practical research image-hit difference is only **two frames across all 14 examinations**. The 100% review ceiling cannot change when all original candidate images are selected.

### Every held-out examination (no suppressed failures)

Each ROC-AUC is computed only from the **512 original, label-blind reference images** in that examination. A dash means undefined AUC due to no blood-positive reference labels, **not** success or failure. Cases with one to six positive images are particularly unstable.

| Exam | Explicit blood-positive reference images | Old AUC | Expanded-fit AUC | Old top-51 hits | New top-51 hits | Old top-256 hits | New top-256 hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 22 | 0.635 | 0.608 | 3 | 3 | 16 | 16 |
| 2 | 1 | 0.153 | 0.155 | 0 | 0 | 0 | 0 |
| 3 | 0 | — | — | 0 | 0 | 0 | 0 |
| 4 | 2 | 0.817 | 0.807 | 0 | 0 | 2 | 2 |
| 5 | 0 | — | — | 0 | 0 | 0 | 0 |
| 6 | 6 | 0.514 | 0.492 | 0 | 0 | 3 | 3 |
| 7 | 208 | 0.827 | 0.880 | 48 | 50 | 163 | 174 |
| 8 | 0 | — | — | 0 | 0 | 0 | 0 |
| 21 | 1 | 0.945 | 0.914 | 1 | 1 | 1 | 1 |
| 23 | 4 | 0.417 | 0.423 | 0 | 0 | 2 | 2 |
| 25 | 14 | 0.166 | 0.225 | 0 | 0 | 2 | 2 |
| 27 | 26 | 0.981 | 0.982 | 24 | 25 | 26 | 26 |
| 29 | 122 | 0.768 | 0.797 | 40 | 38 | 94 | 100 |
| 30 | 120 | 0.742 | 0.755 | 35 | 36 | 89 | 90 |

**The key counterexamples persist:** exam **23** changes from ROC-AUC **0.417** to **0.423**, and exam **25** from **0.166** to **0.225**, with **zero positive images retrieved at K=51 in both methods for both exams**. Exam 29 AUC increases (0.768→0.797) yet its K=51 positive hits **decrease from 40 to 38**. Exam 1 also loses AUC (0.635→0.608). Positive-image hit totals are not source-positive annotation-run coverage, independently adjudicated lesions or actual reader time.

The three older blood-negative-labelled validation studies **3, 5, 8** have undefined ROC-AUC/AP and exactly 51 selected `blood=0` images each at a fixed K=51; this is a forced workload property, **not** a clinical false-positive-diagnosis count. Galar 22 and 24 were never used as held-out evaluation data in this comparison.

## Independent source and model reproducibility

- Original source ingestion verified every one of the **11,147 original PNG source hashes**, byte lengths, image formats, original frame identities, label/role provenance and uniqueness. All original pixel bytes remain in separately preserved private source packages; no newly obtained medical data were copied into GitHub. The input bank has **11,147 resized 96×96 RGB tensors**, SHA-256 `1d70cdfac8e95f18643b1313af58783a6ef31443ef8b40494e1d0286c73cbc8e`; private metadata SHA-256 `76b698a5026a90f82b54692ca74f0d056a0cbf61368a9698499c13f85a6644cb`.
- Three newly trained checkpoints (**folds A/B/C**) were independently loaded into a separately defined CNN and used to recompute all **7,168 held-out class-1 scores**, with **maximum absolute difference 0.0**. All **56** examination × workload positive-image hit counts matched the original outcome; all supported ROC-AUC/AP values matched. Independent verification receipt SHA-256 `455392eafa17452c662d57a1e60382d26da68284c212c883a0fd5d0a46a5eca6`.
- The **old and new validation source frame IDs and blood annotations matched exactly, 7,168/7,168**, not just counts. Nonidentifying canonical reference-identity fingerprint SHA-256 `5ec4c132525b2ae7ceeeda4ad7a83b8142846a511d718a94fee5b40906ce6814`.
- A separate original-PNG spotcheck re-decoded **32 images (two from each of the 16 fitting exams)** and reproduced the cached RGB training tensors with **zero pixel differences**. Spotcheck summary SHA-256 `8e0b63deb545639d7acb8890ab321363ba33c197a14ebf82152c77f37b28310d`.
- Full new 14-examination aggregate SHA-256 `65bec25557b00f0461c490374a3a1c9a0123b215b7f750c0648e3b30537bd471`; independent old/new paired aggregate SHA-256 `1cb2d8d26739a39d4a10339ec2aafedff16bce5c67b79e00b635f2ef91bb349b`.
- The exact training script used, original private per-image metadata, all three actual checkpoints and individual score records, full aggregates, source spotcheck, verification, and immutable protocol are in the **538 KB private reproducibility bundle**, SHA-256 `f9e247a84e6e22ea1455a0171efefa3cf3e359b9fc4da62edaa5377f3994699a`, retained at `Capsule Review/Galar Negative Expansion CV 2026-11-02` in Library. The large re-created tensor bank is not duplicated in the bundle; it is deterministically reconstructed from the original privately retained image archives. No private source-frame IDs, individual labels or scores, actual pretrained/checkpoint bytes or medical pixels are committed to GitHub.

## Research decision and next gate

**Keep the finding but do not promote the expanded model.** Adding the two previously missing negative-label fitting examinations gave a small, examination-variable improvement, but it did not fix the two most concerning blood ranking failures at useful sparse review budgets. This suggests additional examination diversity warrants investigation while also showing that data volume alone is not sufficient.

Future work should broaden original fitting evidence (e.g. negative-labelled fitting examinations 26/28; additional positive visual appearances), design evaluation on unseen examination-level data and only then revisit stronger architectures or policies. Previously explored 1–10, 21–30 are **not independent patient validation**. The reserved Galar evaluation examinations **11–20** and authors' **61–80** remain unopened. There is no clinical lesion sensitivity, calibrated diagnosis, verified patient independence, physician time savings or complete-video evidence preservation in these measurements.

Galar source: Le Floch et al., corrected Galar v2 (2025), CC BY 4.0; original publisher full-source MD5 was never claimed from partial 7z transfers.
