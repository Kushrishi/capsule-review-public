"""Independently reconstruct selection/omissions from a local review ZIP and study manifest.

This is an offline *engineering evidence-accounting* receipt: it never evaluates
clinical pathology or imports model predictions. Inputs may contain sensitive
research data; only non-identifying aggregates leave this function.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .interval_evidence import (
    _integer,
    _sha,
    _validate_intervals,
    _validate_selected,
    read_json,
    read_review_export,
)
from .source_coverage import summarize_source_spacing

MAX_IMPORT_POSITIONS = 200_000
MAX_REVIEW_EVENTS = 500_000


def _verify_complete_import_manifest(review: dict, manifest: dict) -> list[dict]:
    """Recompute the *importer* identity digest, not merely compare two pointers."""
    if not isinstance(review, dict) or review.get("application") != "capsule-review" or review.get("schema_version") != 1:
        raise ValueError("Unrecognized Capsule Review export schema.")
    study = review.get("study")
    if not isinstance(study, dict) or not isinstance(manifest, dict):
        raise ValueError("Missing complete private study manifest.")
    if manifest.get("schema_version") != 1 or not isinstance(study.get("id"), str) or not study["id"]:
        raise ValueError("Invalid study identity.")
    if study["id"] != manifest.get("study_id"):
        raise ValueError("Export belongs to a different imported study.")
    synthetic = manifest.get("synthetic")
    if type(synthetic) is not bool or review.get("synthetic") is not synthetic:
        raise ValueError("Synthetic source provenance disagrees with exported study.")
    if _sha(study.get("manifest_sha256"), "export identity") != _sha(
        manifest.get("manifest_sha256"), "local imported identity"
    ):
        raise ValueError("Export and local imported manifest checksums differ.")
    count = _integer(study.get("frame_count"), "imported count", minimum=1)
    frames = manifest.get("frames")
    if not isinstance(frames, list) or len(frames) != count or count > MAX_IMPORT_POSITIONS:
        raise ValueError("Incomplete or oversized local imported-image manifest.")
    source_names = set()
    identity = []
    for position, frame in enumerate(frames):
        if not isinstance(frame, dict) or frame.get("position") != position:
            raise ValueError("Study manifest has missing, duplicated or reordered positions.")
        source_index = frame.get("source_index")
        if source_index is not None:
            _integer(source_index, "source index")
        filename = frame.get("filename")
        if not isinstance(filename, str) or not filename or filename.casefold() in source_names:
            raise ValueError("Invalid or repeated imported image filename.")
        source_names.add(filename.casefold())
        source_hash = _sha(frame.get("source_sha256"), "imported original image")
        _sha(frame.get("display_sha256"), "imported converted image")
        identity.append({
            "position": position, "source_index": source_index,
            "filename": filename, "sha256": source_hash,
        })
    # This is the exact import_sources() source-identity serialization. It proves
    # the supplied manifest is *internally consistent with the export identity*;
    # it is not an independent rehash of unexported original image bytes.
    computed = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if computed != study["manifest_sha256"]:
        raise ValueError("Complete imported source-image identity manifest SHA-256 changed.")
    return frames


def _replay_reviewer_events(review: dict, imported_count: int) -> dict[int, dict]:
    history = review.get("review_history")
    if not isinstance(history, list) or len(history) > MAX_REVIEW_EVENTS:
        raise ValueError("Invalid or oversized saved-review audit trail.")
    latest: dict[int, dict] = {}
    for event in history:
        if not isinstance(event, dict):
            raise ValueError("Malformed saved-review event.")
        position = _integer(event.get("position"), "review event position")
        revision = _integer(event.get("revision"), "review event revision", minimum=1)
        if position >= imported_count or revision != latest.get(position, {}).get("revision", 0) + 1:
            raise ValueError("Saved-review event position or revision history is inconsistent.")
        content = event.get("content")
        if not isinstance(content, dict) or set(content) != {"revision", "bookmarked", "note", "label"}:
            raise ValueError("Malformed saved-review event content.")
        if content["revision"] != revision or type(content["bookmarked"]) is not bool:
            raise ValueError("Saved-review event revision or bookmark changed.")
        if not isinstance(content["note"], str) or not isinstance(content["label"], str):
            raise ValueError("Malformed saved-review event text.")
        when = event.get("created_at")
        if not isinstance(when, str) or not when:
            raise ValueError("Saved-review event time is missing.")
        latest[position] = {
            "revision": revision, "bookmarked": content["bookmarked"],
            "note": content["note"], "label": content["label"], "updated_at": when,
        }
    return latest


def _longest_run(positions: set[int]) -> int:
    maximum = count = 0
    previous = None
    for position in sorted(positions):
        count = count + 1 if previous is not None and position == previous + 1 else 1
        maximum = max(maximum, count)
        previous = position
    return maximum



def _position_coverage(total: int, selected_positions: set[int]) -> dict:
    """Nearest selected *imported positions*, not patient time/pathology."""
    if not selected_positions or min(selected_positions) < 0 or max(selected_positions) >= total:
        raise ValueError("Invalid selected positions for coverage analysis.")
    chosen = sorted(selected_positions)
    nearest = []
    cursor = 0
    for index in range(total):
        while cursor + 1 < len(chosen) and abs(chosen[cursor + 1] - index) < abs(chosen[cursor] - index):
            cursor += 1
        nearest.append(abs(chosen[cursor] - index))
    ordered = sorted(nearest)
    rank = (total - 1) * 0.95
    low = int(rank)
    p95 = ordered[low] + (rank - low) * (ordered[min(low + 1, total - 1)] - ordered[low])
    return {
        "mean_nearest_selected_imported_positions": round(sum(nearest) / total, 8),
        "percentile95_nearest_selected_imported_positions": round(p95, 8),
        "maximum_nearest_selected_imported_positions": max(nearest),
        "fraction_within_1_imported_position": round(sum(x <= 1 for x in nearest) / total, 8),
        "fraction_within_5_imported_positions": round(sum(x <= 5 for x in nearest) / total, 8),
    }


def _uniform_at_equal_workload(total: int, count: int) -> set[int]:
    """Deterministic label-blind midpoint selection, exactly count positions."""
    if not 1 <= count <= total:
        raise ValueError("Uniform reference must match the selected-image workload.")
    points = {(2 * i + 1) * total // (2 * count) for i in range(count)}
    if len(points) != count:
        raise ValueError("Unexpected duplicate uniform comparison position.")
    return points


def account_review_evidence(review: dict, manifest: dict) -> dict:
    """Validate imported identity + reviewer history and return aggregate-only counts.

    Caller must first validate export ZIP selected-image bytes with
    read_review_export(); this function never receives original images.
    """
    imported = _verify_complete_import_manifest(review, manifest)
    intervals, endpoints = _validate_intervals(review, imported)
    selected, saved = _validate_selected(review, imported, endpoints)
    latest = _replay_reviewer_events(review, len(imported))

    # An export's item list cannot omit a previously saved final review, insert
    # an unsupported save, or silently substitute an older note/bookmark state.
    actually_saved = {
        position for position, state in latest.items()
        if state["bookmarked"] or state["note"] or state["label"]
    }
    expected_selected = actually_saved | endpoints
    if selected != expected_selected or saved != actually_saved:
        raise ValueError("Selected export is incomplete or differs from final saved-review history.")
    for item in review["frames"]:
        position = item["position"]
        default = {"revision": 0, "bookmarked": False, "note": "",
                   "label": "", "updated_at": None}
        if item["review"] != latest.get(position, default):
            raise ValueError("Exported reviewer content disagrees with last audited revision.")

    interval_span: set[int] = set()
    interval_interior: set[int] = set()
    for interval in intervals:
        start, end = interval["start_position"], interval["end_position"]
        interval_span.update(range(start, end + 1))
        interval_interior.update(range(start + 1, end))
    omitted_interior = interval_interior - selected
    imported_count = len(imported)
    observed_indices = [row["source_index"] for row in imported]
    spacing = summarize_source_spacing(observed_indices)
    return {
        "schema_version": 1,
        "kind": "capsule-review-offline-export-evidence-accounting",
        "audit_passed": True,
        "original_import_manifest_identity_digest_recomputed": True,
        "selected_image_display_sha256_verified_by_zip_reader": True,
        "review_event_revisions_replayed": len(review.get("review_history", [])),
        "reviewer_interval_event_revisions_replayed": len(review.get("interval_history", [])),
        "imported_images": imported_count,
        "selected_export_images": len(selected),
        "selected_export_fraction_of_imported": round(len(selected) / imported_count, 8),
        "selected_position_coverage": _position_coverage(imported_count, selected),
        "uniform_reference_position_coverage_at_exact_same_workload": _position_coverage(
            imported_count, _uniform_at_equal_workload(imported_count, len(selected))
        ),
        "imported_images_not_selected_for_export": imported_count - len(selected),
        "explicitly_saved_images": len(saved),
        "interval_boundary_images": len(endpoints),
        "images_both_saved_and_interval_boundary": len(saved & endpoints),
        "images_only_selected_as_interval_boundary": len(endpoints - saved),
        "marked_image_intervals": len(intervals),
        "unique_imported_positions_in_marked_spans": len(interval_span),
        "unique_imported_interval_interior_positions": len(interval_interior),
        "interval_interior_images_not_exported": len(omitted_interior),
        "longest_consecutive_imported_position_gap_inside_intervals": _longest_run(omitted_interior),
        "numbered_imported_images": spacing["numbered_frames"],
        "observed_source_index_assessment": spacing["assessment"],
        "clinical_validity": False,
        "pathology_labels_or_run_recall_evaluated": False,
        "reader_time_savings_measured": False,
        "all_imported_source_image_bytes_rehashed": False,
        "original_full_video_completeness_verified": False,
        "interpretation": (
            "Only exact exported images are directly preserved in this package; "
            "marked interval interiors are NOT automatically exported. "
            "Neither selected images nor spans prove human inspection, pathology, "
            "diagnosis or full-video coverage. The uniform reference compares only ordinal "
            "imported-image distance at the exact same selected-image count; it has no "
            "pathology labels and does not estimate clinical sensitivity. Source IDs are not timestamps. "
            "This audit checks export integrity against the supplied private study "
            "manifest and its original importer digest, not independently acquired "
            "source pixels or external clinical labels."
        ),
    }


def audit_review_export_zip(*, review_zip: Path, study_manifest_path: Path,
                            output: Path) -> dict:
    """Validate ZIP content and locally paired manifest; save a new aggregate-only JSON."""
    if output.exists():
        raise FileExistsError("Refusing to overwrite an evidence audit receipt.")
    review = read_review_export(review_zip)
    manifest = read_json(study_manifest_path)
    receipt = account_review_evidence(review, manifest)
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        destination.write(encoded)
    return receipt
