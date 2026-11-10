# Capsule Review — scientific synthesis

**Retrospective research status, 10 November 2026 UTC.** This is an evidence summary, not a submitted manuscript, a clinical validation or a request for access to patient data. All numbers below refer to the linked, existing reports; the source data and model weights remain private.

## Question and motivation

Video capsule endoscopy produces long image sequences. A review system that prioritizes the frames with the highest anomaly scores may concentrate its selections on a long, conspicuous finding while missing several brief abnormalities. Such a system could retrieve many blood-positive *images* without reaching many distinct positive *episodes*.

We ask: **At the same number of frames reviewed within each examination, can AI-assisted selection cover a greater fraction of distinct blood-positive source-annotation runs than deterministic, outcome-blind chronological sampling?** A follow-on clinical question is whether this matters for expertly adjudicated lesions and clinician workflow; that question has not yet been studied.

The contribution being explored is a reproducible **evidence-retention and omission evaluation**, not a claim to have invented capsule-endoscopy classification. Temporal endoscopy modeling and AI-assisted reading have established prior art; substantive novelty remains to be demonstrated against appropriate task-matched methods.

## What was built

A local FastAPI/JavaScript research viewer imports and hashes images, preserves original ordering, supports human annotations and bookmarks, imports separately identified model scores, compares fixed-size review queues, inspects omitted spans and exports verifiable evidence. The viewer does not auto-create findings or conceal unselected images. A 24-frame generated demonstration is useful for software testing, but its scores are **not trained-model predictions**. [Reproduction guide](SUPERVISOR_DEMO.md); [core source](../src/capsule_review/app.py).

The private research pipeline additionally trains models, verifies original-image identities and evaluation manifests, seals predicted scores before outcomes where specified, and independently replays key numerical analyses. Medical pixels, frame labels, patient records and weights are not shipped publicly.

## The principal locked experiment

**Population and endpoint.** The [original Galar 11–20 evaluation](GALAR_UNSEEN_11_20_RESULTS.md) used **163,161 source-verified original images in ten examinations**. Six had at least one `blood=1` annotation run and four had none, for which positive-run recall is **undefined**. There were **1,742 blood-positive annotated images** and **154 contiguous positive source-annotation runs** at the dataset's native annotation stride. A run is a contiguous reference-label segment, *not* a separately adjudicated lesion or independent patient event.

**Design.** The original compact blood CNN and four deterministic review policies were fixed before the corrected evaluation outcomes were inspected; pre-outcome commitments, examination eligibility amendment A1, original-source verification, and independent numerical replay are documented. The prespecified primary compared **score per chronological bin** with **uniform midpoint sampling**, selecting the same exact *K* positions at **10% of each examination's annotated images**. The paired mean used the **six examinations with positive runs**, not the pooled run count. The full record preserves 5%, 25%, 50% and 100% budgets and competing policies, but only the original locked endpoints carry their original status.

**Primary result:** mean positive-run recall **49.35% score-bin vs 50.62% uniform**, paired difference **−1.2668765 percentage points**, with two positive, two negative and two tied examination-level contrasts. **The prespecified primary improvement was not demonstrated.** At the prespecified **25% secondary** workload the paired difference was **+9.5106442 percentage points**, with substantial examination heterogeneity. This is not confirmatory evidence of benefit.

A mechanistically revealing secondary comparison is that **highest-score ranking at 10%** retrieved **305 blood-positive annotated images but only 28/154 positive runs**. Uniform selection retrieved **170 positive images across 63/154 runs**. The image-score signal enriched positive frames while clustering selections into relatively few positive episodes. Pooled run counts should not replace the prespecified equal-examination primary estimate. [Locked methods, per-exam results and reproducibility caveats](GALAR_UNSEEN_11_20_RESULTS.md).

## Why later development did not rescue the result

The team then tested broader fitting support, different local-ranking losses, source-examination-held-out comparisons, ensembles and a frozen ImageNet MobileNetV3-Small representation using **already inspected development examinations**. Positive pair-ordering results are not a new event-preservation endpoint. The relevant consolidated findings are:

| Development analysis | Observed result | Inference limit |
| --- | --- | --- |
| [Matched training diversity](MATCHED_DIVERSITY_ABLATION_RESULTS_20261107.md) | No mean 10%-workload run-recall improvement in the fixed paired six-model comparison | Previously inspected data; neither independent external replication nor clinician endpoint |
| [Local short-run support](SHORT_EVENT_FOUNDATION_RESULTS_20261109.md) | 69 valid positive–negative native-source boundary pairs across four examinations, 21 singleton runs | Pair ordering is a diagnostic task, not whole-examination run recall |
| [Compact CNN versus frozen MobileNet](FROZEN_REPRESENTATION_SHORT_EVENT_RESULTS_20261109.md) | Examination-held-out ranking: **72.29% compact CNN** versus **49.08% frozen MobileNet** on the matched 69-pair protocol | Different image preprocessing, capacities and training conditions; architecture is not isolated causally |
| [Error persistence](REPRESENTATION_TRANSFER_ERROR_PERSISTENCE_20261109.md) | Frozen MobileNet heads correctly ordered **100%** of their in-sample training pairs but transferred near chance; 31/69 ranking pairs missed by all three seeds | Strong sign of poor transfer on this small development population, not an identified device or patient cause |

The 11,147-image [selected-source audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) across 16 examinations found that positive examples are concentrated in a few source examinations. Later original-image checks verified selected image dimensions, not exact capsule devices or patient identity. Consequently, another same-cohort parameter sweep would have weak inferential value.

## Source, ethical and clinical limits

- **Grouping:** dataset examination IDs are not authenticated unique patients. Device/site metadata and repeat-patient linkage are incomplete. Neither source-file hashes nor visual-similarity screens establish patient independence. [Grouping audit](GALAR_GROUP_AND_FOLD_READINESS_20261105.md).
- **Reference standard:** a `blood=1` label is not a clinical diagnosis, active bleeding, or a unique lesion. Sparse uniformly selected frames are not complete original-video event ground truth. Unknown/absent labels must never be relabeled negative.
- **Externality:** 11–20 is now evaluated and cannot be called untouched; the Galar authors' reserved **61–80** outcomes remain unopened. The available [external dataset screen](EXTERNAL_COHORT_QUALIFICATION_20261104.md) has not qualified a complete, patient-independent blood-run benchmark.
- **Clinical applicability:** there are no prospective readers, measured physician minutes, lesion-level sensitivity, or clinical safety study. No pathology model is promoted, distributed or approved for clinical use.
- **Privacy and rights:** real Galar input images and predictions are private. The repository has no explicit software licence. Public results do not authorize transfer of clinical materials or bypass institutional/data-use requirements.

## Most defensible next evidence step

A [blinded original-image interpretation pilot](BLINDED_SHORT_EVENT_CLINICAL_REVIEW_PILOT_20261110.md) has been prepared for **137 images covering all 69 already-inspected boundary comparisons**, with an escrowed source identity and original-label key. It is selected by native-source eligibility rather than model misses. **No expert has reviewed it, and the packet has not been distributed.** Independent qualified reviewers and a clinician-led arbitration protocol would help distinguish visible fresh blood, hematin, lookalikes, image quality and genuine temporal ambiguity, subject to authorization and ethics/data-use review. This would improve *development label interpretation*, not independently validate a model.

Only after defensible ground-truth semantics, provenance and cohort separation are established should we prespecify one task-aligned model comparison and then seek external evaluation. A successful result must improve **distinct event preservation at fixed workload**, including singleton omissions—not merely image AUC or a favorable retrospective example. A negative result remains publishable only if the design, data and analysis justify the scientific contribution; publication readiness is not yet established.

## Reproduction and evidence trail

- [Current decision and limitations](PROJECT_STATUS.md) · [active research plan](ROADMAP.md)
- [Frozen 11–20 contract](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json) · [complete primary report](GALAR_UNSEEN_11_20_RESULTS.md) · [public aggregate](../experiments/galar-unseen-11-20-20261104/aggregate.json)
- [Later controlled representation result](FROZEN_REPRESENTATION_SHORT_EVENT_RESULTS_20261109.md) · [independent replay](REPRESENTATION_TRANSFER_ERROR_PERSISTENCE_20261109.md)
- [Public source tests](../tests/test_priority.py) · [verification guide](VERIFICATION.md) · [`scripts/project_status.py`](../scripts/project_status.py)

This synthesis is a map to the original, immutable experimental reports, not an invitation to modify historical outcomes or merge incompatible evaluation populations.
