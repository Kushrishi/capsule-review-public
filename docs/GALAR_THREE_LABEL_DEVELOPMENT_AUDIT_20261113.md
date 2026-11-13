# Galar blood, active bleeding and hematin: inspected-development annotation audit

**13 November 2026 — descriptive analysis, not a new experiment or clinical validation.**

## Question

How do Galar's three separately published pathology labels—`blood`, `active bleeding` and `hematin`—co-occur in the development examinations already examined by Capsule Review? Can the existing binary-blood evaluation be treated as a test of all three?

**Answer:** No. The labels represent different recorded targets, and their support is highly concentrated by examination. The analysis informs future target selection; it does not establish lesion identity or a new model result.

## Source and boundary

The existing private Galar v2 corrected-label archive `20251215_Labels_Updated.zip` was recovered from the project's retained November 7 research evidence. Its complete SHA-256 was verified as `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`, matching the earlier frozen [11–20 experiment lock](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json). **Only 16 previously inspected development CSVs were read:** original fitting examinations 1–8 and previously inspected development examinations 21, 22, 23, 24, 25, 27, 29 and 30. The authors' held-out 61–80 and the historical locked 11–20 outcomes were not opened.

These are **207,561 rows of corrected frame-level annotations**, not 207,561 newly verified image pixels or independent patients. The earlier 11,147-image source audit describes selected original PNGs within these examinations and must not be conflated with this wider annotation-row count. Three columns were parsed as explicit dataset `0`/`1` labels. None of the inspected cells in those columns was blank; this does *not* prove clinically exhaustive negatives. There were 16 observed source-index jumps spanning 157 expected stride-five grid positions, which were not filled with assumed negatives.

## Frame-label co-occurrence

| Publisher annotation | Positive frame rows | Examinations with at least one positive | Share in the single largest-positive examination |
| --- | ---: | ---: | ---: |
| `blood` | **20,816** | **12/16** | **47.3%** |
| `active bleeding` | **2,070** | **6/16** | **59.6%** |
| `hematin` | **8,867** | **5/16** | **76.8%** |

Of the 2,070 rows labeled `active bleeding`, **1,985 were also labeled `blood`**, while 85 were `active bleeding` without `blood`. Of the 8,867 `hematin` rows, **only two also had `blood`**; no row had both `active bleeding` and `hematin`. Therefore a binary `blood` target is not equivalent to either a union of these annotations or a clinical judgement about fresh bleeding.

The exact disjoint combinations across all 207,561 rows, ordered as (`blood`, `active bleeding`, `hematin`), were `000`: 177,795; `100`: 18,829; `110`: 1,985; `010`: 85; `001`: 8,865; `101`: 2; `011`/`111`: 0. These are *publisher-label states*, not lesion categories or independently adjudicated medical negatives.

## Temporal and group support

For each label, a *source annotation run* was defined as consecutive positive rows separated by the observed native source-frame increment of exactly five. A zero label or index gap ended a run. This gave **318 blood runs**, **44 active-bleeding runs** and **39 hematin runs**. The union of the three labels contained **355 annotation runs**, but union-run counts are not sums of independent clinical events: adjacent appearances can merge, and repeated views can still represent one lesion.

Class support is extremely uneven. The three examinations contributing the most positive rows accounted for **85.5% of blood**, **99.5% of active bleeding** and **99.4% of hematin** annotations in this 16-examination pool. This limits cross-examination evaluation of separate or combined targets, irrespective of total frame count. No unique-patient linkage was authenticated.

A separate pandas/vectorized implementation independently reproduced the counts, eight label patterns, overlaps, source gaps and annotation-run totals for all 16 explicitly allowed CSVs. Private original-archive and member SHA-256 receipts, both analysis implementations and examination-specific details were retained privately. No model training, score recalculation or medical-image access was involved.

## Decision

Keep the locked Galar 11–20 **negative 10% primary result unchanged**. Do not silently relabel the existing CNN as an `active bleeding`, `hematin` or union-of-pathologies detector; it was trained and evaluated for the recorded `blood` target. Do not treat these frame-label relationships as evidence of distinct lesions or clinical sensitivity.

The next research question is *which clinical entity a review policy should preserve and what chronological visual evidence identifies it*. The present data can support retrospective label-distribution diagnostics, but it does **not** justify a new independent multi-label benchmark, a pathology-model promotion or a clinical event-coverage claim. External outreach remains deferred at the project owner's request.

**Dataset attribution:** Le Floch et al., *Galar — a large multi-label video capsule endoscopy dataset*, *Scientific Data* 12, 828 (2025), [DOI: 10.1038/s41597-025-05112-7](https://doi.org/10.1038/s41597-025-05112-7); corrected Galar v2 annotations, CC BY 4.0.