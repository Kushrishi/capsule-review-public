# Controlled training diversity: no primary mean improvement

Executed November 7, 2026 UTC from PR68. **Six real CNNs were trained and evaluated.
The matched diversity intervention did not improve the primary endpoint:** at
10% workload, both arms averaged **61.0082%** distinct-run recall, versus **78.0864%**
for deterministic uniform and **59.2593%** for the historical checkpoint. The paired
mean effect was exactly zero in run counts, with large seed-dependent differences.
No seed, checkpoint or model was selected or promoted.

This is already-inspected, examination-separated **development evidence**. Patient
linkage is unverified. Annotation runs are not independent lesions; blood labels
are not diagnoses, clinical sensitivity or measured reading-time benefit.

## What was controlled and actually verified

The [design](MATCHED_DIVERSITY_ABLATION_LOCK_20261107.md) and
[machine-readable contract](MATCHED_DIVERSITY_ABLATION_LOCK_20261107.json) were
committed as `4dc7a97f59cb522f24491e0d9de34939985de855` before fitting.
No matching amendment was needed.

All ten retained fitting-source ZIPs matched their previously recorded archive
SHA256s and byte sizes. Every eligible **7,168 original reference PNG** matched its
source hash/length and explicit corrected-v2 label. These are 512 uniform
references from each of 1–8 and 21/23/25/27/29/30, containing 526 positives and
6,642 other images. Enriched additions, 9/10, benchmark sources and 61–80 were
excluded from fitting. Galar v2 is attributed to Le Floch et al. under CC BY 4.0;
the retained publisher catalogue and raw corrected-label ZIP are pinned.

All **53,911** retained benchmark PNGs were freshly rehashed against the frozen
PR68 manifests. There were zero exact PNG or exact 96×96 preprocessed-image
overlaps with the fitting bank, which itself contained 7,168 distinct preprocessed
inputs. Earlier near-neighbour audits and these exact checks do not authenticate
patient separation or rule out transformed/near-duplicate leakage. Added fitting
cases' individual device/site records remain unverified. No new publisher source
acquisition or historical CNN inference occurred.

| Matched property | Original-population arm | Diverse-population arm |
| --- | ---: | ---: |
| Distinct fitting images | 4,096 | 4,096 |
| Blood-positive / other | 239 / 3,857 | 239 / 3,857 |
| Eligible fitting examinations | 8 | 14 |
| Examinations represented among selected positives | 5 | 11 |
| Largest examination's positive contribution | 208/239 | 55/239 |
| Epochs / batch / optimizer updates per fit | 8 / 32 / 1,024 | 8 / 32 / 1,024 |
| Fixed paired seeds | 17, 29, 43 | 17, 29, 43 |

The arms shared 2,293 images; the intervention substituted 1,803 while keeping
class counts fixed. It changed both positive and other-image examination
distributions, not positive diversity alone. A separate implementation reproduced
the entire frozen sampling membership. Both arms used the same class-ordered
label sequence, paired initialization, shuffled indices and batch class counts.
Architecture, EXIF/RGB padded bilinear 96×96 preprocessing, AdamW, learning rate,
weight decay and inverse-frequency cross entropy were identical. No augmentation,
calibration or benchmark-selected stopping was used. All six final-epoch
checkpoints were retained after **6,144 total optimizer updates**.

There were **323,466 new-model benchmark forward passes**, plus 144 independent
technical canary passes. The canary reconstructed the architecture separately,
reopened deterministic original-image positions and reproduced preprocessing and
new-model scores exactly (maximum observed absolute error zero). It never ran
the historical checkpoint. All 18 score snapshots, six checkpoints and fitting
membership were privately sealed and remotely readback-verified before the
separate outcome comparison. This is computational separation, not new blinding.

## Primary: every paired seed at 10%

Values are the mean of Galar31 and Galar34 run recall with equal examination
weights. Galar37 has no positive blood runs, retains its workload accounting and
has undefined positive recall.

| Seed | Original-population CNN | Diverse-population CNN | Diverse − matched original (pp) |
| --- | ---: | ---: | ---: |
| 17 | 67.9012% | 60.4938% | −7.4074 |
| 29 | 66.0494% | 61.7284% | −4.3210 |
| 43 | 49.0741% | 60.8025% | +11.7284 |
| Mean over all fixed seeds | **61.0082%** | **61.0082%** | **0.0000** |

Paired-effect seed SD is **10.2737 pp**, with range **−7.4074 to +11.7284 pp**.
These describe optimizer-seed variation, not additional patients or population
confidence. Selecting seed43's +11.73pp would be a benchmark-selection effect:
diversity worsened the other two paired fits. Conversely, selecting original
seed17 would also be an unallowed favorable-checkpoint choice.

The diverse arm's observed seed range was narrower (60.49–61.73%, SD0.64pp)
than the original arm's (49.07–67.90%, SD10.38pp). Three seeds do not establish
reliable variance reduction or general robustness. The mean did not improve.

Both arm means exceed the historical checkpoint by **1.7490pp**. Because the
same gain occurs without the diversity intervention, it is not evidence that
diversity improved the original AI. The historical run used a different original
input ordering and development-loss checkpoint selection (epoch8 selected from
ten); these fixed retrainings used the final eighth epoch and matched class order.
Retraining/order/seed variation remain explanations for the historical contrast.

## Examination heterogeneity and short-run omissions

Cells are distinct runs reached, with the same exact K for every model.

| Examination / budget | Runs / K | Historical raw-bin | Uniform | Original seeds17/29/43 | Diverse seeds17/29/43 |
| --- | --- | ---: | ---: | --- | --- |
|31 / 10%|162 / 2,492|84|109|94 / 88 / 87|88 / 92 / 89|
|34 / 10%|9 / 1,087|6|8|7 / 7 / 4|6 / 6 / 6|
|31 / 25%|162 / 6,230|121|132|134 / 128 / 127|135 / 138 / 136|
|34 / 25%|9 / 2,717|7|7|7 / 8 / 7|7 / 7 / 7|

At10%, the seed-mean run counts are identical between arms **in each examination**:
269/3 on31 and6 on34. The zero macro effect is not cancellation between a positive
examination effect and a negative one. Every new CNN remains below deterministic
uniform on both examinations at this operating point.

| Examination / budget | Short runs available | Uniform reached | Original seeds17/29/43 | Diverse seeds17/29/43 |
| --- | ---: | ---: | --- | --- |
|31 / 10%|83|33|27 / 21 / 22|23 / 25 / 22|
|34 / 10%|4|4|2 / 2 / 1|1 / 1 / 1|
|31 / 25%|83|53|55 / 49 / 48|56 / 59 / 57|
|34 / 25%|4|2|2 / 3 / 2|2 / 2 / 2|

At10%, the diverse models reach24/26/23 of87 short runs, leaving63/61/64 omitted;
uniform reaches37 and omits50. Original controls reach29/23/23 and omit58/64/64.
Thus reduced fitting concentration did **not** solve the short-run deficit.
Complete medium/long/singleton counts and every fixed policy are retained in the
[aggregate](../experiments/matched-diversity-20261107/aggregate.json).

There are positive but limited secondary observations. On31@25%, diversity adds
1/10/9 runs versus its paired controls, a seed-mean +4.1152pp, with gains in short
runs. On34@25%, it ties two controls and loses one run to seed29, a mean−3.7037pp.
The macro25% diversity effect is only **+0.2058pp**, seed SD2.6250pp, range−2.4691
to+2.7778pp. Diverse mean80.9671% versus original80.7613%, historical76.2346% and
uniform79.6296%. All three diverse models nominally exceed uniform at25%, but this
secondary observation cannot replace the failed10% primary or demonstrate a
consistent diversity-specific advantage.

## Score information, geometry and image enrichment

| Budget | Arm, mean across seeds where applicable | Raw run recall | Raw − uniform (pp) | Raw − exact geometry (pp) |
| --- | --- | ---: | ---: | ---: |
|10%|Historical checkpoint|59.2593%|−18.8272|+7.9660|
|10%|Original-population fits|61.0082%|−17.0782|+9.7150|
|10%|Diverse-population fits|61.0082%|−17.0782|+9.7150|
|25%|Historical checkpoint|76.2346%|−3.3951|−0.6559|
|25%|Original-population fits|80.7613%|+1.1317|+3.8709|
|25%|Diverse-population fits|80.9671%|+1.3374|+4.0766|

Historical geometry/phase arrays were reused unchanged; exact expectations were
recomputed for every new vector. The diverse10% conditional geometry reference
ranges are [−4.94,+22.22], [−3.70,+23.46] and [−4.63,+22.53]pp across the fixed
seeds: all span zero. These are observed-minus-null reference ranges, not patient
confidence intervals. One34@10% diverse-seed29 bin had tied maxima; the independent
tie-aware permutation calculation did not change expected run coverage there.
No favorable phase or null comparison replaced deterministic uniform.

Diversity improves some **positive-image ranking**, which must not be confused
with the primary event endpoint. On31@10%, global ranking finds1,216/1,122/1,135
positive images, versus1,056/691/472 for paired controls, but reaches58/59/61 runs
versus68/57/46. Uniform reaches109 runs with343 positive images. On34, global
ranking remains unstable: diverse seeds find6/4/0 of49 positive images and4/4/0
runs at10%. A favorable image count or one source therefore cannot establish
reliable event preservation. No global selector was promoted.

Galar35/36 remain their completed historical comparisons, without new inference
or repeated old controls. Their earlier favorable raw-bin results do not establish
that these new checkpoints improve on those sources. No posthoc five-case pooled
confirmation is presented. The locked11–20 negative primary remains unchanged.

## Independent replay, durability and decision

The independent scalar implementation imports no production selector/evaluator.
It reproduced **42 examination/budget/model records,168 policy sets,84 exact null
expectations**, all run/image/stratum counts and every paired seed macro change.
See [independent proof](../experiments/matched-diversity-20261107/independent-check.json).
The pre-outcome private evidence bundle is13,632,536 bytes, SHA256
`272d82af5de328f027adf0121ce48e325fd5827cb4b04189154e93273fed3db5`;
all embedded file identities and the persistent readback were verified. The final
private package adds outcomes, queues, replay and receipts. Original fitting PNGs
remain in their verified private source packages; complete benchmark originals
remain durably restorable through the PR68 publisher-block receipts. Temporary
local preprocessing banks are reproducible conveniences, not new durable originals.
Exact private locations belong in the private handoff, not public Git.

Local full suite: **1,022 passed,1 skipped**. The frozen code's CI passed core
Python3.11–3.13, local-model/browser and privacy gates. Local browser installation
was unavailable because the download was truncated; CI independently completed
the browser/local-model test. Final results-head checks must pass before merge.
All medical pixels, individual source labels/scores, queues and weights remain
private. Public Git contains code, contracts and aggregate results only.

**Decision: no primary improvement and no model promotion.** This controlled
substitution refutes neither the general value of diverse medical data nor every
possible sampler; it shows that this fixed, class-matched broadening did not
increase mean10% event recall on these two inspected positive examinations.
It does not support repeating seeds until one wins, increasing architecture size,
or claiming patient-level generalization.

**Single next improvement hypothesis:** align fitting with short-event local
ranking rather than ordinary frame-level cross entropy. Before another fit,
use only permitted fitting labels/images to establish whether enough distinct
short-positive-run examples and genuine neighbouring negative images exist for
a matched within-bin ranking loss. Sparse512-image references alone do not supply
dense local neighbours; if that fitting gate fails, obtain/restore the specifically
bounded fitting examples before launching. Freeze that one objective comparison
against this retained control ensemble; do not tune against31/34 outcomes and
call the result independent. The present experiment supplies a measured control
and a rejected intervention, not an improved AI ready for use.
