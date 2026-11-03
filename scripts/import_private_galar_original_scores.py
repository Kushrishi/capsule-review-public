"""Import *previously verified* private original blood-CNN scores for local review.

The input ZIP is a private historical reproduction package. This command does
not download labels, train, run a checkpoint, use source annotation fields,
or send per-frame data to GitHub. It verifies the exact whole ZIP and named CSV
identities, then matches all 512 original imported-image hashes/source IDs.

Only examined Galar fitting/transfer studies are allowed; reserved original
evaluation studies stay closed. These are exploratory scores, not diagnosis.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

from capsule_review.models import PredictionImport
from capsule_review.prediction_service import save_predictions
from capsule_review.store import Store

SOURCES = {
    "frozen-transfer": {
        "exams": (21, 23, 30),
        "archive_sha256": "9dff0dd9ff38e17353bb6e1a9b343dd0b6a8906f1171bc481a842b74142fce83",
        "member": "private/source-scores.csv",
        "member_sha256": "caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812",
        "original_sha_column": "source_image_sha256",
        "score_column": "cnn_score",
        "reference_only_column": "reference_uniform",
    },
    "appearance-audit": {
        "exams": (25, 27, 29),
        "archive_sha256": "2738a64b47d0be4fecfd89fd8aea9a345ce86e237899e4e423d4d7de8ac36eaa",
        "member": "PRIVATE/private-per-image-features.csv",
        "member_sha256": "c07db3c66d027d730eaef82566e1c3a4d210a312e4b5926ee871381f5d608597",
        "original_sha_column": "source_sha256",
        "score_column": "original_checkpoint",
        "reference_only_column": None,  # Original file has exactly 512 per exam.
    },
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
LABEL = "Blood visual cue — experimental research score"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_source_records(path: Path, source: str, exam: int) -> tuple[list[dict], dict]:
    """Open ONLY the pinned selected CSV member in an intact private archive."""
    spec = SOURCES.get(source)
    if spec is None or type(exam) is not int or exam not in spec["exams"]:
        raise ValueError("Only the six previously examined approved Galar cases are supported.")
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 8 * 1024 * 1024:
        raise ValueError("Missing, unsafe or oversized private reproduction ZIP.")
    if file_sha256(path) != spec["archive_sha256"]:
        raise ValueError("The private reproduction archive SHA-256 is not the frozen verified source.")
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(spec["member"])
        if info.file_size > 3 * 1024 * 1024 or info.file_size == 0:
            raise ValueError("The selected source score CSV exceeds its verified size envelope.")
        raw = archive.read(info)  # CRC-check this permitted entry only.
    if hashlib.sha256(raw).hexdigest() != spec["member_sha256"]:
        raise ValueError("The original score stream member SHA-256 changed.")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    required = {"exam", "frame", spec["original_sha_column"], spec["score_column"]}
    if spec["reference_only_column"]:
        required.add(spec["reference_only_column"])
    if not required <= set(reader.fieldnames or []):
        raise ValueError("The pinned source score schema is incomplete.")
    seen = set()
    records = []
    for row in reader:
        # Parsing the private CSV necessarily decodes rows that include labels.
        # Label fields are never CONSULTED for selection or written to stored
        # predictions, verification receipts, or public research outputs.
        if row.get("exam") != str(exam):
            continue
        if spec["reference_only_column"] and row[spec["reference_only_column"]] != "1":
            continue
        index = row["frame"]
        digest = row[spec["original_sha_column"]]
        score_raw = row[spec["score_column"]]
        if not index.isdecimal() or SHA.fullmatch(digest or "") is None:
            raise ValueError("Malformed original source frame identity in verified stream.")
        index = int(index)
        try:
            score = float(score_raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid original research score.") from exc
        if index in seen or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Duplicate source frame ID or invalid research score.")
        seen.add(index)
        records.append({"frame": index, "sha256": digest, "score": score})
    if len(records) != 512 or any(records[i]["frame"] >= records[i + 1]["frame"]
                                 for i in range(511)):
        raise ValueError("Exact 512-image label-blind reference order is missing or changed.")
    return records, spec


def import_verified_original_scores(store: Store, study_id: str, source: str,
                                    exam: int, archive: Path) -> dict:
    """Persist once as *model suggestions*, not clinical labels or reviewer notes."""
    records, spec = verified_source_records(archive, source, exam)
    study = store.study(study_id)
    if study is None or study["synthetic"] or study["frame_count"] != 512:
        raise ValueError("Target must be an existing 512-image imported real research study.")
    with store.connect() as db:
        local = [dict(row) for row in db.execute(
            "SELECT position,source_index,source_sha256,display_sha256 "
            "FROM frames WHERE study_id=? ORDER BY position", (study_id,)
        )]
    if len(local) != 512 or [r["position"] for r in local] != list(range(512)):
        raise ValueError("The imported study frame identity/order is incomplete.")
    predictions = []
    for row, source_row in zip(local, records):
        if row["source_index"] != source_row["frame"] or row["source_sha256"] != source_row["sha256"]:
            raise ValueError("Imported source image/frame identities differ from verified original scores.")
        image = store.images / study_id / f'{row["position"]}.png'
        if image.is_symlink() or not image.is_file() or file_sha256(image) != row["display_sha256"]:
            raise ValueError("An imported local display image has changed since import.")
        predictions.append({
            "position": row["position"],
            "image_sha256": row["source_sha256"],
            "label": LABEL,
            "score": source_row["score"],
        })
    model = {
        "name": "Original Galar blood-CNN — retrospective research",
        "version": "prior-original-cnn-saved-scores",
        "run_id": f'galar-original-{source}-{exam}-{spec["member_sha256"][:16]}',
        "description": (
            "Previously inspected Galar fitting/transfer examination. Stored original "
            "blood CNN image-score replay, not live inference or calibrated likelihood. "
            "No independent/clinical validation, no specific lesion detection, "
            "no clinical triage claim. Original model weights remain private."
        ),
    }
    payload = PredictionImport.model_validate({
        "schema_version": 1, "study_id": study_id, "model": model,
        "predictions": predictions,
    })
    saved = save_predictions(store, study_id, payload)
    return {
        "schema_version": 1, "study_type": "private-exploratory-original-galar-score-import",
        "examination_id": exam, "imported_reference_images": len(predictions),
        "model_prediction_run_id": saved["run_id"],
        "source_package_sha256": spec["archive_sha256"],
        "original_score_csv_sha256": spec["member_sha256"],
        "all_imported_original_source_hashes_matched": True,
        "all_normalized_local_display_hashes_rechecked": True,
        "private_reference_labels_excluded_from_model_output": True,
        "reviewer_notes_and_bookmarks_unmodified": True,
        "clinical_validation": False,
        "source_annotation_run_coverage_measured": False,
        "interpretation": (
            "This imports one complete previously examined uncalibrated image-score "
            "stream for local research review, not a validated diagnostic model. "
            "No model weights or source annotations were distributed or evaluated."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="Existing private localhost Capsule Review workspace")
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--source", required=True, choices=tuple(SOURCES))
    parser.add_argument("--examination", type=int, required=True)
    parser.add_argument("--private-archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.receipt.exists():
        raise FileExistsError("Refusing to overwrite a prior private verification receipt.")
    result = import_verified_original_scores(
        Store(arguments.data_dir), arguments.study_id, arguments.source,
        arguments.examination, arguments.private_archive
    )
    arguments.receipt.parent.mkdir(parents=True, exist_ok=True)
    with arguments.receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        f"Imported {result['imported_reference_images']} image scores as local research "
        "model suggestions; no clinical validation or source-run recall measured."
    )


if __name__ == "__main__":
    main()
