# Galar 31–40 — verified index-only result and next experiment decision

**November 5, 2026.** [Completed metadata-only GitHub Actions run](https://github.com/Kushrishi/capsule-review-public/actions/runs/42103020040) · [Reproducible aggregate](../experiments/galar-31-40-index-20261105/aggregate.json) · [Source gate](GALAR_31_40_ARCHIVE_INDEX_GATE_20261105.md)

## Verified technical result

The official Figshare v2 source **44755700** passed exact source identity, strict HTTP 206, range accounting, start/NextHeader CRC and 7z metadata-layout checks. **3,629,193 bytes** of header/index were transferred, versus **69,219,317,963** original compressed archive bytes. The header index contains **381,787 image members over 10 examinations and 18 solid compression blocks**. Every study's indexed image count matched the previously audited corrected-label row count and had no internal gaps on its native source-ID grid (stride 5 for studies 31–38, stride 1 for 39–40). The 18 block compressed sizes total **69,215,688,770 bytes**; together with header/index bytes this exactly reconciles to the published archive size. This is a strong *index/layout* check, **not** the full publisher MD5 or image-byte integrity verification.

The nonidentifying artifact ZIP downloaded and CRC-checked for this report has SHA-256 `c4bbbc542bc863fad88745c79195e520a1bf074a87a5968769c05c9c30b6c6de`. GitHub Actions source artifact ID **13448534710** is temporary (7-day retention); this public aggregate and code are the durable nonidentifying record. No source image pixels or individual frame identities were downloaded or committed.

## Acquisition economics from verified solid-block layout

| Full published-export examination | Compressed solid blocks needed | Minimum transfer if complete blocks required |
|---|---|---:|
| **35** | **5** | **3,453,334,016 bytes (~3.45 GB)** |
| 36 | 5, 6 | 6,884,204,970 bytes |
| 34 | 4, 5 | 6,963,285,731 bytes |
| 31 | 0, 1 | 7,094,259,360 bytes |
| 39 | 8–13 | 25,510,343,310 bytes |
| 40 | 13–17 | 19,833,541,469 bytes |

**Recommendation: one fixed development-only source, examination 35.** All **9,643** published original frame entries for this examination lie entirely inside **block 5**, which also contains **2,876 partial image entries from study 34** and **3,098 partial entries from study 36**. Previous corrected labels identify **1,534 blood-positive annotated rows and 29 source-label runs in study 35**. This offers the strongest targeted acquisition at the least verified compressed-block cost.

The partial neighbouring examinations **cannot** be called complete-event sequences, and the 9,643 indexed frames cannot be called every original device exposure without clinical source verification. A source stride of five is an export-index convention, not a five-frame duration or elapsed-time interval.

## Next gate — NOT yet authorized or executed

1. Obtain a separate costed authorization and verify private storage capacity for one **3.45 GB compressed** block plus its larger decompressed contents, source image retention, and source receipt replay. Prior 512 MiB technical-acquisition constraints must not be silently overridden.
2. Pin the byte range for block 5 and original header-only receipt; verify HTTP 206 and SHA-256 after the bounded retrieval, then 7z extraction integrity, individual PNG hashes, exact original indices and original label joins, **outside public Git**. Do not download any other block or source archive opportunistically.
3. Treat study 35 as **development only**, with no patient-independent or clinical effectiveness claims. For a temporal exploratory comparison, verify the original export and prespecify the score model, source stride, window, baselines, equal-K budgets, outcome coverage, and exam-level reporting. Do not retune against already-locked Galar 11–20.
4. Require further examination-diverse source material and patient/custodian grouping before independent or clinical generalization. The authors' Galar 61–80 remain reserved.

**Scientific status:** the prospective original-image acquisition and new performance test are **not yet performed**. Only a structural source-index audit is complete. The original Galar 11–20 negative primary remains exactly unchanged.
