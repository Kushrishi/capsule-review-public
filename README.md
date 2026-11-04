# Capsule Review

A local research viewer for capsule-endoscopy image sequences. Review images, record observations, and export verifiable evidence. Experimental model scores can help prioritize frames, but never replace a human review.

**Status:** Working research software; **not a clinical decision-support device**. No medical model is distributed with the public source.

## Try it locally

Requires Python 3.11+.

**macOS / Linux**

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
capsule-review serve
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\capsule-review.exe serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and select **Open test sequence**. It creates 24 **generated, nonmedical images** and a complete set of **deterministic example scores**—not learned model predictions. Select **Compare six-image queues** to exercise the real four-policy, exact-K queue and inspect omitted spans without any research data or model weights. You can then bookmark frames, add notes, mark intervals, verify evidence and export a review. Earlier generated test sequences are updated on demand without overwriting notes or creating duplicate score runs. The server binds to localhost. The **Study results** link opens the separate public-aggregate-only [locked Galar results explorer](src/capsule_review/static/locked-results.html); the synthetic demo is *not* a replay of Galar clinical findings.

## What works

- **Review:** Import PNG, JPEG or WebP sequences; navigate, bookmark, annotate, and resume locally.
- **Preserve:** Mark image intervals, export saved frames and interval boundaries, or explicitly export every *imported* image in marked spans. Verify exported bytes and review history.
- **Compare:** Import a complete score stream for the exact source images, choose any review count from 1 through all imported images, and compare four label-blind policies: top score, score with spacing, score per chronology bin, and uniform sampling. Inspect their largest omitted spans.

Models provide suggestions only. Reference annotations, predictions and human notes remain separate. Neither image order nor source-index gaps establish original recording time or complete video coverage.

For details, see the [review workflow](docs/RESEARCH_REVIEW_QUEUE.md), [evidence exports](docs/FULL_SPAN_EVIDENCE_EXPORT.md), and [prediction format](docs/PREDICTIONS.md). An optional **anatomy** baseline can be trained locally; it is not a pathology detector. See [MODEL.md](docs/MODEL.md).

## What we have learned

The software works; the biomedical evidence is mixed. Earlier experiments used previously examined material. A completed, locked Galar 11–20 study adds examination-level evidence; no clinical validation is established.

| Observation | Result | Interpretation |
| --- | --- | --- |
| Sparse source-reference ceiling | Only **110 of 283** original blood-positive annotation runs were represented by the 512-image references across eight examined cases | Better ranking cannot recover source intervals absent from its input |
| Highest-CNN-score ranking at 51/512 images per case | **95** labelled-positive images across six examined cases, versus **27** for uniform | Image hits alone are not distinct-run recall; score ranking left much larger unselected spans |
| Examination variation | The original CNN missed positive sampled images in difficult cases **23 and 25** at this workload | Pooled results conceal failures |
| Locked Galar 11–20 evaluation, complete eligible source inputs | Score-bin minus uniform mean annotation-run recall: **−1.27 percentage points** at equal 10% workload | Two wins, two losses and two ties among six positive-run examinations; four zero-positive cases have undefined recall |

See the [source-run audit](docs/GALAR_RUN_COVERAGE_RESULTS.md), [six-examination omission analysis](docs/GALAR_SIX_EXAM_OMISSION_SPAN_RESULTS.md), and [equal-workload source-run robustness study](docs/GALAR_RUN_ROBUSTNESS_RESULTS.md). Negative results are retained.

The private research inventory includes **11,147 fitting images across 16 examinations**, including independently verified fitting-source additions from Galar 22 and 24. This is not an independently validated patient cohort. The [source acquisition](docs/GALAR_NEGATIVE_22_24_RESULTS.md) and [matched training comparison](docs/GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md) document the evidence and limits. **No clinical model was promoted.**

**Locked evaluation completed November 4:** All **163,161 eligible original images** from examinations **11–20** were acquired, source-verified and scored with the original frozen CNN. Predictions and all review queues were privately retained and externally committed before analyst blood-outcome access, following a disclosed outcome-concealed eligibility amendment. At equal 10% workload, score-bin averaged **49.35%** positive annotation-run recall versus **50.62%** for uniform. The primary result does **not demonstrate improvement**. Read the [complete results and failures](docs/GALAR_UNSEEN_11_20_RESULTS.md), [original design](docs/GALAR_UNSEEN_EVALUATION_PLAN.md) and [research issue](https://github.com/Kushrishi/capsule-review-public/issues/24). The authors' reserved **61–80** remain unopened. Annotation runs are not confirmed distinct lesions, and patient independence and actual reading-time benefit are unverified.

## Project map

| Path | Purpose |
| --- | --- |
| `src/capsule_review/` | Local viewer, import, annotations, queue, storage and exports |
| `tests/` | Synthetic unit, API, integration and browser checks |
| `scripts/` | Reproducible research and source-verification utilities |
| `experiments/` | Versioned, non-identifying aggregate research records |
| `docs/` | Protocols, provenance, measured results and scientific limitations |

Run the checks locally:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m playwright install chromium
python tests/browser_smoke.py
```

Public CI tests Python 3.11, 3.12 and 3.13, a local-model/browser run, and a source-file privacy gate. That establishes software test coverage, **not clinical efficacy**.

## Data, safety and licensing

Use only data you are permitted to process and keep the application on localhost. Workspace files are not encrypted; there is no multi-user authentication. Original medical images, individual source labels and predictions, model checkpoints and research packages are **not** in this public repository. See the [release boundary](docs/PUBLIC_RELEASE_SAFETY.md) and [research protocol](docs/RESEARCH_PROTOCOL.md). The historical `Kushrishi/capsule-review` archive remains private.

The application currently has **no software licence**. Dataset attribution, including Galar's CC BY 4.0 terms, is separate from permission to reuse this code. Do not assume this repository grants a software licence.
