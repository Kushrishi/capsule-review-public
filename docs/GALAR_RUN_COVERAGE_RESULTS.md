# What sparse-image blood ranking misses: original Galar annotation-run audit

**Date:** November 2, 2026. **Status:** completed, independently replayed, **post-hoc exploratory** analysis on previously examined Galar cases. **Scientific decision:** prioritize more complete original-source coverage and evidence diversity; **do not promote or retune a model** from this audit.

## The problem in plain language

Finding many blood-labelled pictures is not the same as finding many separate stretches of positive evidence. A model can rank dozens of pictures from one extended stretch above other images, while skipping different short stretches elsewhere. Separately, if the images supplied to a ranking algorithm were previously *sampled sparsely*, some important labelled stretches may never enter its input. No model can retrieve an original frame that was never provided to it.

Our previous exploratory CNN results mainly reported blood-positive **sampled-image hits** at various review budgets. Here we also count how many **different contiguous stretches of original corrected `blood=1` annotations** have at least one selected image. Such stretches are called *annotation runs*, **not physician-verified lesions**, distinct pathology events or continuous-video segments.

## Frozen, verifiable inputs and definition

The [protocol](GALAR_RUN_COVERAGE_AUDIT_SPEC.json) was committed **before the new run-coverage calculations**. However, the source labels and image-ranking results had already been inspected; this is **not** a new blinded or prospective test.

- Official corrected Galar v2 annotation ZIP, publisher file ID **60383963**, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`, Le Floch et al., **CC BY 4.0**.
- Previously saved, independently verified **original CNN and redness-comparator predictions** in exactly **512 source-chronological, label-blind preselected reference images** per examination: **9, 10, 21, 23, 25, 27, 29 and 30**. Also retain separately the two fixed continued-training CNN scores only for held-out fitting-candidate examinations **25, 27 and 29** (those two models were trained on 21/23/30, so not compared as unseen on those cases).
- A run is a maximal sequence of **consecutive corrected source annotation rows** labelled `blood=1` whose numeric source-frame IDs differ by **exactly five**. A `blood=0`/unknown row or source-frame gap ends the run. The actual source annotation stride was independently checked in every allowed case; we **did not** inspect future evaluation exams **11–20** or the authors' reserved **61–80**.
- Compare identical **5%, 10%, 25%, 50%, 75% and 100%** reference-frame budgets (25, 51, 128, 256, 384 and 512 images). Ranking ties use ascending source-frame order. Uniform selection uses the fixed deterministic source-position rule. A 10% point is **not** a product restriction.

## Finding 1 — image hits can conceal missed separate positive runs

In **Galar examination 10**, at the **same 10% review budget** (51 of the original 512 sampled images):

| Selection method | Blood-positive reference images selected | Different original positive annotation runs reached |
| --- | ---: | ---: |
| **Original CNN** | **47** | 3 |
| **Uniform sampling** | 21 | **10** |

The CNN found far more positive *images*, but these were concentrated into fewer original annotated positive stretches. Of the **41** positive annotation runs recorded in the entire corrected examination 10, the original 512 reference images contain representatives from only **31**. Neither method could find a run with no representative image in that 512-image sample.

The same models can behave differently at other budgets; do not infer that uniform sampling generally beats the CNN. Across all **eight** already examined cases:

| Budget | CNN positive-image hits | Uniform positive-image hits | CNN distinct annotation runs hit | Uniform distinct annotation runs hit |
| --- | ---: | ---: | ---: | ---: |
| 5% | 86 | 24 | 18 | 18 |
| 10% | **142** | 48 | 28 | **31** |
| 25% | **316** | 120 | **69** | 55 |
| 50% | **388** | 254 | **81** | 80 |
| 75% | **435** | 374 | 94 | **98** |
| 100% | 500 | 500 | 110 | 110 |

These are descriptive **sums of previously selected examinations** with very different case mix and very different numbers of positives. They must not be interpreted as a clinical lesion-recall benchmark, a patient-independent estimate or a new model-selection criterion.

## Finding 2 — the 512-image sample itself has a severe coverage ceiling

For each examination, we computed a **100%-of-saved-reference ceiling**: how many of the *full corrected source's* blood-positive annotation runs could be reached **even if every one of the 512 previously selected reference images were reviewed**.

| Galar examination | Total positive annotation runs in corrected source | Runs represented somewhere in 512 reference images | Maximum source-run coverage of the saved sample |
| --- | ---: | ---: | ---: |
| 9 (blood-negative-labelled) | 0 | 0 | Undefined |
| 10 | 41 | 31 | 75.6% |
| 21 | 3 | 1 | 33.3% |
| 23 | 28 | 4 | 14.3% |
| 25 | 53 | 3 | **5.7%** |
| 27 | 4 | 4 | 100.0% |
| 29 | 107 | 47 | 43.9% |
| 30 | 47 | 20 | 42.6% |
| **Descriptive total** | **283** | **110** | **38.9%** |

This is a restriction of the **historically saved input sample**, not a claimed upper bound for Capsule Review, the CNN, or the whole original examination. Reviewing more original images could increase coverage. The sample's positive rows are not necessarily independent; patient identities, lesions and original capture timings are not established.

The ceiling varies sharply with original positive-run length:

| Length of original annotation-positive run | Recorded full-source runs | Represented in 512-reference samples | Reachable fraction |
| --- | ---: | ---: | ---: |
| **Short: 1–5 annotated rows** | 124 | **13** | **10.5%** |
| Medium: 6–25 rows | 85 | 25 | 29.4% |
| Long: 26+ rows | 74 | 72 | 97.3% |

The sampling procedure overwhelmingly represents long stretches and frequently omits short ones. This is central to the project's longer-term question about preserving evidence, but **an annotation run is not a confirmed lesion**, and original Galar corrected labels are defined at source positions generally separated by five frames, not verified continuous capture time.

## Finding 3 — a blood-negative-labelled study still consumes a forced review budget

Galar **examination 9** has **zero original `blood=1` annotations across 4,339 corrected source rows**, and its previous sample contains 512 `blood=0` frames. A policy that *always selects 10%* must therefore select **51 blood-negative-labelled images** in that examination. That is an arithmetic property of a fixed per-exam review budget, **not** a clinical false-diagnosis claim.

On examination 9, the unchanged original CNN's **uncalibrated** class-1 score exceeded the *illustrative* thresholds of 0.1, 0.5 and 0.9 on **149**, **1** and **0** of the 512 images, respectively. No threshold was optimized, calibrated or recommended for clinical use. `blood=0` does not prove an image lacks other pathology, and the original checkpoint was historically selected using examinations **9–10**.

A future user-facing triage/review system should compare both *coverage of diverse positive evidence* and *workload consumed in blood-negative examinations*, while leaving original frames accessible to the human reviewer. Optimizing only frame-level accuracy, pooled ROC-AUC or hits within one long region is not enough.

## Independent verification, privacy and decision

### Technical integrity-check correction (disclosed)

The first private development run used Python's full-archive ZIP CRC helper on the corrected-label archive. That helper **decompresses all contained CSV members**, including reserved examination CSVs, even though no reserved label values were parsed, inspected or used in the analysis. This was an avoidable source-access error. The committed implementation no longer performs archive-wide CRC traversal: it verifies the full 17.93-MB archive's SHA-256 and reads/CRC-checks **only** the eight explicitly allowed exam CSVs. A new synthetic test embeds forbidden 11 and 61 entries and fails if either is read or if whole-ZIP traversal is attempted. The entire analysis and independent replay were rerun with the corrected selective-read implementation and produced the **same byte-identical results**. Reserved annotations did not influence models, source selection or outcome calculations, but we disclose this earlier technical traversal rather than claim it never occurred.

The source-locked standard-library script [`galar_reference_run_coverage.py`](../scripts/galar_reference_run_coverage.py) rechecked every permitted original corrected label against **4,096 saved reference records**, validated all **five** private scored-source CSV SHA-256s, and refused mismatched source identities/labels and protected study IDs. Running the complete source script twice produced **byte-identical** aggregate output, SHA-256 **`8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07`**.

A **separate implementation** [`verify_galar_run_coverage.py`](../scripts/verify_galar_run_coverage.py), with its own full-source run segmentation and ranking loops, independently recomputed **144 exam×budget×method comparisons** on the real verified sources and matched the complete source-run ceiling. The nonidentifying [verification receipt](../experiments/galar-run-coverage-2026-11-02/verification.json) and [full aggregate](../experiments/galar-run-coverage-2026-11-02/aggregate.json) are checked in. Private raw frame/score records, image SHA-256s and original source annotation ZIP remain outside Git; no new source medical pixels were accessed in this study.

**Decision:** the next substantive experimental milestone should use more complete, *source-verified* image sequences/denser annotated positions and evaluate annotation-run diversity under identical review workload before attempting to claim lesion-level evidence preservation. On available data, the source sample itself is a major bottleneck. We **do not** promote or retune a blood CNN based on this audit. A truly independent clinical generalization study remains a separate, later requirement; future Galar 11–20 and authors' reserved 61–80 stay unopened.
