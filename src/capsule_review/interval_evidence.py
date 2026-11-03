"""Source-verified, aggregate-only evidence audit for exported reviewer intervals.

This evaluates explicitly selected original image positions separately from numeric
annotation spans that were only marked as reviewer intervals. The latter never
counts as directly seen pathology, a lesion or a source-video sensitivity metric.

The clinical source files, image manifests, notes and frame IDs stay private.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

OFFICIAL_LABELS_SHA256 = "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
ALLOWED_EXAMINATIONS = frozenset(range(21, 31))
ORIGINAL_ANNOTATION_STEP = 5
MAX_REVIEW_IMAGE_BYTES = 128 * 1024 * 1024
SHA_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
STRATA = ("1-5", "6-25", "26+")


def _integer(value, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"Invalid {name}.")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or SHA_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Invalid {name} SHA-256.")
    return value


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path: Path, *, max_bytes: int = 32 * 1024 * 1024) -> object:
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("Missing or oversized local JSON input.")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_corrected_source_rows(raw: bytes) -> list[dict]:
    """Decode one allowlisted corrected Galar CSV; preserve unknown labels."""
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Corrected annotation CSV exceeds the source limit.")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    names = reader.fieldnames or []
    if len(names) != len(set(names)) or not {"frame", "blood"} <= set(names):
        raise ValueError("Unexpected corrected Galar annotation columns.")
    records = []
    previous = -1
    stride = Counter()
    for record in reader:
        if None in record or not isinstance(record.get("frame"), str) or not record["frame"].isdigit():
            raise ValueError("Invalid or missing original annotated source position.")
        frame = int(record["frame"])
        if frame <= previous or record.get("blood") not in ("0", "1", ""):
            raise ValueError("Invalid source order or unknown annotation encoding.")
        if previous >= 0:
            stride[frame - previous] += 1
        records.append({"frame": frame, "blood": record["blood"]})
        previous = frame
    if len(records) < 2 or stride[ORIGINAL_ANNOTATION_STEP] / (len(records) - 1) < .95:
        raise ValueError("Corrected Galar original source index stride is unsupported.")
    if stride.most_common(1)[0][0] != ORIGINAL_ANNOTATION_STEP:
        raise ValueError("Corrected source stride mode differs from the frozen protocol.")
    return records


def load_official_source(labels_zip: Path, exam: int) -> list[dict]:
    if type(exam) is not int or exam not in ALLOWED_EXAMINATIONS:
        raise ValueError("Only allowlisted original Galar fitting examinations 21–30 may be evaluated.")
    if sha256_file(labels_zip) != OFFICIAL_LABELS_SHA256:
        raise ValueError("The official corrected Galar annotation archive SHA-256 changed.")
    # Never iterate the full ZIP's CRC: read/CRC-check only the named permitted entry.
    with zipfile.ZipFile(labels_zip) as source:
        info = source.getinfo(f"{exam}.csv")
        if info.file_size > 32 * 1024 * 1024:
            raise ValueError("Selected corrected source member is oversized.")
        data = source.read(info)
    return parse_corrected_source_rows(data)


def segment_positive_runs(source_rows: list[dict]) -> tuple[list[dict], dict[int, int]]:
    """Split runs at every nonpositive row or source-index discontinuity."""
    runs: list[dict] = []
    membership: dict[int, int] = {}
    current: list[int] = []
    last_source: int | None = None

    def flush() -> None:
        if not current:
            return
        size = len(current)
        index = len(runs)
        runs.append({"frames": tuple(current), "stratum": "1-5" if size <= 5 else "6-25" if size <= 25 else "26+"})
        for frame in current:
            membership[frame] = index
        current.clear()

    previous = -1
    for row in source_rows:
        frame = _integer(row.get("frame"), "source annotation frame")
        blood = row.get("blood")
        if frame <= previous or blood not in ("0", "1", ""):
            raise ValueError("Malformed corrected Galar annotations.")
        if current and (blood != "1" or last_source is None or frame - last_source != ORIGINAL_ANNOTATION_STEP):
            flush()
        if blood == "1":
            current.append(frame)
        last_source = frame
        previous = frame
    flush()
    return runs, membership


def read_review_export(path: Path) -> dict:
    """Validate locally exported evidence ZIP; never execute/render the HTML."""
    if not path.is_file() or path.stat().st_size > 400 * 1024 * 1024:
        raise ValueError("Missing or oversized local Capsule Review export.")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(names) != len(set(names)) or not {"review.json", "review.html"} <= set(names):
            raise ValueError("Review export members are missing or duplicated.")
        if archive.getinfo("review.json").file_size > 32 * 1024 * 1024:
            raise ValueError("Review JSON is oversized.")
        if archive.getinfo("review.html").file_size > 180 * 1024 * 1024:
            raise ValueError("Review illustration is oversized.")
        review = json.loads(archive.read("review.json"))
        if not isinstance(review, dict) or review.get("schema_version") != 1 or review.get("application") != "capsule-review":
            raise ValueError("Unrecognized Capsule Review export format.")
        frames = review.get("frames")
        if not isinstance(frames, list) or len(frames) > 250:
            raise ValueError("Unexpected number of exported selected frames.")
        expected = {"review.json", "review.html"}
        total = 0
        for record in frames:
            if not isinstance(record, dict):
                raise ValueError("Malformed exported image entry.")
            position = _integer(record.get("position"), "selected image position")
            name = f"images/frame_{position:06d}.png"
            if record.get("image") != name or name in expected:
                raise ValueError("Exported image path or identity changed.")
            expected.add(name)
            info = archive.getinfo(name)
            if info.file_size > 32 * 1024 * 1024:
                raise ValueError("Exported image exceeds the per-image limit.")
            raw = archive.read(info)
            total += len(raw)
            if total > MAX_REVIEW_IMAGE_BYTES or hashlib.sha256(raw).hexdigest() != _sha(record.get("display_sha256"), "exported display image"):
                raise ValueError("Export image SHA-256 or image budget mismatch.")
        if set(names) != expected:
            raise ValueError("Extra or unlisted members in local review export.")
    return review


def _validate_study_manifest(review: dict, study_manifest: dict) -> list[dict]:
    study = review.get("study")
    if not isinstance(study, dict) or not isinstance(study_manifest, dict):
        raise ValueError("Missing local study manifest.")
    if (study_manifest.get("schema_version") != 1 or study_manifest.get("synthetic") is not False
        or not isinstance(study.get("id"), str) or study.get("id") != study_manifest.get("study_id")
        or _sha(study.get("manifest_sha256"), "exported study manifest") != _sha(study_manifest.get("manifest_sha256"), "local study manifest")):
        raise ValueError("Export and local study manifest identities do not match.")
    n = _integer(study.get("frame_count"), "study frame count", minimum=1)
    frames = study_manifest.get("frames")
    if not isinstance(frames, list) or len(frames) != n or n > 200_000:
        raise ValueError("Complete local imported-image manifest is missing or oversized.")
    prev_index = -1
    for position, row in enumerate(frames):
        if not isinstance(row, dict) or row.get("position") != position:
            raise ValueError("Imported source positions were reordered or duplicated.")
        idx = _integer(row.get("source_index"), "imported source frame")
        if idx <= prev_index:
            raise ValueError("Source IDs must be known, unique, and strictly increasing.")
        _sha(row.get("source_sha256"), "original imported image")
        _sha(row.get("display_sha256"), "converted imported image")
        if not isinstance(row.get("filename"), str) or not row["filename"]:
            raise ValueError("Imported source filename is malformed.")
        prev_index = idx
    return frames


def _validate_private_source_receipt(source_receipt: list[dict], imported: list[dict],
                                     rows: list[dict], exam: int) -> None:
    if not isinstance(source_receipt, list) or len(source_receipt) < len(imported) or len(source_receipt) > 300_000:
        raise ValueError("Invalid previously verified private original-source manifest.")
    private_by_frame = {}
    private_hashes = set()
    labels = {r["frame"]: r["blood"] for r in rows}
    for row in source_receipt:
        if not isinstance(row, dict) or row.get("exam") != exam:
            raise ValueError("Private original-source manifest has a different examination.")
        frame = _integer(row.get("frame"), "private source frame")
        if frame in private_by_frame:
            raise ValueError("Duplicate source image in private verified manifest.")
        original = _sha(row.get("source_image_sha256"), "private original image")
        if original in private_hashes:
            raise ValueError("Duplicate original PNG byte identity in the verified private manifest.")
        private_hashes.add(original)
        _integer(row.get("source_bytes"), "original image byte length", minimum=1)
        if row.get("blood") not in (0, 1) or labels.get(frame) != str(row["blood"]):
            raise ValueError("Private manifest does not match corrected source blood annotation.")
        if row.get("reference_uniform") not in (0, 1) or row.get("fit_enriched") not in (0, 1):
            raise ValueError("Private source image selection role changed.")
        private_by_frame[frame] = (original, row)
    for frame in imported:
        source_idx = frame["source_index"]
        found = private_by_frame.get(source_idx)
        if found is None or found[0] != frame["source_sha256"]:
            raise ValueError("Imported frame has no matching source-verified original PNG identity.")
        if found[1]["reference_uniform"] != 1:
            raise ValueError("Only the frozen label-blind reference selection is eligible for evaluation.")
        if found[1].get("filename") and frame["filename"] != found[1]["filename"]:
            raise ValueError("Private original filename and imported filename differ.")


def _validate_intervals(review: dict, imported: list[dict]) -> tuple[list[dict], set[int]]:
    intervals = review.get("intervals")
    history = review.get("interval_history")
    if not isinstance(intervals, list) or not isinstance(history, list) or len(intervals) > 100 or len(history) > 100_000:
        raise ValueError("Invalid or oversized reviewer interval record.")
    ids = set()
    pairs = set()
    endpoints: set[int] = set()
    for interval in intervals:
        if not isinstance(interval, dict):
            raise ValueError("Malformed reviewer interval.")
        ident = _integer(interval.get("id"), "reviewer interval identity", minimum=1)
        start = _integer(interval.get("start_position"), "interval start position")
        end = _integer(interval.get("end_position"), "interval end position")
        if ident in ids or (start, end) in pairs or start >= end or end >= len(imported):
            raise ValueError("Duplicate or out-of-range reviewer interval.")
        if interval.get("start_source_index") != imported[start]["source_index"] or interval.get("end_source_index") != imported[end]["source_index"]:
            raise ValueError("Reviewer interval source IDs do not match imported source metadata.")
        if not isinstance(interval.get("note"), str):
            raise ValueError("Invalid reviewer interval note.")
        ids.add(ident)
        pairs.add((start, end))
        endpoints.update((start, end))
    creation = {}
    deletion = set()
    for event in history:
        if not isinstance(event, dict) or event.get("action") not in ("created", "deleted"):
            raise ValueError("Malformed reviewer interval audit trail.")
        ident = _integer(event.get("interval_id"), "interval event ID", minimum=1)
        start = _integer(event.get("start_position"), "audited interval start")
        end = _integer(event.get("end_position"), "audited interval end")
        if start >= end or end >= len(imported) or not isinstance(event.get("note"), str):
            raise ValueError("Invalid reviewer interval history record.")
        details = (start, end, event["note"])
        if event["action"] == "created":
            if ident in creation:
                raise ValueError("Repeated interval creation in source audit trail.")
            creation[ident] = details
        else:
            if ident not in creation or ident in deletion or details != creation[ident]:
                raise ValueError("Invalid or duplicate reviewer interval deletion event.")
            deletion.add(ident)
    for interval in intervals:
        details = (interval["start_position"], interval["end_position"], interval["note"])
        if creation.get(interval["id"]) != details or interval["id"] in deletion:
            raise ValueError("Active reviewer interval is not supported by its immutable event trail.")
    return intervals, endpoints


def _validate_selected(review: dict, imported: list[dict], endpoints: set[int]) -> tuple[set[int], set[int]]:
    saved = set()
    selected = set()
    frames = review.get("frames")
    if not isinstance(frames, list):
        raise ValueError("Exported selected-frame collection is malformed.")
    for record in frames:
        position = _integer(record.get("position"), "selected frame position")
        if position >= len(imported) or position in selected:
            raise ValueError("Export includes duplicate or invalid selected frame positions.")
        imported_row = imported[position]
        if (record.get("source_index") != imported_row["source_index"] or
            record.get("source_sha256") != imported_row["source_sha256"] or
            record.get("display_sha256") != imported_row["display_sha256"] or
            record.get("source_filename") != imported_row["filename"]):
            raise ValueError("Selected export image does not match verified imported source image.")
        if record.get("interval_boundary") is not (position in endpoints):
            raise ValueError("Exported image interval-boundary membership was changed.")
        reviewer = record.get("review")
        if not isinstance(reviewer, dict) or type(reviewer.get("bookmarked")) is not bool or not isinstance(reviewer.get("note"), str) or not isinstance(reviewer.get("label"), str):
            raise ValueError("Invalid explicit reviewer saved-frame record.")
        explicit = bool(reviewer["bookmarked"] or reviewer["note"] or reviewer["label"])
        if explicit:
            saved.add(position)
        if not explicit and position not in endpoints:
            raise ValueError("Unselected image was inserted into exported review.")
        selected.add(position)
    if not endpoints <= selected:
        raise ValueError("Reviewer interval boundaries were not included as selected export images.")
    return selected, saved


def _run_fraction(number: int, denominator: int) -> float | None:
    return round(number / denominator, 8) if denominator else None


def evaluate_interval_evidence(review: dict, study_manifest: dict, source_receipt: list[dict],
                               source_rows: list[dict], *, exam: int) -> dict:
    """Return only nonidentifying counts. Caller must source-verify all inputs."""
    if type(exam) is not int or exam not in ALLOWED_EXAMINATIONS:
        raise ValueError("Reserved, historical, or unapproved Galar examination.")
    imported = _validate_study_manifest(review, study_manifest)
    runs, frame_run = segment_positive_runs(source_rows)
    _validate_private_source_receipt(source_receipt, imported, source_rows, exam)
    intervals, endpoints = _validate_intervals(review, imported)
    selected, saved = _validate_selected(review, imported, endpoints)
    label_by_frame = {row["frame"]: row["blood"] for row in source_rows}
    # All reference frames require an exact explicit annotation (0/1); unknown
    # is never silently classified as 0 in an image-hit denominator.
    if any(label_by_frame.get(row["source_index"]) not in ("0", "1") for row in imported):
        raise ValueError("A verified reference image has an unknown or absent source label.")

    def positive_runs_for_positions(positions: set[int]) -> set[int]:
        return {
            frame_run[imported[pos]["source_index"]]
            for pos in positions
            if imported[pos]["source_index"] in frame_run
        }

    imported_run_ids = positive_runs_for_positions(set(range(len(imported))))
    selected_run_ids = positive_runs_for_positions(selected)
    saved_run_ids = positive_runs_for_positions(saved)
    endpoint_run_ids = positive_runs_for_positions(endpoints)
    overlaps = set()
    for interval in intervals:
        left = imported[interval["start_position"]]["source_index"]
        right = imported[interval["end_position"]]["source_index"]
        for run_id, run in enumerate(runs):
            frames = run["frames"]
            spot = bisect_left(frames, left)
            if spot < len(frames) and frames[spot] <= right:
                overlaps.add(run_id)

    total_positive_selected = sum(
        imported[i]["source_index"] in frame_run for i in selected
    )
    total_positive_imported = sum(
        row["source_index"] in frame_run for row in imported
    )
    strata = []
    for key in STRATA:
        members = {idx for idx, run in enumerate(runs) if run["stratum"] == key}
        strata.append({
            "source_annotation_run_length": key,
            "full_source_annotation_runs": len(members),
            "imported_representable_runs": len(imported_run_ids & members),
            "direct_selected_export_runs": len(selected_run_ids & members),
            "span_overlapped_runs": len(overlaps & members),
            "span_overlap_without_selected_evidence": len((overlaps - selected_run_ids) & members),
        })

    return {
        "schema_version": 1,
        "study_type": "exploratory-local-source-verified-Galar-reviewer-interval-evidence-audit",
        "examination_id": exam,
        "source_annotation_rows": len(source_rows),
        "source_blood_positive_rows": len(frame_run),
        "source_positive_annotation_runs": len(runs),
        "imported_reference_images": len(imported),
        "imported_positive_annotated_images": total_positive_imported,
        "imported_representable_positive_runs": len(imported_run_ids),
        "selected_export_images": len(selected),
        "selected_export_positive_images": total_positive_selected,
        "direct_selected_positive_annotation_runs": len(selected_run_ids),
        "direct_selected_source_run_fraction": _run_fraction(len(selected_run_ids), len(runs)),
        "explicit_bookmark_or_note_selected_images": len(saved),
        "explicit_bookmark_or_note_positive_annotation_runs": len(saved_run_ids),
        "interval_boundary_images": len(endpoints),
        "interval_boundary_positive_annotation_runs": len(endpoint_run_ids),
        "reviewer_marked_image_intervals": len(intervals),
        "span_overlapped_source_positive_runs": len(overlaps),
        "span_overlapped_without_direct_selected_evidence": len(overlaps - selected_run_ids),
        "selected_workload_fraction_of_imported": _run_fraction(len(selected), len(imported)),
        "source_run_length_strata": strata,
        "source_provenance": {
            "official_corrected_labels_sha256": OFFICIAL_LABELS_SHA256,
            "private_verified_original_source_manifest_matched": True,
            "all_imported_images_from_label_blind_reference": True,
            "selected_export_display_images_rehashed": True,
            "original_source_png_pixel_bytes_not_rehashed_in_this_audit": True,
            "protected_source_examinations_read": False,
        },
        "clinical_validity": False,
        "interpretation": (
            "Direct runs require a verified selected blood=1 original image. "
            "Numerically overlapped annotation rows inside reviewer-marked source-ID spans "
            "are NOT reviewed images, diagnosed lesions, or capture-time/clinical sensitivity. "
            "Distinct source exams are not verified independent patients; the input is sparse."
        ),
    }


def evaluate_private_galar_export(*, review_zip: Path, study_manifest_path: Path,
                                  verified_source_manifest_path: Path,
                                  corrected_labels_zip: Path, exam: int,
                                  output: Path) -> dict:
    if output.exists():
        raise FileExistsError("Refusing to overwrite the private audit aggregate.")
    # Evaluate the official SHA-matched source only. There is intentionally no
    # public bypass flag for evaluation of reserved examinations or synthetic
    # labels via the command-line interface.
    source_rows = load_official_source(corrected_labels_zip, exam)
    review = read_review_export(review_zip)
    study = read_json(study_manifest_path)
    verified = read_json(verified_source_manifest_path)
    result = evaluate_interval_evidence(review, study, verified, source_rows, exam=exam)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result
