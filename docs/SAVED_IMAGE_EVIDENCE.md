# Export saved images

Use **Export saved images** to download a disk-streamed ZIP containing only imported images with a saved bookmark, note or label. Save the current draft first (the button also attempts this automatically). Interval boundaries and interiors are not added automatically; active intervals remain context in the metadata. This works without marked intervals.

The ZIP contains `index.html`, `evidence.json` and normalized full-resolution display PNGs. Extract the whole ZIP before opening the index. Source filenames, indices and hashes, review revisions and model-suggestion provenance are retained. Suggestions remain model claims, separate from human entries. This is an evidence selection, not a workspace backup or proof that someone viewed each image. Keep images and notes private.

The existing **Export review** and **Verify evidence** actions retain their 250-image / 128-MiB illustrated-export limits and interval-boundary semantics. **Export full spans** still includes interval interiors and saved images. Neither action is silently substituted for another.

Saved-image export reuses the full-span disk streaming path and independent archive checks, with the same operational bounds: 50,000 images, 8 GiB of image bytes, 32 MiB per image and 64 MiB of metadata. Source/display identity, review history and exact ZIP membership are checked before delivery; failures remove the partial archive. These are safety bounds, not a scalability guarantee. Generated regression coverage includes exactly 251 distinct saved images without intervals and mixed interval context.

For independent verification in Python, use `capsule_review.full_span_evidence.verify_saved_evidence(archive_path, trusted_complete_study_manifest)`. Obtain the complete manifest from the original authenticated local study. This checks exported display bytes against that trusted identity; it does not rehash unexported original source files. The older full-span verifier deliberately rejects this distinct saved-only format. The restricted generated-control interface does not expose this route.
