# Next development cohort: Galar 31–40 (decision checkpoint)

**November 5, 2026. Development-only qualification, not a newly blinded trial or permission to acquire 69 GB.**

## Evidence already in the project

The existing [corrected-label training-pool audit](GALAR_TRAINING_POOL_RESULTS.md) verified all 40 study label CSVs from **21–60** using the official corrected archive (source SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`). **Those labels have already been inspected.** Don't repeat this parsing or claim that studies 31–60 have untouched outcomes. The original Galar 11–20 primary remains negative and frozen; authors' 61–80 remain reserved.

The public immutable [aggregate](../experiments/galar-training-pool-2026-11-02/summary.json) supports the following comparison, derived without reading any new source-level patient or frame data:

| Source image archive | Total compressed original images | Blood-positive exams | Blood-positive rows | Source-label positive runs | Native source stride |
|---|---:|---:|---:|---:|---|
| 31–40 | ~69.22 GB | 6/10 | 17,344 | 605 | 5 (31–38); 1 (39–40) |
| 41–50 | ~173.94 GB | 10/10 | 184,575 | 3,178 | 1 |
| 51–60 | ~202.69 GB | 10/10 | 161,649 | 2,377 | 1 |

**Recommendation:** qualify **31–40 as one ten-examination development group**, including the four zero-blood cases, before trying to acquire a larger bundle. It offers **six newly available positive-examination candidates**, short- and longer-run label patterns and two native export strides at a lower aggregate archive footprint than 41–60. This recommendation is a resource/provenance decision made using **previously inspected development labels**, not a blinded model evaluation, or proof that the images are independently grouped patients.

## Hard data-access gate — before any image transfer

1. Read publisher v2 archive catalog only; verify official Figshare source identity **44755700**, published size **69,219,317,963 bytes** and authoritative checksums. Probe metadata, header and 7z index with strict bounded HTTP Range, without full-archive fallback or accessing the authors' 61–80.
2. Determine source ZIP/7z solid-block layout, estimated minimal byte ranges for the proposed sample and available permitted private storage. If a reliable small transfer is impossible because of solid compression or endpoint/network restrictions, **stop**; don't download 69 GB implicitly or claim images acquired.
3. Before using any physical images, create a private, version-pinned per-exam source manifest: authentic native stride, original-image hashes, label state positive/negative/unknown, source gaps, device/custodian metadata, licence, unique examination IDs, candidate within-exam temporal continuity, and grouping declaration **unknown** until authenticated.
4. Assign all ten source examinations to **development only**. Never use 31–40 as newly independent evaluation after choosing them based on known blood-label support. Require separately qualified, independently locked new outcomes for future confirmatory claims. The previously examined Galar 11–20 and the authors' 61–80 cannot serve as convenient new confirmatory tests.
5. Use the existing `check_development_cohort.py` with verified private original bytes and externally pinned manifest, and perform independent human provenance review. Only then consider a fixed-score CNN comparison or temporal evaluation. No new training on this metadata checkpoint.

## Why the temporal module now takes an explicit source stride

A fixed source-ID increment of one was overly restrictive for the **already verified** label export format of 31–38 (predominantly stride five). The offline temporal baseline now takes a **required-to-be-proven** `source_stride` (default 1), rejecting gaps or mixed strides within a single examination. This fixes an input-compatibility issue without changing the original CNN, product defaults, or evaluated policies. **It does not establish improved blood-run retrieval**.

## Stop / Go

**Current status: BLOCKED FOR NEW PHYSICAL-DATA EVALUATION.** The official image endpoint has not been successfully reached in this runtime, patient linkage and source device/site information remain incomplete, and no new 31–40 source images were acquired here. The next valuable real-world step is a **bounded archive-header and data-access feasibility check** from an environment with permitted source access, not another 16-exam CNN sweep.

Reference: Le Floch et al. (2025), [official dataset](https://doi.org/10.25452/figshare.plus.25304616.v2), CC BY 4.0. No medical images, identifiable source-level records or individual predictions belong in the public repository.
