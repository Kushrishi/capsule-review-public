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


## November 6 update — incremental positive-examination diversity after PR #62

The November 5 status above is superseded **for examination 35 only**. [PR #61](https://github.com/Kushrishi/capsule-review-public/pull/61) completed and privately retained all 9,643 original Galar35 PNGs and block 5, executed the unchanged CNN, and recorded a negative fixed window-3 result. [PR #62](https://github.com/Kushrishi/capsule-review-public/pull/62) found that 16-exam CNN early positive-image retrieval was heterogeneous after conditioning on coarse chronology: macro primary excess **−2.2330 percentage points**. No AI model was promoted.

The previously verified 18-block official index now permits a source-budget comparison for improving *positive-examination diversity* without reacquiring the full 69 GB archive. The new [offline incremental acquisition cost planner](../scripts/plan_galar31_40_development_blocks.py) only reads the public source index, enforces exact publisher source/range/label-count metadata, and never downloads images.

| Full published-export study added alongside study 35 | Incremental block(s), assuming retained block 5 is reverified | Incremental original compressed bytes | Previously audited blood-positive row fraction | Positive source-annotation runs |
| --- | --- | ---: | ---: | ---: |
| **36: first conditional candidate** | **6** | **3,430,870,954** | **209/13,326 (1.57%)** | **59** |
| 34: alternative very-low-prevalence case | 4 | 3,509,951,715 | 49/10,867 (0.45%) | 9 |
| Both 34 and 36 | 4 and 6 | 6,940,822,669 | heterogeneous | 68 additional |

Existing block 5 holds only **3,098 partial Galar36 images** and **2,876 partial Galar34 images**; these are **not complete original sequences**. A bounded block-6 transfer would supply the remaining 10,228 indexed images for Galar36. These are verified *index economics*, not downloaded or checksum-verified new image bytes.

Run the metadata-only cost gate without network access:

```bash
python scripts/plan_galar31_40_development_blocks.py \
  --exam 35 --exam 36 --presumed-retained-block 5 \
  --max-additional-bytes 3500000000
```

**No new source transfer or model training is authorized or executed by the planner.** Before either: independently reverify the saved private block-5 SHA256/parts; establish study grouping and available device/site provenance (patient linkage still **unverified**); verify rights, secure storage and cost; lock a credible examination-separated development experiment; then separately authorize only the exact requested source block. The study labels were already inspected. Neither this planning action nor any subsequent training on 34/35/36 can establish patient-independent clinical generalization. Galar 11–20 locked negative primary and authors' 61–80 remain protected.

The first decision is therefore **source/group qualification**; only then is Galar36's low-positive-prevalence complete published export a defensible candidate for exploring whether additional positive-exam diversity helps difficult-case retrieval.
