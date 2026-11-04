# Original blood CNN — appearance sensitivity and controlled fitting-only candidate

**November 4, 2026. Exploratory development work. NOT independent validation, not clinically validated, and no model promotion.** This experiment materially changes training inputs and runs actual inference on already examined original Galar images; it is **not** another synthetic UI or documentation demonstration.

## Question and data boundary

Does the original saved CNN rank the same previously inspected images differently under defined photometric perturbations? Can one fixed fitting-only color/illumination augmentation recipe improve discrimination across difficult examinations without simply memorizing a favorable one?

- **Original model:** unchanged CNN, SHA-256 `f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3`, Galar 1–8 fitting, original historical development selection. Same checkpoint identity was independently present in the Galar 25 and 27 private reproduction archives.
- **Robustness input:** 512 individually source-hash-verified original *sparse uniform reference* images from each of already examined Galar **23, 25, 27**, with 4, 14, 26 respectively positive blood annotations. **1,536** original-image hashes verified. The replay of recorded baseline original CNN scores matched within at most **0.000003** per score.
- **Five fixed perturbations, plus unaltered reference:** brightness `×0.75` and `×1.25` (clipped), contrast `×0.8` about the mean, saturation `×0.7` and `×1.3` relative to RGB luminance. Applied to already resized/padded **96×96 model inputs**; operations are synthetic stress tests, not photographic calibration or recommended clinical preprocessing.
- **No new independent test:** the three examination labels and historical CNN failures have already been inspected. The authors' reserved **61–80** remain unopened. The completed Galar **11–20** source-complete locked evaluation is **not** rerun, revised, tuned, or used to choose the candidate.

## Repeated original-checkpoint inference — actual results

| Previously examined case | Positive images / N | Original AUC | AUC at 70% saturation | Top-51 positive-image hits, original → 70% saturation | Rank Spearman vs original |
| --- | ---: | ---: | ---: | ---: | ---: |
| 23 | 4 / 512 | 0.203 | 0.296 | 0 → 0 | 0.560 |
| 25 | 14 / 512 | 0.305 | 0.264 | 0 → 2 | 0.792 |
| 27 | 26 / 512 | 0.970 | **0.736** | **22 → 7** | **0.482** |

On Galar 27, lowering saturation replaced **39 of the selected 51 positions**. This demonstrates sensitivity to appearance, not the reason for poor cross-examination generalization. Photometric perturbations can change visible blood characteristics and the model's ranking; neither altered images nor AUC can be interpreted as clinical sensitivity. Full exact condition-by-case values, including worsening and null gains, are in the [nonidentifying aggregate](../experiments/galar-photo-robustness-20261104/aggregate.json).

## Exactly one controlled, fitting-only CNN candidate

After the stress test, train a **single** new compact CNN from scratch using the original **4,096 source-hash-verified fitting images** from Galar **1–8** (239 positive; 208 concentrated in exam 7). Keep original `capsule-cnn-v1` architecture, inverse-frequency weighted cross entropy, AdamW at `0.001` and weight decay `0.0001`, batch size 32, fixed seed 17, and **exactly eight epochs** (the original checkpoint's historically chosen epoch count). No development examination images are used for training or epoch selection. The only changed fitting recipe is deterministic per-image random brightness `[0.75, 1.25]`, contrast `[0.8, 1.2]` and saturation `[0.7, 1.3]`, applied after standard preprocessing using a separate seeded generator.

Evaluate **once**, on all three previously inspected reference examinations, without cherry-picking.

| Examination | Original ROC-AUC | Candidate ROC-AUC | Top-51 annotated positives, original → candidate |
| --- | ---: | ---: | ---: |
| 23 | 0.203 | **0.466** | 0 → 1 |
| 25 | 0.305 | **0.478** | 0 → 1 |
| 27 | **0.970** | 0.881 | **22 → 21** |

The **three-examination descriptive macro AUC** increases from 0.492 to 0.608, but this is not statistically reliable evidence of population improvement: there are just three already examined cases, positive counts are small, patient independence unverified, and examination 27 deteriorates. Both hard examinations remain below 0.5 AUC, and the modest top-51 changes do not establish distinct annotation-run preservation. The new CNN is **NOT promoted** into Capsule Review; no clinical claims or validated best-model status follow.

The candidate checkpoint SHA-256 is `16dff266f242d3bce7a510a0f13f158500776bd2f9ea8626809866ce337cacdb`. **The checkpoint, original pixels, individual annotated source rows, per-frame predictions and private logs remain outside public GitHub.** Its reproducibility and access rights depend on the private research package, not a public Git artifact.

## Runnable engineering work

- [`src/capsule_review/photo_robustness.py`](../src/capsule_review/photo_robustness.py) implements the exact seed-isolated tensor augmentation and fixed deterministic stress-test transformations, without using labels, notes or private images.
- [`scripts/train_blood_photo_candidate.py`](../scripts/train_blood_photo_candidate.py) verifies every fitting PNG against the private original manifest, runs the fixed 8-epoch recipe and saves its checkpoint **only under an explicitly supplied private directory**. It never downloads data, selects a model on the evaluated examinations or touches the reserved cohorts.
- [`tests/test_photo_robustness.py`](../tests/test_photo_robustness.py) exercises seed determinism, RGB tensor boundaries, gradients, malformed input rejection, manifest identity failure and a synthetic one-epoch training smoke.
- [`tests/test_photo_robustness_record.py`](../tests/test_photo_robustness_record.py) validates the public aggregate, source-boundary flags and **negative transfer in exam 27**.

The private exact experiment ran with original model preprocessing and verified source PNG hashes. This public source is a reusable training implementation; the private archive preserves the precise run script, original checkpoint and provenance, per-exam aggregate, perturbation output and run log.

## Scientific decision

**Do not adopt the candidate as the default model.** The stress-test supports a concrete vulnerability hypothesis (appearance-sensitive ranking), and the candidate shows that improving two hard cases can reduce performance in a formerly strong one. The next useful scientific improvement is a predefined, examination-held-out *development* training comparison with more varied source examinations and stronger representations, with attention to positive annotation-run recall instead of image hits alone. Before claiming external benefit, secure an independent appropriately annotated patient-grouped cohort; keep the original Galar 10% negative primary result intact.

The full original source video archive was not reacquired for this audit. The inspected **512-image reference subsets** are not dense temporal sequences. No physician reading study, lesion-level metric or patient-level performance was measured.
