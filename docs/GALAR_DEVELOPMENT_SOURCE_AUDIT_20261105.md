# Galar development-source audit — verified selection, insufficient independence

**November 5, 2026. Status: source-byte verification complete; independent-patient/model-promotion and complete-event evaluation BLOCKED.** This is an audit of already retained **selected original PNGs**, not a new acquisition or medical AI experiment.

## Decision

We can continue **exploratory examination-separated development**, clearly labelled as retrospective work on previously inspected examinations. We **cannot** promote a model as independently validated, claim independent patients, or measure complete-video pathology event recall from this sparse selected pool. More training experiments on the same image bank would only be useful with fixed, outcome-independent splits, explicit source and label boundaries, and hard-to-game metrics.

The priority is **positive-examination diversity and valid evaluation units**, not adding further blood-negative frames or repeatedly retraining a model against the same difficult cases.

## Source-byte audit: what was verified now

Independently read and SHA-256-verified every original image against the privately archived source manifests: the four Galar 1–8 fitting ZIPs and seven additional private source packages (21, 22/24, 23, 25, 27, 29, 30). These **11** private packages contain **11,147 original selected PNGs**, totaling **3,374,503,965 uncompressed original image bytes**. We checked each source image's identity, hash, byte length where available, recorded explicit blood label and reference-versus-enrichment role. **Zero** hash, identity, label or sampling-role mismatches; **zero exact original-PNG SHA-256 duplicates**. The audit also decoded all 11,147 originals for a coarse similarity screen.

These are individually selected original publisher frames, **not every original capsule frame**, and are not proof of a durably retained complete source movie. The official ~31.99-GB Galar source-file MD5 was not recalculated by this selective-archive audit. Original per-frame SHA values and source identities remain private.

| Selected research population | Verified result |
| --- | ---: |
| Examinations represented | 16 |
| Distinct selected source-frame positions | **11,147** |
| Uniform reference positions | **8,192** (512 per examination) |
| Additional enrichment positions, not additional exams | **2,955** |
| Explicit blood-positive selected images | **1,663** |
| Explicit blood-negative selected images | **9,484** |
| Selected images with unknown label | 0; labels **outside** this selection remain unknown |
| Examinations with no selected positive | **5** (3, 5, 8, 22, 24) |
| Positive examples in the four largest-positive examinations | **1,276 / 1,663 = 76.7%** |
| Exact identical original-PNG byte hashes, across selected pool | **0** |

The selected pool has **11** examinations containing any positive reference images, but much of the apparent training support comes from a few source examinations. The descriptive effective-positive-examination concentration is only **~5.77** (using `(sum positives)^2 / sum(positives^2)`), not a count of independent patients or lesions. The earlier 14-study pool contained 10,123 images; adding the zero-blood-selected examinations 22 and 24 created the current 16-study pool of 11,147, **without adding positive examinations or positive images**.

The per-examination selected/reference aggregates and private-receipt hash are preserved in the [non-identifying source audit aggregate](../experiments/galar-development-source-audit-20261105/aggregate.json). We checked it against the [earlier verified expansion records](GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md).

## Duplicate / patient independence audit

All original-PNG SHA-256 digests are different. That does **not** establish unique underlying patients, duplicate-free anatomy, or absence of visually similar images.

A deliberately coarse **64-bit grayscale difference hash (dHash)** screen found **106** hash values shared by different examination IDs, involving **499** selected images and **5,293** cross-examination candidate pairs. Those candidate identities and fingerprints are **private**. Capsule video commonly contains broadly similar luminal shapes, borders and lighting, so an identical low-resolution dHash is **not** a confirmed duplicate. There has been **no adjudication** of those pairs; this does not prove repeated patients, either. This first screen is not an exhaustive perceptual near-duplicate search.

The research packages do not establish deidentified patient-group IDs, independent unique patients, common device/vendor domains or clinical sites. **Examination-disjoint is not automatically patient-disjoint.** Mark all patient-level validation and cross-patient external generalization claims as **UNVERIFIED** until authenticated group data can support them.

## New reusable development gate

- [`development_preflight.py`](../src/capsule_review/development_preflight.py) verifies every future **local** source file against a manifest SHA-256, refuses a changed/unpinned manifest, checks all source byte hashes, requires explicit `positive`/`negative`/`unknown`, flags split leaks at examination/group and exact-image level, and refuses a complete-event endpoint on sparse/unknown source coverage.
- [`check_development_cohort.py`](../scripts/check_development_cohort.py) is an offline CLI that refuses private images/manifests stored under the public repository and outputs only redacted counts/status.
- [Synthetic regression tests](../tests/test_development_preflight.py) exercise source tampering, patient/split leaks, unknown labels, missing sources, malicious paths and failure to qualify sparse samples as complete-event evidence.
- **PASS** means a source-byte and declared-split structural preflight, **not** patient independence, data rights or medical approval. If group identities are absent, it returns `INSUFFICIENT_GROUP_INFORMATION`; if source, label or split gates fail, it returns `BLOCKED`. A human must still verify the authenticity of group assignments, rights and reference standard.

The just-audited historical pool is **not automatically PASS** for a new comparison. It has no uniquely identified patient groups, no complete original-video event reference, unresolved coarse near-duplicate candidates and no new prospectively frozen candidate/test split. A separate private source manifest and a new dated study lock are required before future model evaluations. The original 10% Galar 11–20 primary remains **negative**; that examination set is now examined, and the source authors' reserved 61–80 outcomes remain unopened.

## Adaptive next technical experiment

**First:** resolve whether unique patient/examination group assignments and device IDs can be established from a custodian; review the visual duplicate candidates privately using higher-resolution perceptual comparison or authorized group metadata; freeze a sparse-label development-only manifest with source SHA256s, role semantics and examination-disjoint folds. No new large raw-data acquisition is justified until this is done.

**Then, if that gate passes for development:** run a *single predefined* comparison focusing on **cross-examination positive diversity and early retrieval**. Use source-examination-balanced sampling, compare a transparent non-ML baseline, original compact CNN and one qualified representation under identical development folds. Report every case's **average precision and positive-image hits at exact K**, plus ROC-AUC and regression from original. For distinct positive annotation runs, first qualify **complete source image chronology and exhaustive event annotations**; a 512-position reference subset does not meet that requirement. Predeclare positive-run stratification and stop conditions rather than fitting to our known Galar 11–20 outcome.

**If the gate remains blocked:** invest in authenticated patient/group metadata and source-annotation quality rather than another architecture sweep. We already know that extra negative-only data, simple augmentation and off-the-shelf pretrained features have not consistently solved the 10% workload problem.

### Privacy and reproducibility

The private audit archive is retained separately in the user's Capsule Review Library. It contains the exact per-source hash lists, source archive checksums, labels/selection metadata, visual-similarity candidate identities, reproducible verification scripts and SHA256SUMS; **no original medical pixels**. Its SHA-256 is `5cf828dd0288364bfe0bb2a5e3a6615b9e5ddaac91dec51b1a7765923fd04709`, 801,233 bytes. Repeating the audit requires the original source packages, stored separately. The archive is not encrypted merely because it is in a ZIP; it must remain access-controlled.

This entire audit is a **data-quality milestone**, not an AI accuracy improvement, independent medical evaluation, unique-lesion count or measured reduction in reading time.
