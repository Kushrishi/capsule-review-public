# Current project status

**Reviewed November 5, 2026.** This is the starting point for understanding the entire public repository. For the current numerical research record, run `python scripts/project_status.py`: it reads the existing frozen aggregates rather than a manually maintained score table.

## The project in one minute

**Capsule Review** is local, research-only software for navigating capsule-endoscopy sequences, recording human findings, inspecting AI-generated frame rankings, comparing fixed-size review queues and exporting verifiable source-image evidence.

**What works:** the browser viewer, local import/storage, bookmarks, notes and interval annotations, generated no-medical-data demonstration, score import, five queue policies (four original plus one experimental), evidence exports and checks, a public aggregate results explorer, and automated Python/browser tests.

**What the AI is:** real compact CNN and pretrained-model research using Galar images, evaluated in separate development experiments. The real pathology-model checkpoints, medical pixels, individual labels and scores are **private**. The public 24-frame demo uses generated *non-AI* values. **No pathology model is promoted as a clinically effective default.** This is not a medical device.

## Scientific evidence, in the correct order

| Evidence | What it actually shows | What it does not show |
| --- | --- | --- |
| Original compact blood CNN and anatomy baseline | Real training/inference and working integrations | Reliable independent clinical detection |
| Development studies including 23/25/27 | Considerable cross-examination variation; changing model/augmentation/representation can help some cases and harm others | New untouched patient-level validation |
| **Locked Galar 11–20, November 4** | **163,161** original verified images, ten examinations, six with annotated blood-positive runs. At equal **10% primary** workload, score-bin mean positive-run recall **49.35%** versus uniform **50.62%**: **−1.2668765 percentage points** (negative). At **25% secondary**: **+9.5106442 pp**, heterogeneous | Demonstrated clinical benefit, guaranteed lesion retention, reader-time reduction |
| Matched pretrained representation | Development mean ROC-AUC **0.492 → 0.610**, while mean AP **0.298 → 0.169** and positive-image hits at 51 selected images **22 → 15** on three previously inspected cases | An improved model for use, or evidence of distinct event-run coverage |

The four zero-positive-run examinations (13, 14, 16, 18) have **undefined** positive-run recall. Source annotation runs are not independently diagnosed lesions. High-score ranking retrieved more positive images in the locked primary experiment but fewer **distinct** positive annotation runs than uniform selection; image enrichment is not event preservation.

The completed evaluation **must not be re-opened or retuned**. Galar 11–20 is already examined and is not available as a fresh test. The source authors' reserved Galar **61–80** outcomes remain unopened. Previous clinical source archives and individual predictions are private; the entire original 11–20 image archive was **not durably retained**. Patient grouping, external testing and clinical-time benefits are unverified.

## Find the part of the repository you need

| I want to... | Start here |
| --- | --- |
| Run the product and understand the demo | [README](../README.md), [five-minute synthetic walkthrough](SUPERVISOR_DEMO.md) |
| Inspect the code | `src/capsule_review/app.py` (API), `static/` (viewer), `store.py` (local persistence), `priority.py` (selectors), `interval_evidence.py` / `exporter.py` (review provenance) |
| Understand the scientific target and boundaries | [Research protocol](RESEARCH_PROTOCOL.md), [review policies](RESEARCH_REVIEW_QUEUE.md), [source coverage limitations](DENSE_SEQUENCE_DATA_GATE.md) |
| Read the strongest completed experiment | [Frozen design](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json), [locked results](GALAR_UNSEEN_11_20_RESULTS.md), [nonidentifying aggregate](../experiments/galar-unseen-11-20-20261104/aggregate.json) |
| Understand why the AI is not promoted | [Latest pretrained comparison](GALAR_MATCHED_PRETRAINED_PROBE_20261104.md), [exam-excluded CNN adaptation](GALAR_EXAM_EXCLUDED_ADAPTATION_RESULTS.md), [appearance robustness](ORIGINAL_BLOOD_PHOTOMETRIC_ROBUSTNESS_20261104.md) |
| Understand source qualification | [External cohort screen](EXTERNAL_COHORT_QUALIFICATION_20261104.md), [conditional external protocol](EXTERNAL_REPLICATION_DESIGN_DRAFT_20261104.md) |
| Reproduce software verification | `tests/`, [verification guide](VERIFICATION.md), `.github/workflows/tests.yml` and `public-source-privacy.yml` |
| Find previous experiments | `docs/*RESULTS.md`, `docs/*SPEC.json`, `experiments/*/aggregate.json`, `scripts/`: **historical research archive**. Preserve original dates and outcomes |

**Repository map:** `src/` is the running application; `scripts/` houses research/verification utilities; `experiments/` retains public aggregate outcomes; `docs/` holds protocols and history; `tests/` contains synthetic, source-boundary, API and browser checks. Older experiment files are not necessarily current operating instructions.

## November 5 source-data milestone

A fresh [private-backed development source audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) independently rehashed **11,147 original selected PNGs** from 16 examinations, including source identities, labels and sampling roles. **Zero** exact duplicate PNG SHA values were found; **76.7%** of selected positives sit in four examinations. A coarse visual screen flagged unresolved lookalike candidates, which cannot identify patients. Group identity and complete original-video label coverage remain unverified, so this does **not** qualify a patient-independent or complete-event study.

The 5,293 coarse dHash candidates have now been [rechecked using original-image structural similarity](GALAR_VISUAL_SIMILARITY_TRIAGE_20261105.md): none met strict pixel-aligned close-copy criteria, but this is **not** an exhaustive or patient-identity screen.

A separate [grouping and fold-readiness audit](GALAR_GROUP_AND_FOLD_READINESS_20261105.md) checked the retained official source metadata and the publisher's actual split code. Only **8/16** selected development examinations have documented capsule-device information, no source patient-group mapping is available, and the public example code uses **video ID** as the fold-group key. On **reference-only positives**, four examinations supply **90.5%** of the labels; illustrative equal-frame-count folds are still markedly imbalanced. Do **not** call these patient-disjoint folds.

The next action is to resolve **patient/examination grouping, coarse duplicate candidates and a fixed development-only manifest**, not another arbitrary model fit. A new [local source preflight](../scripts/check_development_cohort.py) enforces hashes, label states and examination/group leakage checks for future data. It never independently authenticates the custodian's assertions.

## November 5 controlled CNN training result

One predefined **16-examination, four-fold from-scratch CNN experiment** tested [exam-tempered loss balancing](GALAR_EXAM_TEMPERED_CNN_RESULTS_20261105.md) against the ordinary global class-balanced loss. Every original image was source-hash reverified; held-out evaluation used **only the original 512 uniform reference frames per examination**. The experiment's **10% primary was negative**: mean positive-exam reference-image recall **17.78% → 17.65%** (−0.1299 pp), with positive-image hits **151 → 148**, slight mean ROC-AUC increase and mean AP decline. **One positive examination improved, two worsened and eight tied** at the primary workload. No model was promoted and none was integrated into the viewer.

All 16 source examinations had already been inspected. A stronger conclusion requires additional diverse positive examinations, authenticated patient/device grouping and a separate independent outcome protocol. The locked Galar 11–20 negative study remains unchanged.

## November 5 expanded cross-examination source audit

The [full cross-examination neighbour audit](GALAR_CROSS_EXAM_NEIGHBOR_AUDIT_20261105.md) compared **57,789,904 cross-exam coarse-hash pairs** across all 11,147 previously verified selected images, plus exact nearest-neighbour searches using **10,123 original-image MobileNetV3 embeddings** across 14 exams. A source-SHA-verified pixel follow-up checked the 551 strongest embedding pairs (451 unique images); none met strict pixel-aligned close-copy criteria. This reduces one leakage concern but **does not prove different patients**, certify exhaustive transformed-duplicate clearance or improve model performance.

## November 5 external-data screening result

A metadata-only [audit of the official Kvasir-Capsule split CSVs](KVASIR_OFFICIAL_SPLIT_AUDIT_20261105.md) found 43 distinct video IDs, seven video IDs appearing in both image-split files, no cross-file frame-ID overlap, and **446 rows labelled `Blood` from only two source videos**. This does not validate patient-level independence, complete event labels or a new model. Kvasir remains a **conditional external candidate**, not a source of confirmed independent blood-event ground truth. The reusable aggregate-only audit has synthetic tests; no clinical images were acquired.
## November 5 software-only temporal control

An [offline, fail-closed contiguous-source temporal score baseline](TEMPORAL_CONTIGUOUS_BASELINE_20261105.md) and synthetic tests are available for future qualified **dense** sequences. This is not training, model promotion, new clinical evidence or a product default. Missing source-frame positions prohibit the computation; sampled Galar reference images cannot be represented as consecutive input. No frozen evaluation was reopened.

## November 5 development acquisition decision

The [prior corrected-label audit for Galar 21–60](GALAR_TRAINING_POOL_RESULTS.md) was recovered and reconciled; its labels were **already inspected**, not newly independent. A [bounded next-source decision](GALAR_NEXT_DEVELOPMENT_COHORT_20261105.md) prioritizes **the full 31–40 development group** for source-archive feasibility: 6/10 blood-positive exams, 17,344 positive annotated rows, 605 native-stride-defined annotation runs, ~69.22 GB compressed. Image access, independent patient grouping and a fresh outcome benchmark **remain blocked**. The experimental temporal control now supports caller-authenticated native source strides 1 or 5 without smoothing across source gaps; no AI-performance claim follows.

## Current constraints and next action

**Galar36 complete-source replication:** [13,326 original PNGs were acquired,
verified and scored with the unchanged CNN](GALAR36_FULL_SEQUENCE_RESULTS_20261106.md).
At 10%, uniform/global-score/raw-score-bin/window-3 reach **15/6/28/20 of 59
positive annotation runs**. Score-bin's advantage over uniform repeats on this
development case, but global ranking performs poorly and temporal processing
again loses net coverage. All outcomes are independently replayed; no model is
promoted and the locked Galar11–20 negative primary remains unchanged.

**November 6 diagnostic:** a [chronology-conditioned score audit](SCORE_ALIGNMENT_RESULTS_20261106.md)
reused the 16-examination out-of-fold CNN predictions without new acquisition,
training, inference or Galar 35 evaluation. At K=51, control CNN macro
positive-image recall is **17.78%**, versus **20.01%** under an allocation-matched
16-block reference expectation (**−2.23 pp**). Pooled hits remain above expected;
five positive examinations have positive conditional contrasts, four negative and
two tied. This heterogeneous retrospective result establishes neither causal
pathology learning nor improved AI. Authenticated, source-diverse development
material remains the next model gate.

**Galar 35 full-source experiment completed:** [all 9,643 original published PNGs were privately retained, scored, sealed before the separate audit, and independently evaluated](GALAR35_FULL_SEQUENCE_RESULTS_20261105.md). At 10%, uniform/raw score-bin/fixed temporal window-3 reach **16/23/17 of 29 positive annotation runs**. Temporal processing loses six raw-covered short runs and gains none; it is not promoted. Raw score-bin is favourable on this previously inspected development case, which does not revise the historical Galar 11–20 negative primary or establish generalization. The original-image package, original checkpoint, corrected labels and frozen score snapshot are retained privately.

The highest-impact missing asset is **diverse, source-verified development data with complete outcome semantics and defensible examination/patient separation**, followed by an independent, fully adjudicated external cohort. Neither a larger neural network nor a polished interface substitutes for those requirements.

The next engineering/scientific stage is **development-cohort qualification and leakage auditing**, then a fixed, comparable model-development benchmark. Read [the adaptive roadmap](ROADMAP.md). Before acquiring/scoring a new external cohort, use the strictly structural `python scripts/check_cohort_gate.py /private/worksheet.json` preflight; even an all-pass result still needs explicit human review and a separate pre-outcome study lock.

Other unresolved engineering decisions: lack of a public software licence, unprotected `main` (CI is voluntarily checked but not enforced), and localhost-only security without encryption or multiuser access. Do not host patient uploads or publish source artifacts to make a quick demo.

**Working principle:** measure improvements on *the right target*—distinct annotated evidence retained at a fixed review workload, with patient/exam-grouped uncertainty when valid. Keep every failure visible. Do not equate higher ROC-AUC, a lower image count or a synthetic demo with clinical benefit.

## November6: scores versus selection geometry

A [frozen-score controlled experiment](SCORE_GEOMETRY_RESULTS_20261106.md) reused
complete Galar35/36 predictions without inference or training. At10%, raw score-bin
exceeded geometry-matched randomized scores by **21.76 /16.08 run-recall pp**;
the equal-examination contrast was **+18.92 pp**. Local score information helped
on both inspected cases, but short-run omissions, global-ranking heterogeneity,
the negative11–20 primary and inconsistent16-exam alignment remain. No model
improved or was promoted; a qualified broader cohort remains the next investment.

## November6 benchmark expansion qualification

A [new source/reference-standard assessment](BENCHMARK_SOURCE_QUALIFICATION_20261106.md)
checked official catalogs, CAPTIV8 grouping metadata, all ten already-inspected
Galar31–40 annotation streams and255 possible new-case subsets. It found324 short
runs among605, but no new source-diverse cohort admitted under the frozen
qualification/resource contract. No additional images, inference or training;
patient/domain linkage and complete external blood-event truth remain blockers.
