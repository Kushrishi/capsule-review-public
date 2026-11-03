# Locked unseen-examination Galar blood-evidence evaluation

**November 3, 2026. Status: design and original-checkpoint provenance fixed; independent evaluation NOT RUN.** The machine-readable [evaluation lock](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json) is the source of truth. This is a project-level prespecified research protocol, **not** a registered trial, blinded patient study, clinical validation or claimed novel diagnostic method.

## Scientific question and why this is next

The existing Capsule Review viewer, model-guided ranking, interval-preserving exports, real-image replay and retrospective Galar run audits all work. But the measured six/eight-examination comparisons used cases that had already been examined, and the 512-image-per-examination reference streams omitted many official annotation runs before ranking began. An AI score can recover many labelled images while losing distinct evidence stretches. More retrospective tuning cannot repair the independence problem.

**Target:** without modifying its original checkpoint or evaluating protected cases during development, compare the fixed blood-score model's four current viewer policies at **equal exact review counts** on Galar examinations **11–20**, which have not yet been opened by the project. Their patient independence from fitting examinations is unknown; do not claim it.

This checkpoint was fitted on exams **1–8**, selected using the **historically inspected 9–10**, and has neither been refitted using additional Galar cases nor selected according to the 11–20 results. The separate Galar 61–80 author-reserved cohort remains untouched.

## What was executed now

The original private `capsule-blood-real-pilot.zip` package (1,361,018 bytes) was independently hashed and matched the frozen outer SHA-256 `5e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc`. Exactly **three original members** were read, checksum-verified and crosschecked for model provenance:

| Member | SHA-256 |
| --- | --- |
| `model/weights.pt` | `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3` |
| `model/model.json` | `6c0c3fa38f4008a03fdc9f48b1911ff8d5f32dc331c0b85aa9fbf9a9b1bab6eb` |
| `model/metrics.json` | `781b855c0e14278fb20cb45f25f2481bcf379182aa4dd9d8e9b9c93a12928d7a` |

The checkpoint is `capsule-cnn-v1`, epoch **8**, derived from original source commit `e3cfb1f4629595d51901829498202d0967f8c83a`. The original model package's medical source manifest, private per-frame predictions and model weights were **not** extracted, loaded into a model runtime or published. This was provenance verification only. The private itemized receipt is retained at `/Capsule Review/Privacy Audit 2026-11-02/capsule_locked_galar_model_provenance_20261103.json`.

Run the same safe preflight with a private locally retained package using:

```bash
python scripts/verify_unseen_galar_checkpoint_preflight.py --private-pilot /private/capsule-blood-real-pilot.zip
python -m pytest -q tests/test_unseen_galar_checkpoint_preflight.py
```

Public CI uses only generated synthetic ZIP members. The private package must **never be submitted to public CI, Git or public workflow artifacts**.

## Prespecified future execution

1. Preserve the exact frozen original checkpoint, code version, all four existing production selection methods and the original corrected publisher label ZIP SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. No later fitted checkpoint is substituted based on observed outcomes.
2. Privately acquire **all official binary-labelled annotated source positions** of each preselected evaluation examination with every original image aligned by independently checked source identity and SHA-256. A sparse 512-image sample or gaps in eligible imported positions **fail the complete-input gate**; do not call any result full-source coverage. Original *annotated* positions are not necessarily all device exposures; original capture timestamps remain unknown.
3. On those images, compute and freeze the original CNN's uncalibrated blood-score predictions, original image hashes, model checksum and source-position mapping **before** opening any evaluation labels. Model selection, weights, decision thresholds and ranking policies cannot be adjusted after evaluation results are known.
4. Privately open *only* the 11–20 members of the verified corrected label archive for outcome evaluation; leave the authors' reserved 61–80 untouched. Missing/blank labels are **unknown**, not negatives. A positive annotation run is a maximal original `blood=1` stretch at the verified **+5 annotated-row source-index stride**, not an adjudicated lesion.
5. Use `select_positions` from the current application without using labels for selection. Compare all four policies: uniform, descending CNN score, score + ordinal separation, and score per chronology bin. The **primary comparison** is score-bin versus uniform at **10% of eligible imported images**; secondary points are **5%, 25%, 50% and 100%**, and both other policies are reported at every point. Exact K is `max(1, floor((N × percent + 50)/100))` capped at N. These percentages are prespecified *research workloads*, not software or clinician constraints; the product supports arbitrary exact K.
6. Preserve all per-examination results, including zero-positive cases (run recall **undefined**) and any cases where the model loses to uniform. Report actual selected image counts, distinct source blood-positive annotation runs reached, fraction of eligible source runs, 1–5 / 6–25 / 26+ run-length categories, image-level hits separately, ordinal gaps, and examination-level heterogeneity. Publish **non-identifying aggregate evidence only** after private source validation.

**Decision rule:** no clinical efficacy or model promotion based solely on these outputs. The primary endpoint would establish only *project-independent examination-level blood annotation-run retrieval* under a fixed retrospective dataset, not patient-generalization, unique-lesion sensitivity, image safety, clinical diagnosis, or actual physician reading-time savings. Without sufficient eligible source data or reliable provenance, report the missing-data failure and keep the scientific gate open.

## Blockers, not waivable assumptions

The original archive of corrected source labels and dense original images from evaluation examinations 11–20 is **not currently present** in the verified private workspace. The 512-image reference subsets from earlier experiments are not a replacement. No 11–20 source image was inspected or source-label value decoded for this work; no holdout score or test accuracy was calculated, and no claim of superior pathology retrieval is made. A prior archive-integrity-only ZIP-wide CRC check touched protected compressed entries without parsing their label values, was disclosed, and was removed from the evaluation pipeline. **The gate stays closed** until verified acquisition and the frozen blinded scoring sequence can be performed in private compute.
