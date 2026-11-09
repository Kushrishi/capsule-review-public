# Matched local short-event objective experiment

Development-only experiment following PR69. Freeze this document, the JSON input
contract and all executable hashes before six new fits. Do not repeat the six
completed PR69 fits. Fitting cases:1–8 and21/23/25/27/29/30; evaluation:31/34/37.
No11–20 or61–80 use, outreach, Google Drive copying or clinical promotion.

## Actual data gate

Retained sources yielded14 true adjacent opposite-label pairs, ten from short
runs. The acquisition lock f187ef0cad36c1895b28200e61af852a4357d880 fixed a32-run
engineering minimum across≥4 exams with≤16 runs per exam, not statistical power.
The minimum verified whole-solid-block repair acquired3,514,256,456 compressed
bytes from source45258019/block8, matching its previously pinned SHA256. Only21
new original PNGs were extracted (4,871,891 image bytes), saved privately and
readback-verified. The full publisher archive MD5 remains unverified.

All10,123 original retained fitting PNGs, ten source ZIP identities, explicit
corrected-v2 fitting labels and21 new originals were reverified. The fixed32
pairs represent32 distinct short annotation runs across21/23/25/29/30 with counts
1/4/1/11/15. Every pair is a genuine same-examination positive boundary image and
its immediate±5 explicitly negative source neighbour. A run has1–5 successive
positive published positions at native+5; source gaps and unknowns are never
bridged. None of these concepts establishes elapsed time or unique lesions.

Keep the exact4,096 PR69 diverse-arm references (239 positive/3,857 other) as a
common background population, adding only the frozen local pairs. The input union
has4,156 distinct original images. Shared endpoints and overlap with references
are preserved transparently; pairs are not independent patients. Check all source
SHA/size/CRC and zero PNG-byte overlap with31/34/37; near-duplicate and patient
linkage remain unverified. New inputs/manifests and existing evaluation identity
lists are pinned in the private and public contracts. Rights: Galar v2, CC BY4.0,
Le Floch et al.; exact corrected-label ZIP SHA remains unchanged.

## One controlled intervention

Use unchanged capsule-cnn-v1, EXIF/RGB black-padded bilinear96×96, float32/255,
AdamW(lr0.001, weight_decay0.0001), CPU two threads, deterministic algorithms.
Paired seeds17/29/43; same initial weights, sample schedule and image exposures.
No augmentation, alternative architecture, learning-rate/loss-weight search,
validation-based stopping or favorable seed/checkpoint selection.

Each of1,024 updates has16 background references, eight pair-positive images and
their eight pair-negative images. References undergo four seeded complete shuffled
passes; each of32 pairs occurs256 times in a separate shuffled stream (seed+100003).
Each fit therefore has32,768 image presentations:9,148 positive and23,620 negative,
with identical batch labels and ordering between paired arms. Pair images are
forwarded only once; no extra model views or updates are granted to the candidate.

Control: inverse-exposure-frequency weighted binary classification cross entropy
on all32 images, using the original two-logit formulation. Weights are
32768/(2×23620) and32768/(2×9148). Two-class CE is the equivalent binary
classification objective for the difference of the two logits.

Candidate: that identical CE plus **0.5×mean softplus(z_negative−z_positive)**
over the eight local pairs, where z=logit_blood−logit_other. Fix0.5 as one moderate
engineering weight before training; no outcome-based alternatives. Use the final
1,024-update checkpoint. All six fits must finish before benchmark scoring. These
new matched classification controls are necessary because the pair-enriched
exposures differ from PR69; comparing only against old fits would confound data
and objective changes.

## Frozen evaluation and decision

Score retained complete31/34/37 sources with all six new checkpoints; never rerun
the historical CNN. Verify every restored PNG against its prior frozen SHA and
the source index; cached tensors must match PR69 preprocessing identities.
Original benchmark restoration is private retained-source recovery, not new
publisher acquisition. Independently verify source preprocessing and new-model
canary predictions. Seal all18 vectors and retain/readback-verify checkpoints,
input membership and predictions before the separate outcome script runs.
Already-inspected development data are not new blinding or independent validation.

Primary:10% exact-K raw score-bin distinct annotation-run recall, half-up integer
K and earliest maximum ties unchanged. Average31 and34 equally; compare ranking
minus matched classification for every paired seed and the mean.37 contributes
workload accounting with undefined positive recall. Jointly report uniform and
exact geometry contrasts; reuse frozen geometry/phase arrays unchanged and compute
tie-aware exact score-permutation expectations. Historical CNN/PR69 fits are
descriptive references only, never selected controls or new pooled confirmation.

Secondary:25%, short/medium/long runs, singleton omissions, positive-image retrieval,
global-score and score-diverse policies, every examination and seed. No temporal,
tie or selector sweep. Run-lengths are annotated positions, not seconds/lesions.

A positive primary mean is an observed development difference; consistency requires
all three paired primary effects positive and both positive-examination seed means
nonnegative. Report failure of any consistency condition, any short-run regression,
and all ordinary seed variation. A benchmark-favorable single seed, better image
enrichment or a25% gain cannot replace the primary. Utility versus uniform and
geometry is a separate gate. No patient-population confidence claim or automatic
model promotion regardless of outcome. Three seeds and two positive examinations
cannot establish clinical or patient-independent improvement.

Any source/label/adjacency/hash/retention failure stops execution; do not swap pairs,
coerce unknowns, relax source rules or retry alternative parameters. Independent
replay imports no production selector/evaluator and must reproduce all counts,
queues and exact expectations. Publish only code and aggregates; preserve all
earlier negative findings. Merge only after final-head matrix/browser/privacy CI.
