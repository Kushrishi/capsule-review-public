"""Opt-in, disk-streamed full reviewer-interval evidence archive.

The standard illustrated review export remains boundary-only and unchanged.
This separate bundle includes every *imported* image in each active marked span,
plus any explicitly saved image outside them. Neither implies the source video
is complete or that these images were viewed or clinically interpreted.

Only synthetic fixtures may be used in public CI; original medical images,
review notes, and source manifests stay in the user's local workspace.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import zipfile

from .evidence_receipt import (
    _replay_reviewer_events,
    _verify_complete_import_manifest,
)
from .interval_evidence import _integer, _sha, _validate_intervals
from .importer import now
from .store import Store
from .suggestion_evidence import snapshot_suggestions

# These are operational safety limits for a localhost ZIP operation, NOT
# restrictions on review budgets or research policy.
MAX_FULL_IMAGES = 50_000
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024 * 1024


def _plan(intervals: list[dict], saved: set[int], *, saved_only: bool = False) -> tuple[set[int], set[int], set[int]]:
    """Union imported image positions; overlapping intervals never duplicate."""
    span: set[int] = set()
    boundaries: set[int] = set()
    for interval in intervals:
        start, end = interval["start_position"], interval["end_position"]
        span.update(range(start, end + 1))
        boundaries.update((start, end))
    return (saved if saved_only else saved | span), span, boundaries


def _summary(imported: list[dict], selected: set[int], saved: set[int],
             span: set[int], boundaries: set[int], intervals: list[dict],
             review_events: list[dict], *, saved_only: bool = False) -> dict:
    return {
        "kind": ("capsule-review-saved-image-evidence-receipt-v1" if saved_only else
                 "capsule-review-full-span-evidence-receipt-v1"),
        "audit_passed": True,
        "imported_images": len(imported),
        "exported_images": len(selected),
        "explicit_saved_images": len(saved),
        "marked_intervals": len(intervals),
        "retained_images_in_marked_spans": len(selected & span),
        "interval_interior_images_retained": len(selected & (span - boundaries)),
        "interval_boundaries_retained": len(selected & boundaries),
        "additional_images_beyond_boundary_only_export": len(selected - (saved | boundaries)),
        ("imported_images_not_in_saved_export" if saved_only else
         "imported_images_not_in_full_span_export"): len(imported) - len(selected),
        "review_event_revisions_replayed": len(review_events),
        "image_bytes_in_export_rehashed": len(selected),
        "all_original_source_png_bytes_rehashed": False,
        "all_original_video_frames_imported": False,
        "human_review_of_every_retained_image_verified": False,
        "pathology_labels_or_clinical_sensitivity_evaluated": False,
        "interpretation": (
            "Only explicitly saved images are retained. Marked intervals are context, "
            "not an instruction to include boundaries or interiors. This is not a workspace "
            "backup or evidence of human viewing, pathology or source-video completeness."
        ) if saved_only else (
            "Every retained *imported* image within active reviewer-marked spans is "
            "present in the ZIP, plus all explicitly saved images. These are not "
            "necessarily all frames from the original recorded examination. "
            "Retaining an image does not prove it was viewed or contains pathology. "
            "Source indices are not timestamps; no clinical sensitivity or time "
            "savings are measured. Exported normalized display PNG bytes are "
            "verified, not all original raw source bytes."
        ),
    }


def _local_snapshot(store: Store, study_id: str, *, saved_only: bool = False) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], dict]:
    with store.connect() as db:
        db.execute('BEGIN')
        study_row = db.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
        if study_row is None:
            raise ValueError("Examination does not exist.")
        study = dict(study_row)
        rows = [dict(row) for row in db.execute(
            "SELECT f.position,f.source_index,f.filename,f.source_sha256,f.display_sha256,"
            "COALESCE(r.revision,0) AS revision, COALESCE(r.bookmarked,0) AS bookmarked,"
            "COALESCE(r.note,'') AS note, COALESCE(r.label,'') AS label,r.updated_at "
            "FROM frames f LEFT JOIN reviews r ON r.study_id=f.study_id AND r.position=f.position "
            "WHERE f.study_id=? ORDER BY f.position", (study_id,)
        )]
        intervals = [dict(row) for row in db.execute(
            "SELECT i.id,i.start_position,i.end_position,i.note,i.created_at,"
            "a.source_index AS start_source_index,b.source_index AS end_source_index "
            "FROM review_intervals i "
            "JOIN frames a ON a.study_id=i.study_id AND a.position=i.start_position "
            "JOIN frames b ON b.study_id=i.study_id AND b.position=i.end_position "
            "WHERE i.study_id=? ORDER BY i.start_position,i.end_position,i.id", (study_id,)
        )]
        events = [dict(row) for row in db.execute(
            "SELECT position,revision,content,created_at FROM review_events "
            "WHERE study_id=? ORDER BY id", (study_id,)
        )]
        interval_history = [dict(row) for row in db.execute(
            "SELECT interval_id,action,start_position,end_position,note,created_at "
            "FROM review_interval_events WHERE study_id=? ORDER BY id", (study_id,)
        )]
        saved = {row['position'] for row in rows if row['bookmarked'] or row['note'] or row['label']}
        chosen, _, _ = _plan(intervals, saved, saved_only=saved_only)
        suggestions = snapshot_suggestions(db, study_id, chosen)
    events = [{**event, "content": json.loads(event["content"])} for event in events]
    return study, rows, intervals, events, interval_history, suggestions


def _source_manifest(study: dict, rows: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "study_id": study["id"],
        "manifest_sha256": study["manifest_sha256"],
        "synthetic": bool(study["synthetic"]),
        "frames": [{
            "position": row["position"], "source_index": row["source_index"],
            "filename": row["filename"], "source_sha256": row["source_sha256"],
            "display_sha256": row["display_sha256"],
        } for row in rows],
    }


def export_full_span_evidence(store: Store, study_id: str, output: Path) -> dict:
    return _export_evidence(store, study_id, output, saved_only=False)


def export_saved_evidence(store: Store, study_id: str, output: Path) -> dict:
    """Stream only explicitly saved images; intervals remain unexpanded context."""
    return _export_evidence(store, study_id, output, saved_only=True)


def _export_evidence(store: Store, study_id: str, output: Path, *, saved_only: bool) -> dict:
    """Create a **new** opt-in ZIP on local disk; fail closed and never overwrite."""
    label = "Saved-image" if saved_only else "Full-span"
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing full-span archive.")
    study, rows, intervals, events, interval_history, suggestions = _local_snapshot(store, study_id, saved_only=saved_only)
    saved = {row["position"] for row in rows
             if row["bookmarked"] or row["note"] or row["label"]}
    chosen, span, endpoints = _plan(intervals, saved, saved_only=saved_only)
    if not saved_only and not intervals:
        raise ValueError("Mark at least one image interval to export full spans.")
    if not chosen:
        raise ValueError("Save at least one image to export saved evidence.")
    if len(chosen) > MAX_FULL_IMAGES:
        raise ValueError(f"{label} selection exceeds the local 50,000-image safety bound.")

    complete = _source_manifest(study, rows)
    record = {
        "schema_version": 1,
        "application": "capsule-review",
        "kind": "saved-image-evidence" if saved_only else "full-imported-span-evidence",
        "selection": ("explicitly saved images only; intervals are context, not expanded" if saved_only else
                      "all imported images in active marked intervals plus explicitly saved images"),
        "exported_at": now(),
        "synthetic": bool(study["synthetic"]),
        "study": {key: study[key] for key in (
            "id", "title", "source", "frame_count", "manifest_sha256"
        )},
        "frames": [], "model_suggestions": suggestions,
        "intervals": intervals,
        "review_history": events,
        "interval_history": interval_history,
        "caveat": ("Saved imported images only; not a workspace backup, clinical finding or "
                   "proof of human viewing.") if saved_only else ("Full imported image spans are retained, not necessarily all original video "
                   "frames; no human viewing, pathology detection or time savings inferred."),
    }
    # The compact HTML is a navigator for the unpacked ZIP; it intentionally
    # does not base64-embed possibly thousands of private images.
    cards = []
    count_bytes = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for row in rows:
                position = row["position"]
                if position not in chosen:
                    continue
                relative = f"images/frame_{position:06d}.png"
                reason = {
                    "explicit_saved": position in saved,
                    "interval_boundary": position in endpoints,
                    "marked_span_interior": position in span - endpoints,
                }
                item = {
                    "position": position, "source_index": row["source_index"],
                    "source_filename": row["filename"],
                    "source_sha256": row["source_sha256"],
                    "display_sha256": row["display_sha256"],
                    "image": relative, "reason": reason,
                    "review": {
                        "revision": row["revision"], "bookmarked": bool(row["bookmarked"]),
                        "note": row["note"], "label": row["label"], "updated_at": row["updated_at"],
                    },
                }
                path = store.images / study_id / f"{position}.png"
                size = path.stat().st_size
                if size > MAX_IMAGE_BYTES or size <= 0 or count_bytes + size > MAX_TOTAL_IMAGE_BYTES:
                    raise ValueError(f"{label} image exceeds the local per-image or 8-GiB safety limit.")
                digest = hashlib.sha256()
                with path.open("rb") as source, archive.open(relative, "w", force_zip64=True) as destination:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        destination.write(chunk)
                if digest.hexdigest() != _sha(row["display_sha256"], "stored normalized display image"):
                    raise ValueError("Local normalized display image SHA-256 does not match its import identity.")
                count_bytes += size
                record["frames"].append(item)
                label = html.escape(row["label"] or (
                    "Saved frame" if position in saved else
                    "Interval boundary" if position in endpoints else "Included span image"
                ))
                cards.append(
                    f'<li><a href="{relative}">Imported frame {position + 1}</a>'
                    f' · {label}</li>'
                )
            if len(record["frames"]) != len(chosen):
                raise ValueError("Local study image positions changed during full-span export.")
            heading = "Explicitly saved-image evidence" if saved_only else "Full marked-image-span evidence"
            retention = ("Only explicitly saved images are included; marked intervals are context, not expanded. "
                         if saved_only else "Every imported image in marked intervals is included, plus saved images outside them. ")
            html_page = (
                '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta http-equiv="Content-Security-Policy" content="default-src '
                "&apos;none&apos;; style-src &apos;unsafe-inline&apos;; img-src &apos;self&apos;; "
                'base-uri &apos;none&apos;; form-action &apos;none&apos;">'
                f'<title>Capsule Review {label.lower()} evidence</title>'
                '<style>body{font:15px/1.6 system-ui,sans-serif;max-width:900px;'
                'margin:35px auto;padding:0 24px;color:#16353c}li{margin:6px 0}'
                'a{color:#075f65}small{color:#516970}</style></head><body>'
                f'<h1>{heading}</h1>'
                '<p><strong>Extract the entire ZIP before opening this index.</strong> '
                f'{retention}'
                'Images were not necessarily viewed by a person. This is NOT a complete original '
                'video, diagnosis or measurement of sensitivity.</p>'
                f'<p>{len(record["frames"])} exported images in '
                f'{len(intervals)} marked intervals; '
                f'{study["frame_count"]} images in the local study.</p>'
                '<p><small>Source frame IDs are not capture timestamps. '
                'Review notes, source identifiers and separate imported model suggestions/provenance are stored in evidence.json. '
                'Do not publish this private archive.</small></p>'
                '<ol>' + "".join(cards) + '</ol></body></html>'
            )
            archive.writestr("index.html", html_page)
            metadata = json.dumps(record, indent=2, ensure_ascii=False)
            if len(metadata.encode('utf-8')) > MAX_MANIFEST_BYTES:
                raise ValueError(f'{label} metadata exceeds its verification limit.')
            archive.writestr("evidence.json", metadata)
        # Independently reopen and checksum the *actual ZIP bytes* before serving.
        verifier = verify_saved_evidence if saved_only else verify_full_span_evidence
        return verifier(output, complete)
    except Exception:
        output.unlink(missing_ok=True)
        raise


def verify_full_span_evidence(path: Path, source_manifest: dict) -> dict:
    return _verify_evidence(path, source_manifest, saved_only=False)


def verify_saved_evidence(path: Path, source_manifest: dict) -> dict:
    return _verify_evidence(path, source_manifest, saved_only=True)


def _verify_evidence(path: Path, source_manifest: dict, *, saved_only: bool) -> dict:
    """Independently validate the archive and a trusted local complete manifest."""
    label = "Saved-image" if saved_only else "Full-span"
    if not path.is_file():
        raise ValueError("Missing full-span evidence archive.")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if len(names) != len(set(names)) or not {"evidence.json", "index.html"} <= set(names):
            raise ValueError(f"{label} evidence ZIP members are missing or repeated.")
        metadata = archive.getinfo("evidence.json")
        page = archive.getinfo("index.html")
        if metadata.file_size > MAX_MANIFEST_BYTES or page.file_size > MAX_MANIFEST_BYTES:
            raise ValueError(f"{label} evidence metadata is oversized.")
        record = json.loads(archive.read("evidence.json"))
        if not isinstance(record, dict) or record.get("kind") != ("saved-image-evidence" if saved_only else "full-imported-span-evidence"):
            raise ValueError(f"Not a Capsule Review {label.lower()} evidence archive.")
        if record.get("selection") != ("explicitly saved images only; intervals are context, not expanded" if saved_only else
                                       "all imported images in active marked intervals plus explicitly saved images"):
            raise ValueError(f"{label} retention policy does not match the verified format.")
        imported = _verify_complete_import_manifest(record, source_manifest)
        intervals, endpoints = _validate_intervals(record, imported)
        latest = _replay_reviewer_events(record, len(imported))
        saved = {position for position, review in latest.items()
                 if review["bookmarked"] or review["note"] or review["label"]}
        chosen, span, boundaries = _plan(intervals, saved, saved_only=saved_only)
        if boundaries != endpoints or len(chosen) > MAX_FULL_IMAGES:
            raise ValueError(f"{label} evidence selection is inconsistent.")
        frames = record.get("frames")
        if not isinstance(frames, list) or len(frames) != len(chosen):
            raise ValueError(f"{label} archive omitted one or more required imported images.")
        if len(frames) > len(imported):
            raise ValueError("Exported selection cannot exceed imported frame count.")
        expected = {"index.html", "evidence.json"}
        accumulated = 0
        previous = -1
        for frame in frames:
            if not isinstance(frame, dict):
                raise ValueError("Malformed retained frame.")
            position = _integer(frame.get("position"), "retained imported image position")
            if position <= previous or position not in chosen:
                raise ValueError("Unexpected or duplicate full-span retained frame.")
            previous = position
            original = imported[position]
            if any(frame.get(key) != original[source] for key, source in (
                ("source_index", "source_index"), ("source_filename", "filename"),
                ("source_sha256", "source_sha256"), ("display_sha256", "display_sha256")
            )):
                raise ValueError("Retained image source identity does not match trusted import.")
            if frame.get("reason") != {
                "explicit_saved": position in saved,
                "interval_boundary": position in boundaries,
                "marked_span_interior": position in span - boundaries,
            }:
                raise ValueError(f"{label} retention reason has been altered.")
            default = {"revision": 0, "bookmarked": False, "note": "",
                       "label": "", "updated_at": None}
            if frame.get("review") != latest.get(position, default):
                raise ValueError("Retained frame review differs from final saved history.")
            relative = f"images/frame_{position:06d}.png"
            if frame.get("image") != relative:
                raise ValueError("Retained image path was modified.")
            info = archive.getinfo(relative)
            if info.file_size <= 0 or info.file_size > MAX_IMAGE_BYTES:
                raise ValueError("Retained image exceeds per-image safety bound.")
            expected.add(relative)
            digest = hashlib.sha256()
            with archive.open(info) as source:
                while chunk := source.read(1024 * 1024):
                    accumulated += len(chunk)
                    if accumulated > MAX_TOTAL_IMAGE_BYTES:
                        raise ValueError(f"{label} archive exceeds local image size limit.")
                    digest.update(chunk)
            if digest.hexdigest() != _sha(frame.get("display_sha256"), "verified exported display image"):
                raise ValueError(f"{label} exported PNG hash mismatch.")
        if set(names) != expected:
            raise ValueError("Extra or missing members in full-span evidence ZIP.")
        if len(chosen) != len(frames) or {frame["position"] for frame in frames} != chosen:
            raise ValueError("Archive contains only a subset of marked imported span images.")
    return _summary(imported, chosen, saved, span, boundaries, intervals, record["review_history"], saved_only=saved_only)
