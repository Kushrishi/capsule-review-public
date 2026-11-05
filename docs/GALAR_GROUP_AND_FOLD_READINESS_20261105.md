# Development-group and fold readiness — November 5, 2026

**Decision: EXAMINATION-SEPARATED EXPLORATION ONLY.** The currently retained Galar source pool does not support independently verified patient-disjoint evaluation, a new untouched holdout, or full-video event-recall claims. This is a targeted **research-data and split-design milestone**, not another model training run.

## What I checked

- The already verified [11,147 original selected PNGs](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md) span **16** Galar examinations, including **8,192 uniform-reference images** (512 per examination) and 2,955 deliberately enriched additional examples. The [refined similarity audit](GALAR_VISUAL_SIMILARITY_TRIAGE_20261105.md) found no strict close copies in the 5,293 *coarse dHash collision candidates*, but full near-duplicate clearance and patient identity remain unverified.
- A retained, source-checksummed publisher metadata extract for studies **1–10** has `File Name`, `Capsule System`, `Gender`, and `Age` fields. The **eight original fitting examinations (1–8)** in our 16-exam pool all identify **PillCam SB3**. The extract has **no patient identifier or collection-site field**. It does not cover the additional selected development examinations 21–30. Individual age and sex values were **not used or copied** to the group-readiness package.
- The [Galar data descriptor](https://doi.org/10.1038/s41597-025-05112-7) describes two sites and several capsule systems, but does **not** justify assigning a specific site or device to an examination missing its own source record. The [publisher's published fold-generation script](https://github.com/EKFZ-AI-Endoscopy/GalarCapsuleML/blob/main/generate_folds.py) uses `groups = list(df['video'])` with `StratifiedGroupKFold`: this groups **by video/study ID**, not a separately authenticated patient identifier. Such folds preserve distinct video IDs; they are **not proven patient-disjoint** without additional custodian evidence. The paper's wording about patients cannot replace that missing mapping.

**Missing source evidence:** patient-to-study linkage for all 16; site fields for all 16; capsule-system metadata for 8/16. The full official 80-study metadata archive was not reacquired in this step; an attempted small metadata-only public download was inaccessible. No labels or images from protected Galar 11–20 or reserved 61–80 were opened.

## The stronger quantitative warning: reference-only class concentration

Using **uniform references only** gives a more relevant feasibility diagnostic than counting deliberately enriched training examples.

| Statistic | 11,147 selected images (enrichment included) | 8,192 uniform reference images |
| --- | ---: | ---: |
| Explicit blood-positive images | 1,663 | **526** |
| Exams with any selected positive | 11 of 16 | **11 of 16** |
| Share of positives from the four largest-positive exams | 76.73% | **90.49%** |
| Effective positive-exam concentration¹ | 5.77 | **3.74** |

¹ `(Σ positive_images_per_exam)² / Σ positive_images_per_exam²`, a descriptive concentration statistic; not an estimate of patients, distinct lesions or effective statistical sample size.

**Why this matters:** adding outcome-enriched images may help supervised fitting, but evaluating on them without an appropriate selection mechanism biases performance. ROC-AUC and early top-K retrieval must be evaluated on a fixed, defensible reference population. Most uniform-reference positives come from a few examinations, limiting any simple claim of cross-exam robustness.

## Four-fold *feasibility* audit, not a frozen clinical study

The new [read-only auditor](../scripts/audit_development_fold_readiness.py) constructs **four illustrative examination-exclusive folds** with four examinations and 2,048 uniform-reference images each. It places the four largest-positive reference examinations in different folds, then assigns the rest by current positive support and a fixed capacity.

| Illustrative fold | Exams | Reference images | Blood-positive reference images |
| --- | ---: | ---: | ---: |
| 1 | 4 | 2,048 | **208** |
| 2 | 4 | 2,048 | **125** |
| 3 | 4 | 2,048 | **125** |
| 4 | 4 | 2,048 | **68** |

Even equal image counts give **substantially different positive support**. These partitions are computed using *already-inspected development outcomes* and are **not** new patient-disjoint test folds or prospective validation. They are a transparent reason to preserve exam-by-exam reporting, use uncertainty appropriately, and avoid promoting a model on a single pooled or favorable fold.

The auditor optionally reads a **private** device/site/patient-group worksheet, requires a source-evidence checksum for any asserted patient group and detects group tokens shared across folds or mechanically copied from video IDs. It never prints patient/group tokens, site assignments, source metadata rows or medical frame identities. **Even a checksum and no detected overlap are not authentication**: human source/custodian verification is still mandatory. Tests use only synthetic group records and the public audited counts.

Run without any private data:

```bash
python scripts/audit_development_fold_readiness.py
python scripts/audit_development_fold_readiness.py --json
```

An optional private metadata worksheet is supported via `--private-metadata /private/path.json`. Its schema and redaction are exercised in `tests/test_development_fold_readiness.py`; the actual partial worksheet, without patient age/sex or original pixels, remains in a private, checksum-verified research archive.

## How this changes the next experiment

1. **Do not run an arbitrary new CNN or select a winner based on these known folds.** First freeze a *development-only* contract, with original image hashes and sampling roles, exact evaluation budgets, primary and secondary metrics, and explicit examination (not patient) grouping.
2. **Use the enriched selected positives only for labelled fitting and diagnostics.** Reserve the source-uniform 512-reference-frame subset in each held-out examination for fixed-workload positive-image retrieval and AP/AUC; never use the held-out examination's enriched examples in fitting.
3. Compare a source-examination-balanced fitting method against the original CNN and a transparent baseline. Make source-examination weighting and positive support explicit, rather than blindly pooling thousands of correlated positives. Report per-exam failures and confidence limited by actual independent groups.
4. **If authenticated patient IDs or source metadata become available**, update the private group map and regenerate the feasibility check *before* fixing new folds. If identities cannot be proven, say “examination-separated development” and withhold all patient-independent claims.
5. **Do not measure complete-video positive-run preservation** on these 512-position sparse references. That needs complete chronology and a separately qualified reference-standard cohort.

**No model promotion.** The completed Galar 11–20 negative primary is unchanged; reserved Galar 61–80 remains unopened.

The [public non-identifying aggregate](../experiments/galar-group-readiness-20261105/aggregate.json) and [synthetic tests](../tests/test_development_fold_readiness.py) preserve these conclusions. The private 1,755-byte four-file metadata-provenance package has SHA-256 `790fb023304ef5e786b9e74c9d885061e796ac9d2f21de87a3f24407f82578c7` and was saved to access-controlled Library; original source medical frames remain separately private.
