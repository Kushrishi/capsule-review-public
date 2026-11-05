# Original CNN — private real-image viewer replay and Galar 35 offline gate

**November 5, 2026 | Technical reproducibility verified; no model promoted.**

## Original unchanged CNN replay

A previously retained **1,361,018-byte private original-model package** was restored from the user's private Library and its SHA-256 verified: `5e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc`. The original `model/weights.pt` tensor-only checkpoint matched SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, with the source's **capsule-cnn-v1**, 96×96 aspect-preserving RGB pad and float32/255 preprocessing. No new model was fit or substituted.

A separate, retained **512-frame Galar 23 application workspace** supplied normalized private viewer PNGs, internal source/display hashes, a private SQLite viewer manifest and **512 previously persisted original-CNN scores**. Each normalized PNG matched its saved **display SHA-256**. **Zero PNG byte streams matched the separate original publisher PNG hashes**, as the viewer assets are re-encoded/normalized. The reported replay therefore validates the actual viewer preprocessing/inference path, **not publisher-original byte replay**.

Using the verified original model and identical preprocessing, **all 512 recalculated numerical scores equalled their persisted values exactly: max absolute difference 0.0**. No scores or image identities were exported. This is a technical reproduction of pre-existing predictions on the same examination, not evidence of clinical accuracy, generalization, new blood-event detection, pathology sensitivity or improved human review.

The safe, immutable summary is in [aggregate.json](../experiments/original-cnn-viewer-replay-20261105/aggregate.json). A [private-local replay program](../scripts/verify_private_cnn_viewer_replay.py) verifies the pinned original model package, a **caller-supplied private workspace SHA**, all saved display-image SHA-256s, 512 aligned scores, and the original architecture/preprocessing, before reporting only a non-identifying aggregate. The program does not need to upload images to public GitHub Actions. Synthetic-only tests cover exact replay, tampered input hashes, changed stored scores, absent images and model identity failure.

## Galar 35 corrected development-label preflight

The previously retained **22,007,390-byte private pre-outcome research package** was independently verified against its existing SHA-256 `3ad6d551e4ac13137e83e406161c1bf005d2754f68bb3880d0f4818db8382d38`. Its embedded official corrected Galar annotation ZIP matched the pinned **17,931,138 bytes**, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. Only **`35.csv`** was decoded, not the protected Galar 11–20 or 61–80 files. It independently reconciled **9,643** published positions on a gap-free stride-5 grid, **1,534** positive blood annotations and **29** contiguous annotation-positive runs. These source-defined runs are not individually adjudicated lesions.

The previously merged [private image acquisition script](../scripts/acquire_galar35_private.py) had a practical bug: **offline `--check-only` required `7z`** even though it never accesses or extracts original images. This change moves the 7z prerequisite to the `--acquire` mode only and adds explicit synthetic tests that prove check-only does not initiate an HTTP/source-pixel transfer.

## Boundaries and next experimental dependency

This execution environment has approximately 30 GiB free space but **no external Figshare DNS/HTTPS access** and **no 7z executable**. The Galar 35 original compressed block **5** (3,453,334,016 bytes) was **not** downloaded and its 9,643 original publisher PNGs were **not** scored. The verified native labels and checkpoint can be reused in an authorized private environment without needing to retrieve those artifacts again. Do not transfer medical images to public CI or commit raw labels, private model weights or prediction records.

The next real performance experiment still requires complete, locally verified Galar 35 original images and a fixed score comparison at equal K. Because 35's labels were previously inspected, that would remain **development-only**; neither its scores nor the earlier sparse temporal checks can revise the locked negative Galar 11–20 primary result. Authors' Galar 61–80 remain reserved. No patient-independent or clinical claim follows from these technical milestones.
