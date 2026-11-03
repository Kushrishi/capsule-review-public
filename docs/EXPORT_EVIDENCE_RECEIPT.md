# Offline export evidence receipt — selected images, omissions and history integrity

**2026-11-03 | Engineering verification, not clinical validation.**

## What this delivers

Capsule Review can already export a selected review containing original-frame references, actual selected image pixels, notes and reviewer-marked intervals. A user may believe marking an interval means all its interior images have been exported, which is **not** how the software works: it exports only explicit saved/bookmarked/noted images and marked interval **start/end boundaries**, with duplicates counted once. The new independent **offline evidence receipt** reconstructs that fact from the exported ZIP, the saved change-event trail, and the full local study manifest. It fails rather than producing a success receipt if they disagree.

The report never reads source clinical labels, makes diagnoses, assumes that selected images were human-viewed, or declares source-index time coverage. Its source-agnostic accounting is compatible with Galar fitting studies, technical Rhode Island sequences, unnamed local PNGs, and synthetic local test data. **Do not upload patient/reviewer data to GitHub or hosted CI.**

## How to run with an existing local review

1. In the local viewer, export the study's ZIP using **Export selected review**. The ZIP includes full reviewer history and only the selected PNGs.
2. On the same trusted local installation, retrieve the **complete** study manifest using the existing localhost GET /api/studies/{study_id}/manifest endpoint. Save that JSON beside the private export. The manifest contains private frame identifiers and image hashes. Do **not** post it to this public repository.
3. With the project's package installed locally (python -m pip install -e .), run:

       python scripts/audit_review_evidence.py \
         --review-zip /private/review.zip \
         --study-manifest /private/study.json \
         --output /private/evidence-receipt-new.json

The output path must not exist. The command prints only counts and creates a **new aggregate-only JSON**. Re-running it from the same inputs produces the same counts (no timestamps or hidden random sampling in the report). The research notebook can compare such receipts but must preserve the private inputs separately.

## What is actually verified

- Export ZIP format and contents are checked; all included PNG display bytes are rehashed and compared against the stored display SHA-256; unexpected or duplicate ZIP members are rejected.
- Every imported manifest row must be present in contiguous imported-position order, with a valid original-file SHA-256 and display-hash field. The CLI **recomputes the exact source-image identity checksum originally produced by the Capsule Review importer** (filename, original source SHA-256, imported position, optional source index) and compares it with both manifest and exported-study identity. This does **not** re-read every original image byte; the actual manifest must come from the trusted original local study.
- Saved-frame events are replayed in sequence with exact per-frame revision increment, final bookmark/note/label state and last-update timestamp. Exported frames must be exactly the union of **current explicitly saved images and active marked interval endpoints**. Clearing a prior saved frame removes it from current selection, but its history remains. An omitted currently saved image, inserted unsupported saved image, forged older note or missing revision causes rejection.
- Interval creation/deletion history must reconcile completely against active intervals. A creation without either an active interval or a matching deletion is rejected, as are mismatched source-index boundaries.
- Counts separately identify saved images, interval boundaries, their overlap, unique positions within interval spans, interior imported images **not in the export**, and the longest consecutive run of such omitted imported positions. Overlapping intervals cannot multiply the count.
- At **the exact same number of selected images**, the receipt compares *ordinal imported-position proximity* to deterministic uniform midpoint selection. It reports mean/95th-percentile/maximum distance to nearest selected image, plus fraction of imported positions within one and five selected-image positions. It is a **technical distribution comparison, not pathology recall**. There is no fixed 10% workload restriction or source-video-time assumption.
- Only aggregate counts and caveats leave the report: no private study IDs, image names, original source indices, per-image image hashes, note content, model scores or training data.

## Limits and threat model

A digest recomputed from the **supplied** manifest proves consistency between that manifest and export's recorded import identity. It does not independently authenticate where the source images came from or rehash **unselected** image pixel bytes. Unexported display-image SHA values cannot be independently checked without those original files. The new tool also cannot prove the historical event log was not wholly replaced together with all other inputs; the export itself is not digitally signed or anchored in an independent ledger. Keep the original SQLite workspace and private source receipts when stronger provenance is needed.

Image positions describe only imported order. Even a perfect uniform ordinal-proximity score cannot establish that a short blood-positive annotation run was found, that a clinician viewed an image, or that a complete original examination was loaded. The exact corrected-label Galar evaluation is a **different frozen source-verified protocol** (see [interval evidence audit](INTERVAL_EVIDENCE_AUDIT.md)); it still requires the official label archive and the private original-image receipt. This tool does not bypass that data gate and does not inspect reserved examinations 11–20 or 61–80.

## Automated reproducibility

A public-only synthetic end-to-end test creates a real local application study, records multiple revisions including an explicitly cleared earlier review, marks an interval, exports a ZIP using the actual FastAPI route, validates the ZIP, and generates an offline receipt. It also checks absent source indices and a synthetic provenance flag. Negative tests try dropping an actually saved frame, changing a reviewer note or revision, forging interval history, changing an original-image manifest identity, and inserting an extra ZIP member; each must fail closed. A small ordinal position-coverage test compares to the exactly matched uniform workload for several sequence lengths.

Run:

    python -m pytest -q tests/test_evidence_receipt.py tests/test_interval_evidence.py tests/test_interval_evidence_export_integration.py

The same tests run in standard public CI on Python 3.11, 3.12 and 3.13, and the browser/local-model test continues to guard the actual viewer.

**Decision gate:** This is a reproducible engineering/evidence-accounting release, not permission to promote the blood CNN or claim the research endpoint is satisfied. Full-source pathology run coverage, independent cases, clinician behaviour and time savings remain unverified.
