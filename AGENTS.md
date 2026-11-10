# Working on Capsule Review

This public repository contains a **local research viewer** plus a historical, versioned scientific record. It is not a validated medical device. Start with [README](README.md), [scientific synthesis](docs/RESEARCH_COLLABORATION_BRIEF.md), [current status](docs/PROJECT_STATUS.md) and [active plan](docs/ROADMAP.md).

## Preserve evidence and safety

- **Never claim clinical benefit without independent clinical evidence.** The locked Galar 11–20 **10% primary** showed no advantage over uniform sampling. An annotation run is not a verified lesion; an image-review budget is not measured clinician reading time. No model is promoted.
- Keep real medical images, individual labels, model scores/checkpoints, private source manifests and patient-related metadata **out of public Git and CI**. Do not upload, publish or email medical images on behalf of the user without explicit authorization and verified data-use requirements.
- The authors' original Galar **61–80** reserved outcomes remain unopened. Do not retune against inspected 11–20 or reuse them as an untouched holdout. Examination-disjoint is not authenticated patient-disjoint; unknown labels remain unknown.
- Original dated reports, frozen experiment locks and aggregate outcomes (including negative results) are scientific records. Do not overwrite, delete, quietly relabel or move them in a way that breaks verification. Mutable status/roadmap summaries may be shortened, with history retained in Git.

## Engineering priorities

- Maintain a readable **core viewer** under `src/capsule_review/` and treat most `scripts/`, `docs/` and `experiments/` as *historical research utilities/evidence*, not current model pipelines.
- **Do not generate another roadmap, audit or documentation-only PR merely to show activity.** Each change needs a specific verified defect, meaningful usability improvement, approved data gate, or prespecified scientific question. Prefer consolidating existing entrypoints over adding files. Avoid speculative model/seed sweeps on previously examined sources.
- Preserve an offline/local-only architecture. The app has no shared-user authentication or encryption, so do not turn it into a hosted clinical service.
- Keep changes scoped and reversible; use a branch/PR, pass Python 3.11–3.13 checks, browser/local-model tests and the public-source privacy gate before merging. Update `README.md` or `docs/PROJECT_STATUS.md` only when the active scientific state materially changes.
- Historic manual source-acquisition GitHub Actions are **not** an invitation to transfer protected clinical images. Do not delete or reactivate them until source/provenance, dependencies, safety and historical reproduction needs are checked.

## Authoritative records

[Original locked study](docs/GALAR_UNSEEN_11_20_RESULTS.md) · [Research question/protocol](docs/RESEARCH_PROTOCOL.md) · [Verified selected sources](docs/GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) · [Research software demo](docs/SUPERVISOR_DEMO.md) · [Public release boundary](docs/PUBLIC_RELEASE_SAFETY.md)
