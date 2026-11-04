# Galar 11–20 amendment A1 — outcome-concealed eligibility verification

**2026-11-04; specified before any corrected 11–20 CSV member is opened in
this phase.** The original November 3 JSON lock remains unchanged. Preserve
this amendment and its implementation in public Git before private execution;
record that commit and both document/code SHA-256 values in the private receipt.

## Purpose and scientific boundary

The image index contains a single internal +5-grid gap in examination 15.
A filename grid is not the eligible population. The original lock defines
eligibility as explicit binary `blood` annotations, excluding blanks as unknown.
Determine eligibility without revealing whether any eligible annotation is
positive. The original publication describes unique-frame extraction and a
CSV `frame` column referencing source images; it does not establish that every
inferred grid position has an image or a binary label:
https://doi.org/10.1038/s41597-025-05112-7.

## Permitted access and isolation

Only the checksum-pinned corrected ZIP (file 60383963, SHA-256
`2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f`)
may be used. Read only explicitly named `11.csv` through `20.csv`; never
traverse member payloads or CRC-test the complete archive. Verify the outer
ZIP bytes without decompressing other examinations. In particular, no 61–80
CSV payload may be opened.

Run `scripts/verify_galar_eligibility.py` as a fresh standard-library-only
`python -I -S` process. The process has no model, predictions, training code
or application database. It disables core dumps, limits CPU/address space,
and denies Python socket/process-creation audit events. This is a trusted-code
separation, **not an operating-system security sandbox or independent human
data custodian**. Its sanitized launcher environment contains no credentials.

CSV decompression necessarily places original cell bytes in worker memory.
The worker may interpret only the `frame` identifier and the predicate
`blood in {"0", "1"}`. Both binary values map to the same eligibility flag;
blank maps to unknown. It must not branch on positive versus negative, count
positives, retain raw clinical fields, print rows, emit source exceptions or
write raw CSVs. Other clinical columns pass through CSV parsing transiently
but are never interpreted. Unexpected encodings/schema/duplicates fail closed
with generic errors and no partial output.

Permitted private output: ordered frame identifiers, eligibility/unknown
flags, comparison to the verified image index, input/code/amendment hashes
and a digest of that projection. Permitted public output: examination-level
row/eligible/unknown counts and source-coverage counts only. Identifiers,
paths and per-position missingness flags remain private. Standard output
contains only a completion status and cryptographic output digest. No raw
CSV content or positive counts may appear in logs or analyst-visible output.

Before real execution, synthetic tests must show: flipping **every** 0/1
value leaves the eligibility projection byte-for-byte identical; changing
unrelated clinical values does not change it; blank is distinct from binary;
reserved members are never read; malformed/duplicate IDs are rejected; and
coverage reports an eligible missing image rather than excluding it.

## Fixed decision rules, before missingness is observed

Use all explicit binary rows for **each** of the original ten examinations;
do not choose examinations, images, K, policies or checkpoints using outcomes.
Compare every eligible row to the complete original archive listing, including
endpoints. Classify absent inferred-grid positions separately as (a) absent
CSV row, (b) unknown row, or (c) eligible binary row. Do not infer a blood value.

If every eligible row has exactly one original PNG, the acquisition gate can
pass on explicit identities even when the filename grid has gaps. An absent
row or unknown row is not an eligible image. Keep examination 15, exclude
unknown rows **before scoring**, freeze the exact eligible identity set and
N, and compute the unchanged exact-K workloads on that N. Runs must split
at unknown rows and all source-index discontinuities; never bridge gaps.
Implement and synthetically verify this explicit-identity extension to the
existing contiguous-grid source gate before inference. The original endpoint
(score_bin minus uniform distinct positive-run recall at equal 10% K) is
preserved if complete eligible inputs are obtained.

If any eligible row lacks original pixels, the original complete ten-exam
endpoint is **not achieved**. Check official catalogue versions and original
distribution for an identical source member; no regenerated frame, thumbnail,
interpolation, neighboring image or unrelated-exam lookalike is a replacement.
Report missing eligible counts and coverage fractions for every examination.
Keep recovery and acquisition decisions blind to the missing row's blood value.

If identical pixels cannot be recovered, retain that examination as a documented
coverage failure. Any later analysis is explicitly **available-source sensitivity
analysis**, not completion of the original endpoint. Before outcomes: freeze
queues on the available eligible N, compare all four methods at equal K on that
same N, retain all ten examinations in the coverage table, and keep complete-
examination and incomplete-examination results separately labelled. Against
all eligible source annotations, count missing-image runs as unreachable;
also report available-input retrieval separately. K then refers to available N,
so it is a transparent denominator change. Do not pool it into the original
ten-examination primary estimate or silently assign a missing model score.
No such sensitivity result is authorized as prospectively frozen unless its
exact specification and predictions are independently committed before outcome
access. This amendment does not itself run or certify that analysis.

## Outcome release remains gated

This is an **outcome-concealed eligibility amendment** to the original stricter
CSV-access ordering; it must be disclosed in any resulting report. It is not
accurate afterward to say no corrected CSV was processed. It remains accurate
only if supported to say blood-positive/negative values were concealed from
the analyst until frozen original-CNN predictions and four-policy selections
were independently committed. Preserve the initial lock, amendment, projection,
code/input hashes and independent commitment receipts. No training, tuning,
calibration, alternative model or clinical claim is introduced.
