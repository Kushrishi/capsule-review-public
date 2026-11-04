# Capsule Review | research collaboration brief

**Last reviewed: November 4, 2026.** Public research software and documented retrospective results; not a medical device or clinically validated AI system.

## Research question

Can AI-guided selection preserve more **distinct, clinically relevant annotated evidence intervals** than simple chronological sampling at the **same image-review workload**, while keeping omissions transparent and original evidence auditable?

The distinction matters: a model can retrieve many adjacent frames from one positive region while missing other positive regions entirely. Frame-level enrichment therefore does not by itself establish evidence diversity, lesion sensitivity or shorter physician reading time.

## Tangible research product

**[Capsule Review](https://github.com/Kushrishi/capsule-review-public)** is a localhost-only FastAPI/JavaScript research viewer with Python research utilities. It supports chronological image import, source-identity checks, human bookmarks/notes/interval marks, read-only score import, model-assisted navigation, and evidence receipts/ZIP export. Four deterministic **exact-K** selection policies can be compared at equal image counts: highest model score, score with ordinal separation, highest score in each chronological bin and uniform selection. The reviewer can inspect the longest omitted *imported-position* spans.

**[Reproducible five-minute demonstration](SUPERVISOR_DEMO.md):** 24 clearly marked generated, nonmedical frames and a deterministic **non-AI** example-score stream; no medical image archives, trained checkpoint or GPU required. An independent [public results explorer](../src/capsule_review/static/locked-results.html) displays already completed aggregate outcomes. The synthetic demo is not a replay of the actual CNN.

## Completed scientific evidence

| Study stage | What was measured | Finding |
| --- | --- | --- |
| Exploratory image ranking | Original compact blood CNN trained on sparse Galar fitting frames; historical development ranking | Pooled ROC-AUC **0.7262**, but the 239 positive fitting frames were concentrated in one examination (208/239). No independent generalization claim |
| Transfer and fitting-only cross-validation | Fixed source-examination separations, different recipes and verified provenance | Very heterogeneous rankings; some source examinations failed badly. No candidate promoted |
| **Locked Galar 11–20 evaluation, November 4** | **163,161** eligible original images across ten examinations, unchanged original CNN and four fixed policies, outcomes opened only after pre-outcome commitments | At the **prespecified 10% primary** workload, examination-weighted mean positive-annotation-run recall was **49.35% score-bin** versus **50.62% uniform**, paired difference **−1.2668765 percentage points** across six positive-run examinations. **No improvement demonstrated** |
| Prespecified 25% secondary analysis | Same policy comparison at higher workload | Score-bin minus uniform **+9.5106442 percentage points**, heterogeneous and substantially influenced by examination 15; does **not** supersede the negative primary |

At the 10% workload, highest-score selection retrieved **305 positive annotated frames** but only **28 of 154** distinct positive annotation runs; uniform retrieved **170 frames** across **63 runs**. The key observation is the divergence between image retrieval and source-annotation-run coverage. A positive *annotation run* is not necessarily an independent pathology/lesion. Four of ten examinations contained no positive annotation run and had **undefined** positive-run recall.

These results have source provenance, a frozen model/policy selection, an externally timestamped pre-outcome commitment, public nonidentifying aggregates and independent numerical reconciliation. The full original-image archive is **not durably retained**; the private handoff records verified retained prediction/checkpoint artifacts but missing original post-outcome execution receipts. [Read the locked results](GALAR_UNSEEN_11_20_RESULTS.md) and [project maturity audit](PROJECT_MATURITY_AUDIT_20261104.md).

## Research limitations and contribution

The method is transparent and falsifiable, **not demonstrated to outperform uniform sampling at its primary endpoint**. Patient independence, complete lesion adjudication, external generalization, calibrated probabilities, clinician reading-time effects and clinical safety are unverified. Labels, images, per-frame predictions and model weights are private; public software ships **no trained pathology model**.

A defensible contribution is an auditable **evaluation framework for evidence-interval preservation and omission** rather than a claim to have invented AI capsule-endoscopy diagnosis. The question of comparative novelty remains open pending methodologically aligned prior-art benchmarks.

## One priority for future collaboration

An independently sourced, sufficiently sized capsule-endoscopy cohort with **complete chronological images and exhaustive expert-reviewed blood-positive event coverage**, patient/examination grouping and permission for private research processing is required before an unchanged-model external replication. Predefine the native source run unit, annotation ontology, 10% primary/25% secondary endpoints, durable storage and provenance **before** any outcome access.

The currently [qualified-dataset screen](EXTERNAL_COHORT_QUALIFICATION_20261104.md) identifies Kvasir-Capsule as a candidate to **ask about**, not a confirmed valid replication corpus; its published labels cover selected segments. No new experiment has been launched and the Galar authors' reserved 61–80 outcomes remain unopened.

**Useful entry points:** [Demonstration](SUPERVISOR_DEMO.md) · [Complete locked report](GALAR_UNSEEN_11_20_RESULTS.md) · [Scientific maturity assessment](PROJECT_MATURITY_AUDIT_20261104.md) · [Source code](https://github.com/Kushrishi/capsule-review-public).

*Public availability is not an open-source software licence: the repository currently has no software licence. No medical records, sensitive images, individual predictions or source annotations are included in this brief.*
