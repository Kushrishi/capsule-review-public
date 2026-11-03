# Evaluation of reviewer-marked image intervals against Galar annotation runs

**Research software milestone — November 2/3, 2026.** The evaluator is implemented and exercised using **synthetic frames and source annotations**. It is **not** an independent clinical validation, a new disease model, a new model-ranking result, or evidence of reduced reading time. No original medical images or per-frame source labels are included in the public repository.

## Why this is needed

Capsule Review can now save reviewer-marked *image spans* and export only their boundary images. But a span that numerically crosses a blood-positive annotation does **not** prove that the relevant original image was loaded, inspected, exported, or identified by the reviewer.

A prior source-verified, retrospective Galar audit found that only **110 of 283** source-positive blood annotation runs were represented in historically saved 512-image reference samples from eight examined studies. Short runs were especially underrepresented. These are **corrected-source annotation stretches, not independently adjudicated lesions**; see [the exact prior study](GALAR_RUN_COVERAGE_RESULTS.md). The new tool answers a more specific question about **what a *particular viewer export* can directly support**.

The [methodology lock](INTERVAL_EVIDENCE_AUDIT_SPEC.json) was committed alone before this evaluator was implemented. Historical cases, modelling errors and source-run outcomes were already inspected. The protocol is a defensible exploratory measurement design, **not preregistered independent validation**.

## Three different concepts: never conflate them

| Concept | Required evidence | What it means | What it does **not** mean |
| --- | --- | --- | --- |
| **Direct selected positive image** | Exact exported image identity matches a source-verified imported image whose corrected source `blood` label is `1` | That positive-labelled original frame was selected into this export | A physician recognized it, a lesion was diagnosed, or elapsed review time was saved |
| **Direct selected annotation run** | At least one directly selected positive image maps to that source annotation run | That particular positive stretch has a selected annotated image | Distinct patient/lesion detection or complete original-video sensitivity |
| **Positive annotation run numerically overlapped by an interval** | A reviewer-marked start/end *source-index span* contains at least one exact positive corrected source annotation row | A positive labelled row lies between the two indices | **It was observed, reviewed, exported, detected, or diagnosed**. Only boundary PNGs and separately saved frames are exported |

The evaluator separately counts positive runs represented by the *entire available imported reference sample* (the sparse-input ceiling), directly selected positive runs, explicitly bookmarked/noted positive runs, boundary-positive runs, and annotation runs overlapped only by an interval. It also reports 1–5, 6–25 and 26+ **positive annotated-row** strata; studies with no positive source runs get `null`, not 100%, for run coverage. Blood-negative-label counts are not clinical false positives.

**Example with synthetic source annotations:** Three separate positive annotation runs lie inside a marked numeric span. The local exported evidence contains three selected images, only one with an explicit positive label. The audit correctly reports **three source-run overlaps, one directly supported annotation run and two overlaps without direct image evidence**. No lesion sensitivity has been measured.

## Private provenance gate and source restrictions

This is an **offline, local analysis tool**, not a web service. It requires all four private inputs:

1. A Capsule Review `review-*.zip` export from the actual local application, including selected PNGs, reviewer interval records and the `review.json` event history.
2. The **complete** source-image manifest returned by the existing local `GET /api/studies/{study_id}/manifest` endpoint, with exactly the same study identity and original manifest SHA-256 as the export. Keep this file private.
3. The previously independently verified original PNG **private source manifest** (the `verified-private-manifest.json` stored inside the acquired Galar source-image packages). Its `exam`, original source `frame`, `source_image_sha256`, corrected `blood` label, original byte length and `reference_uniform` roles must match every imported image. Deliberately positive-enriched-only imports are rejected.
4. The official **Galar v2 corrected source annotation ZIP**, publisher file ID **60383963**, fixed SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. The script reads **only the named approved examination CSV** after checking the outer archive hash; it never traverses every label in the ZIP.

This first adapter deliberately accepts **only fitting examination IDs 21–30**. Examinations 1–10 require their different historical source-manifest format; reserved 11–20 and authors' 61–80 must **not** be evaluated. No `--ignore-checks` or unverified-source mode is provided.

For this Galar adapter, a source positive annotation run is a maximal sequence of *consecutive corrected source rows* with `blood=1` at original numeric source frame stride exactly `+5`. A blood-zero or unknown row or a missing original frame-index step ends the run. Missing/unknown labels are never coerced to negative. Source-frame index spacing is **not** original capsule capture time.

The exported PNG's SHA-256 must also match its own recorded *display-image* SHA; this does not rehash the separately preserved **original** source PNG. The original bytes were independently verified when acquired, and their immutable source-file hashes are cross-matched through the private manifest. The run audit clearly labels this division of evidence.

## Run locally with private files

Install the local app from source with standard dependencies (`python -m pip install -e .`). From the source checkout:

```bash
python scripts/evaluate_galar_review_intervals.py \
  --exam 23 \
  --review-zip /private/review-export.zip \
  --study-manifest /private/complete-study-manifest.json \
  --verified-source-manifest /private/verified-private-manifest.json \
  --corrected-labels-zip /private/20251215_Labels_Updated.zip \
  --output /private/interval-evidence-aggregate.json
```

Do not commit any of the five file inputs or a research output until it has been reviewed for identifiers. The script refuses to overwrite an existing output and writes an **aggregate-only JSON**, not individual source-frame IDs, reviewer notes, per-frame predictions, model weights, clinical findings or hidden annotation values.

Public CI runs only synthetic assertions, including the end-to-end localhost-app export scenario. It never downloads Galar images, protected labels, private manifests, or original model checkpoints.

## Interpreting the output and next scientific gates

A high `span_overlapped_source_positive_runs` count does not imply the human inspected that many positive images. **Only `direct_selected_positive_annotation_runs`** has an exact exported source-image witness. `imported_representable_positive_runs` estimates the input-sampling ceiling for the particular verified imported reference set, **not** the full product or a medical diagnosis. An assessment of actual human interpretation would require independently documented reading actions and specialist adjudication, not simply exports or clicks.

An exploratory original-source replay can be performed **only in the private research workspace**, on previously examined fitting studies, by creating reviewer selections through the real application and comparing the resulting audited aggregate. Such a replay must be explicitly marked as simulated or retrospective if no human reviewer participated. It cannot validate clinical usefulness or justify promoting a model, and no source-index or patient-level records should be moved to public GitHub.

A future independent experiment would need examination/patient-group separation, sufficiently dense verified original sequences, an independent lesion adjudication protocol and a measure of actual reviewer behavior; Galar 11–20 and authors' 61–80 remain unopened until a separately locked gate.

**Source:** Le Floch et al., *Galar — a large multi-label video capsule endoscopy dataset*, *Scientific Data* (2025), DOI [10.1038/s41597-025-05112-7](https://doi.org/10.1038/s41597-025-05112-7). Galar corrected annotation source: CC BY 4.0. This software remains research-only with no automatic diagnosis.
