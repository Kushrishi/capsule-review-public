# First private real-original-image Capsule Review app and score replay

**November 3, 2026 | Actual Galar23 pixels | Application integration QA, not a new scientific validation**

## A working research application on actual source images

The already inspected Galar examination **23** previously had an original-image archive, a frozen 512-reference-image import manifest, and a source-verified historical experimental blood-CNN score package. The new research queue in the public application was previously tested on generated synthetic images. To check the separate *real-pixel data plumbing*, we reconstructed a fresh **private local Capsule Review workspace** from these earlier frozen assets:

- **512/512 original source PNGs** were individually SHA-256-checked against the original private import manifest as they were read from the verified source archive.
- The application independently normalized and stored all **512 images**, and **512/512 resulting normalized display SHA-256s** matched the previous import manifest.
- All **512 original experimental blood-CNN scores** from the source-verified prior private score package were inserted as a complete model suggestion run in the application's **SQLite database**, with all numerical values subsequently compared back to the original score input.
- The browser's real image route and persisted per-frame prediction route were both exercised successfully; an **in-process headless Chromium UI session** opened the real study, displayed an actual endoscopy image with its saved model suggestion, navigated to the next frame, and had **no JavaScript errors**.
- Human review notes/bookmarks were not created by model replay. Original reference labels were **not** imported into model scores or the application's reference-label fields.
- A separate independent earlier research script had already reproduced the four exact-K prioritization policies across six previously inspected real score sets. This new replay additionally verifies that Galar23's score stream survives actual original-image normalization and SQLite persistence.

**Important software version boundary:** this original-pixel viewer replay used a **preserved older application snapshot** from the earlier Rhode Island s288 research reproduction ZIP, **not the latest public `main` browser/API code**. The current four-policy queue itself has already passed separate end-to-end synthetic-image CI and a real-score private analysis. Do not describe this older-snapshot real-image test as exercising the current main build byte-for-byte.

## Private portable workspace

A separately verified **110,095,614-byte private ZIP** contains the 512 original-medical-image-derived normalized PNGs and thumbnails, the review SQLite database with the complete experimental CNN score stream, an actual screenshot of the older viewer, an aggregate verification receipt, and a private-use README. Its SHA-256 is `648a68153a7d85c1a62f1a7e8ddc81e511f93db284255ff57748fb0eb76c8754`.

The full ZIP, the private screenshot, the replay script and verification receipt are stored **only** in the user's private Capsule Review Library, under **Model-Guided Review Queue 2026-11-03**. They must never be added to the public repository: the database and images contain original medically derived pixels, source identities and individual experimental prediction records. The [public machine-readable aggregate](../experiments/galar23-private-real-app-replay-2026-11-03/aggregate.json) contains **no individual source rows or images**.

For a private current-version demonstration, create a backup of the extracted workspace, point the latest locally cloned public app's `CAPSULE_REVIEW_DATA` to that folder, and let the app create any new additive tables. The original normalized image hashes and saved prediction scores should persist. This is further covered by [a synthetic compatibility regression test](../tests/test_legacy_workspace_score_queue.py), which removes interval-related tables from a generated 12-frame workspace, reopens it in the latest app, and verifies model score streams and human-authored notes remain intact.

## Scientific limits and next test

Galar23 belongs to an **already examined fitting/research set**, and its 512 reference images sample the source sequence very sparsely. This run verifies engineering identity, image storage and scoring—not distinct original blood-positive annotation runs, physician review effort, lesion sensitivity, patient independence, or prospective medical performance. The original model's poor performance on this study remains unchanged, and no model has been promoted to clinical use.

To advance the project's real scientific objective, the next gating experiment still needs a **checksum-verified exact corrected publisher source annotation archive**, denser source-image input, a prospectively frozen examination-disjoint design and matched workload comparisons of distinct original source annotation-run retrieval. Do not replace that endpoint with sampled positive-image counts or synthetic coverage, and do not open the reserved Galar holdout examinations for tuning.

**No clinical validity or independent pathology-generalization claim is supported by this milestone.**
