# Corrected Galar training-pool audit — 2 November 2026 UTC

**Decision:** Galar fitting-candidate examinations **21–29** are the first economically plausible image-acquisition group. The official source image archive is **31,989,399,751 bytes (31.99 GB)**. Do not call these images acquired: this milestone inspected *corrected annotation CSVs only*, did not fit a new model, and did not evaluate any held-out examination.

## Provenance and examination firewall

The local saved official file `20251215_Labels_Updated.zip` (Figshare file **60383963**) was byte-verified: **17,931,138 bytes**, MD5 `4428f8d4341cc41ade9fd547c19b6e48`, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. The full source ZIP has 80 CSV entries, but the audit opened *only* `21.csv`–`60.csv`. The previously assigned examinations **11–20** remain unopened for future evaluation. The original authors' **61–80** holdout remains unopened. Examinations **9–10** remain previously inspected historical development material, not an independent test.

The original protocol was frozen in Git commit [`f537eaf`](https://github.com/Kushrishi/capsule-review/commit/f537eaaf85c1a0d2e29695e33d382574cdcfc6b6) before opening 21–60 CSV contents. During initial parsing, their **source-frame stride changed from predominantly 5 in exams 21–38 to 1 in exams 39–60**. The initially specified common stride of five would therefore spuriously split many positive sequences. The separate [transparent post-inspection amendment](GALAR_TRAINING_POOL_AMENDMENT.json) uses each examination's unique *label-blind modal source-frame gap*, requiring at least 95% support among adjacent source-ID gaps; all 40 eligible examinations met that condition. The original protocol is **not** silently rewritten, and the corrected run analysis is *descriptive*, not a prospectively fixed confirmatory comparison.

## Source-annotation coverage

- **40** additional fitting-candidate examinations, **3,004,632 annotated positions**.
- **32** examinations have at least one `blood=1` position, with **373,241** positive annotated rows in total. They form **6,402** source-stride-corrected contiguous positive annotation runs, **not independently adjudicated lesions**.
- Other labels were audited separately without combining them into `blood`: active bleeding **2,290 rows / 6 examinations**; angiectasia **4,433 / 17**; polyp **15,375 / 16**; ulcer **11,305 / 8**. Their meanings differ and no multi-label model was trained.

| Official image archive group | Blood-positive exams | Blood-positive rows | Blood-positive annotation runs | Source archive |
|---|---:|---:|---:|---:|
| 21–29 | 5 / 9 | 5,552 | 195 | **31.99 GB** |
| 31–40 | 6 / 10 | 17,344 | 605 | 69.22 GB |
| 41–50 | 10 / 10 | 184,575 | 3,178 | 173.94 GB |
| 51–60 | 10 / 10 | 161,649 | 2,377 | 202.69 GB |

**Examination 30** was audited and has **4,121** blood-positive annotated rows in **47** runs. It is not included in these four image-archive groups because the official published names include `Galar_Frames_21_to_29_2.7z` and `Galar_Frames_31_to_40.7z` but no explicitly named exam-30 image source. Its image availability must be verified before planning use. Thus group totals intentionally exclude examination 30.

The pre-declared support gate requires at least **three blood-positive examinations**, including at least two with a short positive annotation run (1–25 contiguous annotated rows). **All four source groups satisfy this gate; 21–29 is the smallest**. In 21–29 there are five blood-positive examinations, four with short runs. This is *training data feasibility*, not evidence that any model can retrieve pathology, that the cases are independent patients, or that a short annotation run represents a short-duration clinical lesion. Do not directly equate row counts from stride-1 and stride-5 studies with equal seconds or independent events.

## Reproduce without images or a network request

Run `scripts/audit_galar_training_pool.py` using the **already retained permitted corrected ZIP**, the immutable v1.0 spec, and the disclosed v1.1 amendment:

```bash
python scripts/audit_galar_training_pool.py \
  --labels-archive /private/20251215_Labels_Updated.zip \
  --spec docs/GALAR_TRAINING_POOL_SPEC.json \
  --amendment docs/GALAR_TRAINING_POOL_AMENDMENT.json \
  --output /private/audit-replay.json
```

The source hash, exact roles, ZIP membership, column schema, label values, source IDs, and run accounting are verified before a new output can be written. The script refuses to overwrite a prior result; `tests/test_galar_training_pool.py` tests reserved-label access, varying strides, corruption, unknowns and aggregate arithmetic. The frozen aggregate result is [`experiments/galar-training-pool-2026-11-02/summary.json`](../experiments/galar-training-pool-2026-11-02/summary.json). Raw labels, individual frame IDs, images, weights and patient material are not committed.

## Decision boundary for the next acquisition

The official candidate group 21–29 uses Figshare file **45258019**, source-reported MD5 `dedad47ee55c83a4b991ca60d26fb6ee`. At **~32 GB compressed**, acquisition is a real storage/transfer/compute decision rather than an automatic extension of this label-only audit. It will require verified download and archive integrity, careful original frame/label joins, and a **fitting-only** sampling design recorded before new model training. Training can be pathology-enriched with transparent sampling; independent evaluation must retain its own previously fixed examination assignment and must not be selected to produce positive results. Preserve the prior compact CNN and pretrained candidates as comparators; never promote a model based on the already-inspected 9–10.

Galar attribution: Le Floch et al., [*Scientific Data* (2025)](https://doi.org/10.1038/s41597-025-05112-7), [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2), **CC BY 4.0**. This work is not clinical validation and is not intended for patient care.

## Post-audit archive-membership correction — November 2, 2026 UTC

The subsequently **verified official 7z index**, rather than the incomplete archive filename, established that Figshare frame source **45258019** includes **all 16,953 original image member entries for examination 30**, in addition to examinations 21–29. The 21–29 image-group estimate above was correct for its named subset but was not the complete archive membership. The actual acquired-index group is therefore **21–30: six blood-positive examinations, 9,673 blood-positive annotated rows and 242 annotation-positive runs**, within the same 31,989,399,751-byte source file. The corrected label audit already included exam 30; no held-out labels were accessed. These 16,953 names were listed only through the 1.34-MB index transfer, not by retrieving medical pixels. See [Galar 21–30 source acquisition](GALAR_21_30_ACQUISITION.md) and [verified index proof](https://github.com/Kushrishi/capsule-review/actions/runs/41392550886).
