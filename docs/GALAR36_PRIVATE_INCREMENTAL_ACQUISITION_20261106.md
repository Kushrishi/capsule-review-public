# Galar 36 — private incremental complete-source acquisition

**November 6, 2026.** [Public-safe source-label preflight](../experiments/galar36-source-preflight-20261106/aggregate.json). Original source PNGs for Galar 36 **not acquired** by this change. This is **previously inspected development material**, not a fresh independent validation cohort.

## What has actually been verified

The official corrected-label ZIP was recovered from the existing verified Galar35 private research evidence bundle and independently SHA-256 checked: 17,931,138 bytes, `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. Only the existing corrected development-label member **`36.csv`** was opened, with **13,326 rows, 209 blood-positive rows, 59 source-defined annotation-positive runs**, native source stride **5**, and zero internal published-export grid gaps. No original medical pixel bytes or other examination label CSVs were opened.

The official Galar31–40 archive-index result remains the basis for image acquisition. The source file ID is **44755700**, full published length **69,219,317,963 bytes**; the full publisher MD5 cannot be verified from selective source blocks.

To obtain the *complete published* Galar36 source sequence with minimal new transfer:

| Item | Exact bytes | Original content |
| --- | ---: | --- |
| Previously retained 7z solid **block 5** | 3,453,334,016 | 3,098 of study36's original PNGs, plus neighbouring studies' images |
| **NEW** 7z solid **block 6** | **3,430,870,954** | Remaining **10,228** study36 PNGs plus part of study37 |
| Total restored source blocks | 6,884,204,970 | Enough to extract complete Galar36, not a full verified 69 GB archive |

The new transfer's **exact inclusive Range is 21,255,343,165–24,686,214,118**. Never download the whole 69.2 GB source archive as a fallback.

The retained private block5 SHA-256 pin is `0b24a245d8f7e72b69ad1e1295d757ce43a03ccaa87e73795423804c5e70d225`, from the previously secured Galar35 receipt. Its real original bytes must be **reconstructed and hashed again** before using them in a new private source reconstruction; an inventory metadata check alone is not enough.

## Reuse existing PRIVATE retained source receipts and part archives

The private evidence bundle `Galar35_Private_Full_Sequence_Evidence_20261105.zip` contains:

- `restore_galar35_parts.py`
- `durable-sources/galar35-private-source-retention-manifest.json`
- `durable-sources/galar35-private-source-receipts.zip`

The private Drive folder already retains 35 original block-5 part ZIPs; download those private parts only into an authorized secured workspace. Use the existing private restore program to reconstruct `galar35-source-block5.bin` in exactly 35-part order, verifying each part SHA256 and the complete block5 SHA256. The source receipts ZIP contains the original pinned 7z index header/index parts and the verified official corrected label ZIP. Recover **only the permitted corrected ZIP** to an external private path, without reading unrelated outcome CSV contents.

## Explicit, private-only execution

The new `scripts/acquire_galar36_private_incremental.py` reads only required source files and performs:

1. `--check-only`: strict source-index consistency, block5 original-byte checksum, pinned saved source-index receipt/header SHA256s, corrected `36.csv` source support/contiguity, minimum **22 GB private free disk**. No HTTP, 7z, source-image decompression or output data.
2. `--acquire`: the same checks; requires installed `7z`. Writes a sparse 69.2 GB logical 7z on a sparse-capable PRIVATE volume containing only the exact original publisher index plus source block5. Issues exactly one bounded HTTP206 byte-range transfer for new block6. Lists source members privately and **requires precisely 3,098 study36 originals from block5 and 10,228 from block6**, and a complete source-index-to-corrected-label join.
3. Extract **only** study36 PNG members, verify their 7z CRCs and original PNG structures, retain original publisher basenames and source hashes, validate counts and original label alignment, then create an exclusive-create, non-encrypted PRIVATE original-image ZIP and detailed private receipts. Hash the complete image package and verify ZIP CRC before reporting success. Compressed material from partial neighbours must not be called complete evidence or published as a study.
4. **Do not** upload medical images, individual source IDs, individual annotations, weights, original score vectors or the private source receipts to the public GitHub repository or public GitHub Actions artifacts.

Example (never run inside public CI):

```bash
python scripts/acquire_galar36_private_incremental.py --check-only \
  --index-aggregate experiments/galar-31-40-index-20261105/aggregate.json \
  --retained-block5 /private/galar35-source-block5.bin \
  --retained-index-receipts-zip /private/galar35-private-source-receipts.zip \
  --corrected-labels-zip /private/20251215_Labels_Updated.zip \
  --workdir /private/galar36-stage \
  --private-output-zip /private/galar36-original-pngs.zip

# Deliberately NOT executed by this public change:
python scripts/acquire_galar36_private_incremental.py --acquire \
  --index-aggregate experiments/galar-31-40-index-20261105/aggregate.json \
  --retained-block5 /private/galar35-source-block5.bin \
  --retained-index-receipts-zip /private/galar35-private-source-receipts.zip \
  --corrected-labels-zip /private/20251215_Labels_Updated.zip \
  --workdir /private/galar36-stage \
  --private-output-zip /private/galar36-original-pngs.zip
```

Inputs and outputs are private and must be independently access-controlled and durable. Output ZIP is not encrypted, so its secrecy depends on private storage security. The completed transfer and package hashes are *not yet available*; neither the full publisher MD5 nor source-device frame-completeness/patient identities can be proven with this subset.

## Next scientific experiment, conditional on original source availability

**Fixed-policy replication comes before new model fitting.** Run the *unchanged original CNN checkpoint*, original preprocessing and the same original four exact-K selection policies plus the fixed temporal window-3 comparator on every Galar36 published original image, at the same 5/10/25/50/100% budgets, using separately frozen predictions and private labels. Measure source-defined annotation-run coverage and failure modes, without choosing a new temporal window or selecting the best policy based on Galar35. This is a development replication to study heterogeneity, not an independent clinical test.

Only after source integrity and grouping checks should a distinct, explicitly locked examination-diversity *training* experiment be contemplated. Unique patient linkage and source-site/device provenance are not yet authenticated; do not claim patient-independent generalization. Galar11–20's negative frozen primary remains unchanged and authors' reserved 61–80 outcomes stay unopened.
