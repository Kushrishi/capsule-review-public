# Locked four-policy full-source annotation-run evaluation

**November 3, 2026 | Source-verified scientific evaluation gate | Pending exact corrected publisher archive**

## Research objective

Capsule Review's question is not simply whether a CNN can retrieve many `blood=1` **sampled pictures**, but whether model-guided selection can preserve more **different stretches of relevant original annotation evidence** than a strong uniform control at the same human review workload. The new [source-run evaluation script](../scripts/evaluate_galar_source_run_queues.py) calls the **same fixed selection implementation** used by the working viewer, so the scientific results will refer to the actual product methods, not a separate approximate reimplementation.

This is strictly research. Galar `blood=1` annotation stretches are **not physician-adjudicated lesions**, unique pathology events, diagnosis, sensitivity or time savings.

## Frozen input and source provenance

- Official publisher-corrected Galar `20251215_Labels_Updated.zip` (Figshare file ID **60383963**), **17,931,138 bytes**, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. DOI: [10.25452/figshare.plus.25304616.v2](https://doi.org/10.25452/figshare.plus.25304616.v2). The complete corrected ZIP was verified by the **earlier** original-source run audit; it was **not available for fresh binary verification in the current execution workspace**. The new evaluator **refuses to run** without an exact SHA-256 match.
- Two earlier **private**, source-verified score packages: frozen original-CNN examination 21/23/30 scores and original-checkpoint examination 25/27/29 appearance scores. Both whole private ZIPs and named CSV members are cryptographically pinned; no original images, per-frame scores or source annotations are placed in GitHub.
- Only **six already examined fitting/transfer examination CSVs**: **21, 23, 25, 27, 29, 30**. The script reads exactly those six members from the corrected publisher ZIP. Neither unopened 11–20 nor author-reserved 61–80 is read or used.
- Existing source-run audit aggregate SHA-256 `8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07`: this is an **independent previously computed scientific check**. The new script requires its saved reference ceiling, known case run counts, **all six score-only and uniform results**, and positive image counts to reproduce exactly before releasing *any* new-method comparison.

## Prespecified definitions and methods

**One run** is a maximal stretch of consecutive rows in an original publisher-corrected examination CSV where `blood=1` and the source frame index advances **exactly five** between rows. The first `blood=0`, unknown, source gap, or end of the CSV terminates the run. This rule was frozen in the preceding source-run audit and is *not* retuned here.

Use the same **512 source-chronologically sampled reference frames per examination** and six identical image workloads **K = 25, 51, 128, 256, 384, 512**, across four policies: the original CNN's highest scores, the current app's score + ordinal suppression heuristic, the app's highest score in each of K chronological bins, and exact midpoint uniform sampling. Selection itself sees **only prediction scores and chronological imported positions**. Corrected blood labels are consulted strictly **after selection**, to identify which original source positive-run IDs received at least one selected representative.

For every examination and workload, report all methods, without choosing a preferred workload after seeing the answer: positive sampled image counts, **number of distinct original positive annotation runs reached**, full-original-source run recall, fraction of source runs reachable from the sparse reference set, and 1–5 / 6–25 / 26+ annotated-row run-length categories. The cross-examination summary retains both pooled run counts and examination-weighted mean recall, win/tie/loss against uniform, and whole-examination leave-one-out fragility checks. **No patient-independent claims, confirmatory p-values, confidence intervals or model promotion.**

**Important input ceiling:** the prior full-source audit established that only **110 of 283** original positive annotation runs are represented by the sparse 512-image references across eight previously inspected cases, so new ranking policies cannot overcome missing original images. A stronger independent validation requires acquiring **denser, originally chronological input** and evaluating on genuinely unseen examinations *without looking at their source labels during model selection*. This six-case retrospective extension is a prerequisite quality gate, **not** that independent scientific breakthrough.

## Run with private inputs

The source labeling ZIP cannot be substituted with inferred positive islands from sampled reference images. The exact private publisher source file and frozen score archives must already exist in a private workspace:

```bash
python scripts/evaluate_galar_source_run_queues.py \
  --corrected-labels /private/20251215_Labels_Updated.zip \
  --frozen-scores /private/capsule-galar-frozen-transfer-private-repro.zip \
  --appearance-scores /private/galar-appearance-audit-private.zip \
  --prior-aggregate experiments/galar-run-coverage-2026-11-02/aggregate.json \
  --output /private/galar-full-source-four-policy-replay.json
```

The script refuses to overwrite an existing output and fails on changed source hashes, wrong row counts, mislabeled or mismatched source identifiers, truncated reference sets, unexplained stride changes, impossible selection cardinality, and a disagreement with any previously independently verified score-only/uniform case×workload result. It writes **aggregates only**—no original frame IDs, pixels, raw labels, per-frame scores, patient metadata, or original run members. Examine the output privately first before committing any new summarized results.

## Validation and current status

The script and its public tests use **generated, nonmedical source annotation rows**, including positive segments separated by a missing original source index. The tests verify that separate positive stretches remain distinct, the four policies use exact K, source negatives and score corruption fail closed, publisher/private ZIP SHA-256s are enforced, historical CNN/uniform numbers are checked before release, and even deliberately malformed protected-exam members are **never accessed**.

**Current state:** the evaluation engine is implemented; no novel six-case *original-source-run* outcome from this four-policy extension has been claimed or published, because the required exact corrected publisher ZIP is not currently available in this execution environment. This is an explicit evidence gate, not an assumption that the CNN succeeds. When that exact input is reacquired, run the frozen pipeline and preserve negative outcomes. Do not tune on existing cases or unlock holdouts merely to obtain a favorable result.
