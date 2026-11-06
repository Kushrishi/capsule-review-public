# Chronology-conditioned score audit: retrospective development lock

November 6, 2026. Written before opening the retained prediction arrays for this
new analysis. Prior aggregate outcomes and case support have already been read;
this is a **retrospective diagnostic**, not preregistered independent validation.

## Question and fixed scope

Do held-out-examination CNN rankings retain positive-image information beyond
examination identity and broad chronological location? This tests score/annotation
alignment, **not causal pathology recognition**, calibration, or clinical usefulness.

Reuse only the existing private 949,542-byte examination-balanced CNN archive,
SHA-256 `9dd1cca41d07299191cd867886ddfa7c1d84d8b188a9ff349b8067ca541f1ea1`.
Verify its member checksums, metadata commitment, fixed four held-out folds,
source-reference roles, prediction checksums and all historical exact-K hits
before accepting new results. No checkpoint loading, image acquisition,
training or inference. Galar 35 is not analyzed again. Galar 11–20 and 61–80
are excluded. Patient identity is still unverified.

Use all 16 previously inspected examinations and exactly their 512 chronological
uniform-reference positions, 8,192 per arm. Reuse both saved CNN arms; the
ordinary pooled-class-balanced arm is primary, examination-tempered secondary.
No fitting or policy changes. Existing global-score, score-bin and uniform
queues at K=51,128,256; source-order tie breaking, as in the original software.

## Endpoints and controls

**Primary descriptive endpoint:** equal-positive-examination mean of
`(observed hits − chronology-conditioned expected hits) / positive images`,
for pooled-class-balanced global-score ranking at K=51.

Chronology control: divide each ordered 512-reference sequence into **16 fixed
32-position blocks**. Preserve the queue's selected count and the label-positive
count inside every block. Under uniform random placement of that many selections
within each block, exact expected hits are `sum(k_b * positives_b / 32)`.
This is an allocation-matched negative control, not another deployable queue.
No claim that 32 reference positions correspond to a fixed duration or anatomy.

Secondary diagnostics, all reported without candidate selection:

- Same block-conditioned contrast for both arms, all three queues and budgets.
- Unrestricted random-selection expectation `K * positives / 512`.
- Exact circular displacements of the selected queue across all **512** ordinal
  offsets (including identity), preserving its geometry and the label sequence.
  Report full-orbit mean, minimum, maximum and fraction at least observed.
  The latter is a descriptive alignment rank, **not an inferential p-value**:
  nonstationary anatomy and fixed boundaries do not justify exchangeability.
- Per-examination hits and contrasts, positive/negative/tied contrast counts,
  pooled support and macro recall; zero-positive recall undefined, never 1.
- Leave-one-positive-examination-out range of the primary mean to reveal
  concentration. No frame-bootstrap confidence interval or patient-level CI.

There is no model-promotion rule, optimization or success threshold. Positive
contrast suggests local predictive association conditional on this chosen coarse
partition; it cannot distinguish pathology from fine-scale appearance/annotation
shortcuts. Negative contrast motivates better diverse, authenticated source data,
not another sweep over this partition, architecture or known outcomes.

## Verification and execution boundary

Add a small reusable diagnostic beside existing ranking utilities and a private
archive reader. Test controls on synthetic data, including constant scores,
pure block-location scores, exact local signal, zero positives, invalid/unknown
labels and tampered records. Independently reconstruct queues, block expectations,
circular counts and macro summaries without importing production diagnostic or
selector code; require numerical agreement before publishing aggregates.

The public output contains examination-level summaries only, no original frame
IDs, per-frame labels/scores, weights, group identifiers or medical pixels.
Keep the exact private input, execution code, result, audit and checksums in a
new private retained evidence package. Preserve all previous experiments unchanged.
