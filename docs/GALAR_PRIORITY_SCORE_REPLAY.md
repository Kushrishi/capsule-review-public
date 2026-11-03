# Real model-score replay: evidence selection versus chronological coverage

**November 3, 2026 | Six previously inspected Galar examinations | Exploratory research, not independent validation**

## Research question and sources

Can the original experimental blood CNN prioritize explicitly blood-positive **reference images** at identical reviewer image workloads, and what chronological coverage does that selection sacrifice? This is a retrospective evaluation of **original saved model scores**, not fresh model training, clinical sensitivity, distinct source-run retrieval, patient-level validation or an evaluation of the viewer's separately installed anatomy model.

We recovered two earlier source-verified private model-score packages from Capsule Review Library: Galar **21/23/30** from the original frozen transfer and **25/27/29** from the independent appearance audit. We rehashed both ZIP files and their internal score CSVs and used only the frozen 512 source-chronological reference images per examination. In total, these contain 3,072 real previously source-verified image-score records and **287 explicitly blood-positive reference images**. The positive support by examination is 1, 4, 14, 26, 122 and 120, respectively.

- Private original transfer ZIP SHA-256: 9dff0dd9ff38e17353bb6e1a9b343dd0b6a8906f1171bc481a842b74142fce83
- Private appearance-audit ZIP SHA-256: 2738a64b47d0be4fecfd89fd8aea9a345ce86e237899e4e423d4d7de8ac36eaa
- Private full derived aggregate SHA-256: 589d2a8700d3ebd811cd979cc83a460b87492e144b09af3c15b98de1a35d6ff5
- Independent verification: **144 of 144** examination × workload × method combinations reproduced with a separate selection implementation.

The original image pixels themselves were **not** independently rehashed during this particular replay. This run checked prior score package bytes and original recorded reference identities. Private frame identities, individual blood labels, saved scores, original images, weights and reproduction scripts stay in private Library. A [sanitized, complete all-workload aggregate](../experiments/galar-priority-score-2026-11-03/aggregate.json) is in Git.

## Original CNN at the exact same number of reviewed imported images

Each method retains exactly K of the same 512 reference images **per examination**. Below are descriptive sums of explicit blood-positive *reference images* retained over six examinations:

| K / examination | Uniform | Highest CNN scores | Score + ordinal separation | Best score per chronology bin |
|---|---:|---:|---:|---:|
| 25 | 15 | **61** | 21 | 15 |
| **51** | **27** | **95** | **43** | **31** |
| **128** | **69** | **201** | **77** | **77** |
| 256 | 147 | **247** | 196 | 144 |
| 384 | 217 | **271** | **271** | 214 |
| 512 | 287 | 287 | 287 | 287 |

The original CNN scores find far more positive **images** than uniform at K=51, but such images may cluster within one original annotation run. Earlier independently published work on a *different eight-exam collection* found only 28 CNN original source-positive annotation runs versus 31 uniform at K=51. The two cohorts are **not interchangeable**; that result illustrates why image-level hits cannot substitute for pathology evidence-diversity endpoints.

### The trade-off: unreviewed imported-position gaps

At K=51, the mean over six studies of the **maximum nearest-selected imported-position distance within each examination** was:

| Selection policy | Mean worst ordinal distance |
|---|---:|
| Uniform | **5** |
| Highest CNN scores | **186.8** |
| Score + ordinal separation | 54.5 |
| Best CNN score in each chronology bin | **9.3** |

These are **imported-image ordinal positions, not capture timestamps**, verified video duration, or pathology sensitivity. Still, the score-only method can cluster so heavily that large portions of the imported sequence have no selected image. The greedy suppression method reduces clustering but does not guarantee even coverage. The best-score-per-bin method provides **one imported image per chronology bin** regardless of uncalibrated model scores and stays close to uniform's predictable spacing, albeit with fewer positive-image hits than unconstrained scores in these already examined cases.

The browser therefore defaults to **score per chronological bin** for a transparent, coverage-first user experience. This is a technical policy preference, **not clinical promotion** or a retrospective claim that it wins on all data. Users can select any policy and any exact K up to all frames.

### Negative and unstable outcomes retained

**Galar 23:** the original global CNN ranking retained **zero of four** explicit positive reference images at K=51, K=128 and K=256 and only one at K=384. **Galar 25:** at K=51 the original CNN retained **zero of fourteen**, whereas uniform retained one; at K=128 it retrieved three while uniform retrieved four. These are severe model-transfer failures, not evidence that the studies were pathology-free.

At K=51, the global CNN won on positive image counts in **three of six** examinations, tied once, and lost twice. The equal-exam mean fraction of available positive reference images retained is **24.17% for global CNN versus 22.31% for uniform**—a far smaller macro difference than suggested by the pooled 95-versus-27 image count. The ordinal-suppression policy has a six-exam macro fraction of only **10.55%**, although it selects 43 positive images overall compared with uniform's 27. One sparse positive case can disproportionately affect macro averages. **Patient independence remains unknown.**

The midpoint-uniform and per-bin selections are independently computed for each K and need not be nested. The ordinal-suppression radius also changes with K. Do not interpret these points as a cumulative score-threshold recall curve.

## Software deliverable and scientific decision

The working viewer now builds an **inspectable, paged, user-selected exact-K queue** from a complete model-run score stream; compares technical ordinal coverage at the exact same K with uniform; navigates suggested images without changing human annotations; keeps all original imported frames accessible; and makes model uncertainty/interpretation explicit. Local anatomy-model inference now saves its **full class-score vector** rather than the top class alone. The built-in anatomy model is still *not a pathology lesion detector*, and the historical blood CNN is **not bundled as a clinically validated default**.

This experiment was performed on **previously inspected examinations**. It measures explicit positive **sampled images**, not distinct source annotation runs, adjudicated lesions, physician reading time, or independent patient generalization. We **do not promote any model** from this analysis. The next scientific gate is a preregistered, examination-disjoint full-source annotation-run evaluation on denser original images, with prespecified equal workloads and complete negative findings. The publisher-corrected source archive must be independently checksum-verified before a new full-source audit, and protected 11–20 and 61–80 remain unexamined.
