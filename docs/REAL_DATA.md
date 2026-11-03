# First real Galar run — November 1, 2026

The previously frozen real-data milestone is complete. The official 31,155,949,292-byte first image archive passed its published MD5. Exactly 5,120 requested PNGs were retained, 512 from each examination 1–10. Every selected image passed archive CRC and PNG checks. The selected corrected CSVs were byte-identical to the official December 2025 label ZIP. The original source frame numbers determine the label joins.

## Data and model

Examinations 1–8 supplied 4,095 eligible fitting frames; examinations 9–10 supplied 1,024 development frames. Examination 6, frame 0 remains excluded because its binary anatomy fields are all zero. No exact decoded-image overlap was found across the split. No patient identifier was available, so this is examination-separated development validation. Examinations 61–80 were not opened.

The existing `capsule-cnn-v1` implementation ran once for 10 epochs on CPU, batch size 32, learning rate 0.001, seed 17. Epoch 5 was selected by lowest unweighted development cross-entropy (0.693457). No pretrained weights were downloaded, and no architecture search or additional real-data training run was performed.

## Measured result

| Metric | Model | Training-majority comparator |
|---|---:|---:|
| Accuracy | 68.36% | 70.31% |
| Balanced accuracy | 53.12% | 20.00% |
| Macro F1 | 0.4811 | 0.1651 |

The model gets 700 of 1,024 frames correct; the comparator that always predicts small intestine gets 720 correct. Examination 9 accuracy is 75.98%, versus 64.45% for the comparator. Examination 10 accuracy is 60.74%, versus 76.17%. The model never predicts esophagus (0/2 correct), and stomach precision is only 15.69%. It shows useful multi-class behavior, but it does not outperform the comparator on overall accuracy.

The full confusion matrix, per-class/per-examination measures, history, manifest, source receipts and checkpoint are preserved in the companion real-data run package. All 27 independent arithmetic/identity checks passed. These checks verify the record, not clinical performance.

## Actual viewer

The browser's Run local model action generated and saved 512 predictions for the sparse examination-9 sample. Twelve real-data workflow/consistency checks passed through actual localhost HTTP. Source annotations, image identities and reviewer entries remained separate and unchanged by inference. Browser and server restart preserved the output. Six predetermined positions were bookmarked and exported with original source identifiers. The only note is explicitly attributed to an assistant software workflow check; no clinical assessment was performed.

The desktop/mobile screenshots show predetermined position 256 (displayed frame 257/512), original source frame 11265, with the actual saved small-intestine suggestion. A long DOI attribution exposed mobile overflow; two CSS rules fixed it, with the full source text retained. The final layout fits 320, 390, 768 and 1440-pixel viewports. Model code and CSP were unchanged.

## Independent follow-up error audit

The frozen weights were independently reloaded and run over all 1,024 validation frames again, after verifying every image SHA-256. The regenerated confusion matrix **exactly matches** the original result. The examination-specific, post-hoc audit is in [the experiment record](../experiments/galar-v2-2026-11-01/README.md). Examination 10 has 116 small-intestine-to-colon errors and 38 colon-to-stomach errors. Exploratory error rates near sparse sampled anatomy transitions are elevated, particularly in examination 10; they are not a new clinical endpoint or a reason to tune to these same examinations.

## Limits

- The two development examinations also select the checkpoint; there is no independent final-test result.
- Esophagus has only 8 fitting and 2 development frames; mouth has 33 and 11. All mouth/esophagus/stomach development examples are from examination 9.
- All ten metadata records use PillCam SB3 and are coded M. Patient independence, demographic breadth and cross-device performance are not established.
- These are sparse samples, not complete examinations. Scores are uncalibrated. The task is anatomical-region classification; lesion detection and clinical validation remain future work.
- Weighted training batch loss and unweighted development loss have different definitions and are not directly comparable.

Data: Le Floch et al., Galar v2, https://doi.org/10.25452/figshare.plus.25304616.v2, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). PNG bytes in the retained source sample are unchanged; examination folders are zero-padded. This is our derived development selection, not an official benchmark split.
