# Pre-analysis design — matched frozen pretrained representation versus the compact blood CNN

**Locked 2026-11-04 before fitting this particular probe or inspecting its evaluation scores.**

**Status:** exploratory development on previously examined Galar cases; not new holdout validation, not a clinical model upgrade. Source medical images, per-frame labels, feature vectors and predictions stay private. The completed Galar 11–20 source-complete negative 10% primary remains unchanged; the original authors' Galar 61–80 remain unopened.

## Scientific question

Does an ImageNet-pretrained, **frozen MobileNetV3-Small** 576-dimensional global-average-pooled representation with a training-fold-only L2 logistic blood classifier outperform the original compact CNN and its two previous continuation experiments when **all** use the same **examination-exclusive** training/evaluation populations?

This is a deliberately narrow development comparison, not an architecture search or a claim that MobileNetV3 is novel. Earlier separate MobileNetV3 examination-CV results were reported on **different folds**. Those cannot be used as a substitute for the present matched training comparison.

## Source and identity lock

Reuse the private, independently source-hash-verified MobileNetV3-Small feature cache from the previous, frozen November 2 experiment; no new image acquisition or pixel decoding. Exact bank: **10,123 × 576 float32** elements, SHA-256 `611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae`; matching private metadata SHA-256 `78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2`. The archived provenance specifies ImageNet MobileNetV3-Small weights SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`, original-PNG verification and **160×160 full-field bicubic resize without center crop**. Feature extraction is already completed; **no image pixels or backbone weight files enter the public repo**.

Select *only* the original source-chronology reference rows (`reference == 1`) from fitting Galar 1–8 and development Galar 23, 25, 27. Exactly **512 reference images per examination**, **5,632 total**, with **239 positives** among the 4,096 original fitting images and 4, 14, 26 positive reference images in 23/25/27. Other 14-examination feature-cache rows are **excluded**. Reject unexpected counts, nonfinite features, altered bank hash or changed labels. No source frame selection by observed outcomes.

## Fixed model and three folds

For each excluded examination E in **[23, 25, 27]**, train on the original fitting examination IDs 1–8 plus the other **two** development examinations among [23,25,27]. Exactly **5,120** reference images per fold; held-out E has exactly 512 and is **never** used for training, normalization, threshold or hyperparameter choice. Both source examinations 11–20 and 61–80 are forbidden.

Train a single **frozen-backbone linear probe per fold**:
- `StandardScaler(with_mean=True, with_std=True)` fit only on the 5,120 training embeddings, applied to the held-out 512.
- `sklearn.linear_model.LogisticRegression(C=0.1, class_weight='balanced', solver='lbfgs', max_iter=300, tol=1e-6, fit_intercept=True, random_state=37)` as in the earlier November 2 MobileNetV3 study; **no C grid search**, threshold selection, epoch tuning or augmentation.
- The pretrained backbone remains frozen and is not retrained. Save fitted coefficients, scalers, per-frame scores and private source identities only to a private, checksum-audited archive.
- If convergence warns, preserve that warning and do **not** silently alter `max_iter`.

## Fixed metrics and reporting

For every E and all methods, calculate ROC-AUC, average precision and **positive reference-image hits at exact K = 51, 128 and 256** of the 512 uniformly sampled reference positions. Ranking ties break by earliest reference position. Report equal-examination means, each case's direction versus the original compact CNN and the earlier matched no-augmentation/photometric continuations, and retain negative transfer. The three earlier CNN arms come unchanged from the completed November 4 examination-excluded aggregate. No attempt to infer full-video source-annotation-run recall from 512 sparse frames.

**No model promotion** regardless of apparent win, because these cases were previously examined and independent patient grouping/clinical labels are unverified. A favorable result would justify only an independently planned, new cohort or training-only follow-up. The 10% Galar 11–20 primary remains negative.

## Privacy and integrity

Do not publish medical pixels, per-image labels, source frame indexes, individual predictions, feature bank, fitted coefficients, checkpoint weights, private package locations, or private receipts. Publish only non-identifying per-examination aggregate results and code/tests that run on synthetic data. Verify the saved original feature cache SHA and private metadata SHA before fitting; record fold training/test identities and hashes in the **private** audit. No full-source medical archive reacquisition.

**Commit of this design must precede running the new three-fold fits.**