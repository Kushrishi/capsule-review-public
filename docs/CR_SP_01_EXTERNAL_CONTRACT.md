# CR-SP-01 external arithmetic contract v1

`capsule_review.spatial_external.evaluate` implements the prospectively selected
M1A–M5A research policy. It consumes saved scores; it cannot run a model, fit,
select a checkpoint, calibrate a threshold, open a file or fetch a reference.
Generated tests are the only execution evidence. No actual AIIMS raw vocabulary,
row/reference join, trained model or independent seal has been authenticated by
this implementation. This is not clinical validation or execution authorization.

```python
from capsule_review.spatial_external import evaluate
report = evaluate(contract_bytes, trusted_contract_sha256,
                  population_bytes, prediction_bytes, reference_bytes)
```

The caller must obtain the **expected contract digest independently**, from an
approved pre-outcome seal. A self-created digest does not prove approval. Four
UTF-8 JSON documents use exact field sets; unknown/duplicate fields, invalid
versions and NaN/Infinity are rejected. SHA-256 values are full lowercase hex.
All hashes cover original bytes, not a canonicalized or repaired document.
JSON numeric score/threshold values are compared exactly as parsed decimals;
booleans and strings are not numbers. Reordering input rows is safe only when
the independent contract binds those exact new bytes; joins never use position,
basename matching, case folding or guessed extensions.

## Input schemas

Every document has `schema: "cr-sp01-<kind>-v1"` with kind below. The generated
factory in `tests/test_spatial_external.py` is a complete runnable wire example.
All listed fields are required; extra fields are errors.

| Kind | Other top-level fields |
|---|---|
| `contract` | `policy`, `scope`, `population`, `archive_sha256`, `population_sha256`, `predictions_sha256`, `references_sha256`, `reference_version`, `mapping`, `models`, `six_selection_sha256`, `method_sha256`, `analysis_sha256` |
| `population` | `archive_sha256`, `rows` |
| `predictions` | `six_selection_sha256`, `method_sha256`, `models` |
| `references` | `version`, `rows` |

Contract `policy` is exactly `CR-SP-01-M1A-M2A-M3A-M4A-M5A`.
`scope` is `generated-control` or `reserved-aiims` and is echoed in the report.
Generated scope permits toy population sizes, **not a reserved-test conclusion**.
Reserved scope requires 4,385 rows, 4,377 exact-image SHA groups and archive SHA
`cab4b4f73786734b1805ec34c371379f6f0e9324213ea0b5f2e91c8c799896db`.
Contract `population` has exactly integer `rows` and `groups`.

Population rows have exactly `row_id`, `member`, `image_sha256`. IDs are unique
opaque `[A-Za-z0-9_-]{1,80}` keys, not filenames. Members are unique normalized
relative POSIX archive paths, without parent traversal, absolute paths or
backslashes; Unicode/case-equivalent collisions are rejected. Full member paths
are retained, never reduced to a basename. The independent custodian must verify
the image-hash multiset against original `blind-hashes.json` SHA
`531edf86d932c79eeb70a4b8064ebc9761ab3d63ccdbf09d11c3a8edba6e5215`.
This arithmetic engine does **not** reopen images or establish that provenance
from counts alone. The approved population digest binds the exact row mapping.

Each contract model has exactly `seed`, `arm`, `checkpoint_sha256`,
`selection_sha256`, `thresholds`. Seeds are integers 19, 37, 73; arms are
`classifier`, `detector`, each combination exactly once. Thresholds are two
numbers in [0,1], vascular then mucosal. Prediction models have those fields plus
`complete`, `updates`, `checkpoint_epochs`, `rows`. Completeness requires a true
boolean, 14,180 updates and [4,8,12,16,20]. These are **sealed attestations**, not
proof that fitting or checkpoint verification occurred. The upstream independent
verifier must validate the actual `spatial_training.verify_six` hierarchy and
runtime/resource evidence before approving the contract. Missing models or
incomplete fits produce INCONCLUSIVE; they cannot be dropped or replaced.

Prediction rows have exactly `row_id`, `scores` (two numbers in [0,1]). Each
model must join the entire population one-to-one. Identical image SHA values
must have exactly equal score pairs for each model. Model/selection/method hashes
and thresholds must match the contract. No checkpoint is loaded here. Scoring
remains classifier sigmoid / detector pre-ROI-filter maximum foreground
posterior over fixed RPN proposals, as in frozen `spatial_comparison.py`.

Reference rows have exactly `row_id`, `image_sha256`, `tokens` (nonempty array of
distinct raw strings). Every row joins the population and agrees on image SHA.
Reference `version` must match the contract. `mapping` is an explicit bounded
dictionary (1–32 raw tokens) into nonempty sets represented as arrays of distinct
canonical states: `vascular`, `erosion`, `ulcer`, `normal`, `other`, `unknown`.
Neither `normal` nor `unknown` may be combined with other states in a row.
Repeated positive states across tokens are unioned, not counted twice. Multiple
positive states are supported only when explicitly present in that reference.
The actual raw vocabulary/mapping and reference file version/hash **must be
independently reviewed and sealed before any outcome calculation**. Toy mapping
names are not proposed AIIMS labels. Unknown and other categories are never
silently converted to normal or target-negative references.

## Calculations and verdict

Primary row weight is 1. Mandatory secondary row weight is `1/n_group`, fixed
before references are joined and normalized only within each eligible endpoint
subset. All rows are retained. The exact ratios are serialized as fraction
strings: `hits`, `support`, `rate`; zero support gives `rate: null`. Each metric
also gives row and exact-image-group counts. These are not patient counts.

For each of six models, report vascular, pooled erosion-or-ulcer, erosion and
ulcer recall; source-normal per-target and OR-alert rates; separate other and
unknown any-target alert descriptions. Alert means **score > threshold**.
All paired detector-minus-classifier differences and their three-seed mean are
reported for each recall stratum. Negative individual erosion-seed differences
are explicitly listed. No best-seed selection, ensemble, confidence inference,
rounding tolerance or changed development selection is introduced.

H1: primary mean paired gain >=1/10 for both targets. H2: primary mean erosion
gain >=0 (individual losses disclosed). H3: each paired seed strictly improves
both targets. H4: every detector seed has primary source-normal OR-alert rate
<=1/20. Secondary criteria are mandatory descriptive outputs; they cannot
rescue or veto the primary advancement decision.

Before MET/NOT MET, enforce integrity, completeness and required support. Any
failure or required NA makes overall **INCONCLUSIVE even if another safeguard
fails**. Only otherwise are all four true = MET, or any false = NOT MET.
Ulcer-only zero support is disclosed but is not an extra safeguard. M5 compares
within each exact-image group the required eligibility vector:
`(vascular-positive, mucosal-positive, erosion-positive, source-Normal)`.
Any disagreement makes the verdict INCONCLUSIVE while preserving all rows,
original reference states, weights and descriptive metrics. A difference only
between other and unknown has no required eligibility impact and creates no
veto. No relabeling, adjudication or image-group majority vote occurs.

## Verification and execution boundary

```sh
python -m pytest -q tests/test_spatial_external.py
```

Existing ordinary CI runs these generated tests; no new workflow, training-host
entry point or dependency is added. Tests check independent direct-count
arithmetic, hostile schemas/digests/joins, incomplete studies, verdict precedence
and input ordering. Evaluation works with file/network operations disabled;
fresh import does not load Torch or training. This establishes code separation,
**not actual-host isolation**. The frozen Linux executor/loader protections and
intended-host canaries remain separate prerequisites. No references belong on
the training, checkpoint-selection or calibration host. No source or reference
download/transfer, final seal, external evaluation, fitting or spending is
authorized by running the generated tests. Existing false fitting gates remain
unchanged.
