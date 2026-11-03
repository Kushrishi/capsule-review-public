# Galar data

The first real development sample is verified and used. See [REAL_DATA.md](REAL_DATA.md) for its results and limits.

- Official dataset: https://plus.figshare.com/articles/dataset/Galar_-_a_large_multi-label_video_capsule_endoscopy_dataset/25304616
- Version DOI: https://doi.org/10.25452/figshare.plus.25304616.v2
- Paper: https://www.nature.com/articles/s41597-025-05112-7
- Authors' code: https://github.com/EKFZ-AI-Endoscopy/GalarCapsuleML
- Dataset licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/

## Verified acquisition

The current official catalog was retrieved on November 1, 2026. Image file 44724816, `Galar_Frames_1_to_10.7z`, is 31,155,949,292 bytes; its downloaded MD5 exactly matches `ae6b77548691faa05b288a89410aa62e`. It uses nine solid LZMA2 blocks. The frozen uniform selection spans essentially the full archive, so HTTP ranges do not avoid reading most of that payload.

Exactly 5,120 requested PNGs were retained (512/examination, 1,598,002,230 total image bytes). Archive CRC32, PNG structure, exact membership, sizes and individual SHA256 records were checked. Five reusable image checkpoints preserve the selected files; the original 31.16-GB archive is not needed to load that sample again. Keep raw data outside the application source tree and Git.

Selected annotations are unchanged bytes from corrected file 60383963, `20251215_Labels_Updated.zip`, 17,931,138 bytes, MD5 `4428f8d4341cc41ade9fd547c19b6e48`. Only CSV contents for examinations 1–10 were inspected. Examination 6 frame 0 still has all-zero anatomy flags and is explicitly excluded from model fitting. The source `frame` field, not CSV row position, joins images to labels.

## Reuse or reproduce

The companion run package contains the frozen `requested_frames.csv`, exact development manifest, label files, model artifacts and source receipts. Its `data-checkpoints.json` names the five image packages and their hashes. Extract those trusted checkpoints into a data directory; their paths are `images/001/...` through `images/010/...`.

For a fresh official transfer, use `capsule-review data catalog --output galar-catalog.json` and inspect actual file IDs, sizes and checksums. The built-in downloader retains its default 512-MiB budget and requires an explicit larger `--max-mib` for a larger file. The first image archive needs `--max-mib 30000`. Do not download the whole 562-GB article. Acquisition execution records accompany this pilot; normal continuation should reuse the verified checkpoints.

## Mapping and evaluation

Five anatomy classes are used: mouth, esophagus, stomach, small intestine and colon. Exactly one positive binary anatomy flag is required. Unknown/all-zero annotations stay unknown, and absent quality columns are not interpreted as negatives. Uniform source-order sampling occurs before anatomy filtering. The split remains examinations 1–8 for fitting, 9–10 for development validation; reserved examinations 61–80 were not opened.

Exact decoded-image overlap is rejected by the manifest builder. This pilot has no patient-group identifiers, so examination separation does not establish patient independence. The same development data select the checkpoint. Scores are uncalibrated; no clinical effectiveness is established.
