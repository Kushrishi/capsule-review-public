# CNN score alignment after conditioning on chronology

**November 6, 2026. Retrospective development analysis; negative primary contrast, no AI improvement or promotion.**

[Analysis lock](CHRONOLOGY_CONTROL_LOCK_20261106.md) · [Aggregate](../experiments/score-alignment-20261106/aggregate.json) · [Independent check](../experiments/score-alignment-20261106/independent-check.json)

## Executed beyond PR #61

This new experiment reuses the eight out-of-fold prediction streams from the completed [16-examination CNN comparison](GALAR_EXAM_TEMPERED_CNN_RESULTS_20261105.md). These are **four from-scratch control CNNs and four examination-tempered CNNs**, not the original single checkpoint used on Galar 35. The retained archive SHA-256, member checksums, metadata commitment, examination-exclusive folds and every historical exact-K positive-image hit were reconciled first. No acquisition, fitting, inference or Galar 35 evaluation was repeated.

The analysis was fixed in commit `52ddf6e56560fae0ce54f62650cacec9d89f3f9d` before opening saved arrays for this diagnostic. Historical aggregate outcomes were already known: this is **not independent validation**. All 16 previously inspected examinations and their 512 chronological uniform-reference positions were retained, including five with zero positives. Eleven contain 526 positive reference images. Sparse reference positions cannot establish complete-source run preservation.

**Question:** does score ranking preserve positive-image information beyond examination identity and broad chronological allocation?

## Primary result

At K=51/512 for the ordinary pooled-class-balanced CNN arm:

| Measure | Observed / expectation |
| --- | ---: |
| Positive reference images reached | 151 / 526 |
| Unrestricted random-selection expected hits | 52.3945 |
| Chronology/allocation-conditioned expected hits | 127.5313 |
| Equal-positive-examination observed recall | 17.7815% |
| Equal-positive-examination conditioned expected recall | 20.0145% |
| **Primary observed-minus-conditioned contrast** | **−2.2330 percentage points** |
| Positive / negative / tied examination contrasts | 5 / 4 / 2 |
| Leave-one-positive-examination-out contrast range | −5.5333 to +3.1687 pp |

The control partitions each chronological reference sequence into **16 fixed 32-position blocks**. It preserves the queue's selected count and positive support inside each block; exact expected hits are `sum(k_b * positive_b / 32)`. This is an allocation-matched reference expectation, **not another deployable queue**. Labels enter evaluation only. Blocks are neither elapsed time nor authenticated anatomy.

The pooled count is favourable (151 versus 127.53 expected), while the equal-examination mean is negative. Larger-support cases dominate pooled positives; missing one of two positives strongly affects examination-normalized recall. Preserve both statistics. The leave-one-case range crosses zero: this small retrospective sample does not establish a precise population effect or prove the CNN has no useful image information.

| Positive examination | Positives | Hits | Conditioned expected hits | Excess recall, pp |
| --- | ---: | ---: | ---: | ---: |
| 1 | 22 | 5 | 3.2500 | +7.955 |
| 2 | 1 | 0 | 0 | 0 |
| 4 | 2 | 0 | 1.1250 | −56.250 |
| 6 | 6 | 0 | 0 | 0 |
| 7 | 208 | 50 | 41.8438 | +3.921 |
| 21 | 1 | 0 | 0.1250 | −12.500 |
| 23 | 4 | 0 | 0.0625 | −1.563 |
| 25 | 14 | 0 | 0.4063 | −2.902 |
| 27 | 26 | 23 | 15.0000 | +30.769 |
| 29 | 122 | 34 | 29.4688 | +3.714 |
| 30 | 120 | 39 | 36.2500 | +2.292 |

Cases 3, 5, 8, 22 and 24 have zero reference positives and undefined positive recall. They remain in workload accounting. Their absence from the macro recall does not establish safe negative-examination detection.

## Secondary checks without winner selection

| CNN arm / queue | K | Hits | Conditioned expected hits | Macro excess recall, pp |
| --- | ---: | ---: | ---: | ---: |
| Control / global score | 128 | 298 | 268.250 | +6.648 |
| Control / global score | 256 | 436 | 415.313 | −1.526 |
| Tempered / global score | 51 | 148 | 120.250 | +2.166 |
| Tempered / global score | 128 | 299 | 266.031 | +5.959 |
| Tempered / global score | 256 | 439 | 412.438 | +14.394 |
| Control / score-bin | 51 | 57 | 55.063 | −2.644 |
| Tempered / score-bin | 51 | 59 | 55.125 | +1.662 |
| Uniform, both arms | 51 | 50 | 51.000 | +5.390 |

Uniform's nonzero macro excess illustrates deterministic sampling phase and small-support sensitivity. These contrasts are **not significance tests**. The tempered arm's positive secondary contrast does not rescue its earlier negative primary: actual 10% recall remains below control. All three policies and budgets, including unfavourable outcomes, remain in the aggregate.

Each queue was displaced through all 512 circular offsets. This preserves queue geometry and the observed label sequence. Full-orbit means equal unrestricted prevalence expectations. Orbit ranks are descriptive, **not p-values**: nonstationary anatomy and wraparound do not justify exchangeability. No frame-bootstrap or patient-level confidence interval was calculated.

## Scientific assessment

**Established engineering:** real CNN training/inference, source provenance, distinct human/model annotations, exact-K selection, sealed predictions, independent metric replay and retained failures. The locked Galar 11–20 10% primary stays **−1.2668765 pp**; its 25% secondary is heterogeneous. Galar 35 raw score-bin reaches 23/29 runs versus uniform 16/29 and temporal window 3 17/29. Historical results remain unchanged.

**Learned useful signals?** Some held-out development examinations show annotation-associated score information beyond this coarse chronology, particularly case 27. That supports limited predictive association. It does not identify causal pathology morphology. The reduction from unrestricted to block-conditioned enrichment shows how strongly coarse chronological allocation can affect apparent benefit, but is not a causal decomposition. Device, anatomy, colour, label practice and patient dependence remain plausible contributors. This audit does not isolate them.

**Images versus runs:** repeatedly selecting high-scoring frames from one prolonged finding improves image recall but spends budget that might reach other runs. Run coverage counts each run once. Short runs have few opportunities for selection; smoothing can move a peak onto a negative neighbour. The six extra Galar 35 short-run misses are verified displacements, not adjudicated lesions. A rolling maximum with earliest ties is not a learned temporal pathology model.

**Weaknesses:** inspected development cases; unverified patient linkage and incomplete device/site metadata; concentrated positive support; sparse references; annotation runs without independent lesion adjudication; uncalibrated class-balanced scores; no qualified external event cohort or human reader study. Clinical usefulness, diagnostic safety, reading-time reduction and novelty remain unverified. Higher AUC alone is not an improvement when early retrieval/AP deteriorate.

## Comparable primary research and implications

| Source | Methodological comparison | Consequence here |
| --- | --- | --- |
| [CapsuleAudit, MICCAI 2026](https://papers.miccai.org/miccai-2026/paper/0867_paper.pdf) | Domain-pretrained features plus learned temporal tokens; separate anatomy/anomaly tasks and external anatomy assessment | A max-filter failure does not reject learned temporal models. Separate encoder and temporal ablations; anomaly recall is not blood-run coverage |
| [SEE-AI, online May 2026](https://pubmed.ncbi.nlm.nih.gov/42148037/) | Multicentre crossover readers, adjudicated lesion/patient endpoints and measured reading time; one capsule platform limits transfer | Build toward expert event truth and reader evaluation; image-count reduction is not measured time saving |
| [Kvasir-Capsule](https://www.nature.com/articles/s41597-021-00920-z) | Labelled segments coexist with unlabelled frames; paper describes video-separated evaluation | Preserve unknown outcomes. Reconcile the intended grouping with our saved official split-file audit rather than assuming filenames prove independence |
| [Galar descriptor](https://www.nature.com/articles/s41597-025-05112-7) | Multiple centres/devices and frame annotations require careful splitting | Authenticate subset metadata and annotation version; dataset breadth alone does not prove our selected examinations are patient-independent |

No comparable supplies the project's missing patient linkage, event adjudication or source compatibility. Report examination-level AP and fixed-budget retrieval alongside AUC. Any calibration must be fitted on separate development groups; class-balanced softmax outputs are not clinical probabilities.

## Decision and next major milestone

This alignment audit outranked immediate Galar 36 replication because it tests all saved held-out cases with no new medical download. Another single-case temporal comparison broadens the descriptive record but cannot resolve cross-examination learning failures. A larger network, window/exponent sweep or metadata-conditioned model is premature while authenticated grouping and diverse positive support are unavailable. External full-run testing remains blocked by outcome completeness and independence.

**Next model hypothesis:** greater authenticated positive-examination diversity improves difficult-case early retrieval more reliably than reweighting the current concentrated pool. An expanded development cohort must first pass the existing source/group/annotation gate. Then compare fixed training populations under a group-excluded design with identical evaluation references and a single frozen candidate. Keep 10% early retrieval primary; measure run coverage only on complete eligible sequences. Lock preprocessing, group units, sampling roles, budgets, endpoints and paired analysis before fitting. Do not choose cases using favourable CNN outcomes or call inspected 21–60 untouched.

That experiment remains conditional on data qualification; it was not executed here. Galar 36 remains an available fixed-policy replication direction, not a substitute for cohort diversity or clinical validation. No protected outcome boundary was opened, and no model was promoted.

## Verification and reproducibility

[Private-only runner](../scripts/audit_score_alignment.py) · [Reusable diagnostic](../src/capsule_review/score_alignment.py) · [Synthetic tests](../tests/test_score_alignment.py).

The diagnostic adds no new framework, fitting method or product default. Synthetic counterexamples distinguish pure coarse-location enrichment from within-block association. A separately implemented NumPy replay imported no production selector/diagnostic and matched **288 examination/policy/budget records**, **147,456 circular offsets** and **18 macro summaries** to 1e-12. This checks score-level arithmetic, not original checkpoint re-inference or fresh medical-image verification.

Private source-associated scores/labels, input archive, execution/audit scripts, checksums and logs remain outside public Git. The public output contains examination aggregates only. **AI performance did not improve**: the advance is new controlled evidence about the limits of present learning and a reusable diagnostic for future valid benchmarks.
