# Capsule Review — frozen-representation transfer and persistent-error diagnostic

**Date:** November 9, 2026 in Montréal (November 10, 2026 UTC)  
**Status:** Complete, retrospective development-only analysis. **No new training, source acquisition, protected evaluation, parameter search or model promotion.**  
**Parent evidence:** [PR #77 frozen-representation study](FROZEN_REPRESENTATION_SHORT_EVENT_RESULTS_20261109.md) and the already-sealed PR #72 expanded balanced-support CNN predictions.

## Scientific question and scope

The frozen ImageNet MobileNetV3-Small features plus matched linear heads performed worse than the compact CNN at held-out genuine short-run pair ordering. Two narrower questions are answerable **without retraining or reopening source datasets**: (1) do the fitted heads fail to order their **own training** pairs, or mainly fail to transfer that ordering to excluded examinations; (2) is the poor result seed/objective instability or reproducibly wrong ordering?

This report replays precisely the **69 previously inspected, source-verified positive–negative short-run comparisons** from Galar 23 (23 runs), 25 (20), 29 (11), and 30 (15), including **21 singleton runs**. One source run, one fixed positive–negative boundary pair. Each of the four exclusion folds trained on the other three examinations. For each architecture and objective, the same three historical seeds 17, 29, 43 are evaluated. In-sample ordering is calculated using the existing checkpoint's **saved logits on the training-examination pair endpoints**, not from new image inference or optimization. Held-out ordering is the original unchanged comparison. The pair population, checkpoint identities, and original source membership were not altered.

The historical compact CNN and the frozen MobileNet model **do not isolate encoder architecture causally**: input processing differs (96px padded compact CNN versus 160px full-field MobileNet), while head capacity and pretrained/fine-tuned status also differ. Examination IDs are **not verified patient IDs**.

## Integrity and reconstruction

The audit verifies the SHA of the original 69-run source manifest against the prefit lock, the **4,412×576** private feature bank against its frozen SHA, exact prefit-lock equality, and all **24 MobileNet checkpoint/score SHA pairs**, plus all **24 PR #72 CNN checkpoint/score SHA pairs**. Every scored pair has an explicit original blood-positive and native-source blood-negative endpoint belonging to the same examination. Reconstructed held-out equal-examination/seed means exactly match published PR #72 and #77 results. A separate implementation independently replayed **48 matched architecture/objective/seed/examination cells** and reproduced the train/heldout aggregates, seed-consensus and matched objective-decision counts. The test suite adds nine **synthetic-only** tests.

## Result 1 — in-sample fitting is not the limiting observed behaviour

| Existing model/objective | Training-pair ordering (in sample, exposure-weighted) | Held-out ordering (equal-exam/seed macro) | Held-out ordering (run-weighted) |
| --- | ---: | ---: | ---: |
| Compact CNN classification | **97.10%** | **63.77%** | 63.29% |
| Compact CNN local ranking | **99.84%** | **72.29%** | 70.53% |
| Frozen MobileNet classification | **100.00%** | **50.94%** | 50.72% |
| Frozen MobileNet local ranking | **100.00%** | **49.08%** | 49.76% |

The models saw each fitting pair repeatedly over the prescribed 1,024-update schedule. The training percentages are **not** out-of-sample estimates. There are 621 in-sample model–run–fold–seed observations and 207 held-out model–run–seed observations **per architecture/objective**, but neither is 621 or 207 independent patients; only **69 distinct development runs** are involved, and the 12 models share data. Training and held-out percentages also use different weighting conventions in the first two numeric columns, so do **not** interpret their subtraction as an unbiased population generalization gap.

The direct descriptive finding is that frozen MobileNet linear heads can almost perfectly fit this small training-pair problem but transfer to excluded examinations near chance. The compact CNN also transfers imperfectly; its matched ranking arm nonetheless orders substantially more held-out pairs correctly.

## Result 2 — errors remain wrong across seeds

| Existing model/objective | All 3 seeds correct | All 3 seeds wrong | Seeds disagree |
| --- | ---: | ---: | ---: |
| Compact CNN classification | 29/69 | 9/69 | 31/69 |
| Compact CNN local ranking | 32/69 | 6/69 | 31/69 |
| Frozen MobileNet classification | 30/69 | **29/69** | 10/69 |
| Frozen MobileNet local ranking | 29/69 | **31/69** | 9/69 |

Among the **21 singleton runs**, MobileNet misorders **10** under classification and **11** under ranking in **every** fixed seed, compared with **four** for each CNN objective. These are overlapping development examples, not independent medical events or safety estimates.

The burden is heterogeneous. In Galar 23, MobileNet has **11/23** all-seed wrong pairs under either objective; in Galar 30 it has **8/15** under either objective. In Galar 30, the held-out decision for **all 15 runs** is unchanged across seeds for both MobileNet objectives. This stability is not evidence of robustness when the stable decisions are frequently wrong.

## Result 3 — local-ranking objective changes few MobileNet decisions

At matched examination, seed and run, the frozen MobileNet classification and ranking heads agree on **203/207** held-out pair-ordering decisions (**98.07%**). The ranking objective corrects just **one** classification miss and introduces **three** losses in those matched cells. By contrast, the original compact CNN objectives agree on **154/207** cells (**74.40%**), with 34 ranking-only correct and 19 classification-only correct. All 207 cells in each architecture reuse the same 69 distinct development pairs across three seeds: do not treat them as independent draws or a prospective superiority test.

The ranking objective therefore provides **little observed decision-level change** atop this frozen representation under the original fixed optimization budget. This does not establish that no loss function could improve the encoder, that feature distance causes the failures, or that a different preprocessing resolution would behave similarly.

## Interpretation and decision

**Observed:** 100% in-sample MobileNet pair ordering, near-chance examination-held-out ordering, many all-seed persistent misses (especially singleton examples), and almost no binary-ordering change after adding the local ranking term. These findings make another random seed, mean-logit ensemble, or minor ranking-loss tweak on this same inspected four-examination cohort a poor next scientific investment.

**Not identified:** whether the bottleneck is learned feature transfer, image-domain/device variation, unknown patient relatedness, frozen-head capacity, source-adjacent annotation noise, input preprocessing/field-of-view, or an interaction. The CNN/MobileNet architectures and preprocessing differ, so no causal attribution to ImageNet pretraining is supported. There are no verified patient-group identifiers or new clinician adjudications, and this is not a lesion-level or clinical-efficacy comparison.

**Decision:** Keep the negative PR #77 advancement decision unchanged. **No model promotion and no new full-source 10% exact-K evaluation.** Prioritize authentic independent patient/examination grouping and diverse source support, then formulate a genuinely new, preregistered **domain-relevant** representation comparison if those gates pass. Preserve the already locked 11–20 result, leave reserved 61–80 unopened, and do not re-run same-cohort seed/architecture sweeps.

## Reproduction and confidentiality

`scripts/diagnose_representation_transfer.py` consumes three **private** previously SHA-sealed archives (the PR72 final evidence, PR77 prefit feature/contract bank and PR77 prediction archive). `scripts/independent_representation_transfer_audit.py` replays the same summary independently. Their public outputs are non-identifying counts, percentages, and file-level receipts only. The original PNGs, per-run source indices, labels, logits, weight bytes and individual feature vectors are **never committed to GitHub or run in public CI**.

Numerical differences across seeds, runs and examinations are descriptive only; no patient-level confidence interval, significance test, new held-out population, sensitivity/clinical claim, or posthoc candidate selection is reported.
