# Verified Galar 22 and 24 fitting-source acquisition

**Completed November 2, 2026 local time / November 3 UTC.** This is a source-image *acquisition and integrity* record, not a model or clinical validation result. The source images and identifying per-frame manifest are **not included in this public repository**.

## Acquisition question and frozen selection

We sought additional examination-level fitting examples in the original Galar corrected v2 dataset, particularly studies with no explicit `blood=1` annotation. The source-label audit identified two permitted fitting examinations:

| Corrected source study | Source annotation positions | Explicit `blood=1` rows | Original image positions retained |
| --- | ---: | ---: | ---: |
| Galar 22 | 7,529 | 0 | **512** |
| Galar 24 | 13,418 | 0 | **512** |
| **Total** | **20,947** | **0** | **1,024** |

The exactly sampled positions came from the **already-frozen** Galar 21–30 source-frame selection (source-chronological, label-blind, 512 reference positions per examination). For these entirely blood-negative-labelled studies, fitting-enriched and reference selections coincide; no source pixel scores, lesion interpretations, or model predictions determined the selected positions. The [exact immutable original acquisition specification](GALAR_NEGATIVE_22_24_ACQUISITION_SPEC.json) was committed before image acquisition.

An explicit `blood=0` is **not** evidence of a normal examination or proof that other lesions/pathologies are absent.

## Source provenance and data integrity

The experiment used the original Galar source-image archive (publisher Figshare file **45258019**, 31,989,399,751 bytes) and the corrected v2 annotation ZIP (Figshare file **60383963**, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`). Only the permitted 22/24 labels were used for these images; future Galar 11–20 and authors' reserved 61–80 were not opened.

Both examinations span overlapping original solid 7z compression blocks. The one-shot acquisition validated the publisher index/header and fetched only these **three original compressed ranges** using strict HTTP 206, matching previously verified full-length block SHA-256s:

| Original source block | Compressed bytes | Exact source images selected and verified |
| --- | ---: | ---: |
| 0 | 3,474,498,092 | 425 |
| 1 | 3,475,743,781 | 134 |
| 2 | 3,470,070,406 | 465 |
| **Total** | **10,420,312,279** | **1,024** |

The original images retained from the two studies comprise **316,413,628 unmodified PNG bytes**. Independent verification after downloading the completed private workflow artifact checked:

- The artifact ZIP and nested source ZIP integrity, original PNG structure/decoding, and exact 512-frame membership for each study.
- Each original source-image byte length and SHA-256 against the private manifest, with **zero mismatches and zero exact duplicate original-image hashes**.
- The expected 22/24 examination identities, allowed compressed source-block receipts, `blood=0` labels and predeclared selection roles.
- Absence of original images, per-frame identities or private labels in the public Git repository.

The corresponding temporary GitHub Actions artifact (original SHA-256 `0a44c67e43f31febbfb88815e5d28ec8a4b04d9be1f3d9c2ab47ccd77b674330`) was independently backed up in **Capsule Review Library / Galar 21-30 Images**. The permanent backup stays private with the source manifest and verification record. The original source publisher's **whole-archive MD5 was not independently verified**: hashing three 7z blocks does not amount to hashing the 31.99-GB full archive.

## What the acquisition establishes—and what it does not

These original source frames increase the available fitting collection from **14 to 16 study IDs** and from **10,123 to 11,147 fitting-source images** (including five studies with no explicit blood-positive annotations). Different source examination IDs are **not confirmed independent patients**. These are sparse selected original positions, not verified consecutive device footage or captured event durations.

A distinct, subsequently frozen three-fold comparison added **only these 1,024 images to model fitting**, while retaining the previous 14 examination-level held-out reference sets. Its [complete results, including the unresolved exam23/25 failures](GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md), are preserved without promoting a clinical model. The small descriptive macro ROC-AUC improvement does **not** establish better independent clinical generalization or unique-lesion sensitivity.

The public code repository is for software and nonidentifying aggregate research results. Its medical-source acquisition workflows are **disabled for public execution** and must not be repurposed to upload private images to public Actions. Future real-source acquisition belongs in a separately controlled private research environment.

**Source attribution:** Le Floch et al., *Galar* (2025), corrected v2; original research data CC BY 4.0. Dataset licensing is separate from this repository's software, which remains unlicensed.
