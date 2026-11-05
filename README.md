# Capsule Review

**A local research application for reviewing capsule-endoscopy images and studying how AI-guided selection preserves important evidence.**

Capsule Review lets a human navigate image sequences, record findings, compare fixed-size review queues, inspect what was skipped and export verifiable evidence. It is **working research software, not a clinical decision-support device**. The real AI experiments use private medical data; the public demo uses generated images and **non-AI example scores**. **No clinical model was promoted.**

## Start here

**New to the project?** Read [current status and the code map](docs/PROJECT_STATUS.md), then [the adaptive research roadmap](docs/ROADMAP.md). They explain what is completed, what failed, the next scientific gate and how our priorities change when new evidence becomes available.

**Try the software** (Python 3.11+, from a checked-out repository):

| macOS / Linux | Windows PowerShell |
| --- | --- |
| `python3 -m venv .venv` | `py -m venv .venv` |
| `. .venv/bin/activate` | `.\.venv\Scripts\python.exe -m pip install -e .` |
| `python -m pip install -e .` | `.\.venv\Scripts\capsule-review.exe serve` |
| `capsule-review serve` | |

Open **http://127.0.0.1:8765** and click **Open test sequence**. The self-contained demo creates 24 synthetic frames and generated scores. Try **Compare six-image queues**, switch between the original four methods and the experimental fifth one, then bookmark, annotate, verify and export a review. **Study results** opens the previously completed Galar aggregate, not a live medical prediction.

For a command-by-command walkthrough, see [the reproducible demo](docs/SUPERVISOR_DEMO.md).

## What works, and what is still research

- **Software:** image import and chronological navigation; reviewer notes, bookmarks and intervals; read-only scored suggestions; exact-K selection comparisons; omitted-source-position spans; byte-verifiable review exports; synthetic/API/browser regression tests.
- **Experimental AI:** trained CNNs and a frozen pretrained MobileNetV3 probe have been tested on actual Galar images. Performance varies sharply across examinations. No publicly distributed pathology checkpoint and **no demonstrated generalizable clinical benefit**.
- **Best completed study:** 163,161 original images from Galar examinations 11–20. At the prespecified **10% primary** workload, score-bin retained **49.35%** of distinct positive annotation runs versus **50.62%** for uniform: **−1.27 percentage points**. The **25% secondary** result was positive but heterogeneous and not confirmatory. See [the frozen results](docs/GALAR_UNSEEN_11_20_RESULTS.md).
- **Development data audit (November 5):** all **11,147 selected original Galar image bytes** independently reverified with zero exact PNG duplicates, but **76.7% of positive selected images are concentrated in four examinations**; patient grouping and full near-duplicate clearance remain unverified. A [follow-up similarity audit](docs/GALAR_VISUAL_SIMILARITY_TRIAGE_20261105.md) found no strict pixel-aligned copies among the 5,293 coarse collision candidates, without establishing patient identity. See the [audit and next development gate](docs/GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md).
- **Current blocker:** robust group-separated training, fully qualified external event labels and patient/examination independence. Source-annotation runs are not adjudicated lesions; an image budget is not clinician reading time. The original authors' Galar **61–80** outcomes remain unopened.

The scientific record can be checked without private data:

```bash
python scripts/project_status.py
python scripts/project_status.py --json
```

## Repository map

| Directory | Purpose |
| --- | --- |
| `src/capsule_review/` | Local FastAPI viewer, score/selection methods and evidence exports |
| `tests/` | Unit, API, synthetic ML, browser and research-integrity regression tests |
| `scripts/` | Experiment implementations and verification; **not** all scripts are active workflows |
| `experiments/` | Public non-identifying aggregate results, including failures |
| `docs/` | [Current status](docs/PROJECT_STATUS.md), [adaptive roadmap](docs/ROADMAP.md), original protocols and **historical research archive** |

Run the public tests with `python -m pip install -e '.[dev]'` followed by `python -m pytest -q`. For browser testing, install Chromium with `python -m playwright install chromium` and run `python tests/browser_smoke.py`. The full CI also checks Python 3.11–3.13, a local-model/browser path and a tracked-file privacy gate.

## Privacy, limitations and rights

Keep the application bound to **localhost**. There is no multiuser authentication or workspace encryption. Never commit source medical pixels, per-image labels/predictions, model weights or private research packages. A public aggregate is **not** clinical proof. Read [the research protocol](docs/RESEARCH_PROTOCOL.md) and [public release boundary](docs/PUBLIC_RELEASE_SAFETY.md).

This publicly viewable repository currently has **no software licence**; do not assume unrestricted redistribution or reuse. Original dataset and model-weight rights require separate review.
