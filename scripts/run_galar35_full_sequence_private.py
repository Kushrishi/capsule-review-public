"""Two-stage, PRIVATE-only original-CNN Galar 35 full-sequence experiment.

--score: scores ALL original publisher PNGs without opening ANY outcome labels
         or source-frame manifest. Excludes Galar 11-20 and 61-80.
         Freezes exact-K queues (four established methods plus temporal
         window-3 score-bin) in an exclusive-create PRIVATE snapshot.

--audit: first verifies the frozen snapshot hash, original ZIP identities
         and source PNG hashes, then reads ONLY official 35.csv and the
         private source manifest. Produces aggregate-only event/run metrics.

Galar 35 official labels were already inspected: THIS IS DEVELOPMENT-ONLY,
not blinded, independently validated, clinically validated or a promotion.
No raw images, scores, source frame IDs, weights, private manifests or label
rows are ever written to stdout or public Git. No source image acquisition.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

from capsule_review.priority import (
    largest_unselected_span, ordinal_coverage, select_positions,
)
from capsule_review.temporal_baseline import temporal_max_scores
from capsule_review.unseen_evaluation import (
    WORKLOAD_PERCENTS, evaluate_frozen_queues, exact_k, freeze_queues,
)
from capsule_review.interval_evidence import (
    segment_positive_runs,
)
from acquire_galar35_private import (
    ARCHIVE_SIZE, BLOCK, BLOCK_BYTES, BLOCK_START, EXAM, EXPECTED_ANNOTATION_RUNS,
    EXPECTED_IMAGES, EXPECTED_POSITIVE_IMAGES, NATIVE_STRIDE,
    SOURCE_URL, verified_label_rows,
)

MODEL_PACKAGE_SHA = "5e5f47ccca088855a88f92e795a870264ec3489badd3f341056230deae2e84fc"
WEIGHTS_SHA = "f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3"
MODEL_INPUT = "96x96 RGB, aspect-preserving pad, 0..1 channels"
SOURCE_RE = re.compile(r"images/035/frame_(\d+)\.PNG\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_LIMIT = 16 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
PRIMARY = 10
TEMPORAL_WINDOW = 3
POLICY = "score_bin"


def sha256_file(path: Path, limit: int) -> str:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= limit):
        raise ValueError("Missing, unsafe or oversized private source file.")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_original_package(path: Path, expected_sha: str) -> str:
    if not isinstance(expected_sha, str) or HEX.fullmatch(expected_sha) is None:
        raise ValueError("A separately verified private package SHA-256 is required.")
    actual = sha256_file(path, MAX_ZIP_BYTES)
    if actual != expected_sha:
        raise ValueError("Private source-image package SHA-256 mismatch.")
    return actual


def source_members(z: zipfile.ZipFile) -> list[tuple[int, zipfile.ZipInfo]]:
    """Read ZIP CENTRAL DIRECTORY only; never open embedded label/manifest bytes."""
    indexed = []
    known = set()
    allowed = {"source-frame-private-manifest.json", "source-block-private-receipt.json"}
    seen_names = set()
    for info in z.infolist():
        if info.filename in seen_names or info.is_dir():
            raise ValueError("Duplicate or unexpected directory member in source package.")
        seen_names.add(info.filename)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("A ZIP symlink cannot be trusted as an original image.")
        if info.filename in allowed:
            if info.file_size < 1 or info.file_size > MAX_MANIFEST_BYTES:
                raise ValueError("Source manifest/receipt size is not bounded.")
            continue
        match = SOURCE_RE.fullmatch(info.filename)
        if not match or info.file_size < 1 or info.file_size > IMAGE_LIMIT:
            raise ValueError("Unexpected private source image member or size.")
        frame = int(match.group(1))
        if frame in known:
            raise ValueError("Duplicate original frame in source package.")
        known.add(frame)
        indexed.append((frame, info))
    if seen_names != (allowed | {info.filename for _, info in indexed}):
        raise ValueError("Unexpected or incomplete source package.")
    indexed.sort(key=lambda row: row[0])
    frames = [frame for frame, _ in indexed]
    if len(frames) != EXPECTED_IMAGES or any(
        b - a != NATIVE_STRIDE for a, b in zip(frames, frames[1:])
    ):
        raise ValueError("Complete source examination 35 with native stride 5 is required.")
    return indexed


def load_original_model(model_zip: Path):
    """Load only two safe, pinned original CNN model members, never private labels."""
    import torch
    from capsule_review.baseline import AnatomyCNN

    if sha256_file(model_zip, 2 * 1024 * 1024) != MODEL_PACKAGE_SHA:
        raise ValueError("Wrong historical original-CNN package.")
    with zipfile.ZipFile(model_zip) as z:
        meta_info = z.getinfo("model/model.json")
        weight_info = z.getinfo("model/weights.pt")
        if not (0 < meta_info.file_size <= 64 * 1024
                and 0 < weight_info.file_size <= 2 * 1024 * 1024):
            raise ValueError("Unexpected original CNN model member sizes.")
        meta = json.loads(z.read(meta_info))
        weights = z.read(weight_info)
    if (hashlib.sha256(weights).hexdigest() != WEIGHTS_SHA
            or meta.get("model_weights_sha256") != WEIGHTS_SHA
            or meta.get("architecture") != "capsule-cnn-v1"
            or meta.get("input") != MODEL_INPUT
            or meta.get("classes") != ["blood label absent", "blood label present"]):
        raise ValueError("Original CNN weights or preprocessing identity mismatch.")
    state = torch.load(io.BytesIO(weights), map_location="cpu", weights_only=True)
    net = AnatomyCNN(2)
    expected = net.state_dict()
    if (not isinstance(state, dict) or set(state) != set(expected)
            or any(not isinstance(v, torch.Tensor)
                   or v.shape != expected[k].shape
                   or not torch.isfinite(v).all() for k, v in state.items())):
        raise ValueError("Untrusted or incompatible CNN tensors.")
    net.load_state_dict(state, strict=True)
    net.eval()
    torch.set_num_threads(2)
    return net


def score_source_images(
    originals: Path, expected_sha: str, model_zip: Path, *, batch_size: int = 32,
) -> dict:
    """Stage 1: only PNG member bytes; excludes the outcome-bearing manifest."""
    if type(batch_size) is not int or not 1 <= batch_size <= 64:
        raise ValueError("Choose a bounded model inference batch size.")
    import numpy as np
    import torch
    from PIL import Image, ImageOps

    source_sha = verify_original_package(originals, expected_sha)
    model = load_original_model(model_zip)
    entries = []
    with zipfile.ZipFile(originals) as z, torch.inference_mode():
        members = source_members(z)
        pending = []
        for frame, info in members:
            raw = z.read(info)  # ZIP CRC verified; NO label/manifest access.
            digest = hashlib.sha256(raw).hexdigest()
            with Image.open(io.BytesIO(raw)) as original:
                if original.format != "PNG":
                    raise ValueError("Source file is not a publisher-original PNG.")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image = ImageOps.pad(
                    image, (96, 96), method=Image.Resampling.BILINEAR,
                    color=(0, 0, 0),
                )
                pixels = np.array(image, dtype=np.float32, copy=True) / 255.0
            pending.append((frame, digest, torch.from_numpy(
                pixels.transpose(2, 0, 1).copy()
            )))
            if len(pending) == batch_size or (frame, info) == members[-1]:
                tensor = torch.stack([entry[2] for entry in pending])
                batch_scores = torch.softmax(model(tensor), dim=1)[:, 1].cpu().tolist()
                if len(batch_scores) != len(pending):
                    raise ValueError("Original CNN inference batch was incomplete.")
                for (source_frame, image_sha, _), score in zip(pending, batch_scores):
                    if not math.isfinite(score) or not 0 <= score <= 1:
                        raise ValueError("Invalid or nonfinite original CNN score.")
                    entries.append({
                        "source_frame": source_frame,
                        "original_png_sha256": image_sha,
                        "original_cnn_score": float(score),
                    })
                pending.clear()
    if len(entries) != EXPECTED_IMAGES:
        raise ValueError("Incomplete original source image inference.")
    frames = [v["source_frame"] for v in entries]
    hashes = [v["original_png_sha256"] for v in entries]
    scores = [v["original_cnn_score"] for v in entries]
    frozen = freeze_queues(frames, hashes, scores)
    smooth = temporal_max_scores(scores, frames, window=TEMPORAL_WINDOW,
                                 source_stride=NATIVE_STRIDE)
    queues = [{
        "review_percent": p, "k": k,
        "policies": {name: list(positions) for name, positions in methods},
        "temporal_window3_score_bin": select_positions(smooth, k, POLICY),
    } for p, k, methods in frozen.selection_by_percent]
    return {
        "schema_version": 1, "record_type": "private-galar35-frozen-original-scores-v1",
        "development_only": True,
        "exam": EXAM, "original_model_weights_sha256": WEIGHTS_SHA,
        "private_originals_package_sha256": source_sha,
        "native_source_stride": NATIVE_STRIDE,
        "prelabel_original_queues_commitment_sha256": frozen.input_commitment_sha256,
        "complete_original_scores": entries,
        "frozen_queues": queues,
        "labels_or_clinical_annotations_accessed_in_this_stage": False,
        "original_galar_11_to_20_evaluation_accessed": False,
        "author_galar_61_to_80_accessed": False,
    }


def replay_and_audit(
    snapshot: dict, originals: Path, source_sha: str, labels_zip: Path,
) -> dict:
    """Stage 2: reconcile PNG bytes, private manifest and 35.csv, then outcomes."""
    if (not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1
            or snapshot.get("record_type") != "private-galar35-frozen-original-scores-v1"
            or snapshot.get("exam") != EXAM or snapshot.get("development_only") is not True
            or snapshot.get("native_source_stride") != NATIVE_STRIDE
            or snapshot.get("original_model_weights_sha256") != WEIGHTS_SHA
            or snapshot.get("private_originals_package_sha256") != source_sha
            or snapshot.get("labels_or_clinical_annotations_accessed_in_this_stage") is not False):
        raise ValueError("Untrusted, inconsistent or unsealed private score snapshot.")
    entries = snapshot.get("complete_original_scores")
    if not isinstance(entries, list) or len(entries) != EXPECTED_IMAGES:
        raise ValueError("Original frozen score stream is incomplete.")
    frames, hashes, scores = [], [], []
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("Malformed score stream entry.")
        frames.append(row.get("source_frame"))
        hashes.append(row.get("original_png_sha256"))
        scores.append(row.get("original_cnn_score"))
    frozen = freeze_queues(frames, hashes, scores)
    if frozen.input_commitment_sha256 != snapshot.get(
        "prelabel_original_queues_commitment_sha256"
    ):
        raise ValueError("Original label-blind score commitment changed.")
    smooth = temporal_max_scores(scores, frames, window=TEMPORAL_WINDOW,
                                 source_stride=NATIVE_STRIDE)
    expected_queues = [{
        "review_percent": p, "k": k,
        "policies": {name: list(positions) for name, positions in methods},
        "temporal_window3_score_bin": select_positions(smooth, k, POLICY),
    } for p, k, methods in frozen.selection_by_percent]
    if snapshot.get("frozen_queues") != expected_queues:
        raise ValueError("Previously frozen exact-K selections were modified.")

    verify_original_package(originals, source_sha)
    with zipfile.ZipFile(originals) as z:
        members = source_members(z)
        if [a for a,_ in members] != frames:
            raise ValueError("Frozen source frame IDs differ from the original image ZIP.")
        # Only AFTER the score/queue freeze has been verified may label
        # or manifest data be opened.
        manifest_raw = z.read("source-frame-private-manifest.json")
        receipt = json.loads(z.read("source-block-private-receipt.json"))
        manifest = json.loads(manifest_raw)
        if not isinstance(manifest, list) or len(manifest) != EXPECTED_IMAGES:
            raise ValueError("Private original-image/annotation manifest incomplete.")
        if (receipt.get("official_file_id") != 44755700
                or receipt.get("block") != BLOCK
                or receipt.get("range_start") != BLOCK_START
                or receipt.get("range_stop_exclusive") != BLOCK_START + BLOCK_BYTES
                or receipt.get("compressed_bytes_received") != BLOCK_BYTES
                or receipt.get("full_source_md5_verified") is not False
                or not isinstance(receipt.get("source_block_sha256"), str)
                or HEX.fullmatch(receipt["source_block_sha256"]) is None):
            raise ValueError("Source-block acquisition receipt is invalid.")
        manifest_by_frame = {}
        for item in manifest:
            if (not isinstance(item, dict) or item.get("examination") != EXAM
                    or type(item.get("source_frame")) is not int
                    or item.get("source_frame") in manifest_by_frame
                    or type(item.get("blood_label")) is not int
                    or item["blood_label"] not in (0,1)
                    or type(item.get("original_png_bytes")) is not int
                    or item["original_png_bytes"] <= 0
                    or not isinstance(item.get("original_png_sha256"), str)
                    or HEX.fullmatch(item["original_png_sha256"]) is None):
                raise ValueError("Private source manifest contains invalid row.")
            manifest_by_frame[item["source_frame"]] = item
        if set(manifest_by_frame) != set(frames):
            raise ValueError("Private source manifest lacks original source positions.")
        for i, (frame, zipinfo) in enumerate(members):
            item = manifest_by_frame[frame]
            if item.get("original_filename") != PurePosixPath(zipinfo.filename).name:
                raise ValueError("Original publisher frame basename not preserved.")
            raw = z.read(zipinfo)
            if (len(raw) != item["original_png_bytes"]
                    or hashlib.sha256(raw).hexdigest() != item["original_png_sha256"]
                    or hashlib.sha256(raw).hexdigest() != hashes[i]):
                raise ValueError("Post-freeze original PNG byte integrity mismatch.")

    # Only the single explicitly permitted corrected 35.csv is read.
    checked_labels = verified_label_rows(labels_zip)
    if ([str(checked_labels.get(f)) for f in frames]
            != [str(manifest_by_frame[f]["blood_label"]) for f in frames]):
        raise ValueError("Original-image manifest contradicts official corrected 35.csv.")
    # The existing, already synthetic-tested source-run evaluator expects
    # source CSV bytes (only 35.csv), with exact frame order/known labels.
    with zipfile.ZipFile(labels_zip) as z:
        info = z.getinfo("35.csv")
        if not 0 < info.file_size <= 32*1024*1024:
            raise ValueError("Official development annotation member too large.")
        corrected_source_csv = z.read(info)
    baseline = evaluate_frozen_queues(frozen, corrected_source_csv)
    if (baseline["imported_annotated_images"] != EXPECTED_IMAGES
            or baseline["positive_annotated_images"] != EXPECTED_POSITIVE_IMAGES
            or baseline["positive_annotation_runs"] != EXPECTED_ANNOTATION_RUNS):
        raise ValueError("Original corrected source-run support changed.")

    rows = [{"frame":f, "blood":checked_labels[f]} for f in frames]
    runs, membership = segment_positive_runs(rows)
    if len(runs) != EXPECTED_ANNOTATION_RUNS:
        raise ValueError("Source-defined positive run segmentation changed.")
    audited = []
    for original, commitment in zip(baseline["review_results"], expected_queues):
        p, k = commitment["review_percent"], commitment["k"]
        if original["review_percent"] != p or original["review_images"] != k:
            raise ValueError("Original queue workload mismatch.")
        selected = commitment["temporal_window3_score_bin"]
        if len(selected) != k or len(set(selected)) != k:
            raise ValueError("Temporal selection failed the exact-K requirement.")
        positive_positions = [pos for pos in selected if rows[pos]["blood"] == "1"]
        temporal_hit = len({membership[frames[pos]] for pos in positive_positions})
        temporal_recall = round(temporal_hit / len(runs), 8) if runs else None
        policies = dict(original["policies"])
        policies["temporal_window3_score_bin"] = {
            "distinct_positive_annotation_runs_hit": temporal_hit,
            "positive_annotated_images_hit": len(positive_positions),
            "annotation_run_recall": temporal_recall,
            "run_lengths_hit": {
                stratum: sum(runs[rid]["stratum"] == stratum for rid in
                            {membership[frames[pos]] for pos in positive_positions})
                for stratum in ("1-5", "6-25", "26+")
            },
            "imported_position_coverage": ordinal_coverage(len(frames), selected),
            "largest_unselected_imported_span": (
                largest_unselected_span(len(frames), selected) or {}
            ).get("imported_images_not_in_queue", 0),
        }
        bin_rec = policies["score_bin"]["annotation_run_recall"]
        aud_bin = policies["temporal_window3_score_bin"]["annotation_run_recall"]
        audited.append({
            "review_percent": p, "review_images": k, "policies": policies,
            "temporal_minus_raw_score_bin_run_recall": (
                round(aud_bin - bin_rec, 8) if aud_bin is not None and bin_rec is not None else None
            ),
            "score_bin_minus_uniform_run_recall": original["score_bin_minus_uniform_run_recall"],
        })
    return {
        "schema_version": 1,
        "record_type": "galar35-complete-original-image-descriptive-development-v1",
        "exam": EXAM,
        "original_source_images_verified": EXPECTED_IMAGES,
        "blood_positive_original_annotated_images": EXPECTED_POSITIVE_IMAGES,
        "positive_annotation_runs_not_adjudicated_lesions": len(runs),
        "scoring_checkpoint_sha256": WEIGHTS_SHA,
        "unchanged_original_cnn": True,
        "all_source_images_rescored": True,
        "all_private_manifest_and_source_hashes_checked": True,
        "native_source_stride": NATIVE_STRIDE,
        "model_source_role": "Previously inspected development, NOT confirmatory validation",
        "independent_patient_validation": False,
        "clinical_validation": False,
        "model_promoted": False,
        "protected_11_20_reopened": False,
        "authors_61_80_accessed": False,
        "primary_descriptive_workload_percent": PRIMARY,
        "policy_names": list(audited[0]["policies"]),
        "review_results": audited,
        "limitations": (
            "Source-index grid is not elapsed time or device exposure completeness; "
            "annotated positive runs are not distinct adjudicated lesions; "
            "already-inspected single development examination cannot establish "
            "patient-independent evidence or clinical review-time benefit."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--score", action="store_true")
    mode.add_argument("--audit", action="store_true")
    p.add_argument("--source-originals", type=Path, required=True)
    p.add_argument("--expected-originals-sha256", required=True)
    p.add_argument("--model-zip", type=Path)
    p.add_argument("--score-snapshot", type=Path, required=True)
    p.add_argument("--score-snapshot-sha256")
    p.add_argument("--corrected-labels-zip", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--batch-size", type=int, default=32)
    args = p.parse_args()
    # All outputs must be external to the public source tree. Never upload.
    root = Path(__file__).resolve().parents[1]
    outputs = [args.score_snapshot] if args.score else [args.output]
    if any(path is None or path.is_symlink() or path.exists()
           or path.resolve(strict=False).is_relative_to(root)
           for path in outputs):
        p.error("Private output must be a fresh, external, non-symlink path.")
    if args.score:
        if args.model_zip is None or args.corrected_labels_zip is not None:
            p.error("Scoring needs original model and must NOT receive annotations.")
        snapshot = score_source_images(
            args.source_originals, args.expected_originals_sha256, args.model_zip,
            batch_size=args.batch_size,
        )
        args.score_snapshot.parent.mkdir(parents=True, exist_ok=True)
        with args.score_snapshot.open("x", encoding="utf8") as f:
            json.dump(snapshot, f, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(json.dumps({
            "stage": "original-CNN-scores-frozen",
            "original_images_scored": len(snapshot["complete_original_scores"]),
            "private_score_snapshot_sha256": sha256_file(args.score_snapshot, MAX_SNAPSHOT_BYTES),
            "source_image_pixels_written_to_public_git": False,
            "clinical_outcomes_accessed": False,
        }, sort_keys=True))
        return
    if (args.corrected_labels_zip is None or args.score_snapshot_sha256 is None
            or args.model_zip is not None):
        p.error("Audit requires sealed score snapshot checksum and official corrected labels.")
    if sha256_file(args.score_snapshot, MAX_SNAPSHOT_BYTES) != args.score_snapshot_sha256:
        p.error("Private score freeze SHA-256 mismatch; refusing outcome access.")
    snapshot = json.loads(args.score_snapshot.read_text(encoding="utf8"))
    result = replay_and_audit(
        snapshot, args.source_originals, args.expected_originals_sha256,
        args.corrected_labels_zip,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf8") as f:
        json.dump(result, f, sort_keys=True, allow_nan=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "stage": "complete-original-source-development-audit",
        "original_images_verified": result["original_source_images_verified"],
        "source_annotation_runs": result["positive_annotation_runs_not_adjudicated_lesions"],
        "new_independent_validation": False,
        "original_source_identifiers_disclosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
