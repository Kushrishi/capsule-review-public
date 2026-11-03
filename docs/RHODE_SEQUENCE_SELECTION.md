# Rhode Island image-change selection — first real-sequence pilot

**Status:** exploratory, single published study; **not** a clinical validation, independent test, lesion-sensitivity study, or evidence of reduced reading time. Updated 2026-11-01 / Eastern time. Frozen source: s288 as supplied in the earlier official Rhode Island acquisition package.

## Why this comparison

Image-level pathology retrieval on the historical Galar development sample frequently prioritized similar frames from the same long annotated run. The full Rhode Island `s288` archive provides 4,189 continuously numbered *published* frames, a technical opportunity to compare position coverage and anatomical boundary coverage without fabricating pathology labels. The original acquisition times are unavailable; numerical sequence continuity does not establish elapsed time.

Published source: Charoen et al., *Scientific Data* (2022), DOI [10.1038/s41597-022-01726-3](https://doi.org/10.1038/s41597-022-01726-3); Rhode Island dataset [10.6084/m9.figshare.c.6071216.v1](https://doi.org/10.6084/m9.figshare.c.6071216.v1), nested study `s288` in file 37560007. The paper says CC BY 4.0; source article metadata labels CC0, so preserve attribution. Data were retrospectively de-identified, and the authors say some patients contributed multiple studies without stable patient-group IDs. No patient-independent claim follows from distinct study numbers.

## Frozen method

The [selection specification](SEQUENCE_SELECTION_SPEC.json) was saved and SHA-256-recorded before the transition-coverage outcomes were computed (`c92500af677a12323ea5b8ebf43feb1b17f41bcf44ccfa80e94f28a19289399e`). However, anatomy distributions and images from s288 were inspected previously. **s288 remains exploratory**, not a blinded evaluation. The specification also locks future study IDs before acquisition.

For each 5%, 10%, and 25% frame budget, select exactly `ceil(budget*N)` published positions, always including both endpoints. Compare: (1) uniform index spacing; (2) globally highest 64×64 resized RGB adjacent-frame absolute changes; (3) the same change measure but one maximum per equal-sized chronological bin; (4) 100 endpoint-anchored, seeded random selections. No selection policy reads anatomical labels. Boundaries are the first images in the next of four labelled anatomy folders, *not* adjudicated lesion events. Report nearest selected distances and transition hits at ±0/±2/±5 source positions.

Change scores were independently recomputed from all original s288 image bytes. The maximum absolute discrepancy against the prior acquisition analysis's full 4,188-value vector was `1.98e-8` (minor floating point arithmetic); the original uniform selections were also exactly reproduced. The archive SHA-256 remains `145dad913880a155c7ac5942742e1941cb85c9508dd835e8a444ee66a7b0828e`.

## Real results: 4,189 frames; three labelled anatomy transitions

| Budget | Method | Boundaries within ±2 | Within ±5 | Max unselected-to-selected distance | Max consecutive selected-position gap |
| --- | --- | ---: | ---: | ---: | ---: |
| 5% (210) | Uniform | 0/3 | 2/3 | 10 | 21 |
| 5% (210) | Global image change | 2/3 | 2/3 | **281** | **563** |
| 5% (210) | Chronologically stratified image change | **3/3** | **3/3** | 20 | 40 |
| 10% (419) | Uniform | 0/3 | 3/3 | 5 | 11 |
| 10% (419) | Global image change | 3/3 | 3/3 | **225** | **451** |
| 10% (419) | Chronologically stratified image change | 3/3 | 3/3 | 9 | 19 |
| 25% (1,048) | Uniform | 3/3 | 3/3 | 2 | 4 |
| 25% (1,048) | Global image change | 3/3 | 3/3 | **192** | **385** |
| 25% (1,048) | Chronologically stratified image change | 3/3 | 3/3 | 3 | 7 |

The seeded random control has 100 draws, never used to pick the best seed. Its **mean** number of boundaries within ±5 positions is **1.70, 2.32, and 2.89**, respectively, at the 5%, 10%, and 25% budgets. These fractional counts are replicate averages, not fractional organ transitions.

**Interpretation:** Global image-change ranking can identify sharp changes, but it creates severe uncovered chronological gaps. Stratified ranking limits those gaps and, at 5%, reaches all three *anatomical* transitions within two saved-frame positions, though uniform still has the tighter maximum spacing guarantee. There are only **three** boundaries in one previously explored study. No statistical claim of superiority, clinical benefit, or novelty is justified. The observation may fail on other studies.

## Next independent data gate

Before decoding any further studies, the prespecified rule selects the two smallest separately packaged complete ZIP members from the official `Study 276-300.zip` index, *excluding already studied s288*:

- `Study 276-300/s280.zip`: 103,418,092 bytes.
- `Study 276-300/s284.zip`: 115,960,292 bytes.

These 219,378,384 source bytes fit under the **512 MiB** new-acquisition ceiling assuming verified Range behavior and modest protocol overhead. No data from these studies have been downloaded or examined in this analysis runtime. They are **study-separated, not confirmed patient-independent**. Their labels offer anatomical region boundaries only; this cannot validate the Galar `blood` task. Do not substitute Galar image scores as diagnostic or clinical endpoints.

After lawful, checksum-verified retrieval, run **the identical, unchanged script and frozen specification on both**, report each study separately and then paired study-level results without optimizing policy parameters on those outcomes. If one cannot be obtained, record the failure instead of replacing it after seeing labels. The multi-study experiment is pending acquisition; this document reports **s288 only**.

## Reproduce

The source ZIP is stored in the private companion acquisition package outside GitHub. Using the unchanged original `s288.zip` nested member and Pillow 12.x:

```sh
python scripts/compare_sequence_selection.py \
  --archive /private/s288.zip --study-id s288 \
  --expected-sha256 145dad913880a155c7ac5942742e1941cb85c9508dd835e8a444ee66a7b0828e \
  --spec docs/SEQUENCE_SELECTION_SPEC.json --out /tmp/s288-selection-results.json
```

Compare output to [`experiments/rhode-s288/sequence_selection_results.json`](../experiments/rhode-s288/sequence_selection_results.json). No images, anatomical-source identifiers at the individual-frame level, model weights, patient notes, or database files are committed. The application UI is unchanged.

## Prespecified s280 and s284 follow-up

The previously frozen studies have now been run on real verified, complete source sequences. The replication **did not consistently confirm** s288's 5% stratified-change anatomy-transition advantage. See [the independent-study comparison](RHODE_REPLICATION_RESULTS.md) and the new research records. The historical s288 numeric outputs and selector implementation remain unchanged.
