"""Verify the frozen original blood-CNN provenance *without* opening holdout data.

This is a private-local preflight for the locked unseen Galar 11–20 design,
NOT an evaluation. Only three explicit model members of the private pilot ZIP
are read. Never extract the private package, open image/annotation members,
deserialize model weights, or upload the archive to public Actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

MAX_PACKAGE_BYTES = 4 * 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024
TRAIN = tuple(range(1, 9))
DEV = (9, 10)
UNSEEN = tuple(range(11, 21))
AUTHOR_RESERVED = tuple(range(61, 81))
METHODS = ("uniform", "score", "score_diverse", "score_bin")


def file_sha256(path: Path, expected_bytes: int) -> str:
    if (path.is_symlink() or not path.is_file()
        or type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_PACKAGE_BYTES
        or path.stat().st_size != expected_bytes):
        raise ValueError("Pinned private pilot package absent or size changed.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_package(archive: Path, spec: dict) -> dict:
    """Read only model weights and *two* model metadata JSONs from verified ZIP."""
    scope = spec["scope"]
    model = spec["original_model"]
    publisher = spec["publisher"]
    methods = spec["methods"]

    if (spec.get("schema_version") != 1
        or tuple(scope["training_examination_ids"]) != TRAIN
        or tuple(scope["historical_checkpoint_selection_examination_ids"]) != DEV
        or tuple(scope["locked_evaluation_examination_ids"]) != UNSEEN
        or tuple(scope["authors_original_reserved_examination_ids"]) != AUTHOR_RESERVED
        or tuple(methods["policies"]) != METHODS
        or methods["primary_review_percent"] != 10
        or methods["secondary_review_percents"] != [5, 25, 50, 100]
        or not methods["scoring_model_frozen"]
        or not methods["no_tuning_after_holdout_access"]
        or publisher["figshare_file_id"] != 60383963
        or publisher["expected_sha256"]
            != "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"):
        raise ValueError("The locked examination, scoring or source protocol changed.")
    expected = {
        model["weights_member"]: model["weights_sha256"],
        model["metadata_member"]: model["metadata_sha256"],
        model["metrics_member"]: model["metrics_sha256"],
    }
    if len(expected) != 3 or set(expected) != {
        "model/weights.pt", "model/model.json", "model/metrics.json"
    }:
        raise ValueError("Unexpected private checkpoint member names.")
    if file_sha256(archive, model["private_package_bytes"]) != model["private_package_sha256"]:
        raise ValueError("Pinned private model ZIP checksum changed.")

    with zipfile.ZipFile(archive) as zip_file:
        blobs = {}
        for name, expected_digest in expected.items():
            member = zip_file.getinfo(name)
            if member.is_dir() or not 0 < member.file_size <= MAX_MEMBER_BYTES:
                raise ValueError("Unexpected model member shape or size.")
            payload = zip_file.read(member)  # Only these three private members.
            if hashlib.sha256(payload).hexdigest() != expected_digest:
                raise ValueError("Pinned original model member SHA-256 mismatch.")
            blobs[name] = payload
    # Never torch.load/deserialize untrusted weights and never open source CSV.
    metadata = json.loads(blobs["model/model.json"])
    metrics = json.loads(blobs["model/metrics.json"])
    if (metadata.get("model_weights_sha256") != model["weights_sha256"]
        or metadata.get("source_git_commit") != model["source_commit"]
        or metadata.get("architecture") != model["architecture"]
        or metadata.get("input") != model["preprocessing"]
        or metadata.get("selected_epoch") != model["checkpoint_epoch"]
        or metadata.get("classes") != ["blood label absent", "blood label present"]
        or metrics.get("weights_sha256") != model["weights_sha256"]
        or metrics.get("architecture") != model["architecture"]
        or metrics.get("fitting_examinations") != list(TRAIN)
        or metrics.get("development_examinations") != list(DEV)
        or metrics.get("future_unopened_evaluation_examinations") != list(UNSEEN)
        or metrics.get("training", {}).get("best_epoch") != model["checkpoint_epoch"]):
        raise ValueError("Checkpoint provenance or reserved examination split changed.")
    return {
        "status": "provenance_verified_only",
        "private_package_sha256": model["private_package_sha256"],
        "model_weights_sha256": model["weights_sha256"],
        "source_or_holdout_labels_or_images_opened": False,
        "independent_evaluation_performed": False,
        "model_promoted": False,
        "scientific_conclusion": "None; only checkpoint identity and pre-existing examination split verified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-pilot", type=Path, required=True)
    parser.add_argument(
        "--spec", type=Path,
        default=Path(__file__).resolve().parents[1] / "docs/GALAR_UNSEEN_11_20_EVALUATION_LOCK.json",
    )
    args = parser.parse_args()
    summary = audit_package(args.private_pilot, json.loads(args.spec.read_text(encoding="utf-8")))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
