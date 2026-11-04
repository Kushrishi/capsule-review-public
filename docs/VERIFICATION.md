# Verification

## Public software checks — November 3, 2026

The public repository has passing GitHub Actions on the previously verified `main`
commit `93535ccb9a32f66ec39d6eff4ad5e84fc0232ba1`:

| Scope | Evidence | Result |
| --- | --- | --- |
| Python 3.11, 3.12 and 3.13 | [Tests run](https://github.com/Kushrishi/capsule-review-public/actions/runs/41731955994) | Passed |
| Local-model and Chromium browser smoke | Same Tests run | Passed |
| Source privacy file-format guard | [Privacy run](https://github.com/Kushrishi/capsule-review-public/actions/runs/41731956116) | Passed |

These are **software regression checks**. They do not independently verify medical
model accuracy, unseen Galar examinations, original patient identities, clinical
sensitivity or reduced reviewer time. The public actions load generated data only.
No medical images, private score records or trained weights are bundled with this
repository. Check the latest `main` workflow runs before declaring later commits
verified.

## Historical development verification — November 1–2, 2026

The original November 1 measurements below are retained with their original
run context. They are **not the current public CI test totals**.

| Check | Actual result |
|---|---|
| Python suite after the mobile CSS fix | 95 passed, one upstream TestClient deprecation warning |
| Existing browser workflow preflight | 15 checks passed over actual localhost HTTP |
| Real Galar model/viewer workflow | 12 checks passed; 512 predictions saved and retained across browser/server restart |
| Real data acquisition | Full official MD5 plus all 5,120 selected image CRC/PNG/membership checks passed |
| Corrected label identity | All ten selected CSVs are byte-identical to the checksum-verified corrected source ZIP |
| Split integrity | No exact decoded-image overlap across fitting/development; original frame IDs retained |
| Metrics and model identity | 27 independent arithmetic/identity checks passed |
| Actual mobile layout | 320, 390, 768 and 1440-pixel widths fit after the long-attribution CSS repair |

The browser runs actual model inference, preserves source annotations and reviewer entries separately, downloads the original six-frame illustrated export, and restores state after both server and browser restart. The screenshots use a predetermined midpoint, not a favorable prediction chosen after viewing results. See [REAL_DATA.md](REAL_DATA.md).

The app's strict CSP remains unchanged. Playwright 1.56 had a CSP incompatibility with its page-world `wait_for_function` implementation; the browser smoke test now polls the same predicates using the Playwright `evaluate` API without changing application CSP. The real-data verifier and its original adapter are in the companion package's `real-data-tools` folder. The older synthetic preflight screenshots are historical software-test evidence, not real-data results.

Runtime: Python 3.12.14, Linux CPU, PyTorch 2.15.0+cpu, Playwright 1.56.0, Chromium 141.0.7390.37. No Windows, macOS, CUDA or MPS run was performed. The numbers above describe the recorded local runs, not remote GitHub Actions. Remote CI results must be checked separately; no deployment or clinical validation is claimed. Passing software checks does not establish clinical validity.

The companion package preserves the exact manifests, history, metrics, weights, environment, source hashes, viewer verification and screenshots. The core command remains `python -m pytest -q`; the original browser runner is `python tests/browser_smoke.py --with-test-model`, with the included compatibility adapter available for the observed CSP/wait interaction.

## Historical sparse-image review-budget audit — November 1, 2026 follow-up

An additional post-hoc analysis was performed after the first blood-image model had completed. `scripts/review_budget_audit.py` verifies the SHA-256 of the corrected Galar annotation ZIP, the separate used CSVs, the full frozen 5,120-record manifest, the 1,024 saved development score identities, and the original 5%/10%/25% frame-budget metrics. The reference run also rehashed all 1,024 original PNG file bytes. Its aggregate counts and methodological limitations are recorded in [REVIEW_BUDGET_AUDIT.md](REVIEW_BUDGET_AUDIT.md).

The updated **Python suite passed 134 tests locally** in the current environment. The existing browser/model regression run passed **15 checks** with Playwright using the system Chromium executable and the `--transport in-process` mode; this is not an HTTP/localhost browser-origin test. No application UI behavior was changed in this follow-up. The previous browser/server persistence checks remain historical evidence, not new measurements.

The *source images are sparse*, with large source-frame gaps; consequently the new audit does **not** execute dense temporal inference or report clinical lesion sensitivity or reviewer-time savings. The post-hoc model-versus-chronological-bin comparison was not a blinded confirmatory test.

## Bounded remote ZIP source access — November 1, 2026 follow-up

`tests/test_ranged_zip.py` adds **21 local HTTP-fixture tests** (real `ThreadingHTTPServer` requests) for byte-range-only ZIP index reads, selected-member extraction, CRC/SHA-256, URL/transfer limits, no-Range `200` rejection before reading its response body, invalid `Content-Range`, remote-size changes, zip path traversal/symlink rejection, preexisting outputs, basename collisions, duplicate ZIP paths, multi-member fail-closed staging, corrupted payload rejection, decompression-bomb rejection, and unsafe seeks. The complete local Python suite now passes **155 tests** on Python 3.13.5. No real DataverseNO ZIP or CAPTIV8 video was accessed: outbound DNS is unavailable in this execution environment. Publisher HTTP Range support remains unverified. Tests verify software behavior, **not** pathology performance or actual dataset access. See [DENSE_SEQUENCE_DATA_GATE.md](DENSE_SEQUENCE_DATA_GATE.md).

## Verified sparse-source spacing — November 1, 2026

`scripts/sequence_readiness.py` was run against the **original frozen Galar blood-pilot manifest** and all **5,120 actual PNG image files**. Every original image SHA-256 matched (1,598,002,230 total verified bytes). Of 5,110 within-examination adjacent saved-sample pairs, no source-frame index gap was at most 5; the smallest gap was 40, median 70 and maximum 425. This independently confirms the saved samples **cannot** support a dense-video temporal test. See [DENSE_SEQUENCE_DATA_GATE.md](DENSE_SEQUENCE_DATA_GATE.md).

The new tool has ten focused tests (including file-identity tampering, missing frames, split overlap, duplicate identities and reserved-exam restrictions). The complete local Python suite passed **165 tests**. No additional medical data were downloaded and no models were trained. This does not verify any publisher's live Range support or justify clinical interval-sensitivity claims.

## Prespecified complete-study replication — 2026-11-02 UTC

The archived s288 pilot was frozen before the uninspected s280/s284 studies were selected by file size. A GitHub Actions runner then acquired the official nested ZIP members **only** via verified HTTP `206` byte-range transfers, checked their CRC32 and internal ZIP integrity, and executed the **unchanged** `scripts/compare_sequence_selection.py` on all 4,273 s280 and 5,117 s284 original published frames. The source SHA-256 values, immutable selection protocol digest, cumulative 512 MiB budget accounting, and all actual per-study/budget/method results are in `experiments/rhode-replication/`.

The aggregate artifact ZIP passed SHA-256/ZIP CRC checks after download, and its source receipt SHA-256 values matched both result files. The reproducible three-study summary regenerated exactly from the original frozen s288 result plus s280/s284. The expanded **Python suite passed 191 tests locally**. The study-level result is limited to anatomical boundaries and index coverage; it is **not** clinical diagnostic verification, independent-patient evaluation, or human reading-time evidence. The raw new image archives were not preserved, so re-execution of their pixel computations needs a fresh authorized data transfer. See [RHODE_REPLICATION_RESULTS.md](RHODE_REPLICATION_RESULTS.md).

## Fixed pathology-model domain adaptation — November 2, 2026

The immutable pre-fit `docs/DOMAIN_ADAPTATION_SPEC.json` fixed examination-held-out folds 1 and 7, final fit exams 1–8, three training epochs, full-field image preprocessing, and no checkpoint selection on previously inspected exams 9–10. All 5,120 original Galar sparse source images were revalidated against the frozen manifest before each run. Two held-out fitting-exam models and one final fit generated 2,048 saved prediction records; an independent real-image/checkpoint replay reproduced every value exactly (maximum absolute probability deviation 0.0 in the same CPU environment). The preexisting official ImageNet weights, source manifests and feature-cache checksums were verified. Private original frames and checkpoint bytes were **not** committed. The actual local viewer imported 512 extra research suggestions to make three separate 512-frame model runs while preserving existing dataset labels, 1,024 previous model predictions and reviewer notes; real Playwright rendering used an intercepted in-process FastAPI client, not a public deployment. The old compact blood CNN remains the better historical development baseline. Separate methodology/results in [DOMAIN_ADAPTATION_RESULTS.md](DOMAIN_ADAPTATION_RESULTS.md). The small number of positive-examination groups, different ImageNet-crop preprocessing, and reused 9–10 cases preclude independent clinical claims.
