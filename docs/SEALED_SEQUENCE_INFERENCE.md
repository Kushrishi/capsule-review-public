# Sealed full-sequence inference

`scripts/run_frozen_sequence.py` executes a reviewed local scoring adapter on
an authenticated, complete sequence. It also verifies sealed outputs without
images, weights or reference labels. It performs no download or model fitting.
The final external model roster and clinical event evaluator remain provisional.

Use generated images for engineering tests. External execution requires an
approved study contract, permitted source data and an independent evaluator.
Preserved model identities, preprocessing and scores must be copied from their
existing commitments. This runner does not supply or select a new model.

## Input contract

Keep source files, model assets, manifests and outputs outside public Git.
The output directory must not exist. Python 3.11 or later on Linux/macOS is
supported; Git checks output location and POSIX `resource` measures process memory.
Only CPU execution is qualified by this interface. GPU equivalence is not assumed.

The source manifest is UTF-8 JSONL. Its first line contains:

```json
{"schema_version":1,"sequence_id":"synthetic-example","frame_count":2,"image_size":[480,480]}
```

Each following line contains `position`, `source_frame`, `path` and `sha256`.
Both indices must be integers in the exact order `0, 1, …, N-1`. Paths are
relative to the source root; each SHA-256 authenticates the original image bytes.
`image_size` is optional, but must match every image when supplied. The manifest
defines the complete population; deriving it from an incomplete directory does
not authenticate completeness. A custodian must approve the original coordinate
mapping before an external study. No directory sorting or missing-frame repair
occurs during inference.

The method manifest is one JSON object with these exact top-level fields:

| Field | Content |
| --- | --- |
| `schema_version` | Integer `1` |
| `method_id` | Fixed opaque method name |
| `roster_status` | `"provisional"` |
| `preprocessing` | Nonempty object describing the preserved preprocessing |
| `scoring` | Nonempty object describing the preserved score and membership |
| `implementation` | Result of `capsule_review.sequence_pipeline.implementation_identity()` |
| `files` | Array of `{ "name": ..., "path": ..., "sha256": ... }` records |
| `runtime` | Exact runtime configuration shown below |

```python
import platform
from importlib.metadata import version

runtime = {
    "python": platform.python_version(),
    "packages": {"Pillow": version("Pillow")},
    "device": "cpu", "threads": 1, "batch_size": 1,
}
```

For a Torch adapter, include its exact `torch` and other inference dependency
versions. Copy the previously qualified thread count and batch size; the example
above does not redefine a frozen model's numerical execution. The adapter must
set the declared Torch thread count and enable deterministic algorithms with
warning-only mode disabled. A batch
change needs a separate synthetic compatibility check before it can be frozen.

Every asset path is relative to the asset root. Include model weights, preserved
configuration, the adapter source named `adapter`, and its transitive inference
source dependencies. Hashes are checked before adapter import and again before
sealing. The pipeline code and existing selection implementation are also bound
to the method manifest. Hashes authenticate reviewed code; they do not make
untrusted Python safe to execute. The adapter runs as trusted Python without a
sandbox. Sealed hashes establish retained-byte integrity, not whether the adapter
faithfully implements the declared preprocessing and score. Independent synthetic
agreement with the preserved reference implementation is a separate requirement.
Approved execution must also pin the reviewed runner/entry-point and adapter
source provenance: the callable API assumes trusted, reviewed caller code.

The adapter exposes `create_scorer(method, files)`, returning a callable that
accepts an immutable `Sequence[FrameInput]` (passed as a tuple) and returns one
finite Python `float` or `int` per frame. Each object contains `position`,
`source_frame`, `path`, `source_sha256` and `raw` image bytes. Use those
already-authenticated bytes for the frozen preprocessing. Do not reopen paths,
update model state, read labels or transform the preserved score. Load tensor-only
weights with safe loaders.

## Transition to an approved external study

Version 1 accepts and emits only `roster_status: "provisional"`. It cannot
represent an approved external roster. Before an authorized study, the approved
contract must bind the exact method manifests and model membership, preserved
preprocessing and scores, 10%/25% selection policies, source population and
coordinate mapping, qualified runtime and batch size, and independent evaluator.
The organizer's reference-annotation semantics must be settled before defining
and freezing a clinical event-coverage evaluator and its denominator.

Representing that approval requires a separately reviewed, versioned change to
the method, selection and receipt schemas and their verifier. Bind the approved
study-contract SHA-256 and roster consistently in those artifacts, and retain
verification of existing version-1 bundles. Changing the status string alone
does not establish approval or freeze a study. That transition must include
synthetic tests for contract/roster mismatches and reference compatibility; it
does not authorize changing any historical model, score or advancement decision.
No final model membership or clinical event definition is selected here.

## Execute and verify

Record the source and method manifest SHA-256 values independently before use.
Set the shell variables below to private, approved local inputs and commitments.
No command downloads data or discovers model assets.

```bash
python scripts/run_frozen_sequence.py run \
  --source-manifest "$SOURCE_MANIFEST" --source-sha256 "$SOURCE_SHA256" \
  --method-manifest "$METHOD_MANIFEST" --method-sha256 "$METHOD_SHA256" \
  --source-root "$SOURCE_ROOT" --asset-root "$ASSET_ROOT" \
  --output "$NEW_PRIVATE_OUTPUT"

python scripts/run_frozen_sequence.py verify \
  --bundle "$NEW_PRIVATE_OUTPUT" --seal-sha256 "$INDEPENDENT_SEAL_SHA256"
```

`seal.json` commits `source_manifest.jsonl`, `method_manifest.json`,
`scores.jsonl`, `selections.json` and `receipt.json`. Retain its SHA-256 outside
the bundle and have the evaluator timestamp/acknowledge that commitment before
outcome access. A self-contained hash manifest is not an independent timestamp
or signature. The verifier authenticates every artifact and recomputes selections
from the sealed frame-indexed scores. Console summaries omit source paths and
individual scores/indices. The full bundle remains private.

At each 10% and 25% budget, `exact_k` supplies the existing half-up count and
`uniform_midpoints` supplies the existing uniform policy. Score-bin selection
uses the existing floor-boundary bins and chooses the greatest raw score, with
the earliest position winning exact ties. Selected indices are serialized in
chronological order. Raw CNN margins remain unnormalized. No smoothing, new
threshold, test calibration or model combination is introduced.

Missing, duplicate, reordered, changed or corrupt source records stop execution.
Duplicate file paths, symlinks and hard-link aliases are rejected. Identical bytes
at distinct authenticated temporal positions are retained and counted in the
receipt. Any failure or interruption leaves no success seal; a private failure
receipt records partial progress. Existing output directories are never reused.

Images are decoded within one bounded batch. Source identity metadata and selected
indices scale with the sequence count, capped at 200,000 frames; there is no
full-sequence RGB tensor or feature matrix. The receipt reports throughput and
process lifetime peak RSS, including runtime and loaded model memory. Run each
memory benchmark in a fresh process for meaningful comparisons.

Synthetic custody and selector checks:

```bash
python -m pytest -q tests/test_sequence_pipeline.py
```

These tests establish software behavior, not medical performance, patient
independence, complete reference annotation or permission to evaluate a dataset.
