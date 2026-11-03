# Capsule Review — Six-examination technical omission audit
**November 3, 2026 · Reproducible real-score research · Retrospective, not clinical validation**

## Question and scope

At exactly the same number of imported images proposed for review, how much of the imported **ordinal sequence** can each policy leave unselected? Does retaining many positive individual images come at the cost of extremely large gaps?

Inputs: two cryptographically locked previously source-verified private Galar CNN score archives. Original model scores and labels were taken from previously inspected fitting/transfer examinations **21, 23, 25, 27, 29, 30**, each with 512 source-chronologically selected reference images. No new model fitting or unseen-case testing. Comparison uses the four exact-K policies already implemented in Capsule Review.

## Actual result at 51 of 512 imported images per examination

| Policy | Pooled positive sampled images retained | Mean largest consecutive omitted span | Worst single-exam omitted span | Mean occupied bins out of 16 |
| --- | ---: | ---: | ---: | ---: |
| Highest CNN scores | 95 | 239.7 | 376 | 7.2 |
| CNN + ordinal separation | 43 | 68.8 | 91 | 15.0 |
| Top CNN score / chronology bin | 31 | 17.2 | 19 | 16.0 |
| Uniform positions | 27 | 10.0 | 10 | 16.0 |

At K=51, the highest-score CNN strategy captures **95 explicitly blood-positive reference images** across six previously examined studies, versus **27** for uniform. However, its **average largest uninterrupted span of omitted imported images is about 240** compared with **10** for equal-K uniform. On average it selects frames from only **7.2 of 16** broad ordinal regions, whereas uniform and score-per-bin cover all 16.

**Adverse examination-specific result:** at this budget the original CNN retained **zero** sampled blood-positive images in examinations 21, 23, and 25, despite their saved 512-image references containing **1, 4, and 14** explicitly positive images. This confirms that pooled positive-image counts can conceal dangerous-looking transfer failures; it does **not** quantify actual clinical hazard.

## Actual result at 128 of 512 imported images per examination

| Policy | Pooled positive sampled images retained | Mean largest consecutive omitted span | Worst single-exam omitted span | Mean occupied bins / 16 |
| --- | ---: | ---: | ---: | ---: |
| Highest CNN scores | 201 | 131.3 | 203 | 11.3 |
| CNN + ordinal separation | 77 | 18.3 | 42 | 16.0 |
| Top CNN score / chronology bin | 77 | 6.0 | 6 | 16.0 |
| Uniform positions | 69 | 3.0 | 3 | 16.0 |

## Individual examination checks — 51/512

| Previously inspected exam | Positive reference images present | Highest-score retained | Highest-score longest omitted span | Score-per-bin retained | Score-per-bin longest omitted span |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 | 1 | 0 | 144 | 0 | 17 |
| 23 | 4 | 0 | 116 | 0 | 19 |
| 25 | 14 | 0 | 376 | 2 | 18 |
| 27 | 26 | 22 | 214 | 3 | 17 |
| 29 | 122 | 33 | 293 | 12 | 15 |
| 30 | 120 | 40 | 295 | 14 | 17 |

## Reproducibility checks

- Every historical source-verified input ZIP and relevant CSV member was checked against the pinned SHA-256 in the earlier private score-replay code; only permitted exam IDs 21/23/25/27/29/30 were loaded.
- **144/144** exact examination × K × method combinations reproduced the previously verified positive-reference-image hit totals and nearest-selected imported-position coverage.
- **144/144** largest omitted-span results passed an **independent, explicit 512-position omission-run enumeration** rather than only reusing the boundary-gap formula.
- K was independently fixed at **25, 51, 128, 256, 384, 512** (1 to all remains possible in the application; these are research comparison points).
- Model scores alone select the images; previously examined reference annotations are consulted only afterward for the image-hit descriptions. Results contain **only aggregates**, never individual source frame indexes, per-frame scores/labels, original images, source annotation-run locations, or model weights.

## Limits that cannot be waived

**An omitted span is a count of consecutive *imported image positions*, not original video frames or time.** Because these historical input references are sparse samples from the original sequences, selecting a frame in every bin does not establish that clinically relevant pathology was preserved. The 512-reference studies cannot reach many original corrected-source annotation runs even at 100% of the sampled input. The exact corrected publisher ZIP is still unavailable in the current environment, so **this extension does not calculate new full-original-source distinct annotation-run recall**.

These six exams were previously studied. Original model rankings and policies were already examined; there is **no independent unseen/patient-level generalization**, no diagnostic sensitivity, no estimate of clinician time saved, no confidence in patient independence, and no grounds for claiming a score-per-bin policy is medically superior. The score-bin method remains a transparent coverage-first *engineering default*, not a validated medical model.

## Product consequence

Capsule Review now exposes the equal-K omitted spans of all four policies and lets the reviewer navigate into the worst skipped imported region. This enables technical audit and human examination; it does not automatically save, annotate, or certify any frame as reviewed. [Review queue methods](RESEARCH_REVIEW_QUEUE.md).

**Next scientific gate:** reacquire the exact official corrected annotation archive (known expected SHA-256), compare distinct original positive annotation runs on all six previously inspected cases without retuning, then execute a preregistered denser-examination held-out study with genuinely unseen cases before claiming evidence-preservation gain.
