# Kvasir-Capsule publisher split-file audit — external candidate screen

**Date:** November 5, 2026. **Scope:** two upstream published `official_splits` CSV files, **not** the complete medical-image archive, not patient metadata, and not a new model evaluation.

## Pinned upstream source

- Publisher repository: https://github.com/simula/kvasir-capsule
- Upstream `master` commit inspected: `553601dc316fef82f39c952e28f60aaad66039e2`.
- `official_splits/split_0.csv` Git blob: `ff80ddcdb13b459507da9b2dd84186df68ad4a5f`.
- `official_splits/split_1.csv` Git blob: `9bc8c70747136c0e58fe2be7a402a7edafee2b6b`.
- Method: parse the published `filename,label` rows; obtain video/frame identity from the authors' `videoID_frameNumber.jpg` convention; compare video and frame IDs without publishing any of them. These are **catalogue rows**, not a complete patient-level source inventory.

## Observed aggregates

| Source | CSV rows | Distinct video IDs | Distinct frame IDs | Extra annotation rows on already-seen frames |
| --- | ---: | ---: | ---: | ---: |
| Split 0 | 23,061 | 25 | 23,061 | 0 |
| Split 1 | 24,100 | 25 | 24,092 | 8 |
| Combined | **47,161** | **43** | **47,153** | **8** |

- **Seven video IDs appear in both CSV files.** There are **zero frame-ID overlaps across the two files**.
- The eight repeated frame IDs **within split 1** have different annotation labels; do not call them eight duplicate medical images or cross-split leakage.
- The CSV label spelled `Blood` appears in **446 annotation rows**, from **two distinct video IDs**. Split 0 has 22 such rows from one video; split 1 has 424 from a different video. These are not 446 patients or blood-positive clinical events.
- The sum of these two CSVs is **not** the publisher's 47,238-label full-dataset figure. We did not reconcile the missing rows or verify image/patient archive completeness.

## Scientific decision

**NOT QUALIFIED** for a patient-independent blood-event retrieval study. The published two-fold image files are not video-disjoint, patient identity and repeated examinations are not authenticated, and annotation rows represent selected labelled frames rather than all source-video positions. A missing label cannot be converted to a negative. `Blood` cannot be silently equated with Galar's specific blood annotation, fresh bleeding, hematin, or clinically adjudicated lesions.

This **does not invalidate** the source dataset or its published baseline: the intended split usage and evaluation task may differ. It shows that reusing these files as an independent blood-detection training/test separation would require a new source-grouped split, verified patient mapping where possible, and outcome-specific validation. Two source videos carrying `Blood` do not presently provide useful breadth for the proposed blood-centric external study.

## Reproduce without redistributing source records

Download the two original CSVs from the pinned upstream revision to a **private local directory**, check their Git blob versions against the references above, and run:

    python scripts/audit_kvasir_official_splits.py /private/split_0.csv /private/split_1.csv

The script reads **no image pixels**, prints only totals/category counts and SHA-256 of its input CSV files, and does not output filenames, video IDs or frame IDs. The public regression tests contain entirely synthetic identifiers. Do not commit the source CSVs, clinical images, private analysis worksheets or patient records. The publisher's research-use and attribution terms still apply: https://datasets.simula.no/kvasir-capsule/.

**Next scientific action:** prioritize independently verified **additional blood-positive examinations and custodian-backed group mappings** over more Galar CNN reweighting or opportunistic training on these sparsely labelled Kvasir frames. See [Stage 1 issue #46](https://github.com/Kushrishi/capsule-review-public/issues/46) and the [existing external-cohort gate](EXTERNAL_COHORT_QUALIFICATION_20261104.md). The original Galar 11–20 negative result and reserved 61–80 outcomes remain untouched.
