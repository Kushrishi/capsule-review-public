# Examination-held-out local-pair transfer diagnostic

Freeze before new fits. Base: PR70 main d7bcdc5d0473450312141ab18e865fdd4e9668fc.
This is a limited already-inspected fitting-source diagnostic, not independent
patient validation or a powered efficacy experiment. No benchmark31/34/37
training, scoring, tuning or outcome use; historical negative results unchanged.
No reserved11–20/61–80, acquisition or outreach. No model promotion.

## Source support and eligibility

Use exactly the32 retained genuine adjacent positive–negative pairs from32 short
annotation runs, native stride5, across21/23/25/29/30 (1/4/1/11/15).
Six singleton runs;63 endpoints, one shared negative. Verify corrected-label ZIP
and each permitted CSV, reconstruct zero-based run IDs, adjacency and run lengths,
all original PNG identities and ten retained archive hashes. Restore the fixed
PR70 union4156/4096 core references; its96px bank must match PR70 SHA exactly.
No repeated presentation increases independent support.

All five leave-one-examination-out folds are included. The1/4/1 folds offer only
100/25/100pp ordering resolution and are descriptive. The11/15 folds supply26/32
runs; report their equal-examination contrast as a prespecified support sensitivity,
not as a replacement primary or a favourable post-outcome subset. Five overlapping
training sets, uncertain patient grouping and selected boundary examples do not
support population generalization, clinical event sensitivity or formal power.

Remove the entire held-out examination from both references and pair training,
thus also excluding all its source contexts. No train/test source ID, PNG SHA or
preprocessed byte identity overlap. A new exhaustive aligned-image screen compares
all63 pair endpoints against every other-examination image in the fixed bank:
64px RGB derived from the unchanged96px bank, MAE<=.06 candidates checked for
centralMAE<=.07 and grayscale SSIM>=.95. A strict match stops training; do not
replace pairs. This screen and historical embedding/source audits reduce obvious
copy leakage but cannot clear transformed copies or authenticate patient repeats.
That remaining uncertainty is acceptable only for this examination-level diagnostic.

## Matched exposure and fixed intervention

Thirty new fits: five folds × seeds17/29/43 × classification/ranking. These are
necessary examination-excluded fits; PR69/70 fits are not repeated. Unchanged
capsule-cnn-v1, EXIF/RGB black-padded bilinear96px, uint8/255, no augmentation.
AdamW lr.001/weight_decay.0001,1024 updates, deterministic CPU/two threads.
Final checkpoint only; no validation stopping, seed, weight or architecture search.

Each update:16 allowed background references and8 allowed positive–negative pairs.
Generate seeded complete shuffled cycles of remaining core references, truncating
to16384 slots; pairs use seed+100003 complete shuffled cycles, truncating8192 slots.
Schedules are identical between arms, with seed-specific initial tensors identical.
32768 total image presentations per fit. Background membership and pair counts
necessarily differ by fold; never compare unmatched folds as a causal intervention.
Class weights are inverse actual exposure frequency per fold/seed, identical within
paired arms. Every training pair appears floor/ceil(8192/n_pairs) times, not a new run.
Control: original inverse-exposure weighted two-logit CE. Candidate: same CE+
0.5×mean softplus(z_negative−z_positive), z=blood-minus-other logit, unchanged PR70.
Pair endpoints are forwarded once; no extra image exposures for candidate.

Record all30 final checkpoints and endpoint logits, schedules, initialization,
class counts, source and executable hashes. Seal and durably save complete
pre-outcome records before separate outcome calculation. No ordering diagnostic
is inspected while fitting. Any integrity/nonfinite/retention failure stops;
resume only missing prescribed fits from their recorded inputs, never replace a
completed fit or rerun a seed because its result is poor.

## Endpoints, decision and uncertainty

Principal: held-out positive-minus-negative logit margin and correct pair ordering
(margin>0; tie exactly0 contributes.5). One pair per distinct run, so run weighting
is pair weighting within examination. Report every seed/examination; primary mean
is ranking-minus-classification averaged equally across five examinations and
three seeds. Report mean/min/quartiles/median/max logit margins and probability
margin distributions, plus singleton failures, and training pair ordering/margins.
Raw margin changes depend on logit scale; softmax is uncalibrated. A larger margin
alone is not a transferable ordering benefit or evidence-preservation benefit.

An observed positive primary difference is descriptive. Consistency requires all
three seed macro differences>0 and every examination's seed-mean difference>=0.
Any failed condition, singleton regression, training/held-out divergence and
higher-support sensitivity regression is reported. No promotion regardless of
result, since local ordering is not fixed-workload event preservation.

Report seed-effect SD/range, per-examination variation and leave-one-examination-out
mean-effect range as sensitivity summaries, not confidence intervals. Do not
bootstrap pairs or seeds as patients, use naive binomial significance, or claim
patient-population confidence. The tiny number of source units and overlapping
fold fits prevent a strong mechanistic claim. Perfect fitting ordering with weak
held-out ordering is consistent with source specificity; it cannot isolate
memorization, representation, context, objective or annotation problems.

A separate implementation replays every ordering/margin cell and paired effect,
and independently reconstructs all30 CNNs to verify endpoint logits. Public tests
use synthetic inputs. Public results contain aggregate fold/seed records only;
source frames, labels, raw logits, weights, memberships and similarity scores stay
private. Final-head matrix/browser/local-model/privacy CI required before merge.
