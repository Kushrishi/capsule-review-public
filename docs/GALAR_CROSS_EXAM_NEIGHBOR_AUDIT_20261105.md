# Cross-examination neighbour audit — November 5, 2026

**Status:** completed private image-integrity research; **no patient-independence certification or model improvement**. This extends the earlier [source verification](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) and [equal-dHash candidate triage](GALAR_VISUAL_SIMILARITY_TRIAGE_20261105.md). It does not create a clinical test set.

## Question and result

Do our selected source images contain obvious copied image views **across different Galar examination IDs** that the previous identical-hash comparison missed?

| Scope | Confirmed observation |
| --- | ---: |
| All different-examination pairs of archived, source-verified 64-bit dHashes | **57,789,904** pairs across **11,147** images (16 exams) |
| Exactly equal coarse dHash | **5,293** pairs (previously checked) |
| Coarse dHash Hamming distance at most 6 | **704,222** pairs — most are *not* confirmed duplicates |
| Previously verified ImageNet MobileNetV3 feature vectors | **10,123** images, **14** examinations; source exams 22 and 24 absent from this bank |
| Unique exact top-five cross-exam embedding-neighbour pairs | **43,434** |
| Strongest cross-exam embedding cosine similarity | **0.95879** (none had best cosine >=0.98) |
| Top-five embedding pairs with cosine >=0.92 | **551** |
| Unique original PNGs reverified for these 551 pairs | **451** from 10 private source archives |
| Highest observed pixel-aligned grayscale SSIM in this subset | **0.79154** |
| Pairs reaching pixel-aligned SSIM >=0.90 | **0** |
| Pairs meeting the *same strict close-copy rule as earlier* | **0** |

Each original candidate image was SHA-256-verified against the retained private source-image receipt **before** its fresh pixel comparison. The strict rule remained grayscale 64×64 full-frame SSIM >= **0.95**, full RGB MAE <= **0.06**, and central RGB MAE <= **0.07**. Thresholds describe suspicious *pixel-aligned* copies, **not medically validated identity links**.

For embedding search, the previously source-verified private **10,123×576** frozen ImageNet MobileNetV3-Small feature bank was hash-rechecked before use. All different-exam cosine similarities were searched exactly in bounded matrix batches. We saved each image's five nearest *other-examination* neighbours, deduplicated pairs, and evaluated all pairs with cosine >=0.92 against original pixels. **This is not an exhaustive learned-feature search of 11,147 images**, nor a full pixel-SSIM scan of all 57.8 million pairs. The 0.92 threshold is a descriptive follow-up selection, not a medically established duplicate detector.

## Interpretation

The enlarged screen found **no strict aligned copies among the 551 highest-scoring embedding candidates**. That is stronger source-integrity evidence than the prior test restricted to identical coarse hashes. However, it does not eliminate rotated, cropped, distorted, colour-transformed or different-view duplicate studies; repeated patients might have entirely different images. CNN representations are not validated source-identity detectors, and the selected images are not complete original videos. We do **not** call the source studies patient-independent or externally validated.

For medical AI validity the more important unresolved issue is **authenticated patient-to-video linkage and acquisition-site/device provenance**. As the [Galar data descriptor](https://doi.org/10.1038/s41597-025-05112-7) describes, videos were assigned random study IDs and drawn from multiple systems and sites. The publisher's [fold-generation code](https://github.com/EKFZ-AI-Endoscopy/GalarCapsuleML/blob/main/generate_folds.py) groups by *video*, not an independently verified person key. A small official metadata-only archive was identified, but the download host was inaccessible in this environment; no new patient/device attribution was invented.

## Reproducibility and privacy

- [Nonidentifying aggregate](../experiments/galar-cross-exam-neighbor-audit-20261105/aggregate.json) preserves both screening populations, thresholds, counts and limitations.
- [Reusable private-score audit](../src/capsule_review/similarity_triage.py) now supports embedding-neighbour candidate records, validates cross-examination source tokens and pixel-score thresholds, rejects duplicate rows, and returns **only** redacted counts.
- [Private-archive replay](../scripts/replay_cross_exam_neighbor_audit.py) pins the private archive SHA-256 and reconciles its saved 551 source-pair scores with the public aggregate; it is a **score-level replay**, not an independent original-image re-inference.
- [Synthetic tests](../tests/test_cross_exam_neighbors.py) cover invalid scores, privacy and unverified-group boundaries.

The full **11-file, 571,736-byte private research archive** is saved separately in the user's access-controlled ChatGPT Library, SHA-256 `5e43c1a39422ece4a3b1549f47ec397d14f2c6fddd58146b5492e4443ab6e53d`. It contains research scripts, source-frame neighbour indices, 551 private pairwise measurements and SHA-256 receipts, **no original medical pixels** and no copied 10,123×576 image-derived feature matrix. Reproduction requires the separately retained frozen MobileNet feature bank, original PNG archives and prior source audit.

**Decision:** keep Issue #46 open. These findings reduce obvious image-duplication concerns but cannot clear patient independence, represent external outcomes or justify any new model promotion. The existing Galar **11–20** negative 10% primary remains frozen; the authors' reserved **61–80** examinations remain unopened.

**Next high-value dependency:** authentic cross-study patient/device/site linkage and **additional positive examinations from a legitimate independent development source**, not another loss-weight or architecture sweep on previously inspected cases.
