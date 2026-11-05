# Refined Galar visual-similarity triage — November 5, 2026

**Research status:** the previously flagged coarse visual matches were rechecked; **no strict pixel-aligned close copies were found among those matches**. This is **not** a complete near-duplicate clearance, proof of unique patients, or an AI-model improvement.

## Why we ran this

The [source-data audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) established **zero exact SHA-256 duplicates** among 11,147 independently byte-verified original selected PNGs, but its 64-bit grayscale dHash screen flagged **5,293 cross-examination pairs**, involving **499** images. dHash intentionally loses most image information, so very different capsule frames can collide in similar dark/bordered scenes.

We needed a second-stage measurement before treating those collisions as actual split leakage or duplicated patients.

## Private, source-verified analysis

The same original 11 source archives were read locally, but **only the 499 previously flagged original frames** were re-decoded. Each of those original source PNGs was rehashed and rechecked against the earlier private source manifest before any image comparison.

For each of the 5,293 already flagged cross-examination pairs:

1. Resize both original full-field RGB frames to the same **64×64** grid using area resampling, without a crop or learned transformation.
2. Measure grayscale **structural similarity** (SSIM), RGB mean absolute error (MAE) over the full frame, and RGB MAE in the central **48×48** region.
3. Classify a *candidate close pixel-aligned copy* only if SSIM is **at least 0.95**, full RGB MAE **at most 0.06**, and central RGB MAE **at most 0.07**.

These descriptive thresholds were chosen as a strict close-copy triage, **not fitted to patient identity** or validated on a ground-truth duplicate benchmark. Pixel alignment means rotated, shifted, transformed or compressed copies can escape this test.

| Second-stage result | Observed value |
| --- | ---: |
| Original candidate images individually rehashed | **499 / 499** |
| Previously equal-dHash cross-examination pairs examined | **5,293 / 5,293** |
| Full-frame grayscale SSIM **≥0.70** | **44** pairs |
| Full-frame grayscale SSIM **≥0.90** | **0** pairs |
| Highest observed grayscale SSIM | **0.7902994** |
| Mean grayscale SSIM | **0.4942104** |
| Pairs meeting all three strict close-copy thresholds | **0** |

The lack of high SSIM among these *specific* pairs suggests the earlier coarse collisions do not contain close pixel-aligned copies. It **does not** prove all possible near-duplicates absent because (a) pairs with different dHashes were never searched, (b) geometry or contrast can change, and (c) similarity cannot establish whether two examinations belong to the same person. **No independent source-patient metadata has been authenticated.**

The Galar authors state that their video study IDs were randomly generated and that device/site differences should inform splitting. Their paper documents source-level age/sex/capsule metadata, but it is not a validated pseudonymous patient-identity linkage. See [Le Floch et al., *Scientific Data* (2025)](https://doi.org/10.1038/s41597-025-05112-7).

## Artifacts and checks

The public [aggregate](../experiments/galar-visual-similarity-triage-20261105/aggregate.json) contains only group-level counts and the method definition. A [small verification module](../src/capsule_review/similarity_triage.py), [private-score CLI](../scripts/check_similarity_triage.py) and [synthetic tests](../tests/test_similarity_triage.py) recompute the numerical summary and reject malformed/duplicated pairs or unsupported clinical claims.

The full original pair identities, frame-level numeric metrics, exact source verification and executable original-image comparison remain in a **private** six-file research bundle (124,840 bytes, SHA-256 `aaee88df0c857d645b445a339cb796dc8f89bd1cad07f335167dd3cb4125227c`) retained separately in Library. It **does not include any original medical image pixels**; exact reproduction requires the separately retained private source archives. Private candidate metrics SHA-256: `51f8eee0795efc731a74a41f506a9b9b0fad374f65661d47a9cb998d48022f8b`.

## Scientific decision and next work

The first-stage *coarse-collision warning* is now better characterized and does **not** justify claiming 499 duplicated images or repeated patients. It also does **not** clear the dataset for patient-independent validation.

**Issue #46 remains open** until trustworthy independent-patient/examination grouping, acquisition-device/site metadata and an appropriately scoped source-label manifest are verified. An **all-pairs perceptual nearest-neighbor search** or explicit transform-invariant duplicate analysis is still unperformed, and all event-level performance evaluation remains blocked without complete source chronology and reference annotations.

We can continue research labelled **exploratory and examination-separated**, without treating original Galar 11–20 as a fresh test or accessing the original authors' 61–80 cohort. No clinical validation, model promotion or new AI training occurred in this similarity triage.
