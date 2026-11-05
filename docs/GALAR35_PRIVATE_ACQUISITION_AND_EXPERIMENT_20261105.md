# Galar 35 — private complete-export acquisition and temporal experiment gate

**November 5, 2026 | Implementation ready for synthetic verification; original pixels NOT acquired.**

## Why Galar 35

The [verified 31–40 source-index layout](GALAR_31_40_INDEX_RESULTS_20261105.md) identified the lowest-cost complete *published-export* examination: all **9,643** PNG members belonging to source study **35** are in a single official 7z solid block (**block 5**, compressed **3,453,334,016 bytes**). It contains **1,534 already-inspected blood-positive annotated images and 29 positive annotation runs** according to the corrected official label audit. That does **not** represent 29 independently adjudicated lesions or 29 independent patients.

The explicit source range is **17,802,009,149 through 21,255,343,164 inclusive** of [Galar v2 source file 44755700](https://ndownloader.figshare.com/files/44755700) (official full archive 69,219,317,963 bytes; publisher MD5 `3bd4f9c9132e32d1a15d1ead5d96d0e2`). Only this one compressed block is in scope; the **full publisher MD5 cannot be claimed** from a partial download. The other two studies inside that block are **partial** and must not be evaluated as complete sequences.

## What is implemented

`scripts/acquire_galar35_private.py` has two explicit modes. Both accept:
- `--index-aggregate` pointing to the public [already verified aggregate](../experiments/galar-31-40-index-20261105/aggregate.json).
- `--labels-zip` pointing to a **private verified** `20251215_Labels_Updated.zip` (expected 17,931,138 bytes; SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`).
- `--workdir` and `--private-package` paths on an authorized **private** volume, both outside public Git and not previously existing.

`--check-only` is offline: it verifies the frozen source contract, **reads only 35.csv** from the SHA-verified source label ZIP, checks 9,643 distinct labels at source-index stride 5, validates 1,534 positives and 29 annotation runs, and requires at least **12 GB free private disk** and the `7z` executable. It does **not** connect to Figshare, read evaluation labels 11–20 or 61–80, download medical pixels, or overwrite prior private data.

`--acquire` additionally fetches the pinned 7z signature/header/index using strict HTTP 206 and the 8 MiB index cap; compares SHA-256 of every index part against the previously verified official receipt; privately resolves the original 7z member listing; ensures **all** 9,643 original study-35 indices exactly join the corrected labels and block 5 contains only the published numbers of 34/35/36 source images. **Only then** it streams **exactly block 5** in one byte-counted HTTP 206 request, with hard upper bound 3,453,334,016 bytes and SHA-256 receipt. No unbounded retry/mirror/full-file fallback exists.

Source 7z extraction/CRC, original PNG structure, unique original identities, original SHA-256 for each of all 9,643 PNGs, and private ZIP integrity are required before reporting success. The resulting package includes original PNG bytes, a frame/label/hash manifest and block receipt—all **PRIVATE**, never public CI artifacts. The tool never claims patient independence, expert lesion adjudication, full archive MD5 verification or clinical validity.

### Commands (PRIVATE machine only)

```bash
# Both destination parents must already exist on a private volume.
python scripts/acquire_galar35_private.py \
  --index-aggregate experiments/galar-31-40-index-20261105/aggregate.json \
  --labels-zip /private/20251215_Labels_Updated.zip \
  --workdir /private/galar35-stage \
  --private-package /private/galar35-original-pngs.zip \
  --check-only

# Deliberately NOT run in public GitHub Actions, and NOT performed in this change.
python scripts/acquire_galar35_private.py \
  --index-aggregate experiments/galar-31-40-index-20261105/aggregate.json \
  --labels-zip /private/20251215_Labels_Updated.zip \
  --workdir /private/galar35-stage \
  --private-package /private/galar35-original-pngs.zip \
  --acquire
```

Private storage for **3.45 GB compressed source plus decompression and original-image packaging** must be available; expect significantly higher temporary disk usage than 3.45 GB. No job, download or paid compute is scheduled by the public repository. If a source range, index hash, CRC, label alignment or file count fails, **stop** and retain no public source data.

## Exploratory model comparison — next stage, not yet an achieved result

Once the original image package is durably secured and independently replay-verified, score the **full 9,643-position published export** using the original frozen CNN checkpoint and its exact original preprocessing. Preserve scores and checkpoint privately; do not fit or choose a new model against known study-35 outcomes.

For an initial fixed **descriptive** comparator, use original score-bin and uniform queues plus rolling-max window **1 (raw)** and **3**, with source stride **5**, at **5%, 10%, 25%, 50%, 100%** exact-K image budgets. Report both positive-image recall and **distinct contiguous positive annotation-run coverage**, worst skipped source spans, full source-coverage gaps and paired differences under equal K. Keep zero-positive controls and examination-level heterogeneity visible in any later multi-exam comparison.

**Study 35 labels have already been inspected.** This study can support exploratory engineering and method development, **not** a newly blinded independent performance claim. The historical negative Galar 11–20 primary remains immutable; authors' reserved Galar 61–80 stay closed. Clinical user time savings and pathology sensitivity are not measured by an image-count budget.
