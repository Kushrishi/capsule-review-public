# Galar 23: denser original PNGs do not rescue the fixed redness ranking

**Completed November 2, 2026.** Research status: a source-verified, **post-hoc exploratory** study of a previously examined *fitting* examination, not an independent clinical validation. All prespecified results are unfavorable to an unqualified image-ranking claim; no model was promoted.

## Scientific question and advance lock

After [the Galar 21–30 source-label density audit](GALAR_DENSITY_CEILING_RESULTS.md), we knew that label-blind 512-image candidates represented only **4 of 28** corrected-source `blood=1` annotation runs in examination 23, whereas 4,096 would represent **21 of 28**. However, that study did not acquire those additional image pixels or compute new image-based scores. Here we ask whether **actually acquiring and scoring the original PNGs** helps three fixed, simple methods reach more *different annotated positive stretches* at **identical absolute image-review workloads**.

The complete [protocol](GALAR23_PIXEL_DENSITY_SPEC.json) was committed **alone** in [`61b8403`](https://github.com/Kushrishi/capsule-review/commit/61b840316d0b852526c1fccc2402f55ccd07d8af) before any new 4,096-candidate image acquisition or scoring. Exam 23 and its historical outcome were already known. This is a prespecified comparison **within post-hoc exploratory research**, not blinded preregistration.

- **Source case:** Galar corrected v2 examination **23**, **11,785** originally annotated source positions, **135** explicit `blood=1` positions across **28** original annotation runs (each defined by contiguous positive annotation rows with original source-index stride exactly **5**).
- **Input candidates:** 512 versus 4,096 deterministic, *label-blind* midpoint-spaced original annotation positions, yielding **4,608 unique real PNGs**. Neither sample was enriched using pathology labels.
- **Reviewer workload:** fixed at exactly **51, 128, 256, or 512 selected source images per method and candidate pool**. Never compare percentages against different candidate denominators.
- **Fixed methods:** source-chronological uniform positions; globally highest *unchanged original red-excess pixel scores*; and exactly one highest-redness image from each of K chronological candidate bins (ties by original source index). The redness formula uses the original fixed 96×96 central image crop without training, normalization or threshold search.
- **Endpoints:** different original annotated positive runs reached, positive annotated images selected, and largest nearest-reviewed *original annotation-row* distance. These are not clinical lesions, device frame times or clinician minutes.

## Real source integrity and reproducibility

The [successful official-source GitHub Actions run](https://github.com/Kushrishi/capsule-review/actions/runs/41531426060) first verified the exact official corrected Galar ZIP, file ID **60383963**, SHA-256 `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`, then opened **only** its `23.csv` entry. Future evaluation examinations **11–20** and the original authors' **61–80** holdout were not accessed.

Original image file ID **45258019** is a ~31.99 GB solid 7z archive. The experiment transferred **exactly one previously verified solid block (block 1)** using HTTP 206: original offset `3,474,498,124`, compressed length **3,475,743,781 bytes**, and block SHA-256 **`b5086f018b7e88c57db7562af624c468796a7b1e812101d07236c184131b08f6`**. Publisher original whole-file MD5 is **not verified** and is not claimed. The archived 7z header/index bytes were also strictly reverified (**1,342,072 bytes**). The approved source block includes other examination members compressed in the same solid stream, but only the **4,608 exact allowed exam-23 PNG paths** were extracted and checked. Their total original bytes were **1,376,046,128**, and each was individually PNG-decoded, hashed and source-frame matched. Other examination images were not extracted for analysis.

Before reporting new findings, the run reproduced the existing label-blind 512-reference subset: **4 positive source images / 4 represented annotation runs**, and the historical original fixed red baseline **ROC-AUC 0.4173228346** (historically reported rounded 0.417). A separate offline replay of the retained prior 512-image package also independently reproduced this score and its zero positive hits among the top 51 redness scores.

The complete **8,128-byte** original aggregate (SHA-256 **`648423b1735f1e1a265946805a9ad7386a9ad0fdc2104641cc0dcb4e93fe10de`**) was independently downloaded from the successful workflow artifact and rehashed. It is retained privately in **Capsule Review / Galar23 Pixel Density 2026-11-02** in Library. The smaller [version-controlled nonidentifying complete method table](../experiments/galar23-pixel-density-2026-11-02/summary.json) contains all compared methods and review budgets. **The new 4,608 image files themselves were not archived as a second persistent raw-image package**; the exact source block, immutable protocol and verified script support re-acquisition. No individual image identities, per-frame scores or pathology labels are committed to GitHub.

## Finding 1 — candidate evidence increases substantially

| Candidate original PNG images | Source positive images among candidates | Separate positive annotation runs represented | Original red-excess ROC-AUC | Original red-excess average precision |
| --- | ---: | ---: | ---: | ---: |
| **512** | 4 | **4 / 28** | 0.4173 | 0.00813 |
| **4,096** | 48 | **21 / 28** | **0.3638** | 0.00847 |

The denser candidate input makes many more positive *source annotation runs* available, but the original simple redness score continues to rank `blood=1` images poorly. Average precision is very low in both samples; their positive prevalence and sampling differ. The metric is not a diagnostic probability, and source-run identities are not independently adjudicated lesions.

## Finding 2 — image-based selection at equal absolute reviewer workload

Each cell is **different corrected-source positive annotation runs reached, out of 28 in this examination**, not positive images alone.

| Original candidate PNGs | Images actually selected for review | Uniform | Global redness | Chronology-bin redness |
| --- | ---: | ---: | ---: | ---: |
| 512 | 51 | 0 | 0 | 0 |
| 512 | 128 | 1 | 0 | 0 |
| 512 | 256 | 1 | 2 | 1 |
| 512 | 512 | 4 | 4 | 4 |
| **4,096** | **51** | **0** | **0** | **0** |
| 4,096 | 128 | **2** | **0** | **0** |
| 4,096 | 256 | **4** | **0** | **1** |
| **4,096** | **512** | **3** | **0** | **6** |

At the larger 4,096-image candidate pool, the chronology-bin selection at **512 reviewed frames** reached **six** different positive annotation runs via **eight** blood-positive images; uniform reached **three** runs via three positive images; the global redness ranking selected **zero** positive images/runs despite reviewing 512 of 4,096 images. At **256 reviewed images**, however, uniform reached **four** runs while chronology-bin redness found just **one**. At the tightest **51 reviewed images**, *all methods failed*. **Therefore no general winner or useful clinical operating point is demonstrated.**

Each K uses its own deterministic source sampling/bin partition, and these selection sets are not necessarily nested. A method can legitimately hit more annotated runs at K=256 than K=512. These are outcomes for one previously examined study, not population statistics; we must not choose a favorable K after inspection and claim it was prespecified as a successful operating point.

The result also exposes the difference between selecting diverse *positions* and selecting diverse *positive evidence*: chronology bins constrain spread, but their within-bin redness scores can still pick `blood=0` images. More source candidates alone cannot fix an unreliable ranking signal.

## Finding 3 — global redness concentrates reviewer attention

For the 4,096-image candidates at a fixed **51 images** reviewed, the maximum original annotated-row distance to the closest reviewed image is **116** for uniform, **217** for chronology-bin redness and **2,178** for global redness. At K=512 it is **12**, **21** and **1,425**, respectively. These are distances in original annotated **row positions**, not original device exposures or elapsed time. They illustrate concentration of global top-K redness in only some source regions, not pathology sensitivity.

## Scientific decision

The source-coverage bottleneck was real: using more original image candidates exposes 21 rather than 4 positive annotation runs in this examined study. But image-based rankings based on untrained redness alone are **inadequate** for reliably finding those additional positive runs, especially at low fixed review workloads. Chronology diversity can improve coverage at one larger workload yet lose at other prespecified workloads; this is not a validated improvement.

**Do not promote a model, redesign evaluation splits based on this one case, optimize a threshold on this already-inspected study, infer specialist time savings, or claim clinical lesion recall.** Next, compare a locked *image-trained* candidate on a sufficiently varied training-only set with genuinely examination-separated inner validation, including blood-negative-labelled studies and severe cross-examination failures (23/25), and only then approach the still unopened reserved evaluation cohorts. A more complete, separately sourced sequence remains essential for actual full-video lesion-evidence research.

Galar citation: Le Floch et al., [*Scientific Data* (2025)](https://doi.org/10.1038/s41597-025-05112-7), corrected v2 data, CC BY 4.0.
