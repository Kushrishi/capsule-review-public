# External independent-cohort evidence-preservation replication — **conditional design draft**

**Written:** 2026-11-04. **NOT registered, locked, approved, powered, or run.** No external images, clinical outcome annotations, individual patient records, checkpoint weights or scores were accessed to prepare this draft. The external source and frame/label eligibility are **not yet established**; see [dataset qualification](EXTERNAL_COHORT_QUALIFICATION_20261104.md).

## Research objective

Test externally whether the **unchanged original CNN score-per-chronology-bin (score_bin)** policy preserves a greater mean fraction of **distinct visibly blood-positive annotated source runs** than deterministic **uniform** selection at the **same per-examination 10% workload**. This is an examination/run-coverage question, not patient-level lesion sensitivity or physician-time reduction.

The completed Galar 11–20 comparison (November 4, 2026) is historical, already evaluated and must remain untouched: 10% score-bin minus uniform = **−1.2668765 percentage points**; 25% secondary = **+9.5106442 percentage points**, heterogeneous and heavily influenced by examination 15. No external outcome access or threshold/model changes are permitted merely to improve those findings. The authors' Galar 61–80 remain closed.

## Unresolved fields that block locking this draft

- Independent named dataset, version, video identities, device/system, acquisition site, permissible use, deidentified patient/examination grouping and duplicate-case checks.
- Confirmation of continuous source-video candidate frames and **exhaustive** observation/label-status or expert complete-event boundaries for each eligible input position. Explicit unknown-label handling and event annotation completeness are compulsory. Published Kvasir's selected annotated segments do not satisfy this as-is.
- Clinically signed mapping of external blood category(s) to a single visible-blood frame target. Fresh blood, hematin, vascular findings, active bleeding and normality must not be conflated by convenience.
- Original native consecutive-frame/run definition (e.g., consecutive decoded frame numbers), source gaps, sampling rate, software version and effects of video encoding. Never force Galar's +5 spacing on another dataset.
- Adequacy of independent positive-run patient/examination units, zero-positive-case policy, and an **a priori** sample-size/precision calculation. Data availability is not a substitute for sample-size justification.
- Permissions and durable capacity for privately retaining originals, original checkpoint, per-frame score stream, pre-outcome selection package, hashes, audit logs and reports. No source data in public GitHub or Actions.

**Hard stop:** Do not represent this proposal as preregistered or execute it until all unresolved fields are filled in a separately dated, externally anchored protocol **before external outcome access**.

## Planned fixed comparison, conditional on qualifying data

- **Model:** the original, unmodified capsule-cnn-v1 epoch 8 checkpoint; weights SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`. RGB 96×96, original aspect-preserving padding, 0–1 channels, uncalibrated blood softmax. Exact code/driver/preprocessing hashes must be frozen and checked before scoring; no retraining or model selection.
- **Policies:** existing production uniform, highest-score, score-with-separation, and score-bin. Comparison at identical within-examination exact K, no use of clinical labels or reviewer notes to generate rankings. No algorithmic change or budget-dependent retuning.
- **Workloads:** 10% prespecified **primary**; 25% prespecified **secondary**, plus 5%, 50%, 100% descriptive/technical checks if eligible. For integer p and N eligible source positions: `K = min(N, max(1, floor((N*p+50)/100)))`. A review budget is an image count, not time; queue selections at different K need not be nested.
- **Primary endpoint:** for each examination with at least one confirmed positive annotation run, number of distinct eligible blood-positive runs containing a selected image divided by its total eligible blood-positive run count; compute paired (score-bin − uniform) per-examination recall at 10%, and average equally over **defined positive-run examinations**. Report the signed difference in percentage points (negative counts as failure). If the patient grouping contains repeat examinations, separately prespecify a patient-clustered analysis and do not describe examination-level results as patient-independent.
- **Secondary:** same paired 25% run recall (explicitly non-primary); all-policy results at other workloads; positive-frame hits; pooled run counts with denominator; 1–5, 6–25 and 26+ annotated-row run strata if clinically/technically applicable after harmonization; source-position omitted-span maxima; zero-positive-case technical results. Do not call annotated runs unique lesions.
- **Negative and unknown:** zero-positive examinations have **undefined** positive-run recall, never zero or 100%. Missing or unannotated positions are unknown, not negative. A gap never bridges a run. If complete eligible population cannot be proven without outcome-dependent selection, **stop** or write a new pre-outcome amendment; do not silently exclude cases or substitute sampled images.
- **Independent inference:** freeze the cohort, native-frame eligibility, source hashes, all score streams and each of the four exact-K policies before outcome inspection; put master SHA and independent trusted timestamp/commitment outside the worker; verify and read back; then unseal **only** approved external outcomes. Keep raw pixels, patient groupings, individual annotations, scores, checkpoints and receipts private. Record any worker that processes masked clinical fields accurately rather than claiming a stronger blinding design.
- **Independent audit:** verify source codec/frame identity and input integrity, replay all original queues and exact-K choices, independently reproduce every examination × workload × policy endpoint; retain all failures and any source-denominator mismatches. Clinical-label policy mapping must be frozen in advance.
- **Statistical interpretation:** report each eligible examination, signed paired differences and between-examination variability. Only use patient-clustered uncertainty intervals if patient IDs, enough independent clusters and an exchangeability justification exist; otherwise provide descriptive estimates without patient-level confidence claims. Plan precision/power **before** outcome access; do not select a favorable workload or filter cases by results.

## Analysis sequence and safeguards

1. Get custodian's **written** technical/ethics/data-use answers and establish complete, independently separated source sequences with documented label coverage. No large downloads until feasible.
2. Prepare a dated **final** design and independent timestamp including source IDs, ontology, run adjacency, denominator, missingness, sample-size target, analysis code versions, source licenses, private retention strategy and full exact-K policy hashes. Outcome access forbidden until freeze.
3. Acquire under permission into a private workspace with ample durable storage; verify every intended frame and retain byte hashes/identity while keeping clinical outcome labels concealed. Any departure from complete approved inputs is a stop.
4. Execute the original frozen CNN only once per source frame, lock all predictions and policy snapshots, verify externally anchored commitment.
5. Authorize outcome release, compute fixed primary and secondary statistics, run independent numerical audit and preserve originals/receipts. Publish **only** nonidentifying aggregate result and documented limitations after privacy review.
6. Report negative results, case variability and all missingness; do not claim diagnosis, clinical validation, safety, efficiency or publication readiness.

## Interpretation criteria

A positive 10% paired examination-level difference in a correctly qualified new cohort would be **evidence of better retrospective annotated-run coverage at equal image workload**, not a claim that physicians miss fewer lesions or read faster. A negative, zero-support, incomplete-label or non-independent cohort must be reported transparently; a favorable 25% secondary result cannot replace the 10% primary result. Dataset/domain shift (capsule type, color, illumination, source encoding and annotation standard) may affect the unchanged model, but cannot be assumed causal without a separate prespecified investigation.

## Current decision

**NO-GO for acquisition, training or new outcome testing as of 2026-11-04.** The next actionable dependency is a dataset-custodian confirmation of exhaustive blood-annotation availability and patient/examination grouping, prioritized for [Kvasir-Capsule](https://datasets.simula.no/kvasir-capsule/). If those gates fail, the proposed external replication is presently infeasible and must not be replaced by a superficially similar sparse-image benchmark.
