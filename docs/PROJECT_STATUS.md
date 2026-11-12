# Capsule Review — current research status

**As of 12 November 2026 (UTC).** The outreach wording below has been clarified; the scientific evidence and clinical-review requirements are unchanged. See the [research synthesis](RESEARCH_COLLABORATION_BRIEF.md) for methods and interpretation; use [`scripts/project_status.py`](../scripts/project_status.py) to independently check a selected subset of frozen public aggregates.

## Decision

**The viewer works, and the locked 10% comparison favored uniform sampling.** Further refinements on already inspected Galar runs would not constitute new independent evidence. No pathology model is promoted, and clinical reading-time savings have not been measured.

**Clinical-review recruitment and packet distribution remain paused** pending verified data-use requirements and an authorized reviewer plan. Academic inquiries based on public code and aggregate results are a separate owner decision; they do not authorize private-image sharing or clinical review.

## Current evidence

| Evidence | Result | Valid interpretation |
| --- | --- | --- |
| [Locked Galar 11–20 evaluation](GALAR_UNSEEN_11_20_RESULTS.md) | **163,161** original verified images; **10% primary** score-bin run recall **49.35%** vs uniform **50.62%**, paired mean **−1.2668765 pp** across six positive-run exams | No primary benefit. Four zero-positive exams have undefined positive-run recall. Patients and lesions are not independently authenticated. |
| [Secondary locked workload](GALAR_UNSEEN_11_20_RESULTS.md) | **25%** paired difference **+9.5106442 pp** | Heterogeneous secondary result, not confirmatory efficacy. |
| [New short-event foundation](SHORT_EVENT_FOUNDATION_RESULTS_20261109.md) | 69 source-native positive–negative boundary comparisons, 21 singleton runs, four already inspected development exams | Useful for mechanism diagnostics; not a full-source 10% test or a new holdout. |
| [Matched frozen MobileNet representation](FROZEN_REPRESENTATION_SHORT_EVENT_RESULTS_20261109.md) | Held-out pair ordering **50.94% classification / 49.08% ranking**, below compact CNN **63.77% / 72.29%** | Failed all predefined advancement gates. Different preprocessing and model packages prevent causal encoder attribution. |
| [Independent error replay](REPRESENTATION_TRANSFER_ERROR_PERSISTENCE_20261109.md) | MobileNet heads ordered 100% of training pairs but near chance across excluded exams; many errors persisted in all seeds | Generalization concern, not an identified device/patient cause. |
| [Source/group integrity](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) | **11,147** selected verified originals across **16 examinations**; positive references concentrated in few exams | Source bytes are checked; patient independence, exhaustive event annotations and source domains remain unverified. |
| [Blinded clinical-review pilot](BLINDED_SHORT_EVENT_CLINICAL_REVIEW_PILOT_20261110.md) | 137 original images prepared in private, blinded form for two expert reviewers | **Not clinically reviewed.** No expert-adjudicated reference standard or new medical performance result yet. |

At the locked 10% budget, highest-score ranking found **305 positive annotated frames but only 28/154 positive source runs**; uniform found **170 positive frames across 63/154 runs**. This divergence motivates the project. It does not mean each annotated run is a distinct lesion.

## Working software

Local import and navigation; human notes, bookmarks and interval annotations; score import; four historical deterministic exact-*K* selectors and one experimental guarded policy; skipped-position inspection; evidence export and receipt checks; automated API/browser/source-boundary tests. The [public demonstration](SUPERVISOR_DEMO.md) is synthetic, not a deployed medical AI. No trained pathology model is distributed or promoted.

## What is blocked

1. **Clinical meaning of short events:** blood/hematin/lookalike distinctions and short-run reliability need qualified, authorized independent reviewer adjudication. The prepared 137-image packet remains private and undistributed.
2. **Evaluation independence:** Galar examination IDs have no verified unique-patient mapping; studies 11–20 are already inspected and the dataset authors' **61–80** outcomes remain unopened. [Original group audit](GALAR_GROUP_AND_FOLD_READINESS_20261105.md).
3. **A genuinely comparable external corpus:** full chronology, defensible grouping, exhaustive blood-event reference labels, permissions, source integrity and enough positive cases remain unqualified. [External screen](EXTERNAL_COHORT_QUALIFICATION_20261104.md).
4. **Actual clinical benefit:** no reader-time, lesion-level diagnostic sensitivity, or prospective clinical safety study has been performed.

**Next scientific decision:** hold model sweeps. Improve research readability and technical reproducibility; then qualify reviewer participation and event ground truth before a prespecified model-development or independent external study. See [the active plan](ROADMAP.md). All original experimental reports, positive and negative, remain in `docs/` and non-identifying aggregates remain in `experiments/`.
