# Capsule Review: pathology evidence-preservation pilot

**Protocol draft v0.1 — 2026-11-01.** This is a prospective *design for the next experiment*, not a registered trial, a clinical validation, or a claim of methodological novelty. It was written after the existing anatomy baseline and after inspection of examinations 1–10. The existing anatomy benchmark is unchanged.

## Why this task

The intended application helps a human reviewer find important material in a long capsule examination. The present model instead classifies anatomical regions, and its 68.36% development accuracy is below a majority-class comparator. Anatomy classification proves the data → model → viewer integration, not pathology detection or a reduction in missed findings.

Our next **candidate** target is the single Galar `blood` annotation. It means *blood visible in a labelled frame*; it is **not** equivalent to active bleeding, a uniquely identified lesion, a clinical diagnosis, or a hemorrhage severity grade. A `0` for this label is not proof of a clinically normal frame. We are **not** pooling `blood`, `active bleeding`, `hematin` and vascular-lesion labels without clinical justification.

**Question:** Within previously unseen examination sequences, can a model-based ranking and subsequent temporal grouping cover a higher proportion of *contiguous blood-positive annotation runs* at an equal review budget than outcome-blind sampling or ungrouped image-score ranking?

This is a candidate comparative research question. Strong existing methods already study temporal anomaly detection and clinical evidence selection; any novel contribution remains to be established. A negative result is acceptable.

## Scope and outcomes

- **Evaluation unit:** examination. We cannot claim patient-independent results without a verified patient-group identifier. Do not split neighbouring frames randomly.
- **Review budget:** percentage of *annotated positions in each examination*, not estimated clinician minutes or original video seconds. Primary operating points: **5%, 10%, and 25%**. No budget is tuned on held-out evaluation labels.
- **Primary research endpoint:** proportion of contiguous positive `blood` annotation runs intersected by selected review frames, with a run defined as successive positive annotated rows whose source frame IDs differ by the observed stride of five. This is **annotation-run coverage**, not lesion sensitivity.
- **Primary comparison:** paired per-examination performance at equal budgets. Report both pooled run coverage and a macro average across positive examinations. Examinations without a positive run have undefined run recall, not a perfect score; report their selected workload separately. Always stratify by annotated-run length: prolonged positive stretches make frame-level retrieval much easier than short stretches, and one continuous run may represent the same underlying condition throughout.
- **Secondary:** positive annotated-frame coverage, total selected positions, distribution of run lengths, false *blood-label* prioritization workload, and examination-level variation. If predicted scores exist later, add PR-AUC, calibration and score distribution, but do not call softmax values clinical risk probabilities.
- **Uncertainty:** if enough independent examinations become available, use confidence intervals resampled by examination, never by correlated frames. Multiple random seeds quantify algorithmic sampling variability, not extra patients.

Only annotated positions with an explicit `0` or `1` for the selected label are eligible for label-dependent evaluation. Absent/blank annotations are **unknown**, not negative. Uneven original frame indices and missing sections cannot be silently filled. Uniformly sampled snapshots are **not** complete recordings.

## Baseline ladder (no architecture search yet)

1. **Full annotated-sequence inspection ceiling:** 100% review positions, for reference only, not a useful triage method.
2. **Deterministic uniform sampling:** image-label-blind, equal percentage per examination. Use the same fixed index rule at all budgets.
3. **Seeded random sampling:** 100 label-blind draws per examination per budget, fixed seed 17; report the distribution rather than selecting the luckiest draw.
4. **Simple image score:** only if adequate labelled *training images* and split integrity are verified; start with a transparent image/color-feature comparator and a compact trained binary model. Treat red-toned artifacts as a possible confounder.
5. **Unsmoothed image ranking versus temporal intervals:** select at identical annotated-position budgets, count interval expansion against the same budget, and prespecify any overlap/merging rules on fitting/development data.
6. **Optional uncertainty/defer policy:** investigate only if failure analysis motivates it; compare to an ordinary score threshold and disclose the proportion of uncertain material not prioritized.

Avoid performance fishing on examinations 9–10: they were already used for anatomy checkpoint selection and inspected during the follow-up analysis. They may support a **historical integration demonstration**, not a newly independent confirmatory result.

## Data and split gates

- **Source:** corrected Galar v2 labels, `20251215_Labels_Updated.zip` (the authors' December 2025 correction). Record official file IDs, source hashes, capsule device, and exam IDs. The current preliminary audit reads **only fitting examinations 1–8**; no reserved exams were opened. The published aggregate is verified against a separately retained corrected-release receipt containing the official file 60383963 digest and per-CSV SHA-256 records; only a trusted receipt provides meaningful source assurance.
- **Reserved holdout:** the source authors' examinations **61–80** remain unopened. Their original study held these 20 examinations out from 1–60 and reports that this group came from a separate practice. Do not quietly repurpose them.
- **Before any new images or pathology-model fit:** establish a fixed, documented examination-level fitting/selection/locked-evaluation assignment within permitted 1–60 cases, using acquisition/device metadata rather than evaluation pathology outcomes; check possible shared patients if a reliable mapping becomes available. If the locked cohort has no positive runs, report that limitation instead of reshuffling test cases post hoc.
- **Current data limitation:** we have 512 images per examination for IDs 1–10, not dense image sequences. A label-only run audit is possible now; model-based interval selection and full-review benefit are not. More images may require ~30 GB archive-scale acquisition, and the default 512 MiB transfer cap must not be raised without approval.
- **Class feasibility:** the current 1–8 sampled images contain no `active bleeding` positives; therefore do not fit an active-bleeding classifier on them. `blood` has positive training images across multiple examinations but is extremely concentrated in examination 7. Report both label count and distinct-examination support.
- **Technical label coverage:** Galar image-quality columns are not present on all examinations; missing technical-quality fields cannot be assumed to mean clear view.

## Acceptance decision before expensive work

Advance to a pathology-image baseline only when: (a) source provenance and permitted data use are verified, (b) a locked split is documented before outcome inspection, (c) fitting examples span multiple independent examinations, (d) there is a feasible way to obtain dense review sequences or the endpoint is explicitly narrowed to sampled images, and (e) an image-label alignment and source-frame-gap check passes. Failure of any gate is a **stop/pivot**, not permission to cherry-pick exams or test results.

No autonomous clinical diagnoses, hidden-frame recommendations, prospective clinical claims, actual reading-time reduction, patient-level lesion sensitivity, or automatic medical reporting are part of this pilot. The local viewer remains research software without protected-patient-data security controls.

## Existing competitive work and boundaries

| Source | Evidence | Design implication |
| --- | --- | --- |
| [Galar, *Scientific Data* 2025](https://www.nature.com/articles/s41597-025-05112-7) and [authors' code](https://github.com/EKFZ-AI-Endoscopy/GalarCapsuleML) | 80 pathology-enriched videos, 3,513,539 labelled frames, multiple capsule systems; 60 development / 20 held-out studies and supervised CNN baselines | Model ranking is not new; examination-level and device/site shift matter |
| [CapsuleAudit, MICCAI 2026](https://papers.miccai.org/miccai-2026/0188-Paper0867.html) | Uses Galar for temporal anatomy and anomaly modeling; reports 90% anatomy macro F1 and 67% binary anomaly macro recall, plus edge deployment | A new temporal classifier by itself would duplicate existing work; inspect task/splits and reproduce a relevant comparator where feasible |
| [SEE-AI, *DEN Open*, May 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13177839/) | 249 examinations in a multicentre reader crossover; higher reported lesion sensitivity and lower reader time with AI cues | Human reading-time and lesion sensitivity claims require adjudicated lesion/reader evidence, which Galar alone does not provide |
| [DiCE/VideoCAP, April 2026 preprint](https://arxiv.org/abs/2604.21814) | Evidence-frame selection and diagnostic video summarization for 240 full videos | Relevant prior art for interval evidence retention; no novelty claim without direct task comparison |
| [CE Reporter, *npj Digital Medicine*, August 2026](https://www.nature.com/articles/s41746-026-03079-2) | Medical video-to-report generation | Reporting is outside this project's current scope |

These articles use different cohorts and endpoints. Do **not** compare their headline percentages with our 1,024-frame anatomy pilot as if they were on a common test set. The expected research contribution, if any, will emerge from an independently evaluated, well-controlled error/coverage trade-off, not the words “AI”, “temporal” or “uncertainty”.

## Revision rule

This v0.1 is a **protocol proposal**, not a locked registered analysis: the independent evaluation examination IDs, full-data availability, and model implementation are still open. Record changes with date and rationale **before** new images or labels are inspected. Keep the historical 2026-11-01 anatomy run frozen and separate.

## Exploratory sparse-image experiment completed (2026-11-01)

We fitted and independently replayed a single compact, binary *blood-annotation* CNN on already available sparse images, following the fixed exploratory settings in [BLOOD_IMAGE_PILOT.md](BLOOD_IMAGE_PILOT.md). Its development score does not satisfy the protocol's requirement for independent multi-examination positive cases or dense interval evaluation. It is a feasibility result, **not** a locked confirmatory test or evidence of clinical benefit. The next research gate remains acquiring an outcome-blind, examination-disjoint and dense chronological evaluation cohort before claiming improvement in finding-interval coverage.

## Historical pilot addendum — post-hoc evidence, not a protocol change

The [sparse-image annotation-run audit](REVIEW_BUDGET_AUDIT.md) reuses the existing blood-image pilot on examinations 9–10 and compares global score ranking with fixed chronological-bin selection. On exam 10, the original CNN finds 47 positive sampled frames but only 3 of 41 source annotation runs at 10% of the 512-image candidate pool; one-per-bin selection finds 24 positive frames across 11 runs. These observations were made **after development data were inspected**. They are hypothesis-generating only and do not update the main planned endpoint, unlock reserved examinations or justify claims about full-video review. Dense input and a new, blinded examination-level evaluation remain required.

## Dense-sequence acquisition gate (2026-11-01)

[The bounded-data access assessment](DENSE_SEQUENCE_DATA_GATE.md) identifies CAPTIV8 as a potential *technical* sequence-processing test, not a new per-frame Galar `blood` evaluation set. Its approximately 150-frame video snippets have inherited weak clip labels. The Range-only ZIP accessor is offline-tested, but this environment could not verify DataverseNO network access, so no new videos or independent medical data were obtained. Proceed to actual clinical-annotation-run evaluation only after securing independently labelled, examination-separated, genuinely consecutive frames under an approved transfer budget.
