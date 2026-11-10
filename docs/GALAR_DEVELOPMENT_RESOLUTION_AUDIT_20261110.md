# Original-image native-resolution audit of the Galar development pool

**Performed November 9, 2026 in Montréal / November 10 UTC.** Read-only technical follow-up to [the verified development-source audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) and [the group-readiness assessment](GALAR_GROUP_AND_FOLD_READINESS_20261105.md). **Status: ORIGINAL-IMAGE RESOLUTION CHECK PASSED; AUTHENTICATED DEVICE, SITE, AND PATIENT-GROUP GATES REMAIN UNRESOLVED.** No new fitting, model comparison, 10% benchmark, or clinical advancement.

## Scientific question and why the check is justified

The latest [frozen MobileNet representation comparison](FROZEN_REPRESENTATION_SHORT_EVENT_RESULTS_20261109.md) failed cross-examination pair ordering even though training-pair ordering was perfect. The eight additional development examinations used for exploratory fitting, source audits or short-event diagnostics (Galar 21, 22, 23, 24, 25, 27, 29 and 30) still lack authenticated capsule-system metadata in the retained study-level record. A **native image-geometry audit** can identify gross resolution/PNG-encoding heterogeneity in these *already-verified* images. It cannot authenticate capsule devices or patient grouping, or establish why the encoder failed.

## Original-source validation and observed result

The earlier private source audit contains 11,147 selected source-image identities across 16 previously examined studies (not entire original videos), including 4,096 fitting images from Galar 1–8 and **7,051 selected originals** from the eight additional studies. This check recovered the **seven existing** private source packages for the eight additional studies from the user's access-controlled Library; **zero new original publisher images** were acquired. It independently verified every package's exact byte size and source SHA-256 against the sealed prior source-audit dependency receipt.

The evaluator then reopened each source ZIP, matched **every canonical image examination/frame identity** against the original 11,147-image private membership manifest, rejected unexpected/duplicate/missing selected originals, and validated every 33-byte PNG IHDR header including its CRC. It did not decode/re-hash whole individual PNGs again: those checks are part of the prior private verified-source audit. No original pixels, individual frame IDs, image labels, private patient attributes or source-level predictions are published.

| Examination | Selected original PNGs | Native dimensions | PNG encoding |
|---|---:|---|---|
| Galar 21 | 993 | 512×512 throughout | 8-bit RGB throughout |
| Galar 22 | 512 | 512×512 throughout | 8-bit RGB throughout |
| Galar 23 | 1,001 | 512×512 throughout | 8-bit RGB throughout |
| Galar 24 | 512 | 512×512 throughout | 8-bit RGB throughout |
| Galar 25 | 1,013 | 512×512 throughout | 8-bit RGB throughout |
| Galar 27 | 1,005 | 512×512 throughout | 8-bit RGB throughout |
| Galar 29 | 1,009 | 512×512 throughout | 8-bit RGB throughout |
| Galar 30 | 1,006 | 512×512 throughout | 8-bit RGB throughout |
| **Total** | **7,051** | **512×512: 7,051/7,051** | **8-bit RGB: 7,051/7,051** |

Zero private archive SHA failures, selected-image membership discrepancies or PNG IHDR CRC failures. The [independent evaluator](../scripts/independent_galar_resolution_replay.py) does not import the [primary code](../scripts/audit_galar_development_resolution.py) and independently reproduced the exact per-examination native dimensions, encodings and counts. The independent aggregate verification receipt is [here](../experiments/galar-development-resolution-20261110/independent-check.json); the [aggregate](../experiments/galar-development-resolution-20261110/aggregate.json) is public, whereas source archive SHA lists and the original frame membership manifest remain private. Twelve synthetic tests cover canonical success, audit/archive mutation, source identity/path duplication or mismatch, malicious path names, IHDR corruption, and a deliberately altered aggregate.

## What this establishes—and what it does not

The [source authors' Galar descriptor](https://doi.org/10.1038/s41597-025-05112-7) describes **512×512 PillCam and 336×336 Olympus** native datasets at its two participating centers (Table 1). All 7,051 observed selected development images match the **512×512 acquisition-resolution signature** associated with PillCam in that descriptor, rather than its 336×336 Olympus signature. The original fitting examinations 1–8 separately have authenticated **PillCam SB3** device metadata in the retained source record. The present findings therefore argue against a *gross original-image resolution difference between these eight additional studies* as the sole explanation for poor inter-examination transfer. This does not rule out other hardware variants, device-processing differences, color/lighting changes, clinical-context shifts, anatomical differences, class concentration or other confounders.

**Do not use 512×512 as a substitute for a verified capsule system.** It cannot identify SB2 versus SB3, a recording site, a patient, or whether two randomized study IDs are from the same patient. The new size check is **not** a patient-disjointness test or near-duplicate screen. It cannot show that the selected 512-image reference subsets cover complete videos or exhaustive annotation runs, and it does not reopen reserved studies 61–80 or the completed Galar 11–20 evaluation.

**Stage #46 gate decision:** source-resolution signature **PASS** for the 7,051 selected images; authenticated **patient-group, exact capsule-system and per-study site linkage remains INSUFFICIENT GROUP INFORMATION**. No new independent evaluation is qualified and no model/policy is promoted. The next credible access request is **the official metadata/custodian-confirmed patient-to-study and exact device mapping**, not another pass over the same source PNGs or another 24-fit architecture/seed sweep. Existing source archives and the corrected-label evidence remain private and unchanged.

## Reproduction and safeguards

Run privately with the original sealed source-audit package and seven retained original ZIP packages, all outside the public repository:

```bash
python scripts/audit_galar_development_resolution.py \
  --private-audit-zip /private/Capsule_Review_Private_Development_Source_Audit_20261105.zip \
  --private-archives /private/retained-galar-images \
  --aggregate-output /private/resolution-aggregate-new.json \
  --private-receipt-output /private/resolution-source-hashes.json

python scripts/independent_galar_resolution_replay.py \
  --private-audit-zip /private/Capsule_Review_Private_Development_Source_Audit_20261105.zip \
  --private-archives /private/retained-galar-images \
  --public-aggregate /private/resolution-aggregate-new.json \
  --private-receipt-output /private/resolution-independent.json

python -m pytest -q tests/test_galar_development_resolution.py
```

The private source manifest is pinned by its prior audit package SHA-256; each seven-package source SHA is verified before a PNG header is read; image membership must reconcile exactly. Never put private images or source-level receipts in public Git or GitHub Actions. All 12 tests are synthetic; the real source check was executed locally in private and does not run in public CI. This is an engineering/data-quality result, **not AI accuracy improvement or human clinical evidence**.
