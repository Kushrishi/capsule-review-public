# Model-assisted research review queue — exact-K, transparent, local

**November 3, 2026 | Working product feature, not a clinically validated AI model**

**Evidence update — November 4:** the [locked Galar 11–20 study](GALAR_UNSEEN_11_20_RESULTS.md) is complete on all 163,161 eligible source images. At equal 10% workload, score-bin's mean examination-level annotation-run recall was 1.27 percentage points below uniform. The default remains a transparent coverage heuristic, without a demonstrated primary pathology-retrieval advantage. The November 3 evidence below is retained as history; authors' 61–80 remain unopened.

## What changed

Before this feature, Capsule Review could store and display model suggestions on one image at a time, but could not turn a full image-sequence score stream into an inspectable **review queue**. A user can now open an imported examination, import predictions or run an installed local model, then build a navigable list of proposed images. The queue uses the **selected model run and a single score label**—no reference labels, reviewer notes or model comparisons are secretly mixed into the ranking.

**Complete local anatomy score vectors:** the previous local model stored only the single winning anatomy label on each imported frame. It now stores **one explicit softmax score for every supported anatomy class on every image**, allowing a class-specific queue without treating an unreported label as negative. Earlier local prediction runs remain unchanged; re-run the installed local model if an older run lacks a complete class stream. All scores remain uncalibrated, and the model is still **anatomy classification, not pathology detection**.

This is a *navigation aid* for research. The local application still does not ship a trained pathology detector. Installed anatomy models produce research region-classification suggestions, **not lesion detection**. Imported research blood-classification scores from experimental checkpoints are **uncalibrated**, not lesion probabilities, and cannot be presented as verified medical findings. All original imported frames stay accessible through normal navigation.

## Exact-K methods and user control

The user enters any integer **K between 1 and N**, where N is the number of imported frames. The default is **all N**, deliberately avoiding a silent 10% threshold. Results can be generated at K=1, at 5%, at 10%, at 25%, at 100%, or at any other number. The queue shows the selected frame positions and their original numeric model scores; it paginates at 20 frames without dropping the rest. No model run may be queued unless that specific label has **one imported prediction for every frame**; missing predictions are never silently classified as negative.

The **four original**, previously evaluated policies remain unchanged (and the frozen Galar results still refer only to them):

| Policy | How it uses the model | Interpretation |
| --- | --- | --- |
| **Highest scores** | Sort all images by score descending; tie-break by imported position ascending | High-scoring images may cluster in one run |
| **Score + ordinal separation** | Score-sort, greedily retain a frame and suppress other imported positions at distance at most floor(N/(2K)); backfill by score if required | Heuristic to reduce redundant *imported-position* neighbors; not a trained/optimal algorithm |
| **Top score per chronological bin** | Divide N imported positions into K nonempty consecutive bins and take each bin's highest-scoring image | Ensures one selected image in each equal-size imported-position segment |
| **Uniform baseline** | Select exact deterministic midpoint positions in K source-chronological bins | A label-blind, model-free reference |

**Experimental candidate added November 4:** the optional fifth policy, `score_guarded`, starts from deterministic uniform midpoints and makes two fixed coordinate-improvement sweeps. Each anchor can move toward a higher score only inside its own anchor-defined chronological cell, and only if the global maximum contiguous **omitted imported-position span** remains no larger than uniform's original worst span. Its selected-score sum is therefore at least uniform's, but **the guarantee is solely technical**: different frames are selected and important events may be missed. It is **not** part of the locked Galar 11–20 comparison, has not been evaluated on its outcomes, and cannot be called an improved medical model or validated review policy. See the [algorithm and proof conditions](EXPERIMENTAL_GAP_GUARDED_SELECTION.md).

All five current options retain **exactly K** imported images, with no duplicate positions. For fair comparison, the queue reports **ordinal nearest-selected-image coverage**, including maximum distance, alongside the same-K uniform control. These numbers are distances in the imported sequence; they are **not original capture times, clinically adjudicated lesions or pathology sensitivity**. Uniform and per-bin selections are recalculated at each K and need not be nested. Diversity suppression also changes as K changes; do not treat separately computed results as cumulative retrieval curves.

## Preserving the human workflow

Opening a suggested queue image uses the existing, safe frame navigation: an unsaved draft is saved first, and the viewer loads the selected frame. It **never automatically bookmarks the image, creates intervals, modifies notes, changes reference annotations, records a diagnosis or hides nonselected images**. Human saved-frame review and image-export evidence are still separate from predictions, unchanged by queue use. A "score" cannot be promoted to a human label without an explicit human action already present in the original viewer.

Scores are pulled from the local SQLite prediction run specified by the user; the algorithm reads only (position, score) rows for the chosen label, not the database's reference labels or clinical records. Incomplete labels, wrong-exam run identities, unsupported methods, impossible requested counts, duplicate positions and invalid scores are rejected. Runs and score lists remain localhost-only under the app's existing origin/host restrictions.

## Scale and technical limits

The same pre-existing prediction-import envelope supports at most 200,000 prediction rows. The queue uses score sorting O(N log N), a linear-time ordinal-diversity blocking pass, and a paged 20-image browser list. An exact-K full selection is computed server-side per request; the UI is not limited to a 10% or 250-image shortlist. The 250-image bound on the **separate illustrated review ZIP** is an export-size safety guard, **not a limitation on the queue**. The other optional full-span ZIP remains a different evidence-export path and does not auto-export queue-selected images.

No network inference, cloud upload, automatic clinical report or diagnostic threshold is involved. A completely flat score stream is explicitly flagged as uninformative.

## Real original-score retrospective check

On November 3 the same fixed selection methods were compared on **3,072** earlier source-verified original-CNN reference scores from six previously inspected Galar cases. The comparison ran at six equal-K workloads and a second implementation independently rechecked all **144** case–budget–policy results. At K=51, top score retained 95 explicit positive reference images, versus 27 uniform; but it left an average worst imported-ordinal gap of **186.8**, while uniform's was **5**. Several sparse positive examinations remain severe failures. The UI therefore defaults to **one highest-score image per chronology bin** for a transparent imported-position coverage guard, not because it is a confirmed pathology winner. **All real-image conclusions are exploratory, image-level, and not clinical.** See [full honest experiment record](GALAR_PRIORITY_SCORE_REPLAY.md).

## What this does NOT validate

This feature provides **working model-guided navigation** and a reproducible, fixed policy ladder—not evidence that any current model detects important medical intervals better than uniform at a given workload. Real Galar score experiments must be evaluated separately, using exact source-image identity, examination-separated cohorts, full original-source annotation-run membership, and nonidentifying public summaries. Sampled blood-positive **images** are not source annotation runs, and source annotation runs are not clinically adjudicated lesions.

The same exact corrected Galar archive must be verified before claiming additional full-source run metrics. Do not open reserved exams 11–20 or the original authors' 61–80 for model tuning or convenience. No automatic model promotion should follow a favorable retrospective workload.

## Verification

Synthetic-only CI exercises deterministic exact-K selection for all four original policies and the exploratory bounded-gap candidate, invalid score/identity fail-closed behavior, pagination, incomplete-label refusal, no reference-label reads, and reviewer-note immutability through actual localhost API requests. The browser/local-model smoke test **trains and executes** an original geometric software-test model, builds an exact-K review queue, opens a prioritized image without changing saved human notes, and compares with uniform. Private original images, per-frame annotations, saved model predictions and research workspaces remain outside the public repository.

## Review the omitted positions across all policies

**Engineering safeguard (November 3; expanded November 4):** the local viewer compares all four original policies and the optional experimental candidate
current policies at the *same user-selected K* via the read-only
`/api/studies/{study_id}/priority-comparison` endpoint. For each policy it
reports the maximum and 95th-percentile nearest-selected *imported position*
distance, plus the largest consecutive **unselected imported-position span**.
The viewer can open the middle of that skipped span without selecting,
annotating, bookmarking, or exporting it. If the user chooses all imported
images (K=N), every policy reports no omission span. Missing or incomplete
model-label streams are rejected just as they are for the review queue.

This is **transparency for human reviewers**, not risk estimation or a
content-based diagnosis. No original-video timestamp, physician label,
clinical event, or continuous footage is inferred from imported ordinals.
The comparison does not consult source annotations, ground-truth labels,
patient outcomes or reviewer notes. It is intentionally conservative:
a technically small ordinal gap does **not** imply clinical safety when
the originally imported sequence is sparse. The exploratory Galar 10 result
([retrospective evidence-run audit](GALAR10_FOUR_POLICY_SOURCE_RUN_RESULTS.md))
illustrates why reviewers should be able to see and inspect gaps, but this
feature is not tuned or clinically promoted from those already examined cases.

