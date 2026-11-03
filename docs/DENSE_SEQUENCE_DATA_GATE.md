# Dense-sequence data gate — 2026-11-01

**Decision: no new clinical evaluation yet; real technical sequence acquisition now completed (see below).** The existing 5,120 Galar snapshots do not provide contiguous video context, and the prior blood-positive interval results reused examined development cases. This note checks a smaller **technical** route to consecutive video frames without silently downloading another 30–40 GB archive.

## Acquired complete published sequence — 1 November 2026

**Technical sequence gate passed; clinical evaluation gate remains closed.** Official Rhode Island collection v1, article [21183970 v1](https://doi.org/10.6084/m9.figshare.21183970.v1), file 37560007 contains nested per-study ZIPs. We acquired the smallest study in the smallest bundle, chosen by size before pixel inspection: 79,873,437 bytes. Exact HTTP 206 retrieval, outer-member CRC, all inner ZIP CRCs, per-file SHA-256 and decoded RGB hashes passed; independent `unzip -t` and an independent replay verified the retained data. The outer 5.99-GB file's published MD5 was **not** verified. Conservative total dataset transfer upper bound, including the interrupted attempt's full allowance: 191,022,493 bytes (<512 MiB).

The complete published study has **4,189 images**, all 320×320, unique continuous numeric IDs and no internal gaps, corrupt images or exact file/pixel duplicates. All are **JPEG-encoded despite .png filenames**. Original bytes/names remain unchanged. The paper states it retained all images from esophagus through colon; this plus the file audit supports consecutive **published-export** positions, not proof of every original device exposure. Capture times and acquisition cadence remain unknown. Paper CC BY 4.0 and Figshare CC0 metadata conflict; both records and full attribution are retained.

The existing viewer imported all images and preserved original hashes, order and decoded pixels. Its dedicated source-index field remains null for `image-NNNNN.png` names; the original filename and separate manifest retain numeric IDs/full archive paths.

**Importer follow-up (November 2, 2026):** the viewer now recognizes numeric `image-NNNNN.png` source IDs while retaining the original filenames/hashes. Study-level and per-frame spacing checks can therefore describe this published sequence's source-index adjacency without implying complete original device capture or verified elapsed time. Galar `frame_NNNNN`-only label matching remains separate. Anatomy folders remain in the manifest, not reviewer findings. Seven actual-localhost UI checks passed, including predetermined first/last/midpoint navigation, page/server restart and a real export. No product-source change or model training was needed.

Mean adjacent 64×64 RGB absolute difference was **0.04461**, versus **0.08284** for seed-17 shuffled pairs (0–1 scale, borders included). Fixed endpoint-inclusive uniform sampling at 5%/10%/25% selected 210/419/1,048 frames, with maximum nearest-selected-position distances 10/5/2. These are descriptive technical coverage checks; full 100-position-bin coverage is expected from the sampling rule, not evidence of clinical effectiveness. [Aggregate results](../experiments/rhode-island-sequence-2026-11-01/results.json) contain no image or individual frame identity.

The reusable companion **capsule-real-sequence-s288.zip** contains the unchanged source study ZIP, provenance, manifests, fixed analysis specification, acquisition/analysis/independent verification scripts, exact application source snapshot, screenshot/export and logs. It is retained outside Git. Local Python suite: 150 passed, two optional Torch-dependent modules skipped; standard localhost browser smoke: 12 checks. Frozen Galar experiments are unchanged.

CAPTIV8 v1.2 metadata and ZIP index are now live-verified: 3,951,201,762 bytes, 1,360 video members including MPEG, CC0, HTTP Range supported. No CAPTIV8 video was acquired or pathology label evaluated. The historical network limitations below describe the previous session.

**Next experiment:** prespecify multiple additional complete studies, then compare uniform and fixed image-change selection at matched budgets for anatomy-transition neighbourhood coverage and maximum uncovered position span. Keep selection/evaluation studies separate. Pathology-evidence evaluation still needs suitable dense frame/interval ground truth and an examination-disjoint cohort.

## Historical source comparison

| Dataset | Verified release facts | What it could support | What it does **not** establish |
| --- | --- | --- | --- |
| [Galar v2](https://doi.org/10.25452/figshare.plus.25304616.v2) | 80 annotated examinations, frame-level multi-label CSV; original pilot's first image archive was 31.16 GB in solid 7z blocks. The next 11–20 archive is listed at ~40 GB. CC BY 4.0. | Main *blood-positive annotated-run* coverage endpoint on truly consecutive frames, provided additional images are available | Patient-independent or clinically adjudicated lesion sensitivity without further reference evidence |
| [CAPTIV8](https://doi.org/10.18710/BSXNA1) (DataverseNO v1.2) | Ten ulcerative-colitis patients, PillCam Colon2 **colon** examinations, ~150-frame short video segments centered on representative images, main `Frames_and_videos.zip` ~3.7 GB, CC0. | Investigating clip decoding, frame order, model-score continuity and research-viewer integration on real adjacent frames | A per-frame pathology truth label: segment labels are **weak** labels inherited from representative frames. Its colon/UC domain is not equivalent to the Galar blood task. |
| [Kvasir-Capsule](https://datasets.simula.no/kvasir-capsule/) | 43 labelled videos (1,955,675 frames) plus 74 unlabelled videos; 47,238 annotated images, labelled-videos ZIP 32.2 GB. Research/education use; other use needs permission. | A distinct imaging/video robustness dataset if individual videos and matching sparse labels can be obtained | Dense negative labels for *every* frame or unconstrained commercial redistribution. |
| [Rhode Island GI VCE](https://doi.org/10.6084/m9.figshare.c.6071216.v1) | 424 VCE examinations and 5,247,588 images; original images are numerically ordered inside a **separate ZIP per study**. Published under CC BY 4.0; actual per-study file sizes must be checked before download. | A comparatively direct route to genuine consecutive-image ingestion, source-order integrity, and anatomy-boundary experiments if an individual permitted ZIP fits the 512-MiB cap | **No pathology annotations**; repeated patients across studies cannot be identified, so study-disjoint ≠ patient-independent. |

We chose **CAPTIV8 as a lower-volume *technical feasibility candidate***, not as the new primary diagnostic study. This is an explicit, limited extension of the Galar-only research protocol. Its labels must never be silently renamed `blood` or counted as per-frame lesion truth. The existing training, testing and saved result remain frozen.

## Audited physical-data gap — 1 November 2026

Run the reproducible, **real-image-backed** spacing audit before claiming dense video:

```bash
python scripts/sequence_readiness.py \
  --manifest /private/capsule-blood/manifest.json \
  --images /private/galar/images \
  --output /private/sequence-readiness.json
```

All **5,120 previously retained original PNGs** (1,598,002,230 bytes) were individually rehashed against the frozen blood-pilot manifest. Of the **5,110** consecutive *sample positions* within ten examinations, **none** have source-frame index delta 1 or delta <=5. Minimum source-index delta is 40; median is 70; maximum is 425. The result is in [`sequence_readiness.json`](../experiments/galar-v2-2026-11-01/sequence_readiness.json); it contains no patient image, individual frame identity or classifier prediction. This is a **verified NO-GO for dense-video evaluation using only the saved sample**. The label-file indexing convention is not a substitute for observing consecutive decoded video frames.

The local execution environment cannot resolve `dataverse.no`, `api.figshare.com`, or other public dataset domains through its network interface. The separately documented Figshare API collection and CAPTIV8 links have not been probed successfully for live byte-range behavior. The newly considered Rhode Island source is an **access candidate**, not acquired/evaluated data. Do not route around institutional network controls, use unapproved paid compute or exceed the 512-MiB acquisition cap. Before retrieving any individual Rhode Island study, inspect its official Figshare article/file metadata, exact download size, checksum, label scope and licence, then verify the downloaded file and frame order. Data from different studies are not automatically independent patients.

## Selective ZIP access: tested offline, not yet verified on DataverseNO

`python scripts/ranged_zip.py` uses only HTTP `Range` requests, requires exact `206 Partial Content` and `Content-Range`, and **never falls back to a full download** on `200 OK`, redirects to HTTP, mismatched length or incorrect ranges. It uses Python's ZIP central directory/ZIP64 support, a bounded 1-MiB read-ahead, and a **128-MiB default / 512-MiB hard maximum** total transfer budget. For selected members it checks expected uncompressed size, the ZIP CRC, unsafe paths, ambiguous member names and likely ZIP bombs; selected files are staged and verified before publication, and it records per-member SHA-256. No raw videos are committed to GitHub.

The publisher's [DataverseNO file page](https://dataverse.no/file.xhtml?persistentId=doi:10.18710/BSXNA1/JQXYBL) identifies the `Frames_and_videos.zip` file. A *candidate* URL using Dataverse's documented persistent-ID access API is:

```
https://dataverse.no/api/access/datafile/:persistentId?persistentId=doi:10.18710/BSXNA1/JQXYBL
```

First test **index-only** access, without selecting or downloading video members:

```bash
python scripts/ranged_zip.py \
  'https://dataverse.no/api/access/datafile/:persistentId?persistentId=doi:10.18710/BSXNA1/JQXYBL' \
  list --match .avi
```

Inspect the returned exact member names, sizes and cumulative transfer. If individual video members are safely small, **only then** perform an explicit bounded extraction, using the exact path discovered in the index:

```bash
python scripts/ranged_zip.py \
  'https://dataverse.no/api/access/datafile/:persistentId?persistentId=doi:10.18710/BSXNA1/JQXYBL' \
  extract --member 'ACTUAL/MEMBER/NAME.avi' --output-dir /research/captiv8
```

The member path above is a **placeholder**, not a claim about the ZIP's actual layout. Determine whether files are AVI/MP4 before choosing. No automatic video retrieval occurs during `list`.

**Important access limit:** The current execution environment could not resolve the DataverseNO domain, and live `206` support for this exact archive has **not** been established. Tests exercise local synthetic ZIP servers, not live CAPTIV8 data. An explicit official-source URL might redirect, require a guestbook or ignore Range requests. If any of these occurs, the command must stop. Do not claim selective remote retrieval succeeded without recorded server responses and checksums, and do not work around an administrator network restriction.

A ZIP's central directory can be read from its end without the whole file *only if* the publisher supports standard byte ranges and the index fits the budget. Unlike Galar's solid LZMA2 `7z` archive, ZIP member compression is normally independent; our tool does not operate on Galar `7z` files.

## Gate for a real consecutive-frame study

1. **Provenance:** verify publisher, exact release and file/member identity; for sampled ZIP files verify CRC/SHA-256, not the full 3.7-GB archive MD5 (which requires the full archive). No fabricated checksum match.
2. **Sequence evidence:** inspect frame count, decoded order, missing/duplicated frames and file/clip timestamp conventions. Video-export frame rates may differ from original capsule acquisition time. Preserve clip-relative frame IDs; do not invent absolute Galar IDs.
3. **Independent cases:** extract multiple distinct labelled-examination or patient groups, never random nearby frames into opposite partitions. Do not use Galar 9–10 as a new independent test or open reserved Galar 61–80.
4. **Labels:** CAPTIV8 weak clip labels stay weak. Score continuity, order preservation and import performance may be measured; **blood-run recall or clinical lesion sensitivity may not** without independently verified frame/interval labels.
5. **Relevance:** show that the selected video clips address a concrete failure of the existing sparse-frame workflow. If not, stop and preserve the Galar-based benchmark without adding unhelpful models or UI.
6. **Budget:** no unapproved transfers over the 512-MiB hard cap and no paid compute; if official byte-range access is unavailable, report the exact blocker.

The next scientifically meaningful experiment remains **dense, examination-disjoint Galar blood-annotation-run evaluation**. CAPTIV8 is useful only as an earlier, explicitly bounded test of whether our tools preserve actual video sequence context.

## Primary references

- Le Floch et al. (2025), [Galar](https://www.nature.com/articles/s41597-025-05112-7), corrected v2 data.
- Vats et al. (2024), [CAPTIV8 archive and licence](https://dataverse.no/dataset.xhtml?persistentId=doi:10.18710/BSXNA1), DataverseNO.
- Smedsrud et al. (2021), [Kvasir-Capsule dataset and terms](https://datasets.simula.no/kvasir-capsule/).
- Charoen et al. (2022), [Rhode Island GI VCE dataset](https://www.nature.com/articles/s41597-022-01726-3) and [Figshare collection](https://doi.org/10.6084/m9.figshare.c.6071216.v1).
- [DataverseNO API guidance](https://info.dataverse.no/deposit/api/) and [Dataverse Data Access API](https://guides.dataverse.org/en/6.5/api/dataaccess.html).
