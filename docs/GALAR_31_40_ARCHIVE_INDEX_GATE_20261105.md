# Galar 31–40: bounded original source index feasibility

**Research gate — November 5, 2026.** Development-only. A successful index check is not approval to download clinical images or train an independent clinical model.

## Pinned source

- Le Floch et al., *Galar* v2, DOI: https://doi.org/10.25452/figshare.plus.25304616.v2 (CC BY 4.0).
- Publisher file **44755700**, `Galar_Frames_31_to_40.7z`: **69,219,317,963 bytes**; published MD5 `3bd4f9c9132e32d1a15d1ead5d96d0e2`. The **full source MD5 is not verified** here.
- Previous immutable [corrected-label training audit](GALAR_TRAINING_POOL_RESULTS.md): 10 cases, six with blood-positive labels, 17,344 positive annotated rows and 605 source-label-defined runs. The labels were **already inspected**; none of these exams can now be presented as an untouched independent test. Study 39 accounts for 10,565 of the 17,344 positives (60.9%).
- Native source-frame export stride: five for examinations 31–38, one for 39–40, from the previously verified label-blind source-index statistics.

## Safeguarded metadata-only workflow

The [bounded source reader](../scripts/probe_galar_archive.py) and [aggregate-only 31–40 index audit](../scripts/audit_galar31_40_index.py) require fresh publisher metadata matching exact file ID, name, size, URL and publisher MD5. They require exact HTTP **206** and **Content-Range**, HTTPS redirect allowlisting, 7z start/NextHeader CRC verification, an **8 MiB total archive-index transfer cap**, and a separate bounded metadata-JSON retrieval. **HTTP 200 full-content responses are rejected before reading**; there is no automatic fallback.

The sparse 7z archive is **logical archive-size only**; only retrieved metadata header/index bytes are physically written. Its full private `7z l -slt` member listing is never published. The audit output contains only aggregate source counts, internal native-grid gaps, block IDs and compressed block-size estimates, and limited source checksums. The workflow uploads only its public-safe aggregate and index receipt; no source image pixels, individual frame IDs, model predictions or patient identifiers are placed in Git.

The workflow triggers automatically only when its own YAML is first committed on the isolated research branch. It is not triggered automatically on `main`, and any future image-block transfer requires a distinct deliberately bounded plan.

## Technical decision requirements

An acceptable index must show all ten cases (31–40), one original frame index per image, native-stride-compatible source IDs, compressed sizes for every 7z solid block and image-member counts consistent with previously audited corrected label rows. Any unexpected member from another examination, malformed index, duplicate frame, metadata mismatch, missing block size or unsupported transfer is a **BLOCK**.

Even a successful index is only **source access feasibility**, not proof of completed clinical coverage, unique patients, independently adjudicated lesions or device-exposure/timestamp completeness. Any contemplated acquisition must use source-block cost estimates with explicit private storage and CPU limits. A 69 GB full archive must **not** be pulled just to complete a roadmap.

If the official Figshare endpoint cannot be reached in the cloud runtime, record the failure and stop rather than retrying with unbounded transfer or alternative unverified mirrors.

The original Galar 11–20 negative primary result is immutable. Authors' 61–80 remain reserved. No additional model training, pathology scoring or clinical validation takes place in this stage.
