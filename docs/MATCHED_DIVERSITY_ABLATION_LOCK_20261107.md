# Matched-budget fitting-examination diversity ablation

This is a development-only, retrospective improvement experiment following PR68.
It is not patient-independent validation. This document and the companion JSON
contract must be committed before any of the six fits. The JSON pins the actual
verified private manifest, input tensors and executable code. If that preflight
fails, this document is a proposal only; training must not start.

## Question and matching

Does spreading a fixed fitting-image budget across more permitted examinations
improve the compact CNN's complete-source distinct-annotation-run retrieval?
The intervention changes the distribution of both positive and other fitting
images across examinations. It cannot isolate positive diversity from negative
diversity, frame appearance, anatomy, site/device or particular image membership.

Original population: the existing 512 uniform references from each of 1–8.
Broader candidate population: those references plus the existing 512 uniform
references from each of 21/23/25/27/29/30. No enriched additions, 9/10, benchmark
examinations, or reserved 61–80 are eligible. Labels must be explicit corrected-v2
`blood=0/1`; zero does not mean absence of other pathology.

Each arm has exactly 4,096 distinct images: 239 positive and 3,857 other. Original
uses all 4,096 eligible 1–8 images. Diverse uses a capacity-constrained round-robin
sampler separately within each class, cycling examination IDs in ascending order,
and consuming hash-ordered images within examination. Hash input is the literal
`20261107:exam:frame:source_sha256` string. This is one fixed membership sample
shared by every optimizer seed; sampling variability is not estimated. It reduces
the largest positive-examination contribution from 208/239 to 55/239 and expands
positive-examination support from five to eleven, subject to verified assets.

Sort both arms by `(blood, exam, frame)`. This preserves the identical label
sequence, so paired seeds generate identical batch class counts and share
initialization and shuffled index permutations. Images necessarily differ.
Overlap between fitting arms is allowed and must be quantified; overlap with
benchmark examinations or exact benchmark source-image hashes is prohibited.

## Source, rights and leakage gates

Use only privately retained original images attributed to Galar v2, Le Floch et
al., DOI 10.25452/figshare.plus.25304616.v2, under CC BY 4.0. Verify the retained
publisher catalogue licence, original source-archive dependency hashes, every
eligible PNG hash/length, existing reference membership and corrected-label joins.
Pin corrected labels ZIP SHA256
`2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`.
Open only the permitted fitting and already-completed benchmark CSV members.

Recheck all 53,911 retained benchmark PNGs against the frozen PR68 hash manifests;
reuse their originals without publisher reacquisition or historical CNN inference.
Screen exact PNG overlap and exact preprocessed-image overlap. Any overlap in
selected fitting inputs stops the proposed comparison pending an explicit
pre-outcome amendment. Authenticated patient linkage remains unavailable; exact
hash checks and prior neighbour audits cannot prove patient separation or exclude
transformed/near-duplicate leakage. Devices for added fitting cases and individual
site assignments remain unverified. These limits prohibit patient/domain claims
but do not prohibit this expressly authorized examination-separated exploration.

## Fixed learning and scoring

Architecture: unchanged `capsule-cnn-v1`, three stride-two 3×3 convolutions with
16/32/64 channels, GroupNorm(4), ReLU, global average pooling and two-class linear
head. Original EXIF transpose, RGB, bilinear black `ImageOps.pad` to 96×96,
float32/255 preprocessing. Cached uint8 tensors must reproduce that transformation.
No augmentation, pretrained weights, extra normalization or calibration.

Paired optimizer seeds **17, 29, 43**; torch deterministic algorithms, two CPU
threads. AdamW, learning rate 0.001, weight decay 0.0001, batch 32, inverse-frequency
weighted cross entropy `[4096/(2×3857),4096/(2×239)]`. Exactly eight complete epochs,
1,024 optimizer updates and 32,768 image presentations per fit. Use the final
checkpoint, without intermediate benchmark scoring, early stopping, checkpoint,
seed, hyperparameter or sampler selection. The historical checkpoint happened
to be selected at epoch eight from its original ten-epoch development-loss run;
that historical selection and input ordering remain different from these fixed
retraining arms. Compare its frozen results descriptively, never as a paired seed.

Train all six models before scoring. Retain every final checkpoint, initial
tensor digest, epoch loss log and runtime identity. Score all three complete
retained sources with each model, using CPU eval/inference mode, batch 32 and
blood-class softmax. The total is 323,466 new-model forward passes. Do not rescore
the historical CNN. Seal all 18 snapshots and retain a privately verified evidence
package before the separate outcome script runs. Already-inspected labels mean
this computational separation is auditable, not new blinding.

## Endpoints and analysis

The primary is **10% distinct blood-positive annotation-run recall**, using the
unchanged raw score-bin selector, exact K = floor((N×percent+50)/100), earliest
maximum tie rule and native +5 source-position runs. Primary unit: examination;
31 and 34 receive equal weight, regardless of their 162 versus nine runs. 37 has
no positive runs, contributes workload/score accounting and has undefined positive
recall. It cannot establish clinical normality, specificity or false-alert rate.

Report jointly:

1. Diverse minus matched-original macro run recall for each paired seed and their
   mean; seed SD/range are optimization variation, not patient confidence bounds.
2. Each arm's macro contrast against the unchanged historical checkpoint.
3. Each arm's raw-minus-deterministic-uniform and raw-minus-exact-geometry
   contrasts. Reuse the historical geometry/phase reference arrays unchanged;
   do not rerun the original experiments. Recompute exact expected geometry
   counts and tie-aware score-permutation expectations for each new score vector.
   Quantization ties can change the permutation expectation; report this separately
   from score-free geometry rather than assuming they coincide.

**25% is secondary.** Also report every examination and seed, positive-image
retrieval, short (1–5), medium (6–25), long (26+) runs, singletons and omissions.
Keep uniform, global-score and score-diverse comparisons descriptive; no selector
winner is chosen. Keep Galar35/36 historical reports unchanged and descriptive:
new models are not evaluated there, so no new-model improvement is asserted there.
Do not pool five inspected cases into a new confirmatory success.

Interpretation is layered. A positive mean paired contrast is an observed
development improvement under this fixed membership; support is stronger if all
three paired contrasts and both examination-level seed means improve. If signs
vary, explicitly retain ordinary training variation and heterogeneity as competing
explanations. Beating a weak retrained control without beating the historical
checkpoint is not improvement over the deployed research baseline. Beating that
checkpoint while remaining below uniform is not evidence of a useful triage gain.
No magnitude, favorable seed or secondary endpoint substitutes for these joint
comparisons. Three seeds and two positive examinations do not establish population
significance, robustness, patient independence, unique-lesion sensitivity or
clinical utility. No model promotion or automatic viewer integration.

## Independent verification and retention

A separate scalar implementation imports no production selector/evaluator and
recomputes all exact-K policy sets, run/image/stratum counts, geometry and tied-score
expectations, paired changes and seed variation. Independently verify source
preprocessing and checkpoint/score identities. Keep original frozen evaluation,
all seeds, failures, individual records, queues, source labels and weights private.
Publish reproducible code and non-identifying aggregates only; run source-boundary,
core Python matrix and browser/local-model checks before merging a narrow PR.

No authors, researchers, clinicians or supervisors are contacted. If any matching
constraint is infeasible, freeze an explicit comparable amendment before fitting
or outcomes; do not silently reduce counts, substitute sources or relabel unknowns.
