# Capsule Review — adaptive scientific and product roadmap

**Decision date: November 5, 2026.** This is the **current plan**, not a preregistered clinical study, a promised schedule, or a substitute for the dated protocols in the research archive. Review it when a dependency changes or an experiment produces new evidence; preserve historical protocols/results.

## Mission and definition of success

Build a **research-grade, auditable, human-in-the-loop capsule-endoscopy review system** that (a) helps prioritize meaningful evidence without hiding skipped frames, (b) preserves distinct expert-annotated events at a measurable review workload, and (c) generalizes to truly independent examinations and, ultimately, supports a properly designed human reader study.

**Research north star:** higher *expert-adjudicated distinct-event retrieval under equal, prespecified review effort*, with transparent misses and patient/exam-level uncertainty. Frame/image ROC-AUC and recall@K are supporting diagnostics; a reduction in images selected is **not** measured clinician time savings. No clinical effectiveness claim until appropriate independent and reader evidence exists.

**Current reality:** a working viewer and completed negative 10% Galar run-recall primary, plus mixed/negative development CNN and pretrained-representation tests. [Current evidence](PROJECT_STATUS.md) is the canonical human guide; `python scripts/project_status.py` checks the numerical record.

## What the field has already demonstrated, and what we can borrow

| Comparable, primary source | Demonstrated approach | Appropriate Capsule Review adoption / difference |
| --- | --- | --- |
| [CapsuleAudit, MICCAI 2026](https://papers.miccai.org/miccai-2026/0188-Paper0867.html) | Endoscopy-pretrained CNN features + temporal transformer for anatomy and anomaly monitoring; reports ~90% anatomy macro F1 and ~67% binary anomaly macro recall on Galar | **Test a simple temporal baseline and, conditionally, an endoscopy-domain encoder** once dense eligible source sequences exist. Match tasks and splits before any numerical comparison; these are not our event-retrieval metrics |
| [SEE-AI, 2026 multicentre reader study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13177839/) | 249 examinations, six hospitals, crossover readers, lesion/patient sensitivity and actual reading time | **Design toward clinician-adjudicated event and time endpoints** later. Our local prototype, image-count budgets and run labels are not equivalent evidence |
| [Kvasir-Capsule, Scientific Data 2021](https://www.nature.com/articles/s41597-021-00920-z) and [official splits](https://github.com/simula/kvasir-capsule/tree/master/official_splits) | 117 videos, 47,238 labelled images, many unlabelled frames; public reference splits and video-to-frame identities | **Reuse the idea of official source/group splits and explicit unknown labels**, not the assumption that unlabelled video frames are blood-negative. Candidate for temporal software engineering and a custodian inquiry, **not yet qualified for full-run replication** |
| [Galar, Scientific Data 2025](https://www.nature.com/articles/s41597-025-05112-7) | 80 selected pathological examinations, 3,513,539 annotated frames, multiple capsule systems and anatomical/pathological labels | Preserve native source indexing, study/device heterogeneity, label provenance and independent patient grouping. Dataset selection is pathology-enriched; original authors' 61–80 remain closed |
| [MONAI model bundle format](https://monai.readthedocs.io/en/1.6.1/bundle_intro.html) | Models tied to versioned architecture, preprocessing, inference/postprocessing and provenance metadata | Adopt **private model-card/experiment-contract metadata and hashes** without distributing our pathology weights or claiming MONAI compatibility |
| [CLAIM 2024 update](https://pmc.ncbi.nlm.nih.gov/articles/PMC11304031/) and [TRIPOD+AI 2024](https://www.bmj.com/content/385/bmj-2023-078378) | Reporting guidance for source populations, reference standards, splits, metrics, caveats and external testing | Use them as an **audit checklist**, not as proof of clinical quality or a requirement to invent missing data |

We are not copying code, weights, dataset licences or claims from these projects. Any external reuse requires independent licence/provenance review.

## Workstreams, gates and deliverables

### Stage 0 — One comprehensible, verifiable starting point

**Deliverables:** short README, canonical [status and technical map](PROJECT_STATUS.md), this roadmap, machine-derived public `project_status.py`, and an external-cohort structural gate with synthetic tests. Historical results stay immutable.

**Exit:** new contributor can run synthetic demo, read the completed negative primary and identify the next scientific blocker without browsing dozens of dated documents. All CI and public-source privacy checks pass. This makes later scientific work easier; it is **not** itself an AI-performance milestone.

### Stage 1 — Qualify development material and eliminate split ambiguity (**next scientific priority**)

**November 5 checkpoint:** byte verification is complete for all **11,147** retained selected originals. See [source audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md). The [November 5 group/fold feasibility follow-up](GALAR_GROUP_AND_FOLD_READINESS_20261105.md) found that **90.5% of uniform-reference positive images** occur in four source examinations, and only **8/16** selected source examinations have documented capsule system metadata. Source authors' published split script groups by **video**, not an authenticated patient ID. Build/train only under explicit **examination-separated exploratory** language until independent patient linkage is verified.

The next gate is **NOT passed**: no verified independent patient grouping, no exhaustive visual-near-duplicate adjudication and no complete event-label coverage. The [second-stage coarse-collision triage](GALAR_VISUAL_SIMILARITY_TRIAGE_20261105.md) found no strict pixel-aligned close copies among 5,293 candidates, but this does not establish group independence. Use [the offline verified-source preflight](../scripts/check_development_cohort.py) when a new private manifest is available. This is a measurable step toward better AI, not an accuracy result.

**Build:** one private, checked inventory of available fitting/development examinations and image/video identities; label coverage states *positive / negative / unknown*, patient/exam grouping where available, device/source domain, positive-run distribution, partial/truncated sequence flags, consent/licence, deduplication and retention. The already described **11,147-image 16-examination fitting inventory** is not automatically eligible for any proposed task: recheck source grouping and what is actually labeled. Keep source pixels and patient groups private.

**Acceptance:** a fixed **development-only cohort manifest** plus an executable leakage/annotation preflight; failures and small positive-run support explicitly counted; training/selection/evaluation group identities checked. First choose independent-group units where defensible; if patient grouping is unverified, say examination-separated only.

**If blocked:** stop new training comparisons and prioritize authoritative source metadata or adjudication. Do **not** relabel unknown as blood-negative to increase sample size.

### Stage 2 — Build a *fair, hard-to-game* AI benchmark

**November 5 development finding:** the [matched 16-exam class-weighting comparison](GALAR_EXAM_TEMPERED_CNN_RESULTS_20261105.md) trained eight real CNN checkpoints and found **no benefit on its predefined 10% mean examination-positive-image recall endpoint**. That eliminates a simple examination-tempered loss fix on the current, already inspected pool. Further training-exponent/epoch sweeps on the same cases would be posthoc; prioritize **new positive-examination diversity and authentic source/patient grouping** instead.


**Build:** one standardized training/evaluation harness, with frozen task semantics, splits, source hashes, model identity, preprocessing, budgets, seeds, exact-K tie policy, and a model card/receipt per candidate. No repeated tuning against the already inspected Galar 11–20 or original authors' 61–80.

**Minimum comparison:** uniform / existing original CNN / a simple transparent colour or linear baseline / an endoscopy-relevant pretrained encoder **only if rights and input compatibility are established**. A compact temporal smoothing or 1-D sequence model is warranted **only on verified consecutive sequences**; sparse 512-frame references must not masquerade as dense temporal videos. Use a simple temporal baseline before a transformer. No automatic increase in architectures just because a prior model failed.

**Metrics and gate:** report **per examination**, not just pooled: ROC-AUC, average precision, positive-image hits at prespecified 5%/10%/25% image budgets, distinct annotated-run recall **only where exhaustive event truth actually exists**, longest skipped source-position span and uncertainty conditioned on real independent groups. Note zero-positive and missing-label cases separately. A model whose AUC rises but AP or early retrieval collapses is **not automatically better**. Freeze the candidate choice using development folds before external outcome access.

**If blocked or mixed:** run error-taxonomy/shortcut analysis (colour, device, anatomy, long versus short events, domain shift) on *training/development* data, or improve labels/group diversity. Do **not** promote the best of many retries as independent evidence.

### Stage 3 — Improve evidence-aware selection and review ergonomics

**Build:** use uncertainty/context and temporally aware candidate scores when supported by data; compare against fixed-K uniform and the four historical policies. Keep the fifth gap-guarded candidate **experimental** until real benefit is measured. Surface source-coverage warnings, original frame identity, missing/unknown regions, selected-run rationale and the ability to inspect all omitted frames. Preserve human notes separate from suggestions; never auto-label or hide omitted images.

**Engineering gate:** exact-K, deterministic replay, no label leakage, safe receipt/export verification, complete browser/API synthetic tests, credible performance with longer source sequences. **Scientific gate:** no event-level claim from ordinal gaps or sparse image references.

### Stage 4 — Independently qualify and lock an external study

**Dependency:** written permission, demonstrably independent source/grouping, complete chronological frame identities, **exhaustive clinically meaningful target-event annotations or adjudicated event boundaries**, ontology mapping, native event-run definition, enough positive-group support, durable private originals and audit receipts.

Run the local metadata-only `python scripts/check_cohort_gate.py /private/worksheet.json`. It **blocks** absent evidence; even all ten structural gates returning pass means **human review required**, not data rights or study approval. Then finalize a separately dated, independently timestamped study protocol and power/precision plan **before outcome access**. Use the existing [dataset screen](EXTERNAL_COHORT_QUALIFICATION_20261104.md) and [conditional draft](EXTERNAL_REPLICATION_DESIGN_DRAFT_20261104.md), not a new unreviewed 10% post-hoc benchmark.

**If Kvasir remains sparsely labelled:** use its video sequences only for permitted engineering/pretraining tasks; request full annotation coverage, fund a feasible blinded annotation study or select a different source. Do not call the sparse subset exhaustive.

### Stage 5 — Clinical collaboration and reader-centric testing (**long-term, contingent**)

With appropriately approved data and expert participation: define real lesion/event reference standards, reader randomization/crossover design, expected patient/case distribution, omissions, sensitivity, inter-reader variation, actual reading time and adverse missed findings. Investigate whether AI adds value to the clinician's real workflow, not just an image-ranking metric.

**If the external primary fails:** publish the negative result and reframe the scientific conclusion; the auditable viewer and methodology remain valuable. **If it succeeds:** replicate across device/site subgroups, measure uncertainty and perform a prospective reader study before any clinical claim. Neither outcome authorizes unattended diagnostic deployment.

## Rules for selecting the next task

Choose work in this order: **(1) validity blocker, (2) measurable AI or evidence-preservation gain, (3) reviewer usability/security, (4) packaging/documentation.** Every substantial PR must state its hypothesis, acceptance/failure criteria, verified source scope, protected-data boundary and what changed versus the current baseline.

| New information | Change in plan |
| --- | --- |
| No group independence or exhaustive labels | **No-go** for external event-coverage test; qualify/adjudicate first |
| Model improves AUC but loses AP or retrieval | **Do not promote**; run fixed error analysis and examine the training objective |
| Strong model on one exam but collapses on others | Prioritize domain shift, data diversity, group-level robustness, not another favorable average |
| Complete eligible sequences become available | Trial a simple temporal baseline, then compare a temporal encoder fairly |
| Only sparse video frames available | Work on software, self-supervised features or *explicit sparse-label tasks*, not full-event recall |
| Clinical reviewer collaboration becomes possible | Prioritize reference-standard/reader-protocol design over additional model experiments |
| Original raw data/receipts cannot be retained | Treat the proposed evaluation as **blocked**, even if compute is available |

## Research quality and repository controls

All future studies should carry a privately retained immutable **experiment contract**: question, reference-standard definition, rights and data version, grouping/splits, preprocessing and model weight SHA, frozen code commit, candidate list, tuning boundary, exact-K rules, handling of missing outcomes, endpoints and uncertainty, irreversible-outcome access log, full source/checkpoint/selection/score receipts, and independent replay. Publish non-identifying aggregates and negative findings only.

Keep `main` stable via required tests/privacy checks and reviewed changes. Before an ordinary open-source release, decide code ownership, a software licence and third-party weight/dataset licences. Do not weaken localhost-only security or host private patient data. Follow [AGENTS.md](../AGENTS.md) for technical/privacy boundaries.

**Single next execution priority:** Stage 1, a reproducible development-cohort/split/annotation-coverage audit; **not** another arbitrary CNN candidate, outreach email, or new download. This is the dependency most likely to unlock legitimate AI progress.
