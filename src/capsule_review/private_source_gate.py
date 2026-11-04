"""Private-only pre-label evidence gate for the frozen Galar evaluation.

Verify actual original PNG bytes, then persist score-only queue choices before
accessing corrected annotations. Only generated synthetic pixels reach public
CI. This module does not run a CNN, establish patient identity, or independently
timestamp a commitment: anchor its returned digest outside this workspace.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import warnings
import zipfile

from PIL import Image, UnidentifiedImageError

from .priority import MAX_FRAMES
from .unseen_evaluation import (
    FrozenQueues,
    evaluate_frozen_queues,
    freeze_queues,
)

SHA256 = re.compile(r"[a-f0-9]{64}\Z")
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_PRIVATE_RECORD_BYTES = 128 * 1024 * 1024
MAX_LABEL_MEMBER_BYTES = 32 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _spec(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 64 * 1024:
        raise ValueError("Frozen public protocol is missing or invalid.")
    raw = path.read_bytes()
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get("schema_version") != 1
        or data.get("scope", {}).get("locked_evaluation_examination_ids") != list(range(11, 21))
        or data.get("scope", {}).get("authors_original_reserved_examination_ids") != list(range(61, 81))
        or data.get("methods", {}).get("primary_review_percent") != 10
        or data.get("methods", {}).get("secondary_review_percents") != [5, 25, 50, 100]
        or data.get("methods", {}).get("policies")
           != ["uniform", "score", "score_diverse", "score_bin"]
        or not SHA256.fullmatch(data.get("original_model", {}).get("weights_sha256", ""))
        or not SHA256.fullmatch(data.get("publisher", {}).get("expected_sha256", ""))):
        raise ValueError("The locked source, cohort or selection protocol changed.")
    return data, _sha(raw)


def verify_original_pngs(
    root: Path,
    records: list[dict],
    *,
    expected_first: int,
    expected_last: int,
    expected_count: int,
) -> tuple[list[int], list[str]]:
    """Rehash/fully decode each PNG, not just trust its supplied checksum.

    The expected first/last/count MUST have been separately established from
    an approved source index, not read from reserved outcome labels.
    """
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Private original-image directory is absent or symlinked.")
    if (type(expected_count) is not int or not 1 <= expected_count <= MAX_FRAMES
        or type(expected_first) is not int or type(expected_last) is not int
        or expected_first < 0 or expected_last != expected_first + 5 * (expected_count - 1)
        or type(records) is not list or len(records) != expected_count):
        raise ValueError("The separately pinned original annotated-position range is incomplete.")
    frames: list[int] = []
    hashes: list[str] = []
    used_names: set[str] = set()
    for i, row in enumerate(records):
        if not isinstance(row, dict) or set(row) != {"frame", "name", "sha256"}:
            raise ValueError("Only source identities may enter the label-blind image manifest.")
        frame, name, claimed = row["frame"], row["name"], row["sha256"]
        if type(frame) is not int or frame != expected_first + 5 * i:
            raise ValueError("Original annotated source-index completeness check failed.")
        if (not isinstance(name, str) or not 1 <= len(name) <= 240
            or not isinstance(claimed, str) or SHA256.fullmatch(claimed) is None):
            raise ValueError("Invalid original source filename or SHA-256.")
        relative = PurePosixPath(name)
        if (relative.is_absolute() or len(relative.parts) != 1 or ".." in relative.parts
            or "\\" in name or relative.suffix.lower() != ".png" or name.startswith(".")):
            raise ValueError("Original PNG paths must be plain names in a private directory.")
        if name.casefold() in used_names:
            raise ValueError("Duplicate original image path.")
        used_names.add(name.casefold())
        path = root / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
            raise ValueError("Original source PNG is absent, symlinked or oversized.")
        raw = path.read_bytes()
        if not raw.startswith(PNG_MAGIC) or _sha(raw) != claimed:
            raise ValueError("Original PNG byte identity changed or is not a PNG.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if (image.format != "PNG" or getattr(image, "n_frames", 1) != 1
                        or not 0 < image.width * image.height <= MAX_PIXELS):
                        raise ValueError("Unsupported original PNG dimensions or format.")
                    image.load()  # Decode all pixels; do not accept valid headers alone.
        except (OSError, UnidentifiedImageError, Image.DecompressionBombWarning,
                Image.DecompressionBombError) as exc:
            raise ValueError("Original PNG could not be decoded safely.") from exc
        frames.append(frame)
        hashes.append(claimed)
    return frames, hashes


def _selection_record(
    frames: list[int],
    hashes: list[str],
    scores: list[float],
    weights_sha256: str,
    protocol_sha256: str,
) -> tuple[dict, FrozenQueues]:
    frozen = freeze_queues(frames, hashes, scores)
    private = {
        "schema_version": 1,
        "purpose": "PRIVATE pre-label queue freeze; not clinical validation",
        "protocol_sha256": protocol_sha256,
        "model_weights_sha256_claimed": weights_sha256,
        "source_frames": frames,
        "source_image_sha256": hashes,
        "model_scores": scores,
        "selection_by_percent": [
            [percent, count, [[method, list(positions)] for method, positions in policies]]
            for percent, count, policies in frozen.selection_by_percent
        ],
        "score_input_commitment_sha256": frozen.input_commitment_sha256,
    }
    return private, frozen


def freeze_private_queues(
    *,
    image_root: Path,
    image_records: list[dict],
    scores: list[float],
    expected_first: int,
    expected_last: int,
    expected_count: int,
    weights_sha256: str,
    protocol_path: Path,
    destination: Path,
) -> str:
    """Write-once private snapshot; return SHA-256 for EXTERNAL anchoring.

    The digest alone is not a trusted timestamp. Verify the actual checkpoint
    separately using the pinned model-package preflight, then run inference
    privately before calling this function. No source labels may be supplied.
    """
    spec, protocol_digest = _spec(protocol_path)
    if weights_sha256 != spec["original_model"]["weights_sha256"]:
        raise ValueError("The claimed scoring model differs from the original pinned model.")
    if not isinstance(scores, list) or len(scores) != expected_count:
        raise ValueError("The frozen score stream is missing images.")
    frames, hashes = verify_original_pngs(
        image_root, image_records, expected_first=expected_first,
        expected_last=expected_last, expected_count=expected_count,
    )
    record, _ = _selection_record(frames, hashes, scores, weights_sha256, protocol_digest)
    raw = _canonical(record) + b"\n"
    if len(raw) > MAX_PRIVATE_RECORD_BYTES:
        raise ValueError("The private freeze snapshot is too large.")
    private_parent = destination.parent.resolve(strict=True)
    repo_root = Path(__file__).resolve().parents[2]
    if private_parent.is_relative_to(repo_root) or destination.is_symlink():
        raise ValueError("Private freeze records may not be written inside public source.")
    # O_EXCL, restrictive permissions and fsync prevent accidental overwrites
    # and partial success; they do not protect against later external tampering.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return _sha(raw)


def load_private_queues(
    *,
    destination: Path,
    expected_snapshot_sha256: str,
    image_root: Path,
    protocol_path: Path,
) -> FrozenQueues:
    """Verify externally anchored snapshot and rehash ALL original PNG bytes."""
    if not isinstance(expected_snapshot_sha256, str) or SHA256.fullmatch(expected_snapshot_sha256) is None:
        raise ValueError("A separately anchored private snapshot SHA-256 is required.")
    if destination.is_symlink() or not destination.is_file() or not 0 < destination.stat().st_size <= MAX_PRIVATE_RECORD_BYTES:
        raise ValueError("Private frozen snapshot is missing or invalid.")
    raw = destination.read_bytes()
    if _sha(raw) != expected_snapshot_sha256:
        raise ValueError("Frozen snapshot was changed after its external digest.")
    record = json.loads(raw)
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "purpose", "protocol_sha256", "model_weights_sha256_claimed",
        "source_frames", "source_image_sha256", "model_scores",
        "selection_by_percent", "score_input_commitment_sha256",
    } or record["schema_version"] != 1:
        raise ValueError("The private frozen snapshot schema changed.")
    spec, current_protocol_sha = _spec(protocol_path)
    if (record["protocol_sha256"] != current_protocol_sha
        or record["model_weights_sha256_claimed"] != spec["original_model"]["weights_sha256"]):
        raise ValueError("The protocol or claimed model changed since the freeze.")
    frames = record["source_frames"]
    hashes = record["source_image_sha256"]
    scores = record["model_scores"]
    if not isinstance(frames, list) or not frames:
        raise ValueError("Frozen original source identities are missing.")
    rows = [{"frame": f, "name": f"frame_{f:06d}.png", "sha256": h}
            for f, h in zip(frames, hashes)]
    if len(rows) != len(frames):
        raise ValueError("Frozen original source checksums are incomplete.")
    observed_frames, observed_hashes = verify_original_pngs(
        image_root, rows, expected_first=frames[0],
        expected_last=frames[-1], expected_count=len(frames),
    )
    if observed_frames != frames or observed_hashes != hashes:
        raise ValueError("Original source identities differ from the frozen private record.")
    recalculated, frozen = _selection_record(
        frames, hashes, scores, record["model_weights_sha256_claimed"], current_protocol_sha,
    )
    if recalculated != record:
        raise ValueError("The frozen source/score policies do not replay exactly.")
    return frozen


def load_locked_corrected_csv(labels_zip: Path, *, exam: int, protocol_path: Path) -> bytes:
    """Read exactly ONE approved Galar 11–20 label member, and nothing else."""
    spec, _ = _spec(protocol_path)
    if type(exam) is not int or exam not in spec["scope"]["locked_evaluation_examination_ids"]:
        raise ValueError("Examination is outside the locked evaluation cohort.")
    if labels_zip.is_symlink() or not labels_zip.is_file():
        raise ValueError("Official corrected source archive is missing or symlinked.")
    h = hashlib.sha256()
    with labels_zip.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != spec["publisher"]["expected_sha256"]:
        raise ValueError("The official corrected label archive SHA-256 changed.")
    with zipfile.ZipFile(labels_zip) as archive:
        member = archive.getinfo(f"{exam}.csv")
        if not 0 < member.file_size <= MAX_LABEL_MEMBER_BYTES or member.is_dir():
            raise ValueError("Unsupported corrected label member size.")
        return archive.read(member)  # Do not call testzip()/infolist().


def evaluate_private_snapshot(
    *,
    destination: Path,
    expected_snapshot_sha256: str,
    image_root: Path,
    protocol_path: Path,
    labels_zip: Path,
    exam: int,
) -> dict:
    """Fail closed on all pre-label commitments BEFORE reading approved CSV."""
    frozen = load_private_queues(
        destination=destination, expected_snapshot_sha256=expected_snapshot_sha256,
        image_root=image_root, protocol_path=protocol_path,
    )
    corrected = load_locked_corrected_csv(labels_zip, exam=exam, protocol_path=protocol_path)
    return evaluate_frozen_queues(frozen, corrected)
