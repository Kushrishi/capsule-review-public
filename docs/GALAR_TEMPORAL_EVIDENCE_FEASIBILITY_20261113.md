# Galar temporal evidence feasibility on inspected development annotations

**13 November 2026 — exploratory annotation topology and historical source-index linkage. No new model or clinical evaluation.**

## Finding

The corrected records support deterministic chronological **annotation spans and context candidates**, but not clinically distinct events. Packet counts change substantially under plausible engineering rules, and the retained selected-image verification ledger does not establish complete neighboring context. The next independent task is to reconcile existing retained source inventories with these candidate intervals; specialist decisions about visibility, identity and clinical relevance remain necessary.

This extends the [three-label audit in PR92](https://github.com/Kushrishi/capsule-review-public/pull/92). Its overlap totals and original run counts are consistency controls, not new results. The locked Galar 11–20 negative 10% result is unchanged. No model performance was recalculated.

## Boundary and rules recorded before analysis

Only corrected annotation members for previously inspected examinations **1–8, 21, 22, 23, 24, 25, 27, 29, 30** were parsed: **207,561 rows**. The retained corrected-label archive SHA-256 was `2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`; all 16 member hashes matched the prior private audit. No 11–20 outcomes, 61–80 annotation contents, images or model predictions were opened. No new dataset acquisition or model fit occurred.

The private preanalysis record, written before new source calculations, has SHA-256 `562c0105572c668f91c54edd1b076ec5730e751f48d06f86c48911e0d05a3216`. This was an exploratory specification, not a registered clinical protocol. A separately recorded extension preceded the historical source-index linkage; it followed the primary temporal results and is explicitly exploratory.

- **Continuity:** original file order, unique increasing source indices, native increment exactly 5. A larger increment splits the sequence. Missing positions are never inserted or labelled negative. Distances below are published grid positions, not seconds or anatomical distances.
- **Span:** maximal consecutive 1 labels within a source-contiguous block, separately for `blood`, `active bleeding`, `hematin` and their union. An observed 0 or source gap ends a span.
- **Separation:** explicitly 0 positions between successive spans within the same block. A 0 for one label may be positive for another; only union separations necessarily contain three recorded zeros. Recorded 0 is not independently established clinical absence.
- **Transitions:** the eight possible joint label states, ordered `(blood, active bleeding, hematin)`, compared only across an increment of 5.
- **Gap rule:** merge spans transitively through at most `g = 0,1,2,5,10,25` explicitly 0 positions; never across source gaps or examinations.
- **Context rule:** expand every span by `r = 0,1,2,5,10,25` positions on each side, clip at source-block boundaries and merge overlapping or immediately adjacent intervals. Count each exposed position once. The same numeric gap threshold and context radius are different operations.
- **Summaries:** conventional median; other percentiles use nearest rank. Pooled descriptions are not population estimates. Full per-examination results and every parameter setting remain private; no preferred clinical threshold was selected.

## Span lengths and interruptions

| Publisher target | Spans (prior count reproduced) | Median length |25th–75th percentile|95th percentile|Maximum|
|---|---:|---:|---:|---:|---:|
|Blood|318|6.5|3–24|186|7,415|
|Active bleeding|44|12.5|6–34|315|510|
|Hematin|39|6|3–16|1,532|6,812|
|Union|355|7|3–23|192|7,415|

Union span-length bins were **37/119/116/53/25/5** for 1, 2–5, 6–25, 26–100, 101–1000 and 1001+ positions. The five longest-bin spans contained 18,101 of 29,766 union-positive rows. Thus a large positive-frame count can be concentrated in very few continuous annotation spans; it does not establish correspondingly many findings.

The 16 index jumps divide the 16 examinations into **32 source-contiguous blocks**. Missing-grid sizes ranged 1–75, median 3, totaling 157 positions. All observed rows immediately on either side of these gaps had three recorded zeros. That observation cannot establish what the missing positions contained. One pair of successive union spans was separated by a source gap and was excluded from within-block gap joining. Three union spans reached an observed stream end; their clinical continuation is unknown.

There were **340 within-block separations** between union spans: **32/93/114/42/47/12** in the same six size bins, median 9, range 1–7,611. In particular, 125 were separated by only 1–5 recorded-zero positions. Short separation does not establish same-lesion identity; long separation does not establish different-lesion identity.

## Label transitions

There were 207,529 eligible adjacent-row comparisons. **763 changed joint state**: 707 between 000 and a nonzero state, and 56 between different nonzero states. Of the 56, 46 were switches between blood-only and blood-plus-active-bleeding, 8 between blood-only and active-bleeding-only, 1 from blood-plus-active-bleeding to active-bleeding-only, and 1 from hematin-only to blood-plus-hematin.

**20/355 union spans contained multiple joint states;29/355 contained more than one target somewhere.** Those counts differ because persistent co-annotation can contain two targets without a state change. These are publisher-label transitions, not observed evolution of bleeding, distinct diagnoses or evidence that one lesion reappeared.

## Sensitivity of candidate interval construction

|Parameter value|Gap-joined union intervals|Positions included by gap rule|Context-expanded union intervals|Unique positions exposed by context rule|
|---:|---:|---:|---:|---:|
|0|355|29,766|355|29,766|
|1|323|29,798|289|30,441|
|2|289|29,866|244|30,992|
|5|230|30,092|177|32,245|
|10|177|30,492|131|33,762|
|25|116|31,520|91|36,865|

All settings preserve the same 29,766 union-positive annotation rows. Context 25 adds 7,099 recorded-zero rows and produces 91 intervals, while gap 25 adds 1,754 zero rows and produces 116. Neither 91 nor 116 is a clinical-event count. Context 25 also clips seven seed-span sides at source gaps and six at observed stream ends; clipping is retained explicitly.

The different label targets remain different construction problems. At context 25, blood/active-bleeding/hematin produce 82/17/12 intervals containing 27,340/3,203/9,614 positions, respectively. These are descriptive engineering quantities; none supports changing the historical binary-blood model's target.

## What original-image support is actually documented

An exploratory exact-index linkage reused the [November 5 selected-source audit](GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md). The 801,233-byte private archive matched its previously published SHA-256; selected member checksums and the separate metadata checksum matched. The ledger contains 11,147 unique permitted examination/index pairs, all present in the corrected grid. Linkage used only examination and index fields, not historical labels, selection flags or heuristic scores.

|Union context radius|Required annotation positions|Positions represented in historical ledger|Intervals with any ledger match|Intervals completely represented|
|---:|---:|---:|---:|---:|
|0|29,766|2,163|294/355|122/355|
|1|30,441|2,190|244/289|0/289|
|2|30,992|2,217|206/244|0/244|
|5|32,245|2,289|167/177|0/177|
|10|33,762|2,372|125/131|0/131|
|25|36,865|2,514|91/91|0/91|

**This is a historical selected-image ledger, not an exhaustive inventory of currently retained archives.** Absence does not prove that an image is unavailable elsewhere, including later retained sources. No pixels were reopened or freshly verified. The result establishes that this ledger alone cannot certify a complete chronological context packet—even at radius 1. It does not establish zero feasible packets after a complete inventory reconciliation.

## Interpretation and next action

Keep three levels separate: an annotation span, a chronological presentation interval, and an adjudicated finding identity. The first two can be constructed mechanically under stated rules. Identity requires visual review: one finding may recur in disconnected intervals, one interval may contain several findings, and luminal blood need not identify a visible bleeding source. The current 137-image isolated-frame pilot can support descriptive appearance/uncertainty judgments after qualified review; it cannot establish these identity relationships or exhaustive event coverage.

**Next executable task:** reconcile already retained archive/member manifests against the candidate contexts, without acquiring or distributing images. Record verified-present, listed-but-unverified and unresolved positions separately; distinguish image availability from source-grid continuity. Acceptance requires exact source identity and checksum provenance, complete enumeration of required context positions, independent count reproduction and an explicit unresolved list. Do not build or distribute a chronological adjudication packet before the owner authorizes that stage and qualified specialists approve its clinical target and context requirements.

For later reference-standard design, preserve appearance intervals separately from proposed finding IDs; permit same/different/unresolved identity links and multiple findings in one frame. Reviewers must record assessability, requests for more context and uncertain target/identity decisions. A full event-recall denominator requires documented assessment throughout a prespecified source domain, including areas outside publisher-positive anchors. Enriched packets alone do not supply it.

Galar documents chronological study folders, framewise annotation and removal/cutting during preparation; this supports released-source ordering, not uninterrupted original acquisition time or authenticated patient grouping [1]. Kvasir-Capsule supplies video/frame mappings but labels selected segments; its nominal exported AVI rate differs from its original acquisition rate [2]. Neither descriptor supplies the project with an independently adjudicated distinct-finding reference. Clinical relevance also depends on indication and finding context [3], consistent with current reporting guidance [4]. No universal clinical frame-gap threshold is established by these sources.

## Reproduction and verification

Two separately written implementations—sequential span/interval scanning and NumPy/Pandas mask operations—independently parsed the allowed bytes. **Every per-examination and pooled metric matched exactly**, including histograms, state-transition matrices, endpoint categories and all fixed gap/context comparisons. The prior audit's counts also matched at both levels. The historical ledger linkage was separately reproduced by Boolean-mask/prefix-sum and set-based calculations: **510 numerical comparisons, no differences**.

Seven primary synthetic tests, the independent implementation's hand-checked assertions and four source-linkage tests passed. One pre-existing anyio/pytest deprecation warning appeared; no analysis or test failed. Synthetic tests validate calculation semantics, not medical interpretation. Private evidence retains the preanalysis record, linkage addendum, allowed-member bytes, scripts, exact commands, environment, hashes, per-examination results and comparison receipts. Public content contains only aggregate research findings. No clinical reference standard, patient independence, model improvement or reading-time benefit is claimed.

## Primary sources

1. Le Floch et al. *Galar — a large multi-label video capsule endoscopy dataset*. Scientific Data 12, 828 (2025). [DOI](https://doi.org/10.1038/s41597-025-05112-7). Corrected Galar v2 annotations; original dataset attribution retained, CC BY 4.0.
2. Smedsrud et al. *Kvasir-Capsule, a video capsule endoscopy dataset*. Scientific Data 8, 142 (2021). [DOI](https://doi.org/10.1038/s41597-021-00920-z).
3. Leenhardt et al. *A guide for assessing the clinical relevance of findings in small bowel capsule endoscopy*. Clinics and Research in Hepatology and Gastroenterology (2021). [DOI](https://doi.org/10.1016/j.clinre.2021.101637).
4. Sidhu et al. *Performance measures for small-bowel endoscopy: ESGE Quality Improvement Initiative—Update 2025*. Endoscopy (2025). [DOI](https://doi.org/10.1055/a-2522-1995).
