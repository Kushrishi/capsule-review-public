"""Audit whether real Galar image checkpoints support a *dense-video* experiment.

The audit uses the frozen individual-image identity manifest, not predictions or
labels to select cases. It deliberately does not infer physical frame adjacency
from filenames or assume that annotation-index spacing is video-frame spacing.

Example:
  python scripts/sequence_readiness.py --manifest /private/manifest.json \
      --images /private/images --output /tmp/sequence-readiness.json

Only aggregate counts are returned. Neither frame identities nor patient images
belong in the Git repository. An absent images directory is **not** verification.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import statistics
import sys

_RECORD_PATH = re.compile(r"^(\d{3})/frame_(\d+)\.PNG$")
_HEX_SHA = re.compile(r"^[0-9a-f]{64}$")
_MAX_FRAME_BYTES = 32 * 1024 * 1024
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ReadinessError(ValueError):
    """An input or source-integrity precondition was not satisfied."""


def _source_frames(manifest: dict) -> dict[int, list[tuple[int, str, str]]]:
    if manifest.get("format") != "capsule-blood-sparse-v1":
        raise ReadinessError("This audit requires the frozen Galar blood-sparse manifest")
    split = manifest.get("split", {})
    training, validation = split.get("train_exams"), split.get("development_exams")
    if not (isinstance(training, list) and isinstance(validation, list)
            and all(type(i) is int for i in training + validation)):
        raise ReadinessError("Missing or invalid examination-separated assignments")
    if not training or not validation or set(training) & set(validation):
        raise ReadinessError("Fitting and development examination IDs must be disjoint")
    if set(training + validation) & set(range(61, 81)):
        raise ReadinessError("Reserved Galar examinations 61–80 must not be accessed")
    if not isinstance(manifest.get("records"), list) or not manifest["records"]:
        raise ReadinessError("No source-image records in manifest")
    assignments = {i: "train" for i in training}
    assignments.update({i: "development" for i in validation})
    records: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    identities = set()
    for rec in manifest["records"]:
        if not isinstance(rec, dict):
            raise ReadinessError("Malformed source-image record")
        exam, frame, rel, split_value = (rec.get(k) for k in ("exam", "frame", "path", "split"))
        digest = rec.get("source_sha256")
        if type(exam) is not int or type(frame) is not int or frame < 0 or not isinstance(rel, str):
            raise ReadinessError("Malformed examination, source index or path")
        match = _RECORD_PATH.fullmatch(rel)
        if (match is None or int(match.group(1)) != exam or int(match.group(2)) != frame
                or exam not in assignments or split_value != assignments[exam]):
            raise ReadinessError("Source-frame path, index and split do not agree")
        if not isinstance(digest, str) or _HEX_SHA.fullmatch(digest) is None:
            raise ReadinessError("Missing or invalid original-source image SHA-256")
        identity = (exam, frame)
        if identity in identities:
            raise ReadinessError("Duplicate source-image identity")
        identities.add(identity)
        records[exam].append((frame, rel, digest))
    if set(records) != set(assignments):
        raise ReadinessError("All declared fitting/development examinations must have records")
    return records


def _check_image(root: Path, rel: str, expected_sha256: str) -> int:
    path = root.joinpath(*PurePosixPath(rel).parts)
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ReadinessError(f"A required image is missing or is not a regular file: {rel}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ReadinessError("Image escaped the trusted root")
    size = path.stat().st_size
    if not (len(_PNG_MAGIC) <= size <= _MAX_FRAME_BYTES):
        raise ReadinessError(f"Unexpected source image size: {rel}")
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(len(_PNG_MAGIC)) != _PNG_MAGIC:
            raise ReadinessError(f"Image is not an expected PNG: {rel}")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    if sha.hexdigest() != expected_sha256:
        raise ReadinessError(f"Source-image SHA-256 mismatch: {rel}")
    return size


def audit(manifest_path: Path, *, images: Path | None = None) -> dict:
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ReadinessError("Manifest is not a JSON object")
    records = _source_frames(manifest)
    verified = 0
    verified_bytes = 0
    if images is not None:
        if not images.is_dir() or images.is_symlink():
            raise ReadinessError("Image root must be an existing ordinary directory")
        for items in records.values():
            for _, rel, digest in items:
                verified_bytes += _check_image(images, rel, digest)
                verified += 1
    examinations = {}
    all_deltas = []
    for exam, items in sorted(records.items()):
        source_indices = sorted(frame for frame, _, _ in items)
        gaps = [b - a for a, b in zip(source_indices, source_indices[1:])]
        all_deltas.extend(gaps)
        examinations[str(exam)] = {
            "frames": len(source_indices),
            "source_index_min": source_indices[0],
            "source_index_max": source_indices[-1],
            "min_gap": min(gaps) if gaps else None,
            "median_gap": statistics.median(gaps) if gaps else None,
            "max_gap": max(gaps) if gaps else None,
            "pairs_at_gap_1": sum(g == 1 for g in gaps),
            "pairs_at_gap_5_or_less": sum(g <= 5 for g in gaps),
        }
    return {
        "schema": "capsule-sequence-readiness-v1",
        "status": "not_eligible_for_dense_video_evaluation",
        "source_manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "input_format": manifest["format"],
        "images": sum(len(v) for v in records.values()),
        "examinations": len(records),
        "exam_split": "examination-separated historical development; not independent patient groups",
        "image_verification": "all_original_sha256_matched" if images is not None else "not_performed",
        "verified_images": verified,
        "verified_bytes": verified_bytes,
        "source_index_gaps": {
            "pairs": len(all_deltas),
            "min": min(all_deltas) if all_deltas else None,
            "median": statistics.median(all_deltas) if all_deltas else None,
            "max": max(all_deltas) if all_deltas else None,
            "gap_1_pairs": sum(d == 1 for d in all_deltas),
            "gap_5_or_less_pairs": sum(d <= 5 for d in all_deltas),
        },
        "per_examination": examinations,
        "interpretation": (
            "No adjacent or five-source-index-neighbouring retained images are present. "
            "Galar annotation/index spacing is not verified native video timing; "
            "even source-index adjacency would not alone certify real continuous video. "
            "Do not calculate video-frame continuity or clinical lesion/interval sensitivity "
            "from these sparsely selected images."
        ),
        "next_data_gate": (
            "Acquire an explicitly provenance-verified consecutive exported-image or decoded-video "
            "clip from a separate examination, preserving ordinal order and independent-group identity. "
            "Never infer pathology truth from anatomy or weak clip labels."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images", type=Path, help="Verify every source PNG against its frozen SHA-256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    try:
        result = audit(args.manifest, images=args.images)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (ReadinessError, OSError, json.JSONDecodeError) as exc:
        print(f"Sequence readiness not verified: {exc}", file=sys.stderr)
        return 2
    print(f"Source readiness: {result['status']}; verified {result['verified_images']} source images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
