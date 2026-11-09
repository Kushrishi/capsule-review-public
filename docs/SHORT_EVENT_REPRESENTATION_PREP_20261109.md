# Frozen MobileNet short-event representation comparison — implementation preparation (9 November 2026)

**Status: engineering preflight only. No real-image linear-head comparison has been fitted or evaluated, and no new model is promoted.** This preparatory code is not a frozen scientific run contract. A complete private prefit lock must be sealed after verifying the exact combined feature bank and before any real-model fit.

This work follows balanced short-event support PR72, exploratory seed ensembles PR73–74, and the source-safe redness comparator PR75. The outcome remains distinct Galar `blood=1` annotation-run preservation at **10% exact review count**, not clinical lesion detection or inferred reader time. The 69 local positive/negative source-neighbour pairs are a development gate only, not a substitute for exact-K full-source evaluation.

## Source and provenance gates

- Retained 10,123 × 576 float32 frozen features have a pinned SHA256 and original exam/frame identities; 4,232 match the current 4,412-image PR72 target bank.
- Exactly 180 additional embeddings are required (exams 23/25/29/30: 81/78/8/13). All 180 original PNGs have already been privately recovered and independently byte-length/SHA256/decoding checked. No publisher bytes or additional positives need acquiring.
- A private, source-hash-verified three-image historical canary package exists. Before extracting new features, verify the canary ZIP against the **separately retained private SHA256**, the exact official MobileNetV3-Small ImageNet V1 checkpoint SHA256, historical cached row identities, 160px full-field pixel tensors and numerical feature agreement (`rtol=atol=1e-4`). Failure stops extraction; do not substitute different weights or regenerate only a favorable subset.
- Preserve all 4,232 historical features byte-identically. Do not use the nine fully cached local pairs as a convenience cohort; all 69 run pairs are required. The 180 added features and 4,412-row assembled bank remain private.

## Future prefit lock and evaluation

`recover_frozen_mobilenet.py audit` rechecks the private source bank and missing originals. `extract` requires the official checkpoint and the independently pinned three-image canary ZIP. It records the feature-bank SHA and canary discrepancy but cannot run here without that exact checkpoint.

Once the verified 4,412 × 576 float32 feature file exists, create a **private immutable** `PREFIT_LOCKED` contract containing exactly the keys checked by `validate_prefit_lock`, including the source manifest SHA256, input feature SHA256, code SHA256s, official weights, private canary package/receipt hashes, fixed examinations, three seeds, 1,024 updates and ranking weight. Save/readback this lock **before** fitting. The CLI rejects missing/mismatched locks. No new model-training data or outcome inspection is authorized as part of this PR.

The planned comparison trains 24 fixed lightweight 576→2 linear heads (four entire-examination held-outs × seeds 17/29/43 × classification/ranking). The objectives share identical initialization, 32-image presentation schedule, weighted CE, AdamW and 1,024 updates; ranking adds `0.5 × softplus(z_negative − z_positive)` on true source neighbours. Fit-only feature scaling excludes the complete held-out examination. All checkpoints and score files are retained and hashes sealed before accessing heldout ordering results. A separate independent implementation reconstructs logits and compares all 24 cells to the PR72 CNN controls, including singleton regressions and seed/source consistency. No favorable seed/threshold/fold selection.

Future full-source benchmarking requires a separately frozen protocol and the unchanged **10% exact-K distinct annotation-run recall** comparison against deterministic uniform and geometry controls. Galar 11–20 is a completed, inspected locked test; authors' 61–80 remain unopened. No medical image, individual label, embedding, prediction, or checkpoint is committed to Git/CI.

## Reproducibility checks in this preparatory PR

The production source parser, source schedule, source identity and canary validator are accompanied by **19 synthetic-only unit tests**; the separate private handoff also executed a two-arm, 1,024-update synthetic training smoke test. Synthetic success establishes engineering behavior only, not real clinical or image-level accuracy. The tests require the optional ML dependencies and skip on the light core CI matrix but run under the repository's `local-model` job. The complete public-source and browser/privacy CI matrix must pass before merging this PR.
