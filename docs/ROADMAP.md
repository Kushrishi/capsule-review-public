# Capsule Review — active research plan

**10 November 2026 UTC.** This document is the current decision record, not a preregistered study or a chronology of every experiment. The complete retrospective history is preserved in dated reports under `docs/` and `experiments/`. The scientific question and primary negative result are summarized in [the research synthesis](RESEARCH_COLLABORATION_BRIEF.md).

## North star

Can a human-in-the-loop review policy preserve **more distinct expert-adjudicated capsule-endoscopy events** at an **equal, prespecified review-image budget**, without concealing omissions? Frame AUC, model classification, and saved-image count are diagnostics, not substitutes for distinct event retrieval or measured reader time.

**Starting evidence:** the prespecified Galar 11–20 **10% primary** was negative (score-bin **49.35%** vs uniform **50.62%** across six positive-run examinations). Its **25% secondary** contrast was favorable but heterogeneous. No clinical model was promoted. Do not reinterpret examined 11–20 as untouched or open the authors' reserved 61–80 without a separate ethical, provenance and study decision.

## Stage A — make existing research independently understandable (current)

- Present a readable README, one scientific synthesis, a concise status, stable run instructions and a small set of authoritative links. Avoid a growing lab notebook on the front page.
- Keep all frozen protocols, source receipts, independent checks, unsuccessful results and their original dates unchanged. Preserve code/scripts required to replay them; use Git history and archival context for older mutable plans.
- Separate *core application* from *historical research utilities* in navigation. Review legacy manual GitHub Actions and optional dependencies separately before retiring anything; do not delete workflows until their dependencies and data-access safeguards are verified.
- Exit: an unaffiliated engineer can understand the software and negative evidence quickly and reproduce synthetic behavior without any private medical source data. Documentation and architecture cleanups must not weaken privacy gates or tests.

## Stage B — improve clinical interpretation evidence (next scientific dependency)

- The **11,147 original selected images / 16-examination** audit showed severe positive-event concentration. Source bytes are verified, but patient linkage, certain device IDs and complete original-video annotation coverage are not. [Group/source readiness](GALAR_GROUP_AND_FOLD_READINESS_20261105.md).
- A [private, blinded 137-image, 69-boundary-pair pilot](BLINDED_SHORT_EVENT_CLINICAL_REVIEW_PILOT_20261110.md) is prepared. First confirm local browser usability, source rights and ethics/institutional permissions. With user authorization, seek two qualified capsule-endoscopy reviewers and blinded, independent classification of fresh blood, hematin, visual lookalikes, quality and need for temporal context. Keep unblinding information separate; expert disagreement requires adjudication.
- Seek authenticated source/exam/patient grouping where practicable, but time-box metadata requests. If patient linkage cannot be established, use **examination-separated exploratory** language only and seek other qualified external material.
- Exit: a validated label ontology and adjudication plan, with concrete group/rights evidence. **No synthetic review or retrospective label agreement can replace actual clinician input.**

## Stage C — one scientifically justified model/selection experiment (conditional)

- Only start if Stage B identifies adequate original-image support and a new, defensible target and outcome protocol. **No repeat seed/architecture sweeps** on the same inspected 69 runs, no tuning against Galar 11–20 outcomes.
- Compare deterministic uniform, original compact CNN, an appropriate simple non-ML baseline and *one* qualified, independently pretrained endoscopy-domain representation if licences, preprocessing, and no training-label overlap can be verified. CapsuleAudit anomaly weights trained on overlapping Galar studies are **not** an independent comparator on those cases.
- Lock data identity, group separation, masks for `unknown` annotations, preprocessing, exact-*K* budgets, short/singleton run metrics, seeds and advancement/stopping gates **before** outcome inspection. Require event-preservation improvements, not AUC alone. Report per-case failures and abstentions.
- Exit: a replicated improvement on qualified development data or an informative negative result; **neither implies clinical efficacy**.

## Stage D — independent medical evidence (long-term)

- Obtain an external or separately adjudicated set with complete source chronology, relevant target-event coverage, permitted retention, patient/case grouping and a formal provenance lock. Published sparse label subsets cannot be treated as exhaustive negative frames. [External qualification requirements](EXTERNAL_COHORT_QUALIFICATION_20261104.md).
- Prespecify the external 10% primary and 25% secondary workload comparison, report omission harm and confidence at the true independent group level, then consider a clinician-reader study measuring actual time and lesions/events missed. Independent expert review and any required ethics/data-use approval precede clinical interpretation.
- Stop and publish negative evidence honestly if the target does not generalize. Never convert an image-budget percentage directly into a claim of physician time savings.

## Decision discipline

A new PR or experimental run must either (i) remove a documented reproducibility/security defect, (ii) unlock a verified data or clinical-reference-standard gate, or (iii) deliver a prespecified, interpretable performance result. Do not equate PR count, generated files, model fits, extra archives or synthetic test count with scientific progress. The codebase is a **research workbench**, not a clinical decision-support device.
