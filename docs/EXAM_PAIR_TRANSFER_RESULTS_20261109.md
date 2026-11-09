# Examination-held-out local-pair transfer — 9 November 2026

**The fixed ranking objective did not demonstrate transferable ordering improvement.** Thirty new examination-excluded fits completed; all checkpoints/predictions were privately sealed, saved and byte/hash-readback-verified before outcome calculation. Independent replay verified60 metric cells,15 paired effects and all30 reconstructed models (3,780 logits; maximum difference0). No model promoted; PR69/70 and historical Galar11–20 negative results remain unchanged.

## Feasibility, source recovery and frozen design

Main was still PR70 merge `d7bcdc5d0473450312141ab18e865fdd4e9668fc`, with no newer PR. The PR70 final archive matched SHA256 `acdaed69246321d8efcc446787b83eb34fd0fa47ad88026a0aa6d8a0b30e0d07`; all18 manifest entries were verified. PR69 recovery verified15 final and56 pre-outcome entries, including corrected labels. Ten retained fitting-source packages and10,123 PNGs plus the21 added originals were reverified. All63 pair endpoints match retained official source-index CRC/byte lengths. Zero-based run IDs, native±5 boundary adjacency, explicit corrected blood labels and run lengths were independently rederived. The reconstructed4156-image input bank exactly matches PR70 SHA256 `ab80763638c4e13187c03e50203de2f1e0af3c50c932f75d09213ab50c340401`. No new original images or historical inference/training were repeated.

Five folds provide32 distinct short runs, not32 patients. Counts are1/4/1/11/15; six runs are singletons. There are63 endpoint images because two runs share one negative. Each held-out examination was entirely removed from background references and pair training, including all its contexts. Cross-examination original/preprocessed byte identities do not overlap. A new screen made240,356 endpoint-to-other-examination comparisons on64px RGB derived from the unchanged96px bank:1,359 MAE<=.06 candidates, zero strict aligned copies; maximum candidate grayscale SSIM0.819885. This is not exhaustive transformed-duplicate clearance or authenticated patient separation. Prior embedding/source audits are supporting context only.

All five folds were prespecified. The1/4/1 folds have100/25/100pp ordering resolution and cannot yield precise transfer estimates. Folds29/30 provide26/32 runs and form the prespecified higher-support sensitivity. The available support permits a **limited examination-held-out diagnostic**, not powered efficacy, patient-independent validation or a general mechanism test.

The [design](EXAM_PAIR_TRANSFER_LOCK_20261109.md), [JSON lock](EXAM_PAIR_TRANSFER_LOCK_20261109.json) and executables were locally committed and privately retained before fitting; the equivalent public snapshot is `837eb2cc407168dc4168ea8153b5b9ba60f0cc7e` (published shortly after launch). Seeds17/29/43; unchanged capsule-cnn-v1/96px preprocessing;1024 deterministic CPU AdamW updates;32,768 image presentations per fit. Each batch has16 eligible references and8 real pairs. Shuffled remaining-reference/pair cycles preserve the budget after examination removal. Within each fold/seed, initial tensors, exposure schedule, actual inverse-exposure class weights and optimizer budget match exactly. Candidate uses unchanged CE+0.5×softplus(z_negative−z_positive); control uses CE. Final checkpoint only; no seed, fold, weight or architecture selection. No31/34/37 benchmark fitting, scoring or tuning; no11–20/61–80 payload use or outreach.

## Every held-out result

Cells report correctly ordered pairs; there were no exact ties. One pair represents one annotation run.

| Examination | Runs | Seed17 classification/ranking | Seed29 classification/ranking | Seed43 classification/ranking | Seed-mean difference |
|---|---:|---:|---:|---:|---:|
|21|1|0/0|1/0|0/0|-33.3333pp|
|23|4|0/1|3/0|2/2|-16.6667pp|
|25|1|0/0|1/0|1/1|-33.3333pp|
|29|11|7/6|8/8|7/8|+0.0000pp|
|30|15|10/10|12/12|11/11|+0.0000pp|

| Summary | Classification | Ranking | Paired change |
|---|---:|---:|---:|
| Primary: equal examination/seed ordering |56.3333%|39.6667%|−16.6667pp|
| Higher-support29/30 sensitivity |70.0000%|70.0000%|0.0000pp|
| Pooled repeated seed-run opportunities (secondary) |63/96|59/96|−4/96|
| Training pair ordering (repeated fold/seed opportunities) |384/384|384/384|0|
| Singleton ordering (repeated seed-run opportunities) |13/18|13/18|0|

Primary paired seed effects are+3.1818,−55.0000,+1.8182pp (SD33.2046pp). The single seed29 loses both one-run folds and3/4 exam23 pairs relative to classification; this drives much of the macro regression. The prespecified consistency rule fails: not all seeds improve and three examination mean effects are negative. Leave-one-examination-out mean effects range−20.8333 to−12.5000pp. These are sensitivity summaries, not confidence intervals. Examinations/folds have overlapping training sets; seeds and repeated runs are not new independent source units. No naive binomial or patient-population significance claim is made.

In29, seed17 loses one correct ordering and seed43 gains one. In30, every seed has identical correct counts between arms. Both objectives order substantial fractions of these two examinations correctly, but the ranking intervention adds no mean ordering benefit there. This is limited evidence of some cross-examination image discrimination, not proof of generalizable pathology recognition. The small poor-support folds cannot be hidden behind the pooled65.6250%→61.4583% result or omitted after outcomes.

All32 held-out runs are short (1–5 published annotated positions), not timed events or adjudicated lesions. Exam23’s singleton is misordered by both arms in all seeds. In29 singleton correct opportunities improve5/6→6/6; in30 they worsen8/9→7/9. These repeated opportunities summarize six distinct singleton runs; they are not18 independent events.

## Margins and interpretation

Ranking increased every matched fit’s mean training logit margin; the equal-cell training mean rises5.35716→6.33270 while training ordering remains perfect. Equal-examination/seed held-out mean margins are0.01796→0.03849 despite worse ordering. Increasing logit scale can enlarge both useful and harmful separations; softmax scores are uncalibrated and local-margin gains are not event-preservation gains. Low-support individual margin distributions remain private.

For transparency, the public aggregate reports held-out logit-margin histogram counts across96 **repeated** seed-run opportunities. In bins (−∞,−1),[−1,−.25),[−.25,0),[0,.25),[.25,1),[1,∞), classification has11/14/8/11/26/26 and ranking10/24/3/2/20/37. The broader tails do not establish a calibrated improvement. Full per-fold/seed logit and probability margin distributions are privately retained.

| Hypothesis | What the new evidence supports | What remains unresolved |
|---|---|---|
| Too few independent training examples |32 runs, five strongly imbalanced source examinations and hundreds of presentations per pair are a concrete support limitation |No learning curve or sample-size intervention was performed |
| Examination-specific fitting or memorization |Perfect training ordering and larger fitting margins fail to produce consistent held-out gains; source specificity is plausible |Cannot isolate memorization from representation/context/labels; patient repeats unverified |
| Inadequate local context |Only one positive boundary and one negative neighbour per run were trained |No two-sided/context intervention was tested |
| Weak ranking objective |The unchanged0.5 ranking term fails the matched transfer comparison |Does not show all ranking losses fail or justify a weight sweep |
| CNN representation limitations |Shared compact representation remains a possible bottleneck |No matched representation intervention was tested |
| Selection geometry/reference limitations |Pair ordering is distinct from fixed-workload run coverage; prior geometry failures remain relevant |No selector or clinical annotation standard changed; this test cannot estimate clinical benefit |

## Single next experiment and bounded source preflight

**Increase and balance independent short-run boundary support, then repeat the same fixed examination-held-out objective comparison.** Prioritize data support before a new complete-source benchmark or architecture sweep. A concrete conditional engineering target is10 distinct genuine short runs in each of the five existing permitted fitting examinations that have at least10 eligible runs:7/23/25/29/30, selected by label/source support rather than observed model success. This yields50 runs and10pp within-fold resolution. It is not a power calculation, a promise of improvement or patient validation;21 has only two eligible short runs and cannot reach this target. Keep its completed result as a stress diagnostic.

A metadata-only enumeration of the retained corrected labels and verified source indexes identifies a deterministic50-pair plan needing35 additional original PNGs (11,754,850 bytes). Exhaustive independent checking of all512 relevant complete-block subsets confirms a minimum18,006,872,916 compressed source bytes under this specific10-per-exam gate. Selected source blocks are44724816:5/6/7 and45258019:1/4. Pixel choice is deterministic low-byte per-run selection, not a proof of globally minimum extracted bytes with shared endpoints. Actual new transfer depends on recovering any already-retained compressed blocks first. No payload was acquired.

The18GB container cost is disproportionate to11.75MB of needed pixels. Treat this as a resource gate, not permission for a speculative download: recover already-retained blocks or obtain the exact bounded subset through an existing permitted source route first. Before any acquisition, pin exact members/CRC/hash records, refresh Galar correctedv2 CC BY4.0 rights, check streaming capacity plus8GiB headroom, and freeze the source-transfer cap and new matched experiment. Do not silently relax the support target, repeat an available download, choose favourable source cases or call the target statistically sufficient. No broad survey or outreach is needed for this decision.

## Reproduction, privacy and validation

[Public aggregate](../experiments/exam-pair-transfer-20261109/aggregate.json) contains non-identifying counts and pooled margin summaries only; low-support raw margins are redacted. Original pixels, labels, source membership, endpoint logits, weights, similarity records and private group information remain outside Git/Actions. No model was integrated into the viewer.

Local full suite:1,028 passed,1 skipped. Three focused transfer tests pass. Frozen-branch Python3.11/3.12/3.13, local-model/browser and privacy CI passed. Local browser launch was blocked by the environment’s socket permissions; the identical repository smoke path passed in GitHub CI. Final result-head checks are required before merge; exact outcomes and run identifiers are recorded in PR#71 and the private final handoff.

Private pretraining contract:281,432 bytes, SHA256 `90b90f621c98ad8c9b8d10b2118a785e9699055162765d98dcb2bf42a7a9cc8a`. Private pre-outcome evidence:3,345,076 bytes, SHA256 `21feb7e7da0e8f2b50b16c5be90efbb0cc559d406ebc58f0d69b8f8b5c62a385`, saved/readback-verified before outcomes. The reconstructed input bank and recovered local source copies are temporary caches backed by separately verified retained sources, not a newly retained complete publisher archive. Final private evidence, exact source locations/checksums, CI and merge receipts are supplied in the private final handoff.
