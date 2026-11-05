# Galar 35: original-image acquisition verified; durable-retention gate pending

November 5, 2026. [Aggregate](../experiments/galar35-private-acquisition-20261105/aggregate.json).

The existing private acquisition program successfully retrieved **only block 5** of official Figshare v2 file **44755700**: exactly **3,453,334,016 compressed bytes**, plus the verified **3,629,193-byte header/index**. A fresh official v2 catalog matched the pinned identity, size and publisher checksum metadata. No other image block or full archive was requested; the full publisher archive MD5 was **not** verified.

All **9,643 original study-35 PNGs** passed 7z extraction/CRC, PNG structure, source-grid, corrected-label alignment, individual SHA-256 and package CRC checks. A second byte replay independently reconciled every PNG's size and SHA-256 with the private manifest and found **zero exact PNG duplicates**. The originals total **2,609,216,822 bytes**; their private ZIP is **2,612,937,210 bytes**. Previously inspected development labels reconcile to **1,534 positives / 29 positive annotation runs** at native source stride **5**. Only `35.csv` was opened; no protected outcome files were read.

**Inference has not executed.** Complete originals are currently temporary cloud-workspace files. The private source receipts, corrected-label archive and unchanged original checkpoint have been durably retained, but the storage service rejected the complete-source save because of its quota. A separate private destination requires explicit authorization. Do not treat locally available originals or unfinalized uploads as durable copies. Keep this prerequisite before scoring, then durably freeze scores and exact-K queues before the separate outcome audit.

Software verification: **908 passed / 1 skipped** on Python 3.12; the focused acquisition/full-sequence/temporal tests passed **85 checks**. An independent queue verifier matched all four original policies across **96 synthetic exact-K cases** with tied scores and independently checked window-3 processing. The local browser smoke was blocked by sandbox socket restrictions; public synthetic CI remains the browser-verification route. No application, model or selection implementation changed.

This is an acquisition/provenance milestone, **not an AI performance result**. The prespecified 5/10/25/50/100% comparisons and missed-run analysis remain unexecuted. The historical Galar 11–20 **negative 10% primary** stays unchanged; Galar 35 is previously inspected development data, and authors' **61–80 remain unopened**. No model is promoted.
