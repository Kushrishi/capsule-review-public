# Rhode Island complete-sequence replication — s280 and s284

**Status:** completed prespecified *study-level anatomy/position* comparison. Run 2026-11-01 Eastern / 2026-11-02 UTC on a bounded GitHub Actions Ubuntu runner. Original s288 is an exploratory historical comparison. No pathology model, lesion ground truth, independent patient identifiers, clinical reading-time measurement or original acquisition timestamps were used. No claim of clinical validity, patient independence or new state-of-the-art method is warranted.

## Prespecified acquisition

The frozen specification [SEQUENCE_SELECTION_SPEC.json](SEQUENCE_SELECTION_SPEC.json) had SHA-256 `c92500af677a12323ea5b8ebf43feb1b17f41bcf44ccfa80e94f28a19289399e`. **Before examining labels/images**, two additional complete nested studies were selected by published member size: `s280` (103,418,092 bytes; ZIP CRC32 `1a870799`) and `s284` (115,960,292 bytes; CRC32 `6f1947e6`). Original source: Figshare file 37560007 in Rhode Island collection, https://doi.org/10.6084/m9.figshare.c.6071216.v1; Charoen et al., *Scientific Data* (2022), https://doi.org/10.1038/s41597-022-01726-3.

Both source members were fetched with **exact HTTP 206 byte-range responses**, not the entire 5.99 GB outer archive. Both nested archives passed the stored-member CRC32, ZIP member CRCs and decoder checks. The verified source SHA-256 identities were:

| Study | Full selected ZIP SHA-256 | Decoded original images | Anatomical transitions |
| --- | --- | ---: | ---: |
| s280 | `2f6e407a17820e56a1c6af34c6d9853b35ca24fe324336e0b13a8a779a7e14d8` | 4,273 | 3 |
| s284 | `42eeb48d8ca640c8e3b18dfcf89d98903f6165ca85dbdb9e4c7192be1e107633` | 5,117 | 3 |
| s288 (previously explored) | `145dad913880a155c7ac5942742e1941cb85c9508dd835e8a444ee66a7b0828e` | 4,189 | 3 |

Cumulative conservative source acquisition upper bound, including the s288 run: **412,500,050 bytes (393.39 MiB)** out of 536,870,912 bytes (512 MiB). No extra archive was downloaded and no unapproved new compute service was purchased. GitHub Actions reused existing CI infrastructure. The research-data downloads occurred only on that ephemeral runner. **The original s280/s284 ZIPs were not retained in ChatGPT Library or GitHub Actions artifacts**; reanalysis requiring their pixels needs another lawfully acquired copy and an acquisition-budget decision. The immutable source SHA-256/CRC/size records and full aggregate numeric outputs are preserved here.

## Unchanged frozen comparison

For each complete sequence, select exactly `ceil(budget × N)` images at 5%, 10% and 25%, including both endpoints. The four methods were identical to the earlier s288 analysis: uniform index spacing, globally highest adjacent 64×64 RGB change, the strongest change in each chronological bin, and the mean of 100 seeded endpoint-anchored random selections. Anatomical region folder labels were **not inputs to any policy**. Report boundaries within 0, 2 and 5 source indices, maximum/mean distance to a selected image, and chronological gaps. The original acquisition rate is unknown, so these distances are frame-index units, not seconds.

### Anatomy boundaries reached within ±5 source frames (of three per study)

| Budget | Study | Uniform | Global change | Stratified change | Random mean |
| --- | --- | ---: | ---: | ---: | ---: |
| 5% | s280 | **2** | **2** | 1 | 1.75 |
| 5% | s284 | 1 | **3** | 2 | 1.26 |
| 5% | s288 — exploratory | 2 | 2 | **3** | 1.70 |
| 10% | s280 | **3** | 2 | 2 | 2.27 |
| 10% | s284 | **3** | **3** | **3** | 2.32 |
| 10% | s288 — exploratory | **3** | **3** | **3** | 2.32 |
| 25% | all three studies | **3** | **3** | **3** | 2.83–2.91 mean |

**Important coverage caveat:** s280 has only **two esophagus frames**. Because every deterministic policy always selects the first frame, the first anatomical transition is automatically within two positions of a selected frame and therefore counts as one of three ±5 hits regardless of visual selection quality. This further weakens comparisons based on just three anatomical boundaries. All **9,390 new images** have `.png` filenames but decode as **320×320 JPEG**, so the actual source encoding must not be misreported.

**Interpretation:** the positive 5% stratified-change s288 observation failed to replicate consistently. On s280 it reached only one anatomical boundary versus two for both uniform and global; on s284 global reached all three, stratified two, uniform one. On the two newly selected studies, uniform reached all three at 10%, while each change policy reached 2/3 on s280. There is no consistent boundary-recall winner across these few studies; only three boundaries occur per study, and each was selected after previously inspecting s288, not selected using these outcomes.

### Worst-case source-frame distance to any chosen image

| Budget | Study | Uniform | Global change | Stratified change |
| --- | --- | ---: | ---: | ---: |
| 5% | s280 | 10 | **219** | 20 |
| 5% | s284 | 10 | **235** | 20 |
| 5% | s288 | 10 | **281** | 20 |
| 10% | s280 | 5 | **155** | 10 |
| 10% | s284 | 5 | **141** | 10 |
| 10% | s288 | 5 | **225** | 9 |
| 25% | s280 | 2 | **71** | 4 |
| 25% | s284 | 2 | **94** | 3 |
| 25% | s288 | 2 | **192** | 3 |

**Replicated technical finding:** selecting frames only by global visual change can leave very long unseen portions of the original source timeline. Chronological distribution reduces those gaps, but uniform sampling offers the tightest maximum-distance guarantee. This is *not* evidence that uniform review is clinically safer, because the endpoint is ordinal proximity, not lesion retention.

## Verification and next scientific gate

The cloud workflow verified all source-member and internal ZIP CRCs, numerical image index completeness and four correctly ordered anatomical regions for both new studies; it recomputed each image-change score and evaluated the unchanged frozen selection code. The downloaded aggregate artifact SHA-256 `31a51c2738d6f1ce17cfa9b5a0e0c52ed8d5698c341a12d79012fb0e8ec407b0` was separately checked locally against receipt/result SHA-256 values and all table arithmetic; see the aggregate JSONs in `experiments/rhode-replication/`.

The most defensible next step is **not** to optimize the image-change rule on these tiny counts, but to design an *independent anatomy-transition coverage benchmark over a larger fixed collection*, or return to the primary pathology task with a suitable, densely labelled dataset. Important clinical questions remain unanswerable without actual per-interval pathology references and patient-independent splits.

For study 280 and 284 results, see `experiments/rhode-replication/s280-results.json` and `s284-results.json`; the preexisting s288 record remains frozen. `scripts/compare_sequence_selection.py` is unchanged. No original image bytes, raw annotations, model weights or individual frame decisions have entered the repository.
