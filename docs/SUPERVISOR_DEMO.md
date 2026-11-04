# Capsule Review — reproducible research demonstration

**November 4, 2026. Audience:** prospective biomedical-engineering collaborators, research supervisors, technical reviewers. **Runtime after installation:** about five minutes of guided interaction. **Data:** generated, nonmedical examples plus previously published, non-identifying Galar aggregate results. **No checkpoint, medical archive, clinical account, training, GPU or external service required.**

This is a demonstration of the **research software**, not a demo of clinically functioning pathology detection. A *real* original blood CNN was trained and retrospectively evaluated in private research experiments, but no pathology model weights or individual medical outputs are shipped in this repository. Generated sample numbers are **not produced by that CNN**.

## A. Run the complete synthetic workflow

Use a dedicated local workspace so real images, old data and clinical records never enter the demonstration. The command-line `demo` operation is repeatable; reopening the same built-in fixture does not create another sample study, overwrite human reviews or duplicate its example score run.

Requires Python **3.11+**, Git and a browser. From a fresh source clone:

**macOS / Linux**

```bash
git clone https://github.com/Kushrishi/capsule-review-public.git
cd capsule-review-public
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
capsule-review --data-dir ./demo-workspace demo
capsule-review --data-dir ./demo-workspace serve
```

**Windows PowerShell**

```powershell
git clone https://github.com/Kushrishi/capsule-review-public.git
cd capsule-review-public
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\capsule-review.exe --data-dir .\demo-workspace demo
.\.venv\Scripts\capsule-review.exe --data-dir .\demo-workspace serve
```

Open **http://127.0.0.1:8765** on the same computer. The server binds to `127.0.0.1`, stores the generated example under the explicitly chosen demo workspace, and makes no remote medical inference requests. **Keep this application localhost-only**; there is no multiuser authentication and workspace files are not encrypted. A new user can instead omit the CLI `demo` step and click **Open test sequence** in the browser.

### Five-minute guided walkthrough

| Order | What to do in the browser | What it proves | What it does **not** prove |
| --- | --- | --- | --- |
| 1 | Select **Test sequence** in the examination list (or **Open test sequence**). Browse several of 24 numbered geometric frames and inspect the synthetic banner. | Local navigation, source/image identity, stable order | An examination of real anatomy |
| 2 | Select **Compare six-image queues**. Read the four equal-workload methods and their longest omitted imported-position spans. | One generated complete score stream drives real, deterministic exact-K selectors; policy differences are inspectable | That generated scores detect lesions or reflect a trained AI |
| 3 | In the **Selection policy** control, switch from **Highest model scores** to **Top score in each chronology bin**, then **Uniform baseline**; select **Build review queue** each time. Optionally click **Inspect gap** and return. | Equal K is enforced, unselected frames stay reachable, and viewing a suggestion does not auto-label or bookmark it | A favorable pathology recall result or review-time savings |
| 4 | Bookmark a frame, enter a clearly fictional note (for example, "Synthetic frame for navigation check") and select **Save review**. Mark a short image interval with **Mark start**, navigate ahead, and select **Save end**. | Human-authored observations and interval edits persist separately from generated scores | Automated medical findings |
| 5 | Select **Verify evidence**, then **Export review**. Observe the export counts and check that the boundary-only export does not silently include all interval interiors. **Export full spans** is a separate explicit action for imported images inside marked spans. | Verifiable audit/export mechanics and explicit evidence coverage | Unimported full-video preservation or specialist reading proof |
| 6 | From the header, select **Study results**. Keep **10% · primary** and **Highest score per chronology bin**; note the **negative** difference. Change to **25% · secondary**, review individual examination results, and return to 10%. | Actual previously published, locked Galar aggregate data are inspectable independently of the synthetic demo | New inference, a new clinical study, or confirmation of clinical benefit |

If the button **Verify evidence** is unavailable, save at least one reviewer note or interval first. The local verification uses the actual saved selection and history. Exported demonstration ZIPs should be treated as test outputs, not medical documentation.

## B. Scientific discussion — what to say and what to show

> **Problem.** Capsule video review involves long image sequences. A model may rank visible blood-positive frames but concentrate its selections on one stretch of frames, leaving separate annotated stretches unseen.
>
> **Approach.** Capsule Review is a local tool that preserves a human review workflow while comparing highest-score, separated-score, chronological-bin and uniform selection at *identical image counts*. It reports what was retrieved and which imported spans were omitted, and can verify saved review evidence.
>
> **Real research.** We trained and compared neural networks on real Galar capsule images and conducted one source-verified, locked study of **163,161 eligible images from ten examinations**. At the **prespecified 10% primary workload**, mean blood-positive annotation-run recall was **49.35% for score-bin** versus **50.62% for uniform** across six positive-run examinations: **−1.2668765 percentage points**, *no demonstrated improvement*. At 25%, score-bin exceeded uniform by **9.5106442 points**, a case-dependent **secondary** observation, not replacement of the failed primary.
>
> **Insight.** At 10%, highest-score ranking retrieved **305** blood-positive labeled frames but only **28** distinct positive annotation runs; uniform found **170** frames across **63** runs. Frame-level image enrichment is therefore not a reliable substitute for preserving distinct annotated evidence intervals.
>
> **Next scientific gate.** Before another confirmatory evaluation, obtain an **independent**, fully and appropriately annotated external cohort, check patient/examination grouping, and freeze an outcome-compatible protocol. The original Galar 11–20 outcomes have been examined; the authors' 61–80 holdout remains unopened.

The referenced **annotation run** is a consecutive run of corrected `blood=1` rows at Galar's native +5 source-frame annotation stride, **not** an independently diagnosed lesion. The study does **not** establish independent patients, patient-level sensitivity, adequate generalization, clinical use, physician time savings, or safety of unattended skipping. Four examinations had zero labeled blood-positive runs; their positive-run recall is **undefined**, not 0% or 100%. The original complete image archive was not durably retained, although the private handoff recovered key commitments, scores and checkpoint.

Source evidence:
- [Completed locked Galar 11–20 study](GALAR_UNSEEN_11_20_RESULTS.md) and [nonidentifying aggregate](../experiments/galar-unseen-11-20-20261104/aggregate.json).
- [Original locked evaluation protocol](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json), [research commitment issue #24](https://github.com/Kushrishi/capsule-review-public/issues/24).
- [Project scientific/software maturity audit](PROJECT_MATURITY_AUDIT_20261104.md), including model variability and failure modes.
- [External-cohort qualification](EXTERNAL_COHORT_QUALIFICATION_20261104.md) and [conditional replication design](EXTERNAL_REPLICATION_DESIGN_DRAFT_20261104.md).

## C. Verify the demonstration instead of trusting screenshots

From the installed source directory, run the small automated API/source checks:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_demo_scores.py tests/test_locked_results_explorer.py tests/test_public_docs.py
```

For a real Chromium end-to-end check that exercises the generated queue, evidence export and results explorer without medical images:

```bash
python -m playwright install chromium
python tests/browser_smoke.py --transport localhost --output test-results/supervisor-demo
```

This produces synthetic UI screenshots and a JSON browser result **locally under `test-results/supervisor-demo`**, not as hosted demo media. Tests must pass rather than be edited to suppress an unfavorable result. The regular GitHub CI runs the core suite on Python 3.11/3.12/3.13 plus a browser/local-model smoke test and the public-source privacy check. The optional synthetic-test CNN trained in that heavier CI path is **not a medical model**.

The demonstration uses no external clinical data and no protected research artifacts. To share screenshots, use only the generated images and public aggregate results; do not include a private workspace path, individual source records, model checkpoint, clinical pixels, reviewer notes from real cases or patient identifiers.

## D. Criteria for an honest demonstration

A reviewer should be able to verify all of the following without access to private material:

- Generated fixture: **24** frames, **one** complete generated score run, **zero** medical labels, no model weights. Repeating `capsule-review --data-dir ./demo-workspace demo` returns the **same** study ID.
- Research queues: **four** methods and **six of 24** selected positions per method in the guided comparison; no queue click automatically changes a human note or source label.
- Evidence: saved human notes, image-interval boundaries, explicit distinction between normal review export and full *imported*-span export, independent receipt verification.
- Completed science: **negative** 10% primary and **secondary** 25% comparison, including per-examination heterogeneity and undefined zero-positive cases.
- Limitations: no publicly bundled trained pathology model, no clinically validated diagnostic function, no verified independent patients, no measured reading-time savings, no permanent full-original-image archive.

**Do not:** describe generated demo numbers as output from the actual Galar CNN; present a selected-frame count as read-time improvement; use synthetic image geometry to illustrate a real endoscopy lesion; share private input or outcome data; claim an unverified patient-level study or publication-ready method.

**Public-source licensing:** this repository is publicly readable but does **not** currently grant a software licence. External use and redistribution should be resolved deliberately; dataset licences are independent of the software.
