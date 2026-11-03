# Galar source-density ceiling: preserving more original annotated evidence

**November 2, 2026 — completed post-hoc, source-label-only feasibility experiment.** This is not an image-backed model evaluation or a clinical validation. No new medical image pixels or model scores were acquired, and no model was promoted.

## Why this matters

The original 512-frame candidate sample frequently omitted short blood-positive annotation runs before any AI could rank them. This audit varies the number of **label-blind input candidates** while keeping the human reviewer workload fixed at **51, 128, 256 or 512 images per exam**. It does not compare 10% of 512 against 10% of thousands of images while pretending the reviewer workload is equal.

The complete protocol [GALAR_DENSITY_CEILING_SPEC.json](GALAR_DENSITY_CEILING_SPEC.json) was committed in [`b469fcb`](https://github.com/Kushrishi/capsule-review/commit/b469fcb88f3cf4f31debfed7255796584767ebae) **before the new calculation**. Cases and historical outcomes had already been examined: this is prespecified *within a post-hoc exploration*, not a blinded independent evaluation.

## Verified original source

The real original corrected Galar v2 annotation ZIP (Le Floch et al., CC BY 4.0), publisher file **60383963**, was verified against SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`. Only fitting-pool CSVs **21–30** were read, totaling **134,311 corrected original annotation positions** across **10 examinations**. Six have explicit `blood=1`; the other four have none. The six positive exams have **242 separate positive annotation runs**, of which **117 are short (1–5 original annotated rows)**, 70 medium (6–25) and 55 long (26+).

A run is a contiguous stretch of **source annotation rows** with blood=1 and source-frame-index step 5. It is not an independently verified lesion, unique clinical event, complete source video interval or capture-time measurement. Future evaluation 11–20 and the authors' holdout 61–80 were not opened.

The calculation reproduced the **previous 512-frame positive-image and positive-run counts for all ten exams**, otherwise it would have stopped. Input source positions are label-blind, selected by the previously fixed midpoint rule; no labels enter candidate selection.

## Finding 1 — denser candidates make previously omitted positive runs accessible

| Candidate positions / exam | Total candidates across ten exams | Source-positive annotation runs represented | Short annotation runs represented |
| --- | ---: | ---: | ---: |
| **512** | 5,120 | **79 / 242 (32.6%)** | **10 / 117 (8.5%)** |
| 1,024 | 10,240 | 118 / 242 (48.8%) | 19 / 117 |
| 2,048 | 20,480 | 157 / 242 (64.9%) | 37 / 117 |
| 4,096 | 40,960 | **201 / 242 (83.1%)** | **76 / 117 (65.0%)** |
| 8,192, clamped per exam | 80,543 | 226 / 242 (93.4%) | 101 / 117 |
| **All source annotations** | **134,311** | **242 / 242** | **117 / 117** |

At 512 candidate images, **53/55 long** runs but only **10/117 short** runs were even represented. Two especially informative examples: Galar **23 increased from 4/28 represented runs at 512 to 21/28 at 4,096**, and Galar **25 from 3/53 to 38/53**. These are *source annotation candidate ceilings*, not observed CNN recovery.

## Finding 2 — fixed-workload uniform selection barely improves by itself

At a **fixed 51 images actually selected per exam** (510 images across ten exams), the label-blind uniform selector reached **21** distinct positive runs from 512 candidates and **26** from all source positions. At the same workload, an impossible *label-privileged oracle* could reach up to **79** from the 512 candidates or **184** from all original annotation positions, by using the ground-truth run identities.

| Candidate pool | Actual uniform run hits at 51 frames/exam | Ground-truth oracle upper bound at 51/exam | Actual uniform run hits at 512/exam |
| --- | ---: | ---: | ---: |
| 512 | **21** | 79 | 79 |
| 1,024 | 25 | 101 | 86 |
| 2,048 | 24 | 129 | 84 |
| 4,096 | 25 | 156 | 74 |
| 8,192 clamped | 26 | 173 | 76 |
| Full source annotations | **26** | **184** | **79** |

These ten exams include **four without blood-positive annotations**. At 51 forced selections each, that accounts for **204 `blood=0` selections**, not 204 clinically adjudicated false positives. Those images can contain other pathology.

Increasing candidate access and increasing successful *selection* are therefore **distinct technical problems**. The oracle is a mathematical reference bound, **not deployable or an expected model result**. The separate deterministic candidate sets at different sizes are not nested, so individual uniform-hit counts need not be monotonic. At present no source-verified new image scores have been computed on those extra source positions.

## Reproducibility and next decision

The [official-source GitHub Actions replay](https://github.com/Kushrishi/capsule-review/actions/runs/41528910104) completed successfully after tests and exact source checksum verification. It produced a full **107,312-byte** nonidentifying original-source aggregate with SHA-256 **`0eda3ad58fc05947d490d7420b7926178e3f21ff900ee2f557419b54a253aa05`**, independently recovered and rehashed from the workflow artifact. It is also stored privately in the **Capsule Review / Galar Density Feasibility 2026-11-02** Library folder. The smaller [public summary](../experiments/galar-density-2026-11-02/summary.json) records study-wide tables and the full report hash.

**Scientific decision:** the 512 candidate configuration was too sparse to represent most short annotated runs in these already inspected studies. The next experiment should acquire **actual denser verified PNG pixels**, initially from the source-confirmed one-block Galar examination 23, and compare locked, image-derived ranking and evidence-diversifying policies at identical absolute image-review workloads. Do not infer clinical lesion recall, patient-independent generalization, positive predictive value or specialist reading-time benefit from this annotation-only audit.
