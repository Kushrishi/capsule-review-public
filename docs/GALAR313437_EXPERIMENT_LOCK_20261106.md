# Galar 31/34/37 complete-source development experiment — lock A2

Frozen November 6, 2026 before new source-block acquisition and CNN outcomes. Base: bc26bcf0b2b6955184f6beaf4f39a2765d7c25e4 (merged PR67). This is a resource-defined, examination-separated development replication, not newly blinded, patient-independent, cross-device or clinical validation. The labels and selection rationale were previously inspected. No substitution if acquisition fails; no external outreach.

## Versioned amendments and admission

A2 supersedes only the PR67 operator-selected 8 GiB new-source cap for this exact cohort: authorize **14,065,827,988 new compressed bytes** (13.10 GiB), no retries beyond missing verified ranges without a separately logged receipt. The latest user instruction authorizes this increase. It also explicitly authorizes examination-level development despite unresolved patient-repeat/site/device provenance; it does not waive the gates for patient-independent or domain-diversity claims. No other frozen historical result is revised.

Official Figshare Galar v2 (10.25452/figshare.plus.25304616.v2), CC BY4.0, file44755700, 69,219,317,963 bytes; publisher full-file MD5 3bd4f9c9132e32d1a15d1ead5d96d0e2 remains unverified because the whole archive will never be fetched. Validate the current catalog against the existing pinned source profile. Verify retained signature/next-header/encoded-index SHA256 identities, 7z CRCs, requested HTTP206 ranges, source block SHA256, original PNG CRC/decoding/SHA256, full membership/native grids and corrected-label archive SHA256. Only31/34/37 outcome members may be opened; no11–20 or61–80 payloads.

| Exam | PNGs | Original PNG bytes | Required blocks | K10 | K25 |
| --- | ---: | ---: | --- | ---: | ---: |
|31|24,919|8,181,689,551|0,1|2,492|6,230|
|34|10,867|3,223,269,590|4,5|1,087|2,717|
|37|18,125|5,065,721,113|6,7|1,813|4,531|

Native published stride is five. Complete published exports are not continuous full device exposures. Galar37 has zero annotated blood runs, not a normal diagnosis; positive recall is undefined. The original model fitted examinations1–8;9–10 and21/23/25/27/29/30 were prior development. New IDs do not overlap those examination IDs. Patient-repeat overlap and authenticated site/device assignments remain unresolved; image duplicate checks cannot establish patient identity.

| New block | Inclusive byte range | Compressed bytes |
| --- | --- | ---: |
|0|32–3,488,427,782|3,488,427,751|
|1|3,488,427,783–7,094,259,391|3,605,831,609|
|4|14,292,057,434–17,802,009,148|3,509,951,715|
|7|24,686,214,119–28,147,831,031|3,461,616,913|

Reuse retained blocks5/6 (6,884,204,970 bytes), verifying original-byte identity when restored; do not reacquire them from the publisher. No full-archive fallback. Sparse logical archive length does not represent disk consumption. Only target PNGs are extracted; neighbouring partial examinations are not benchmark cases.

## Storage and technical gates

Observed local free capacity before dependency installation:57,496,600,576 bytes. New PNGs total16,470,680,254 bytes. Maximum simultaneous source blocks20,950,032,958 bytes; all stored-PNG ZIPs approximately16.49GB; largest temporary extracted examination8.182GB. Stage one examination at a time and remove only reproducible temporary extraction after its private ZIP has been verified. Budget2GB for dependencies, manifests, scores, upload/readback scratch plus3GB reserve: peak new allocation approximately50.7GB, below observed free capacity. Recheck capacity before every extraction/transfer, never upload sparse69GB files. Use bounded transport chunks with remote readback before discard.

Authenticated Drive storage UI reports113.1GB used of400GB, **286.9GB available** on this date. Reserve at least40GB for new compressed14.066GB + original16.471GB + manifests/queues/checkpoint/audits/upload overhead, including readback. Existing retained5/6 are not duplicated remotely. Verify private parent/no-sharing and actual remote bytes/hash, not upload acknowledgments alone. Validate executable extraction and the unchanged checkpoint/runtime before substantial image transfer. A failed technical/storage/rights gate blocks acquisition without replacing cases.

## Fixed computation and stage separation

Original capsule-cnn-v1 checkpoint SHA256 f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3, original private model package SHA2565e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc. CPU eval/inference mode, original EXIF transpose/RGB, ImageOps.pad96x96 bilinear black padding, float32/255, blood-class softmax; batch32, bounded64, two CPU threads. No training, calibration, threshold/model/policy sweep. Store library/runtime versions. The original checkpoint loader verifies exact tensor keys/shapes/finiteness with weights_only loading.

Freeze original unchanged uniform/global-score/score-diverse/raw-score-bin policies and window3 temporal-max score-bin using repository implementations at this lock. ExactK=max(1,floor((N*percent+50)/100)), capped atN. Preserve original5/10/25/50/100 queues if provided by existing freeze_queues; only10/25 are new analytic endpoints. Earliest-max tie rule and original uniform ordering unchanged. Freeze PNG hash/source manifests and scores/queues in exclusive-create private artifacts. Durably readback-verify all three original packages, checkpoint and all prediction/queue snapshots **before** separate outcome audit. Record seals/timestamps/remote hashes. Already inspected labels mean computational separation only, not new blinding.

## Outcomes and independent replay

Joint primary10%: equal-positive-examination mean (31 and34, each1/2) raw-bin distinct-run recall minus (a) geometry-matched randomized exact expectation and (b) deterministic uniform. Report both, all per-exam results and heterogeneity.37 remains in workload/source/score accounting, excluded from undefined positive recall denominators. A run is maximal consecutive explicitly blood-positive published positions at native+5; split at gaps, unknown labels fail. No interpretation as distinct lesions.

Reuse PR66 unchanged:10,000 PCG64 within-bin score-permutation controls, earliest tied maximum distribution; SeedSequence([20261106,exam,percent,1]); exact bin/run expectations plus coupled geometry-only controls. Secondary1,000 fixed16-block nonidentity circular shifts with stream2 and100 fixed phase offsets.25% secondary. Report positive-image retrieval,1–5/6–25/26+ strata, singleton/short omissions, ranking and temporal failures, spacing/source coverage. Retain private repetition arrays. Report conditional95% randomization ranges, Monte Carlo SE, descriptive examination contrasts and two-exam resampling support; do not present these as population confidence from independent patients.

A separate implementation must recompute all five queues and principal counts/null expectations/repetition summaries from sealed scores/labels, without importing production selectors or geometry code. It must reproduce source membership, workload, label joins and run strata. Replay the new cases only;35/36 are descriptive comparisons from existing frozen aggregates, with no new inference or repeated old controls. Public results contain aggregate counts only; private originals/source IDs/annotations/scores/queues/weights remain private. No model promotion or clinical/reader-time claim.

## Decision after audit

Preserve negative/inconclusive findings. Attribute observed differences separately to discrimination, chronology, short-run support, source heterogeneity and reference limitations. Choose one next controlled improvement hypothesis from these results, without training or fitting to31/34/37 in this task. Any later use of these inspected outcomes for development precludes claiming them as independent confirmation.
