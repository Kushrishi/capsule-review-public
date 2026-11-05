"""Audit published Kvasir-Capsule labelled-image *split CSVs* without reading pixels.

Use two locally downloaded upstream official_splits/split_{0,1}.csv files.
The result contains aggregate counts only: never filenames, frame indices or
video IDs. Published splits are NOT verified patient-disjoint partitions, and
selected annotated images are NOT exhaustive consecutive-video ground truth.

Example:
    python scripts/audit_kvasir_official_splits.py /private/split_0.csv /private/split_1.csv
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
import re

_FRAME = re.compile(r"(?P<video>[A-Za-z0-9]{1,128})_(?P<index>[0-9]{1,12})\.(?:jpg|jpeg|png)\Z", re.IGNORECASE)
_MAX_BYTES = 10 * 1024 * 1024
_MAX_ROWS = 100_000


def _read(path: Path) -> dict:
    """Fail closed on invalid identifiers, rows or repeated identical labels."""
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= _MAX_BYTES:
        raise ValueError("Invalid official split CSV input.")
    files: dict[tuple[str, int], set[str]] = defaultdict(set)
    labels: Counter[str] = Counter()
    label_videos: dict[str, set[str]] = defaultdict(set)
    videos: set[str] = set()
    total = 0
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        rows = csv.DictReader(source)
        if rows.fieldnames != ["filename", "label"]:
            raise ValueError("Unexpected Kvasir split CSV columns.")
        for row in rows:
            total += 1
            if total > _MAX_ROWS:
                raise ValueError("Too many rows in split file.")
            if not isinstance(row, dict) or set(row) != {"filename", "label"}:
                raise ValueError("Invalid split row.")
            filename, label = row["filename"], row["label"]
            if not isinstance(filename, str) or not isinstance(label, str) or not label or len(label) > 80:
                raise ValueError("Malformed source filename or category.")
            match = _FRAME.fullmatch(filename)
            if match is None:
                raise ValueError("Source image does not follow published video-frame naming convention.")
            video = match.group("video")
            key = (video, int(match.group("index")))
            if label in files[key]:
                raise ValueError("Repeated identical source frame/category row.")
            files[key].add(label)
            labels[label] += 1
            label_videos[label].add(video)
            videos.add(video)
    if total == 0:
        raise ValueError("Split file is empty.")
    return {"files": files, "labels": labels, "label_videos": label_videos,
            "videos": videos, "rows": total, "sha256": digest.hexdigest()}


def audit(first: Path, second: Path) -> dict:
    """Aggregate structural overlap; never publish the identifiers being compared."""
    if first.resolve() == second.resolve():
        raise ValueError("Two distinct official split files are required.")
    parts = (_read(first), _read(second))
    shared_frames = set(parts[0]["files"]) & set(parts[1]["files"])
    shared_videos = parts[0]["videos"] & parts[1]["videos"]
    labels = sorted(set(parts[0]["labels"]) | set(parts[1]["labels"]))
    category_rows = {key: sum(part["labels"][key] for part in parts) for key in labels}
    category_video_count = {key: len(set().union(*(part["label_videos"][key] for part in parts))) for key in labels}
    return {
        "schema_version": 1,
        "subject": "Kvasir-Capsule publisher labelled-image split CSVs only",
        "inputs": [
            {"sha256": p["sha256"], "rows": p["rows"],
             "unique_video_ids": len(p["videos"]),
             "unique_source_frame_ids": len(p["files"]),
             "extra_rows_for_already_seen_frame_ids": p["rows"] - len(p["files"])}
            for p in parts
        ],
        "combined_rows": sum(p["rows"] for p in parts),
        "combined_unique_video_ids": len(parts[0]["videos"] | parts[1]["videos"]),
        "combined_unique_source_frame_ids": len(set(parts[0]["files"]) | set(parts[1]["files"])),
        "shared_video_ids_across_files": len(shared_videos),
        "shared_source_frame_ids_across_files": len(shared_frames),
        "category_row_counts": category_rows,
        "category_distinct_video_counts": category_video_count,
        "eligible_for_patient_independent_study": False,
        "eligible_for_complete_event_recall": False,
        "clinical_validation": False,
        "interpretation": [
            "A nonzero shared_video_ids_across_files count blocks video-disjoint training/evaluation.",
            "No authenticated patient identifier or repeat-examination mapping was checked.",
            "Repeated frame IDs within a CSV can carry different labels; they are not automatically duplicate pixel files.",
            "A category named Blood is not a clinician-approved harmonization to Galar blood=1.",
            "Only selected annotated images are covered; absence from the CSV is UNKNOWN, not negative.",
            "The study remains blocked pending independent source, grouping, annotation and rights review.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split_0", type=Path)
    parser.add_argument("split_1", type=Path)
    args = parser.parse_args()
    try:
        summary = audit(args.split_0, args.split_1)
    except (ValueError, OSError, UnicodeError, csv.Error):
        parser.error("Official split CSV audit failed; verify the files locally. No source identifiers disclosed.")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
