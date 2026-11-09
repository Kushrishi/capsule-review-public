# Short-event support and examination-balance intervention

## Scientific scope

Base main bf0783d4dae60b3ad2f5def9d8884fde88d0fc66; PR69–71 failures remain immutable.
This tests a joint local-data support and exposure-balancing intervention under
unchanged compact CNN/objectives. It cannot isolate sample count from balancing,
prove a primary causal limitation, authenticate patients or validate clinical use.
The downstream research primary remains10% exact-K distinct annotation-run recall;
this examination-held-out pair diagnostic is a development gate, not a substitute.

## Data gate before any new fit

The frozen two-block acquisition selects45258019 blocks1/3,7,014,787,752 payload
bytes, cap7.2GB charged including identical retries. It adds159 original PNGs
(46,128,770 bytes) for38 additional short runs and15 additional singletons.
All70 recoverable runs have counts21=1/23=23/25=20/29=11/30=15. Forty-three have
complete positive positions plus two explicitly negative native positions on each
side. The new43 contexts are retained for future work; they are not extra inputs
or extra independent units in this experiment. Both complete compressed blocks
and all new originals must be privately retained with matching readback before fits.

New fitting/evaluation local-pair population: all69 runs in the four examinations
with>=10 source-supported runs23/25/29/30. This support gate was fixed from source
metadata, without choosing CNN outcomes. Keep21’s one-run historical failure as a
stress diagnostic; do not represent it as an adequately supported new fold.
One pair per distinct run: preserve the PR70/71 pair when that run is retained;
otherwise choose the source-left immediate negative boundary, then right only if
left is unavailable. Native stride5, explicit blood1/0, run length1–5, no gaps or
unknown bridging. No repeated presentations, two sides or nearby context images
increase the number of distinct runs. Shared negative endpoints remain visible.

Keep the exact4096 PR71 background references and their order. Build the source
bank with the original4156 identities/order as a prefix, then append needed
source/context images deterministically. Existing prefix pixels must exactly match
PR71. Verify new PNG CRC/bytes/SHA/decoding, corrected-label joins, full run and
context membership, zero source/preprocessed cross-examination duplicate identity,
and zero byte overlap with31/34/37. Repeat the existing64px aligned-copy screen
on all common pair endpoints versus every other-examination bank image. A strict
MAE<=.06,centralMAE<=.07,SSIM>=.95 match stops fitting, rather than dropping a bad
case. This does not clear transformed copies or repeated patients.

## Reuse and controlled execution

Reuse the24 PR71 fits for four supported held-out examinations, two objectives
and seeds17/29/43. Never retrain the legacy32-run cohort. Reuse every saved endpoint
logit; score only newly required endpoints with those retained checkpoints. Verify
checkpoint/prediction hashes and source membership. Shared held-out69-run outcomes
are a new, already-inspected-source development comparison; they do not replace
the original32-run/five-examination PR71 numbers.

Train exactly24 new models: four folds×two objectives×three seeds. Remove each
held-out examination completely from both background references and pair training,
including context/source overlap. Training run counts are46/49/58/54 for held-out
23/25/29/30. All69 source runs remain evaluation-eligible when their exam is held out.

Unchanged capsule-cnn-v1,96px EXIF/RGB black-pad bilinear,uint8/255, no augmentation,
AdamW(lr.001,weight_decay.0001),1024 deterministic CPU updates/two threads. Each
batch has16 references+eight pair positives+eight pair negatives;32768 image
presentations,8192 pair slots. Final checkpoint only. No weight/architecture/seed,
checkpoint or stopping-rule search.

The sole data intervention uses all supported runs and equal training-examination
pair exposure. Shuffle complete cycles of the three remaining examination IDs
(seed+100003),truncate8192 slots. Within each examination, shuffle complete run
cycles(seed+200003+exam ID),truncate its slot count. Examination exposures differ
by at most one; each run’s presentations within its examination differ by at most
one. Reference schedules are unchanged seeded shuffled cycles of remaining core,
truncated16384. Within each seed/objective pair, initial tensors, exact image
exposures, actual inverse-exposure class weights and optimizer budget match.
Reconstruct legacy schedules/class counts to verify the reference exposure and
initialization match PR71; changed pair membership/schedule is the intended joint
support intervention. No new forward views are granted to the ranking arm.

Control: original inverse-exposure two-class CE. Candidate: identical CE+
0.5×mean softplus(z_negative−z_positive), z=logit_blood−logit_other. The fixed PR70
objective implementation is reused unchanged.

All24 new fits and24 legacy prediction extensions must finish and be sealed,
privately saved and readback-verified before outcome calculation. Any source,
finite-value, hash, leakage or retention failure stops execution. Preserve failed
attempts; no alternative case/seed/parameter chosen to get a positive result.

## Endpoints and advance criteria

Shared held-out pairs: one per run,69 runs, four examinations,21 singletons.
Report all four population/objective cells for each seed and examination; correct
ordering margin>0, exact tie0 contributes.5. Equal-examination/seed ordering is the
development summary. Principal data contrast: expanded classification minus legacy
classification. Also report expanded ranking minus legacy ranking, and ranking
minus matched classification within each cohort. This is a factorial-style reuse
comparison, not four newly fitted arms.

Report per-source counts, distinct-run weighting, seed variation, singleton
regressions, training ordering, logit and softmax margin distributions. A margin
increase can reflect logit scale; scores are not calibrated clinical probabilities.
Use seed SD/range and leave-one-examination-out contrasts as descriptive sensitivity,
not patient-population CIs. Do not bootstrap correlated pairs or count three seeds
as additional patients; folds share much training material.

A contrast passes consistency only if all three seed macro differences>0, every
examination’s seed-mean ordering difference>=0, and equal-examination/seed singleton
mean difference>=0. Report any cell-level regression regardless of macro result.
No favorable individual seed is selected. More data is not demonstrated helpful
merely because training ordering is perfect.

Full-source new-model benchmark eligibility: new classification only if its data
contrast passes; new ranking only if both its data contrast and new-cohort ranking
contrast pass. Any later full-source experiment needs a separate full-fit/prediction
commitment. Use unchanged10% exact-K run recall primary, short-run and25% secondary;
no training on31/34/35/36/37 or61–80. No model promotion from this diagnostic.

If neither new arm passes, do not fit another architecture or acquire more pairs
in this task. Execute one prespecified alternative-formulation control: unchanged
existing score_guarded versus uniform and score_bin, using the retained original
CNN scores on already-inspected31/34/37. This is an exploratory fixed-score policy
test, not new CNN inference or independent confirmation. Keep the exact historical
source/labels/scores and half-up10%/25% K; run definition native5 unchanged.
Primary equal-positive-examination10% distinct-run recall; short/singleton and25%
secondary;37 zero-positive recall undefined. No selector weight/sweep/tie change.
The gap guard is technical only. Report all misses and whether the policy exceeds
uniform on both positive examinations without short-run regression. Independent
implementation must reproduce every selected set and count. No policy promotion
or clinical guarantee regardless of outcome.

Public code/tests/aggregates only. Keep medical pixels, individual labels/scores,
weights, membership/context records and provenance private. External outreach is
not authorized. Final-head matrix/model/browser/privacy checks required before merge.

## Operational retention amendment, before fitting

Observed host limit:104857600 bytes per transferred file; multi-file large prepare
requests failed before writes. The source blocks have therefore been losslessly
repacked into71 pieces below that limit, with unchanged concatenated block hashes
and zero additional publisher bytes. Save/verify all actual new PNGs, memberships,
source/protocol commitments before fitting, as already completed. Compressed-block
piece saving may run alongside fitting, but all71 pieces must be saved and their
readback block hashes verified before final merge. This supersedes only the earlier
compressed-block-before-fitting timing rule; data/metrics/exposures/stop criteria
are unchanged. No model fit or outcome inspection preceded this amendment.
