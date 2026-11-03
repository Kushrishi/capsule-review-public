# Original-image reviewer-interval replay: verified engineering result and explicit source-label blocker

**November 2, 2026 Toronto/Montreal local / November 3 UTC.** This was a **private, retrospective, scripted engineering replay**, using real original Galar 23 source pixels—not an independent clinical or model evaluation and not a human reader session. The [machine-readable aggregate](../experiments/galar23-interval-real-pilot-2026-11-03/aggregate.json) intentionally contains no original frame identities, individual predictions, reviewer notes, image SHA-256s or medical images.

## Objective and preselected method

The newly merged viewer supports reviewer-marked imported-image spans and exports only their selected boundary images. Our [frozen source-run evaluation protocol](INTERVAL_EVIDENCE_AUDIT_SPEC.json) separately distinguishes exact selected positive-image evidence from positive annotations whose indices merely fall inside a marked span. This pilot asks whether the **real-image software/provenance pathway** works when fed an existing source-verified Galar fitting study.

Before source-image import, the private execution plan fixed all selection rules without examining the label outcomes:

- Load the **512 original PNGs** tagged `reference_uniform=1` in the independently verified, previously preserved **Galar examination 23** image receipt. This is one *already examined* fitting study, not a new holdout. The private source package also includes enriched-only frames, which were **not** imported.
- Simulate precisely **51 bookmarks**, by selecting imported positions `floor((i+0.5)*512/51)` for `i=0..50`. These are deterministic, label-blind positions, not human judgments or a product workload limit.
- Simulate **16 marked intervals**, with start/end imported positions `(32*j, 32*j+16)` for `j=0..15`. No CNN ranking or true source annotation was used to choose the spans.
- Export through the **local Capsule Review application API**, reopen its persisted interval/bookmark workspace, and independently validate each selected exported image SHA-256 and source identity.

The locally executed archived v0.2 importer/application was adapted with the **byte-identical current public interval SQLite store and exporter** (Git blob IDs `9c500496...` and `c7eedd3e...`) and current interval endpoint semantics. This is **not** a byte-for-byte checkout of all current public-main source files; the complete current application is verified separately by its real hosted CI/browser tests. The replay is an additional source-image engineering gate.

## Observed outcome on original medical-image bytes

| Quantity | Verified count |
| --- | ---: |
| Previously source-hash-verified original reference images imported | **512** |
| `blood=1` labels in those 512 prior-verified reference records | **4** |
| Simulated bookmarks | **51** |
| Simulated image spans | **16** |
| Distinct imported images selected for the export (bookmarks + interval endpoints, deduplicated) | **79** |
| Exact source-positive labelled images among the 79 directly exported | **0** |
| Source-positive labelled imported images **strictly inside** simulated spans but **not exported** | **2** |
| Source-positive labelled imported images outside all marked spans | **2** |

All **512 original image file hashes** matched their private per-frame acquisition receipt during import. The complete 512-image study manifest preserved original source file hashes, source IDs and imported positions. The resulting **79-image review ZIP** was produced by the application, inspected by the independent public `read_review_export` verifier, and separately rechecked: all 79 exported PNGs matched their recorded display SHA-256s, all selected source identities matched the original receipt, and the 51 bookmarks/16 intervals persisted after reopening the local application.

**Why this matters:** two positive-labelled *imported* images lie inside numerically marked spans, while **no positive-labelled image was selected into the export**. Therefore, merely marking a span does not establish that those images were inspected, included as saved evidence, clinically identified or diagnosed. A positive span overlap cannot be substituted into the direct selected-evidence numerator.

This is a **single deliberately scripted case** and a negative direct-image-selection observation, not a model comparison. The source image labels came from the previously verified private acquisition receipt, not a fresh read of the official full corrected-label archive during this replay.

## Incomplete full-source annotation-run evaluation

The precise official corrected Galar annotation ZIP `20251215_Labels_Updated.zip` (expected SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`) was **not present or retrievable** in the private runtime. The [offline interval evidence evaluator](../scripts/evaluate_galar_review_intervals.py) deliberately refuses an archive without that exact source digest and permitted examination CSV.

Consequently **all full original-source positive annotation-run metrics remain unavailable (`null`)**: source-run denominator, import-representability ceiling, directly selected positive runs, and numerically overlapped source-positive runs. We did **not** manufacture a substitute ZIP, segment sparse reference frames as if they were the full original annotation sequence, unlock evaluation cases, or infer lesions.

This result does **not** replace our earlier [source-run audit](GALAR_RUN_COVERAGE_RESULTS.md) or measure patient-independent sensitivity, human clinical review behavior, original device capture times, completeness of the video, or clinician time savings. The original protected Galar 11–20 and authors' reserved 61–80 datasets remained unopened.

## Reproducibility and private retention

The **complete 32.8-MB private reproduction bundle** is preserved under:

`Capsule Review Library / Interval Evidence Evaluation 2026-11-02 / Private Galar23 Real-Image Replay`

It contains the 79-image application export, full private study manifest, immutable selection plan, replay/verification scripts, independent verification record, and checksums. The underlying source-verified 1001-image package remains in its preexisting private Library location. **Neither package is committed to this public repository.**

**Next gate:** obtain the exact public-source corrected labels ZIP privately and hash-check the complete archive. Then run the unchanged evaluator against the saved review ZIP, full study manifest, and private source receipt, with only `23.csv` read. Report the results as a retrospective simulated export, keeping direct evidence and numerical span overlap separate. If the source archive cannot be verified, leave the full-source outcome blocked.

**Citation:** Le Floch et al., *Galar — a large multi-label video capsule endoscopy dataset*, *Scientific Data* (2025), DOI [10.1038/s41597-025-05112-7](https://doi.org/10.1038/s41597-025-05112-7). Public Galar annotations are CC BY 4.0; source dataset licensing does not supply a separate software licence.

## November 3 addendum — verified export-evidence accounting on the preserved real review

After the [offline export-evidence receipt](EXPORT_EVIDENCE_RECEIPT.md) was merged, the exact previously retained **32.8-MB private pilot bundle** became accessible in an authorized private session. The private bundle's manifest checksums were verified for both the original **79-image application-export ZIP** and **512-row complete study manifest**. The exported ZIP passed the existing frozen selected-PNG SHA-256 and ZIP-member integrity reader. Its complete original importer-identity hash was recomputed and matched both source and export manifests. All **51 saved-frame revision events**, **16 interval creation events**, **16 active intervals** and the exact set of 79 exported frame positions reconciled. The pre-existing verified original-PNG receipt was not re-downloaded or republished.

This run used a **private independent reconstruction of the newly merged evidence-receipt accounting algorithm**, calling the archived locked ZIP reader and interval validators. It did not check out and execute the complete current public repository's command-line script byte for byte in the private container; public CI independently exercises that script on end-to-end synthetic application exports. The private audit therefore establishes consistent actual export data and *same-algorithm accounting*, not a byte-identical application rerun.

| Engineering receipt statistic | Verified result |
| --- | ---: |
| Verified imported original reference images | **512** |
| Directly exported images | **79 (15.43%)** |
| Previously saved/bookmarked images | **51** |
| Active reviewer-marked intervals | **16** |
| Distinct interval boundary images | **32** |
| Frames simultaneously saved and interval-boundary | **4** |
| Boundary-only images | **28** |
| Unique imported positions in marked spans, including boundaries | **272** |
| Unique imported positions strictly inside marked spans | **240** |
| Imported span-interior images **not** selected/exported | **216** |
| Total imported images not in the export | **433** |
| Longest run of consecutive unexported imported positions inside marked spans | **9** |

### Equal selected-image workload, technical position coverage only

At exactly **K=79 of 512 imported positions**, compare the original predetermined 51-bookmark/16-interval policy to a deterministic **79-position midpoint-uniform comparator**. Neither method is chosen from labels; importantly, K=79 is the actual resulting union of selected frames, not a product or scientific budget cap.

| Same-K imported ordinal-position metric | Simulated bookmark + interval selection | Midpoint-uniform 79 |
| --- | ---: | ---: |
| Mean distance to nearest selected imported position | **1.9941** | **1.6113** |
| 95th-percentile nearest imported-position distance | **4** | **3** |
| Maximum nearest selected imported-position distance | **5** | **3** |
| Fraction within one imported position | **42.58%** | **46.29%** |
| Fraction within five imported positions | **100%** | **100%** |

The naive deterministic uniform comparator distributes the **same number** of selected images more evenly in **imported order**. This is *not* evidence of higher blood-label or annotation-run retrieval, lesion detection, video-frame completeness, patient safety, clinician workload savings or verified original temporal coverage. The original imported source positions have **index jumps**, and cannot be converted to capture times. This was a **scripted** prior-inspected-case replay, not human reviewing and not an independent blind validation cohort.

The public, nonidentifying [machine-readable audit receipt](../experiments/galar23-interval-real-pilot-2026-11-03/export_evidence_receipt.json) contains counts and technical nearest-position metrics only. A [public-only arithmetic test](../tests/test_galar23_real_export_receipt_record.py) independently regenerates every positional count and distance from the **previously documented label-blind selection rule** (512 imports, 51 midpoint bookmarks, 16 intervals starting every 32 positions with width 16). The test has no original medical images, per-frame source identities, annotations or reviewer notes and cannot verify private PNG bytes; that verification occurred separately on the original preserved archive.

The private local evidence receipt JSON SHA-256 was **3391e33a1c8a6d23b0f462a873689934da4e2c2803cf744e89613654dec61465**. The receipt has no source-image identity data and remains in the private execution workspace; the source-review ZIP and private manifest were **not** pushed to GitHub.

### Remaining locked source-label gate

**Unchanged:** the exact 17,931,138-byte official corrected Galar label ZIP with SHA-256 **2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f** is still missing. Consequently **all full-source annotation-run denominators, direct source-run hits and interval source-run overlaps remain unavailable**. An engineering-export audit—even one involving original medical PNGs—cannot substitute for the original-source label-run evaluation. No protected Galar 11–20 or original authors' 61–80 source annotations/images were inspected.
