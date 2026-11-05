"""Private-only replay of original blood CNN on previously imported viewer PNGs.

Reproduces historical persisted uncalibrated scores, never a new clinical
outcome. Reads only the pinned 1.36-MB original model ZIP and explicitly
selected 512 normalized display PNGs and numerical scores from a privately
retained application workspace. No image, source hash, source position,
reference label, model weight or score vector enters the aggregate output.

The workspace includes transformed display images, NOT original publisher
PNG bytes. Their hashes are cross-checked against the local SQLite manifest.
The caller privately supplies the workspace ZIP SHA-256, so it is not
published in source code or the report.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

EXPECTED_ORIGINAL_MODEL_ZIP_BYTES = 1_361_018
EXPECTED_ORIGINAL_MODEL_ZIP_SHA256 = (
    "5e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc"
)
EXPECTED_WEIGHTS_SHA256 = (
    "f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3"
)
EXPECTED_DISPLAY_FRAMES = 512
MAX_WORKSPACE_ZIP_BYTES = 256 * 1024 * 1024
MAX_DISPLAY_PNG_BYTES = 4 * 1024 * 1024
MAX_SQLITE_BYTES = 8 * 1024 * 1024
MAX_MODEL_MEMBER_BYTES = 2 * 1024 * 1024
LABEL = "Blood visual cue — experimental research score"
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_STUDY = re.compile(r"[a-f0-9]{32}\Z")


def sha256_file(path: Path, *, maximum_bytes: int) -> str:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= maximum_bytes):
        raise ValueError("Private archive missing, symlinked or outside size limits.")
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_member(z: zipfile.ZipFile, member: str, limit: int) -> bytes:
    i = z.getinfo(member)
    if i.is_dir() or not 0 < i.file_size <= limit:
        raise ValueError("Unexpected private source member shape or size.")
    with z.open(i) as stream:
        data = stream.read(limit + 1)
    if len(data) != i.file_size:
        raise ValueError("Incomplete private member.")
    return data


def original_cnn_model(model_zip: Path):
    """Read only weights and model metadata; do not read private predictions."""
    import torch
    from capsule_review.baseline import AnatomyCNN

    if (model_zip.stat().st_size != EXPECTED_ORIGINAL_MODEL_ZIP_BYTES
            or sha256_file(model_zip, maximum_bytes=2 * 1024 * 1024)
               != EXPECTED_ORIGINAL_MODEL_ZIP_SHA256):
        raise ValueError("Original model archive identity changed.")
    with zipfile.ZipFile(model_zip) as z:
        weights = read_member(z, "model/weights.pt", MAX_MODEL_MEMBER_BYTES)
        meta = json.loads(read_member(z, "model/model.json", 64 * 1024))
    if (hashlib.sha256(weights).hexdigest() != EXPECTED_WEIGHTS_SHA256
            or meta.get("model_weights_sha256") != EXPECTED_WEIGHTS_SHA256
            or meta.get("architecture") != "capsule-cnn-v1"
            or meta.get("input") != "96x96 RGB, aspect-preserving pad, 0..1 channels"
            or meta.get("classes") != ["blood label absent", "blood label present"]):
        raise ValueError("Original CNN weights, architecture or preprocessing changed.")
    state = torch.load(io.BytesIO(weights), weights_only=True, map_location="cpu")
    network = AnatomyCNN(2)
    expected = network.state_dict()
    if not isinstance(state, dict) or set(state) != set(expected):
        raise ValueError("Original CNN parameter names changed.")
    if any(not isinstance(v, torch.Tensor) or v.shape != expected[k].shape
           or not torch.isfinite(v).all() for k, v in state.items()):
        raise ValueError("Unexpected or nonfinite original CNN parameters.")
    network.load_state_dict(state, strict=True)
    network.eval()
    return network


def replay(model_zip: Path, workspace_zip: Path, expected_workspace_sha256: str) -> dict:
    import numpy as np
    import torch
    from PIL import Image, ImageOps

    if (not isinstance(expected_workspace_sha256, str)
            or _HEX.fullmatch(expected_workspace_sha256) is None
            or sha256_file(workspace_zip, maximum_bytes=MAX_WORKSPACE_ZIP_BYTES)
            != expected_workspace_sha256):
        raise ValueError("Private viewer workspace SHA-256 mismatch.")
    model = original_cnn_model(model_zip)
    with zipfile.ZipFile(workspace_zip) as z:
        db_blob = read_member(z, "workspace/reviews.sqlite3", MAX_SQLITE_BYTES)
        with tempfile.TemporaryDirectory(prefix="capsule-private-sqlite-") as d:
            db_path = Path(d) / "viewer.db"
            db_path.write_bytes(db_blob)
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.execute("PRAGMA trusted_schema=OFF")
                studies = conn.execute("SELECT id, frame_count FROM studies").fetchall()
                if len(studies) != 1 or studies[0][1] != EXPECTED_DISPLAY_FRAMES:
                    raise ValueError("Expected one 512-image private study.")
                study_id = studies[0][0]
                if type(study_id) is not str or _STUDY.fullmatch(study_id) is None:
                    raise ValueError("Invalid private workspace study identifier.")
                frames = conn.execute(
                    "SELECT position, source_sha256, display_sha256 FROM frames "
                    "WHERE study_id=? ORDER BY position", (study_id,)
                ).fetchall()
                scores = conn.execute(
                    "SELECT position, score FROM predictions WHERE study_id=? "
                    "AND label=? ORDER BY position", (study_id, LABEL)
                ).fetchall()
                if (len(frames) != EXPECTED_DISPLAY_FRAMES
                        or len(scores) != EXPECTED_DISPLAY_FRAMES
                        or [x[0] for x in frames] != list(range(EXPECTED_DISPLAY_FRAMES))
                        or [x[0] for x in scores] != list(range(EXPECTED_DISPLAY_FRAMES))):
                    raise ValueError("Missing, duplicated or reordered private source images/scores.")

        tensors = []
        display_matches = 0
        original_byte_matches = 0
        for pos, original_sha, display_sha in frames:
            if (not isinstance(original_sha, str) or _HEX.fullmatch(original_sha) is None
                    or not isinstance(display_sha, str) or _HEX.fullmatch(display_sha) is None):
                raise ValueError("Saved source/display hashes missing.")
            filename = f"workspace/images/{study_id}/{pos}.png"
            payload = read_member(z, filename, MAX_DISPLAY_PNG_BYTES)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != display_sha:
                raise ValueError("Private normalized viewer image bytes changed.")
            display_matches += 1
            original_byte_matches += digest == original_sha
            with Image.open(io.BytesIO(payload)) as im:
                if im.format != "PNG":
                    raise ValueError("Expected a normalized PNG from the viewer.")
                # Exact historical image_tensor() preprocessing.
                im = ImageOps.exif_transpose(im).convert("RGB")
                im = ImageOps.pad(
                    im, (96, 96), method=Image.Resampling.BILINEAR,
                    color=(0, 0, 0)
                )
                pixels = np.array(im, dtype=np.float32, copy=True) / 255.0
            tensors.append(torch.from_numpy(pixels.transpose(2, 0, 1).copy()))

    saved = [float(x[1]) for x in scores]
    if any(not math.isfinite(s) or s < 0 or s > 1 for s in saved):
        raise ValueError("Invalid original persisted model score.")
    torch.set_num_threads(2)
    predicted = []
    with torch.inference_mode():
        for k in range(0, len(tensors), 32):
            batch = torch.stack(tensors[k:k+32])
            values = torch.softmax(model(batch), dim=1)[:, 1].cpu().tolist()
            predicted.extend(float(v) for v in values)
    if len(predicted) != EXPECTED_DISPLAY_FRAMES:
        raise ValueError("Original CNN replay returned incomplete scores.")
    differences = [abs(a-b) for a,b in zip(saved,predicted)]
    exact = sum(x == 0.0 for x in differences)
    within_tolerance = sum(x <= 1e-6 for x in differences)
    max_difference = max(differences)
    if within_tolerance != EXPECTED_DISPLAY_FRAMES:
        raise ValueError("Original CNN scores failed the 1e-6 reproduction tolerance.")
    return {
        "schema_version": 1,
        "record_type": "historical-original-cnn-private-viewer-replay-v1",
        "historical_original_model_checkpoint_sha256_verified": True,
        "private_workspace_sha256_verified": True,
        "viewer_display_png_sha256_matches": display_matches,
        "previously_saved_score_records_replayed": EXPECTED_DISPLAY_FRAMES,
        "exact_score_matches": exact,
        "scores_within_absolute_1e_minus_6": within_tolerance,
        "maximum_absolute_score_difference": max_difference,
        "original_publisher_png_bytes_replayed": original_byte_matches == EXPECTED_DISPLAY_FRAMES,
        "viewer_images_are_normalized_display_copies": True,
        "independent_model_validation": False,
        "clinical_diagnostic_accuracy_established": False,
        "new_model_training_or_fitting": False,
        "protected_galar_evaluation_opened": False,
        "individual_source_records_or_prediction_scores_exported": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-model-zip", type=Path, required=True)
    p.add_argument("--private-workspace-zip", type=Path, required=True)
    p.add_argument("--expected-workspace-sha256", required=True)
    p.add_argument("--private-report", type=Path)
    args = p.parse_args()
    if args.private_report:
        root = Path(__file__).resolve().parents[1]
        if args.private_report.exists() or args.private_report.is_symlink() or (
            args.private_report.resolve(strict=False).is_relative_to(root)
        ):
            p.error("Private replay receipt may not overwrite or enter public Git.")
    result = replay(args.original_model_zip, args.private_workspace_zip,
                    args.expected_workspace_sha256)
    if args.private_report:
        args.private_report.parent.mkdir(parents=True, exist_ok=True)
        args.private_report.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
