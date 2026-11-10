# Capsule Review — blinded short-event clinical interpretation pilot (November 10, 2026 UTC)

**Deliverable:** actual local, offline, single-image blinded clinician-review instrument created and exercised on original verified Galar development images. **Current status:** `PREPARED_NOT_CLINICALLY_REVIEWED` — no expert annotation, clinician consensus, new pathology model, stronger AI performance or independent test result is claimed.

## Why this instrument exists

The locked Galar 11–20 10% run-retention comparison failed; subsequent fixed short-event CNN and frozen ImageNet MobileNet experiments showed persistent wrong decisions on **brief native-source positive annotation runs**. We do not know if those reflect genuine visually apparent fresh blood, old blood/hematin, lookalikes, unreadable frames or inter-reviewer ambiguity. Dataset-provided `blood` labels are not adjudicated lesion identities, and source runs are not unique clinical lesions. A dedicated interpretation pilot is the next useful **medical reference-standard acquisition step**, before additional model sweeps.

## Actual private-source pilot that was built

- Reused **all 69** distinct original-source short-positive-run / explicit-negative native-stride boundary comparisons on the already-inspected Galar development studies 23/25/29/30: **23/20/11/15** pairs, including **21 singleton runs**. There was **no selection based on observed CNN or MobileNet errors**.
- The 69 positive–negative pairs reference **137 unique original publisher PNGs**. All 137 endpoints were recovered from **six already retained** private image source packages. Each source package's entire-file SHA-256 was pinned and verified. Every selected original PNG's exact SHA-256 and byte count were checked against the old frozen source manifest; source exam/frame and native adjacency were enforced. **No new image acquisition**.
- Every reviewer image was re-encoded to strip possible PNG ancillary metadata while retaining *exactly identical 512×512 RGB pixels*, independently matched to the source originals. All 137 underwent a second, separate source-archive/pixel verification.
- The private reviewer ZIP contains one image at a time in a **globally randomized order**, with opaque image IDs only; neither pair grouping, original source frame/examination, source `blood` label, selected original `positive`/`negative` role, nor model scores are exposed. The source mapping and original labels are held in a distinct private unblinding-key ZIP, **not shared with reviewers**.
- The reviewer HTML/JS has no server component, network calls, trackers, CDNs or medical model execution. The CSP prohibits network connections. It allows separate `yes`/`no`/`uncertain` judgements for *fresh visible blood*, *hematin/old blood*, *suspected lookalike/artifact*, *temporal context needed*, and *image quality*, plus a short rationale. It exports only local, packet-specific pseudonymous JSON and can restore an export for continued review. No personal name or patient ID is requested.
- The public `audit_blinded_review_responses.py` checks **two independent, complete** pseudonymous exports, prohibits filling missing answers with negatives, reports per-field agreement and produces a **private opaque-ID disagreement register**. All differences and uncertain readings remain subject to subsequent qualified clinician arbitration. It **does not** generate a medical reference standard or inference accuracy automatically.

## Actual verification, and one operational limit

- **20 synthetic tests passed** for source role/adjacency, spoofed ZIP bytes/hashes, duplicate/missing source and blinded IDs, image pixel identity, response completeness, packet mismatch, reviewer independence and no clinical overclaim.
- Source-only browser instrumentation exercised the *actual shipped HTML/JS*: 137-item index, radio response fields, local JSON export, local response restore and navigation. This was done via DOM/script injection because **this execution sandbox blocks browser navigation to both `file://` and `http://127.0.0.1` URLs under its administrative policy**. Thus a normal user-machine file/localhost browser launch has **not** been end-to-end demonstrated here. That launch remains an acceptance gate before a clinician uses the instrument.
- Independently reverified **137/137** original-source RGB pixels, 69/69 original native stride-five pairs, 21/21 singleton run memberships, per-study counts and reviewer-key image identity. Private receipt seals the reviewer and escrow ZIP SHA-256 separately.
- No external clinical material or information was sent. The original medical-image reviewer ZIP and separate unblinding key remain **private**; do not commit or serve them through GitHub or public CI. The user's private Library accepted the key and text receipts but reported **storage quota exceeded for the ~25 MB image-bearing reviewer ZIP**. That ZIP is retained as a verified conversation attachment for user download; the user must save an additional durable private copy before external reviewer distribution.

## How to run the reusable tool (with authorized private inputs)

```bash
python scripts/build_blinded_short_event_review.py \
  --foundation-evidence-zip /private/Short_Event_Foundation_Private_Final_Evidence_20261109.zip \
  --archive /private/galar-exam23-verified-frames-private.zip \
  --archive /private/galar-exam25-verified-frames-private.zip \
  --archive /private/galar-exam29-verified-frames-private.zip \
  --archive /private/galar-exam30-verified-frames-private.zip \
  --archive /private/Short_Event_Foundation_New_Originals_20261109.zip \
  --archive /private/Local_Short_Event_New_Originals_20261109.zip \
  --archive-hashes-json /private/PRIVATE_PINNED_SOURCE_ARCHIVES.json \
  --output-dir /private/blinded-review-new
```

The generator refuses an existing destination and outputs `REVIEWER_BLINDED_ORIGINAL_IMAGES.zip`, `PRIVATE_UNBLINDING_KEY.zip`, and `PREPARATION_RECEIPT.json` **only in the private destination**. Before actual clinical use, **extract the reviewer ZIP locally**, open `index.html`, and verify images, controls and export. If a browser blocks local file scripts, from the extracted private directory use `python -m http.server 8766 --bind 127.0.0.1` and open `http://127.0.0.1:8766` locally; stop the server afterward and never bind externally. The browser application itself has no API or external requests.

After **two separate, qualified, complete** blinded reviews, the private comparison tool can identify disagreements without releasing source IDs:

```bash
python scripts/audit_blinded_review_responses.py \
  --reviewer-zip /private/REVIEWER_BLINDED_ORIGINAL_IMAGES.zip \
  --reader-a /private/reviewer-A.json --reader-b /private/reviewer-B.json \
  --output-private /private/DUAL_REVIEW_DISAGREEMENTS.json
```

## Scope, ethics, and advancement

This is an **interpretation/annotation feasibility pilot** sampled from *already inspected, deliberately label-enriched source-native positive–negative boundary images*. It is not representative of disease prevalence, a new independent test cohort, patient-independent validation, a prospective clinical review, or an event-detection benchmark. Reviewers see single images and may be unable to judge temporally continuous pathology; the `needs_context` answer captures that limitation rather than fabricating certainty. No clinician adjudications yet exist.

**Go/no-go before training:** obtain authorized qualified clinician review and independent arbitration of disagreements; establish source/patient grouping and intended disease ontology; then specify a genuinely new development/independent dataset and source-complete event-preservation protocol. Do not tune models or re-open the locked Galar 11–20 benchmark based on this pilot. Do not externally share clinical images before data-use, institutional and reviewer requirements are checked.

**Attribution:** Le Floch et al., *Galar — a large multi-label video capsule endoscopy dataset*, *Scientific Data* 12, 828 (2025), DOI: 10.1038/s41597-025-05112-7. Galar source licensed CC BY 4.0; acknowledge original authors. Dataset license does not establish clinical-study ethics approval.
