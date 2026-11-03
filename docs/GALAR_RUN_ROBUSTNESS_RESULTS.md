# Examination-level robustness of Galar source-run retrieval

**November 3, 2026 | Source-locked reanalysis of eight previously inspected examinations | NOT independent validation**

## Why this matters

The original CNN sometimes ranks many `blood=1` reference images highly while finding relatively few *distinct stretches* of original corrected positive annotations. Capsule Review's goal is evidence diversity at controlled workload, not a large count of adjacent positive frames. Our previous source-run audit showed **283** original positive annotation runs across the eight examined cases, of which just **110** appear in the sparse 512-image reference inputs. The current analysis asks whether the original CNN's advantage over uniform selection remains convincing when **each examination gets equal weight** and **one examination is excluded at a time**.

The original model was historically developed or selected using previously examined data. None of these cases constitutes a fresh independent validation or verified independent patient. No additional labels, original source images, per-frame predictions, protected examinations or source-run identifiers were read.

**Inputs:** exact [public previously verified source-run aggregate](../experiments/galar-run-coverage-2026-11-02/aggregate.json), SHA-256 `8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07`. Its official corrected-source label ZIP had been verified in the earlier analysis (SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`). That ZIP **was not newly retrieved or verified in this session**; the results below are a deterministic reanalysis of already verified public aggregate counts.

## Fixed comparison

Eight examined Galar cases: **9, 10, 21, 23, 25, 27, 29, 30**. Exam **9** has zero explicitly blood-positive annotations and is **excluded only from run-recall denominators**, not erased from the equal-workload review accounting. The other **seven positive-source cases** each contribute one equally weighted examination-level recall proportion.

At each of six unchanged review budgets, compare the *same exact number of imported 512-reference images* selected by **original CNN**, **simple red-excess ranking**, and **label-blind midpoint uniform**. The original continued-model arms appear on only a subset of examinations and are **not** misleadingly pooled across the eight-case audit.

The principal descriptive metric is the mean over seven positive-source cases of:

`number of distinct original blood-positive annotation runs hit / total original blood-positive annotation runs in that examination`.

We separately preserve the **pooled count of runs hit**, which weights examinations in proportion to their numbers of annotated runs. We also calculate the difference in examination-weighted run recall (CNN minus uniform), the seven **win/tie/loss** signs, and the range of those mean differences obtained by excluding each entire examination. **The leave-one-examination-out range is a fragility diagnostic, not a confidence interval or a new held-out validation study.** There are no p-values or significance claims because the cases and scores were already inspected and patient independence is unverified.

## Original CNN versus matched-K uniform

| Per-exam imported-image workload | CNN distinct runs hit | Uniform distinct runs hit | Equal-exam mean CNN run recall | Equal-exam mean uniform run recall | CNN − uniform, percentage points |
|---|---:|---:|---:|---:|---:|
| 5% (25) | 18 | 18 | 13.83% | 7.86% | +5.97 |
| **10% (51)** | **28** | **31** | **19.50%** | **15.85%** | **+3.64** |
| **25% (128)** | **69** | **55** | **32.37%** | **23.49%** | **+8.87** |
| 50% (256) | 81 | 80 | 34.78% | 37.55% | −2.77 |
| 75% (384) | 94 | 98 | 39.30% | 39.20% | +0.10 |
| 100% (512) | 110 | 110 | 45.05% | 45.05% | 0 |

**Why pooled totals and mean percentages can disagree:** at 10%, the CNN finds fewer annotation runs in total (**28 vs 31**) but appears +3.64 percentage points ahead when each case is given equal weight. The 10% difference is **unstable**: the CNN wins only **two** of seven cases, ties two, and loses three. Removing Galar **27** alone changes the mean difference from **+3.64 to −8.25 percentage points**. Galar27 has four original positive annotation runs; its large per-exam contribution can dominate a seven-case unweighted mean. Neither pooling nor macro-weighting should be selectively presented as the truth.

At 25%, the CNN is descriptively stronger (**69 vs 55** source annotation runs; five case wins and two losses), and its leave-one-exam-out mean difference stays positive (**+4.80 to +13.20 percentage points**). This is the most encouraging *previously inspected* signal, **not a locked new review budget, independent evidence, or permission to claim a clinically useful model**. An eventual blinded experiment must specify all budgets and hypotheses before opening its evaluation cases.

At 50%, the CNN's macro disadvantage (**−2.77 points**) reverses if exam 10 is omitted. At 75%, the macro difference (**+0.10 points**) is close to zero and reverses when 27 or 29 is omitted. All six budgets, including negative and null results, are retained in the [machine-readable derived audit](../experiments/galar-run-robustness-2026-11-03/aggregate.json).

## Source coverage and missed short evidence

The **512-image candidate supply**, not just model ranking, is a critical bottleneck. The 283 original positive annotation runs include **124 short runs** of 1–5 annotated rows. Only **13 short runs** are reachable anywhere in the frozen 512-image reference sets. Even at 100% of the saved reference images, **173/283** original source annotation runs—and **111/124** short runs—remain unreachable. This is **not** an upper bound for a future denser-source system.

At the matched 10% budget, the CNN retrieved **zero** of these 13 reachable short positive runs, while uniform retrieved **two**. At 25%, CNN reached eight and uniform three. Again, these runs are original **annotation stretches**, not adjudicated lesions, and frame IDs separated by five annotated source positions do not provide actual video frame rate or elapsed time.

Exam 9 still requires all methods to choose their budgeted number of images even though none bears an explicit blood-positive annotation. This demonstrates a **forced-workload design limitation**—not a clinical false-positive rate or evidence of an absence of all disease.

## Reproduce without private medical data

The standard-library [script](../scripts/audit_galar_run_robustness.py) verifies the **exact SHA-256 of the previously released aggregate**, rejects any unexpected examination (including reserved IDs), checks same-K workloads for every method, reconciles annotated run-length strata and all 100%-candidate ceilings, then regenerates the reported macro, micro, short-run and leave-one-exam-out results.

```bash
python scripts/audit_galar_run_robustness.py \
  --input experiments/galar-run-coverage-2026-11-02/aggregate.json \
  --output /tmp/galar-run-robustness-independent-replay.json
```

Public CI tests reproduce every output field, verify the counts including unfavorable comparisons, and reject tampered identity hashes, changed workloads, impossible hit totals and an inserted examination 11. The input and output contain **non-identifying aggregates only**. The private corrected label ZIP, original PNGs, source-frame identifiers, reviewer notes, model weights and individual scores stay private.

**Research decision:** No model promotion and no validated benefit claim. Our next consequential step is a **prospectively frozen, examination-disjoint source-run retrieval experiment using denser original-image coverage**, with an outcome-blind model-selection policy, multiple explicit workloads, and both frame-hit and unique annotation-run metrics. Preserve the original authors' reserved 61–80 and future 11–20; do not retune on them. The corrected publisher archive must be reobtained with its exact SHA-256 before any new full-source label analysis. This is more scientifically important than building additional export modes.
