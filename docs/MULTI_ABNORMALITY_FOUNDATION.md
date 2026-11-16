# Multi-category detector suggestions and next development fit

Research implementation, 16 November 2026. This path is separate from scalar
prediction imports, exact-K scoring, saved human entries and draft PR #95.
No historical results or model-selection decisions change.

## Verified SEE-AI capability

The three preserved detectors expose ordered categories:
`angiodysplasia`, `erosion`, `stenosis`, `lymphangiectasis`, `lymph follicle`,
`SMT`, `polyp like`, `bleeding`, `diverticula`, `redness`, `foreign body`, `venous`.
These are the original strings; they are not a newly harmonized clinical ontology.

Each decoded model output is float32 `[1, anchors, 17]`: center x/y, width/height
in letterboxed input pixels, objectness and 12 class probabilities. For a square
576 input there are 20,412 candidates per model (61,236 concatenated). Rectangular
automatic letterboxing changes that count. The independent path retains 12
pre-NMS maxima of float32 objectness × class probability; these are not calibrated
probabilities that a frame contains a disease. The unchanged historical scalar
definition still takes only the class-7 maximum without confidence filtering/NMS.

The private source-reviewed implementation uses 576-pixel automatic letterbox,
stride 32, OpenCV linear resize, padding 114, RGB CHW float32 /255, batch one.
The new path begins with the importer's EXIF-corrected RGB display PNG and checks
its byte hash. It concatenates the three unfused detectors, retains the best
class per anchor with confidence strictly >0.1, uses class-aware NMS at IoU 0.45,
30,000 candidate cap and 300 detection cap. These defaults are versioned; the
viewer filter operates **after** that NMS and does not rerun it or change scores.
The offset-based upstream NMS and tie decisions are runtime-specific.

Coordinates are converted from xywh to xyxy by the qualified private processor.
The public inverse uses the actual input shape, removes fractional padding,
divides by gain and clips to the oriented display bounds, without integer
rounding. Padding-only boxes with no display area are omitted. The viewer's SVG
shares the displayed image geometry, including zoom and aspect-ratio changes.
Raw camera/EXIF coordinates are not accepted as display coordinates.

The preserved qualification compared two separately constructed graphs using
all three real weight sets on nine full-resolution synthetic cases: unfused
outputs matched bitwise. Historical-loader-style fusion differed by at most
0.00216675 px and 1.58548e-5 probability in those checks. This is qualified
historical-v5 source equivalence, not the authors' unknown original training
commit/environment or clinical detection validation. The blueprint retains all
131 saved BatchNorm settings (`eps=.001`, `momentum=.03`).

Exact original/SafeTensors SHA-256 rosters are enforced in `detections.py`.
The runner authenticates the existing graph, preprocessing/postprocessing and
blueprint **before importing code**, authenticates all weights, and rechecks
them before output. It records implementation hashes and runtime versions.
No `.pt` is loaded, no models are converted or downloaded. Frozen scoring code
is neither called nor modified. Hashes bind records to bytes; imported claims
are not signed proof of the inference producer or clinical correctness.

The historical implementation is GPL-3.0-derived and stays in the existing
private qualification bundle. Its code and weights are not included in this PR.
Author weight redistribution/product-use rights remain unresolved. The provided
runner therefore accepts only generated synthetic studies (at most 32 frames,
four CPU threads, five-minute cap). Medical-image execution requires separate
rights and study qualification; synthetic success does not clear that gate.

## Local use

Install the viewer normally. For private synthetic reproduction, additionally
install the already-qualified runtime packages (torch, torchvision, NumPy,
OpenCV and SafeTensors). Extract the existing November 16 execution evidence and
restored frozen assets into the same **private** directory; do not reconvert.

```
python scripts/run_seeai_detections.py --data-dir /private/workspace \
  --study-id SYNTHETIC_STUDY_ID --run-id seeai-synthetic-v1 \
  --bundle /private/private_readiness/assets/seeai \
  --output /private/detections.json
```

The runner writes a versioned JSON and adds an immutable detection run. The
viewer can also import that JSON using **Detector suggestions → Import detections**.
Pick a run/category and navigate to the next matching frame. Suggestions never
write human labels, bookmarks or notes. All frames remain available.

`capsule-review-detections-v1` binds the examination manifest and **every** frame's
position, source SHA, display SHA, oriented dimensions, 12 category scores and
zero or more boxes. Empty boxes mean no retained suggestion, not normality;
missing frames are rejected. Import validates the whole run before insertion,
rehashes stored displays and rejects duplicate run IDs. JSON limits: 64 MiB,
200,000 frames, 300 boxes/frame. Provenance is available in the viewer. Manual
review and scalar predictions stay in their original independent tables.

## CR-MA-01: conditional three-category fitting experiment

**Question:** On a video-grouped, selected-frame Kvasir development task, does an
ImageNet-pretrained compact model improve recognition of two abnormality labels
against explicit normal-clean-mucosa labels over a small supervised CNN?
This is three-way nominal classification, not multi-label absence detection,
box training, full-examination sensitivity or a new clinical validation study.

Reuse publisher commit `553601dc316fef82f39c952e28f60aaad66039e2` and the existing
split audit. Seven videos cross the two official files; do not reuse those folds.
The split catalogues cover 47,153 unique frames/47,161 rows, not the advertised
47,238 labels. Eight Erosion frames also carry another label: exclude all eight
multi-label frames rather than forcing a target or silently losing a label.

| Nominal source target | Single-label frames | Distinct source videos | Meaning/mapping |
| --- | ---: | ---: | --- |
| Angiectasia | 866 | 6 | Publisher superficial vascular finding; not automatically SEE-AI angiodysplasia |
| Erosion | 498 | 9 | Publisher small excavated mucosal lesion; keep separate from ulcer |
| Normal | 34,338 | 37 | Explicit publisher normal-clean-mucosa annotation; not inferred from absent labels |

Other categories are out of scope. Missing/unlabelled frames remain unknown.
No Galar sources are needed for this first task: mixing its ontology/devices
would add confounding without solving limited independent-video support.
No inspected 69-pair fitting images or reserved examinations enter this task.

`prepare_kvasir_multi_abnormality.py` authenticates the existing catalogue hashes,
coalesces source-video/frame keys, excludes multi-label frames, assigns whole
videos using a fixed SHA-256 order (`CR-MA-01-v1|video`), fills test support of
two videos/category then validation support of one, and assigns the remainder
to training. It stops if any training target has fewer than three videos.
Within each video/category, retain at most 128 published frames using existing
uniform midpoints. No image content, scores or outcomes affect this preparation.

| Split | Angiectasia frames/videos | Erosion frames/videos | Normal frames/videos |
| --- | ---: | ---: | ---: |
| Train | 247 / 3 | 323 / 6 | 4,096 / 32 |
| Validation | 21 / 1 | 81 / 1 | 256 / 2 |
| Test | 74 / 2 | 78 / 2 | 384 / 3 |

Category video counts overlap; do not sum them as independent examinations.
This is a provisional catalogue, not a frozen image-backed fit contract. Before
fitting, reconcile keys/filenames/labels with authoritative metadata and archive
membership (the split convention uses .jpg while publisher text describes PNG).
Commit exact image-byte and oriented-pixel hashes privately. Link duplicate
components across videos before splitting; stop and refreeze if that changes
this proposed split. Record perceptual-neighbour risk without claiming a
perceptual threshold proves patient independence. Patient/repeat-exam linkage
is unauthenticated, so claims must remain video-grouped.

**Two fixed fits, no sweep:** reuse `AnatomyCNN(classes=3)` with fresh random
weights as baseline; compare MobileNetV3-Small initialized from the already
preserved official ImageNet-1K V1 checkpoint (SHA-256
`047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`),
with a new three-output head and all layers trainable. This changes the task,
source and supervision; it does not repeat the prior frozen-feature blood fits.

Both arms: EXIF-corrected RGB, full-field aspect-preserving bilinear pad to
224×224 (no center crop), ImageNet mean/std normalization, no augmentation,
seed 37, batch 32, 512 optimizer steps, AdamW, weight decay 1e-4. Learning rates
are fixed at 1e-3 for scratch CNN and 1e-4 for pretrained challenger. Sample
class uniformly, then training video within class uniformly, then frame within
that video/class uniformly, with replacement. This prevents long normal-video
segments dominating fitting. No resampling of validation/test.

Validate only at steps 128/256/384/512. Select each arm's checkpoint by highest
**class-then-video macro recall**: average frame recall separately within each
true-class/video cell, then videos within class, then the three classes. Resolve
ties by lower validation multiclass log loss, then earliest step. Use argmax
(lowest class index on ties), no tuned thresholds. Freeze both selections and
prediction commitments before opening test outcomes once.

Report the same test macro recall, class/video recalls, macro-F1, confusion
matrix, multiclass log loss and per-video arm differences; include frame counts,
class/video support and failures. No frame-independent confidence intervals.
With only two test videos for each lesion category, any favourable result is
exploratory. Descriptive advancement requires improved macro recall without
reducing either lesion-category video-macro recall; failure retires this fixed
configuration on this split, not a hyperparameter search on its test outcomes.

**Resource/stop contract:** 5,560 selected catalogue frames; use only the labelled
image archive (publisher lists ~521 MB), not 32/58 GB video downloads. Reserve
4 GiB disk headroom before acquisition; stop if inspected archive sizes exceed
the allowance. CPU float32, four threads, at most 4 GiB RSS and one hour per arm
(two hours total); no paid accelerator. Stop on identity/label mismatch,
cross-split duplicates, unsupported class, nonfinite loss or resource exhaustion;
do not silently shrink data, switch model/precision or extend the budget.

Kvasir's paper identifies Olympus Endocapsule 10/EC-S10, 336×336, Bærum Hospital,
Norway (2016–2018), despite the landing page's generic PillCAM heading. SEE-AI
was developed using selected Japanese PillCam SB3 images; Galar spans German
sites and two capsule systems. These are different source/device domains.
The challenger uses generic ImageNet pretraining, not SEE-AI or a capsule-trained
checkpoint; no known Kvasir training overlap is documented, and absence of overlap
is not authenticated at patient/image level.

**Fitting decision: CONDITIONAL, not started.** Resolve authoritative image
mapping/counts, duplicate grouping, final private split/byte commitments,
checkpoint availability and research-use/institutional requirements first.
The dataset paper states CC BY 4.0; the current publisher page limits competition
and commercial uses without written permission. This proposed task is private
research; do not infer commercial deployment or checkpoint redistribution rights.

Sources: [publisher paper](https://doi.org/10.1038/s41597-021-00920-z),
[publisher terms](https://datasets.simula.no/kvasir-capsule/),
[source catalogues](https://github.com/simula/kvasir-capsule/tree/553601dc316fef82f39c952e28f60aaad66039e2/official_splits),
[ImageNet weight definition](https://github.com/pytorch/vision/blob/main/torchvision/models/mobilenetv3.py).

## PR #96 qualification update — 16 November 2026

Navigation now uses a persistent category/position index of retained boxes.
The SQL query applies category, exclusive `after`, ordering and a bounded page
limit before reading JSON. Next-detection requests ask for one result. Existing
runs receive a one-time transactional index backfill; original records are not
rewritten. A 50,000-record regression limits SQLite work and verifies one JSON
decode for a one-result request and none for an absent category.

The visible provenance notice distinguishes producer-supplied claims from
independent verification. Import checks source/display correspondence and record
structure; it cannot establish that a claimed model was actually executed. API
run metadata carries `IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED`; imported hashes
or a familiar profile name never promote a run to independently verified status.

The preserved CR-MA-01 catalogue is reused unchanged, not regenerated. Source
qualification uses the publisher-linked Google Drive mirror of the three labelled
class archives and both CSV/JSON metadata exports. Exact filenames in those
archives are JPEG `.jpg`, despite the publication/landing-page PNG description.
A source key maps through explicit CSV `video_id`/`frame_number`/`filename` fields
to a unique archive member. Source identities and individual audit records stay
private. No video archive or reserved Galar data is required.

The two-arm protocol is a bounded **systems comparison**: scratch AnatomyCNN
versus ImageNet-initialized MobileNetV3-Small. Architecture, capacity, normalization
layers, dropout and fixed learning rates differ alongside initialization. Equal
512-step budgets match sampled-image exposure, not FLOPs or optimal convergence.
The comparison cannot isolate pretraining. Use the same source split, sampled
frame sequence and batch order for both arms; only training RNG streams for
model initialization/dropout differ. Retain both best validation checkpoints
and all four scheduled validation measurements. No arm-specific extra updates,
augmented data, retries or test-based selection are permitted. An arm exceeding
the fixed resource cap is a technical failure, not a shortened comparable fit.
Results remain descriptive on this small selected-frame, video-grouped task.

### Image-backed CR-MA-01 qualification result

**GO for the specified two-fit private, noncommercial, video-grouped feasibility
experiment; no fitting started.** This supersedes the initial metadata-only
CONDITIONAL decision for that narrow experiment. It does not authorize medical
use, a competition, commercial use, or claim institutional ethics clearance.

All 5,560 retained catalogue rows map exactly through the authoritative CSV
video/frame/filename fields to unique members of the publisher-linked Angiectasia,
Erosion and Normal-clean-mucosa archives. No extension substitution or index
correction was needed: all selected files are 336×336 JPEGs. The CSV has 47,248
rows representing 47,238 unique filename/class pairs; repeated bounding-box
annotations explain the ten extra rows. One selected Erosion image has two
same-class box rows; both are retained as source annotations on one image.
All selected lesion identities also match the publisher's JSON findings.

| Source class archive | Selected authenticated images | Archive bytes | Archive SHA-256 |
| --- | ---: | ---: | --- |
| angiectasia.tar.gz | 342 | 9,521,122 | `0019d659dfc7c2b97e218a13de3d4855dfc8e4b517bbd37f9d52c4fee26a1b89` |
| erosion.tar.gz | 482 | 6,574,862 | `6f0db92ce2ff6769d1ba87077c9903ec9f4e902ce86ab246fca05119a18e670a` |
| normal_clean_mucosa.tar.gz | 4,736 | 390,319,693 | `4dc2b91b1b128e28eb47e13d34d0f106a0976d381838e8e7e30b7a9f2b9ca533` |

The original catalogue SHA remains
`4bcef12ae285dadbff0570676b12808fc332ebead022ede08c9e0f0ca182e9d8`.
All selected source bytes and oriented RGB identities were checked, gzip CRCs
passed, and a separate pass replayed the catalogue and image-byte commitments.
No byte-identical or decoded-RGB duplicate groups were found, within or across
splits. The 39 source videos remain disjoint: 34 train, 2 validation, 3 test.

The predeclared cross-split perceptual screen considered 4,363,292 pairs, using
64-bit DCT pHash distance ≤6 OR dHash distance ≤4 for candidate retrieval. The
205 candidates were checked using normalized 32×32 RGB MAE and grayscale SSIM
averaged over 8×8 windows. A pair is flagged if SSIM ≥.98, or both hash distances
are ≤4 and MAE ≤.025. None met that flag (maximum candidate SSIM .81628; minimum
candidate MAE .03286). This bounded screen does not prove absence of every near
duplicate or authenticate independent patients. No test model outcomes were read.

The existing private ImageNet checkpoint was recovered and matched its full
pinned SHA-256 without deserialization or execution. Research/education use is
permitted by the publisher terms; attribution is required, and competition or
commercial permission is not inferred. No new patient/reviewer data is collected.
No institutional approval or exemption is asserted; institutional adoption must
follow the responsible institution's requirements.

The private, exclusively created commitment binds the unchanged catalogue,
image-backed split, exact byte/RGB/perceptual hashes, complete source metadata,
duplicate report, fixed protocol and shared PCG64(37) training batch sequence.
Its SHA-256 is
`ac9b6615c69d7f31a9f26ea8d114188fbc681885e0c74e7495ffec138f8e8a18`.
The private files are read-only; hashes and retention provide the audit boundary,
not a claim of WORM storage, a digital signature or completed fitting.
