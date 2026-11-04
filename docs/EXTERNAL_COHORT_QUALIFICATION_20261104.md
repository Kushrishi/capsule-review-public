# External capsule-endoscopy cohort qualification (research gate)

**Date:** 2026-11-04. **Status:** source-documentation qualification only; no cohort approved, acquired, annotated or evaluated. This is not a registered protocol or an independent replication.

## Decision and reason

**Do not acquire or score an external cohort yet.** Among the reviewed resources, Kvasir-Capsule is the first candidate to contact because its medically reviewed image labels map to source-video/frame identifiers. However, its publicly described labels cover selected segments rather than every frame, and its pathology ontology is different from Galar blood=1. Consequently the existing public annotation records do **not** establish complete blood-positive source-run ground truth. No listed dataset currently passes the unchanged endpoint's admission gates on the published evidence alone.

Keep the 2026-11-04 locked Galar 11–20 experiment and negative 10% result unchanged; 11–20 is already evaluated and the authors' 61–80 outcomes remain untouched. See [original evaluation lock](GALAR_UNSEEN_11_20_EVALUATION_LOCK.json), [completed results](GALAR_UNSEEN_11_20_RESULTS.md) and [final handoff issue #24](https://github.com/Kushrishi/capsule-review-public/issues/24).

### Candidate screen based on publisher/source documentation

| Candidate (primary source) | Verified useful feature | Blocking gap for the **same distinct blood-positive annotation-run** endpoint | Decision |
| --- | --- | --- | --- |
| [Kvasir-Capsule (Simula)](https://datasets.simula.no/kvasir-capsule/) and [2021 descriptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC8160146/) | 117 total videos (43 with labeled excerpts, 74 without); 47,238 expert-annotated frames; metadata maps image labels to source video and frame number; full corresponding labeled videos available | The 43 labeled videos have ~1,955,675 frames, of which 1,932,047 frames are **not labeled**. The publication describes selected segments. Cannot infer missing labels are blood-negative, exhaustive events, or cross-video unique patients; 'Blood - fresh' and 'Blood - hematin' need an outcome mapping decision | **Inquire first; conditional candidate, NOT qualified** |
| [CAD-CAP](https://pubmed.ncbi.nlm.nih.gov/32118115/) | Multicenter 25,000-image collection with clinically evaluated pathology categories | Published description concerns extracted pathological frames; complete consecutive examination streams, negative-label denominator, patient grouping and access for independent run-recall evaluation not established | **Collaboration/access inquiry only; NOT qualified** |
| [WCEbleedGen v2](https://zenodo.org/records/10156571) and [dataset paper](https://arxiv.org/abs/2408.12466) | Public bleeding/nonbleeding image benchmark (2,618 frames reported in paper); detection and segmentation annotations | Frames drawn from various sources, with no documented complete per-examination chronology or exhaustive event coverage. Dataset is useful for different tasks but cannot support this unchanged run endpoint | **Not eligible for primary replication** |
| [Rhode Island GI VCE](https://www.nature.com/articles/s41597-022-01726-3) | 424 studies and 5,247,588 anatomical-class images; source-sequence review engineering possible | Four anatomical classes only; publication explicitly does not include pathology annotations | **Not eligible for blood-run endpoint** |
| [RARE-Vision 2026 held-out test set](https://opara.zih.tu-dresden.de/items/64342f8d-b739-4055-8e7c-9d2dce0d39d4) | Three chronological capsule sequences reported | Outcome ground truth withheld; three cases are not an adequate independent comparison; related Galar investigators and source relationships would need investigation | **Do not repurpose as replication** |

**Source-count caution:** reports may count videos, frames, or exported records slightly differently; use publisher member inventories when planning acquisition. Nothing was downloaded to verify individual files for this screen.

**Use rights:** Simula states Kvasir-Capsule is open for research and educational purposes with paper citation; competitions/commercial purposes need prior written permission. These terms do not establish permission to redistribute original frames through the public Capsule Review source or to reuse the project's own unlicensed code commercially. Verify any additional ethics/consent/data-transfer obligations with the data custodian. Do not copy original clinical images, metadata with individual identities, patient identifiers, or labels into this public repository.

## Eligibility gates to resolve *before* spending on external images or changing protocols

Each gate has status **unverified** until a written source/custodian answer or an access-controlled identity-only verification exists.

1. **Provenance and permitted use:** named source version, file identity/checksums, approved research purpose, any contractual/ethics restrictions, permitted storage, publication of nonidentifying aggregate findings and prohibition on public pixel redistribution.
2. **Independence and sample unit:** unique examination IDs, a verified patient-group mapping (including repeat examinations), institution/capsule-device metadata sufficient to assess externality and overlap; if patient mapping cannot be established, no patient-independent inference.
3. **Full source chronology:** ordered frames in a complete, source-verified examination or a prospectively defined complete review stream, explicit policy for dropped frames and unknown duration. No invented images, indices or elapsed time.
4. **Complete outcome ascertainment:** each eligible review position must have explicit binary blood-status coverage or independently adjudicated complete positive-event intervals with known assessment of gaps. A selected positive segment or sparse image catalogue cannot serve as complete ground truth. Missing means **unknown**, never negative.
5. **Ontology mapping:** determine whether expert-assessed visible fresh blood corresponds to the Galar blood annotation, whether hematin is included, and whether the mapping is medically defensible. No opportunistic inclusion of favorable categories or conversion of a positive image into a distinct lesion.
6. **Run definition and denominator:** the Galar +5 source-label stride is dataset-specific. An external native frame stride and any unavoidable annotation discontinuities must be prespecified and validated; runs must split at true source/label gaps. Harmonize the *meaning* of run recall without claiming the identical pixel/index protocol when acquisition differs.
7. **Analysis support:** identify positive-run examinations, zero-positive examinations and total independently grouped units through an outcome-concealed feasibility gate or an appropriately documented design sample. Predefine the analysis unit and sample-size rationale without selecting cases from observed held-out performance.
8. **Durable retention:** verify private archival capacity for original input bytes when legally possible, original frozen CNN package, per-frame predictions, exact-K queues, label access receipts, source hashes, independent audit, and checksum readback **before** expensive acquisition.
9. **Freeze and protection:** lock cohort, any label harmonization, preprocessing, score/policy implementations, identical within-case exact K, 10% primary, 25% secondary and all negative/undefined handling *before* analysis of external outcome values; store cryptographic pre-outcome commitment independently. No public GitHub Actions patient data.

**Go/no-go:** Proceed only if gates 1–9 pass and a dated final protocol is committed independently of external outcomes. Otherwise record **no eligible replication**, and pursue additional annotation/collaboration without substituting a noncomparable image-classification result.

## Priority questions for the Kvasir-Capsule custodians (not yet sent)

Official contact addresses listed by Simula: paalh@simula.no, steven@simula.no, michael@simula.no. No outreach was sent by this PR.

1. Are there complete frame-by-frame binary annotations for visible fresh blood (including examined negative frames) or interval boundaries throughout the original 43 videos beyond the published 47,238 labeled images? If not, could expert-reviewed exhaustive event boundaries be made available or developed for a separate study?
2. Are video IDs unique examinations, and can repeated exams from one individual be grouped under a deidentified patient key for independent evaluation? Are hospital/site and capsule platform fields available?
3. What are the canonical video/frame mapping rules, encoding/frame-drop behavior, and any known incomplete recordings? Which official version/hashes should be pinned?
4. How should 'Blood - fresh' and 'Blood - hematin' be interpreted relative to visible blood, active bleeding, and unknown frames? Can a clinician approve an outcome ontology for external replication before accessing labels?
5. Would the custodian permit locally run, noncommercial research evaluation of fixed original-CNN policies, private original-data retention and publication of non-identifying aggregate examination-level comparisons? Can available metadata be assessed without examining event outcomes first?

## Scientific boundary

The proposed replication is the **single next experiment**, not launched. The current Galar 11–20 primary result is score-bin minus uniform **−1.2668765 percentage points at 10%** across six positive-run examinations; its 25% **+9.5106442-point** secondary result is descriptive and heavily case-dependent. A new cohort must test that preexisting hypothesis, not be used to tune the previously frozen model, invent a new definition of truth, or advertise clinical sensitivity or reading-time savings.

Next artifact if source custodians confirm gates: finalize the separate [external replication design draft](EXTERNAL_REPLICATION_DESIGN_DRAFT_20261104.md) **before any label-bearing payload is opened**.
