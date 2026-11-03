# Opt-in full marked-span evidence archive

**2026-11-03 — Product/evidence-preservation change, not a clinical result.**

## Problem identified by the frozen Galar 23 engineering replay

Our standard **Export review** intentionally includes explicitly saved/bookmarked/noted images and the two boundaries of marked intervals. It does **not** contain all imported interior images. In the already-inspected, scripted 512-image Galar23 replay, that gave **79 exported images** while **216 imported interval-interior images** were omitted. This is an image-retention problem, not evidence of a missed diagnosed lesion; only 79 images were selected by the original scripted protocol.

**New separate action: Export full spans** includes the exact union of every **imported** image position within every currently active marked interval (including interiors and both boundaries), and all other explicitly saved/bookmarked/noted imported images. Duplicate and overlapping image positions are retained once. This does NOT reconstruct original video images never imported into Capsule Review.

The default **Export review** remains unchanged, preserving historical research comparison semantics. The existing offline evidence receipt and locked Galar corrected-label evaluation remain pinned to the boundary-only selection. The new full archive is a **distinct output**, never silently substituted into frozen experiments.

## How to use

In a local Capsule Review examination, save a marked image interval. The **Verify evidence** action audits the existing boundary-only review export. The **Export review** action downloads that standard review ZIP. Select **Export full spans** separately to request a private, potentially larger archive. The browser confirms that this retains all imported interval images and may contain research images, source identifiers and reviewer notes. The server writes the ZIP to a disposable local directory, reopens and independently verifies it, and streams the completed file to the browser. The temporary directory is removed after download.

Extract the full-span ZIP before opening **index.html**, which lists the included image paths. **evidence.json** includes source identity fields, per-image selected reasons, review history and interval history. The images folder contains byte-for-byte normalized display PNGs. The index avoids embedding thousands of images in base64. Keep the entire ZIP private.

## Verify an archived full-span ZIP independently

With the matching trusted local complete study manifest from the original localhost GET /api/studies/{id}/manifest route, run:

    python scripts/verify_full_span_evidence.py \
      --archive /private/full-span-evidence.zip \
      --study-manifest /private/complete-study.json \
      --output /private/new-full-span-aggregate.json

The verifier rejects missing, duplicated, modified or unexpected ZIP members; mismatched SHA-256 for any retained image; modified source identities; changed review history or interval history; omitted span positions; and misrepresented per-image retention reasons. It verifies imported source-image identity using the existing importer digest and complete manifest without re-opening the original unselected source pixels.

The receipt is aggregate-only and contains no private frame paths, individual source identifiers, image bytes or reviewer notes. An existing output path is never overwritten. This independently checks the **exported normalized display bytes** in the supplied ZIP; it does not establish original source-file provenance beyond the trusted local manifest.

## Scale and safety

The separate exporter writes ZIP members incrementally to disk, with a streaming download response rather than collecting an entire archive in RAM or base64-embedding every frame. It enforces an operational 50,000-imported-image and 8-GiB image-byte bound, plus a 32-MiB per normalized-image bound. These are local archive safety limits, NOT a 10% review restriction or a clinical-workload policy.

The archive keeps reviewer notes and metadata only as user-authored records. Dataset reference labels and model scores never become clinician findings. Like the rest of Capsule Review, it must stay on localhost. No network service is used to acquire source images through this feature.

## End-to-end quality gate

Public tests run the actual FastAPI import, frame bookmark, interval marking, default export, full-span export, and independent ZIP verifier. A **512-image generated software-test sequence** reproduces the prior Galar23 label-blind positional plan, checking 79 boundary-only images versus **295 full-span retained images**, including all 240 imported strict-interior positions and 216 additional images beyond the boundary-only selection. This is arithmetic/test-fixture replication, **not a new real medical-data evaluation**.

Adversarial tests corrupt or omit a PNG, change an imported image after import, reject the no-interval case, and check temporary-file removal. The browser smoke test downloads both ZIP formats and confirms an interior image appears only in the optional full-span package.

The original-source blood-positive annotation-run denominators for the separate frozen Galar23 source-run protocol are still gated on the publisher's exact SHA-matched corrected label archive. Neither the extra archive frames nor the synthetic regression test establishes AI model performance, source-run recall, patient independence, physician review time, or clinical validity.
