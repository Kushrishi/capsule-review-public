"""Fail-closed, byte-verified development-cohort preflight.

The caller owns a private, externally pinned manifest and a private local root
containing the declared source images. The function does not upload or copy
images, load a model, open outcomes from a new cohort, or trust self-declared
hashes without reading source bytes.

"PASS" means the *structural/software* requirements tested here hold. It is
never authorization for clinical use, independent validation or new outcome
access: a researcher must separately approve provenance, labels and rights.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import re

VALID_LABELS = ("positive", "negative", "unknown")
VALID_SPLITS = ("fit", "evaluate")
VALID_TASKS = ("sparse_image_ranking", "complete_event_retrieval")
MAX_RECORDS = 100_000
MAX_SOURCE_BYTES = 32 * 1024 * 1024
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def manifest_digest(payload: dict) -> str:
    """Digest the exact canonical JSON including private source identities."""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def inspect(manifest: dict, *, source_root: Path, pinned_sha256: str) -> dict:
    """Verify every source image, label state and split without exposing identities.

    A trusted external record must pin the canonical manifest SHA256. The
    program cannot establish whether a claimed patient group is correct or
    whether an outside custodian truly licensed data: these require human
    source-document review even after a structural PASS.
    """
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "task", "source_coverage",
        "exhaustive_event_annotations", "rights_evidence_ref",
        "near_duplicate_screened", "records"
    } or manifest["schema_version"] != 1:
        raise ValueError("Unsupported private cohort manifest schema.")
    if not isinstance(pinned_sha256, str) or not SHA_RE.fullmatch(pinned_sha256):
        raise ValueError("A trusted external 64-hex manifest digest is required.")
    if manifest_digest(manifest) != pinned_sha256:
        raise ValueError("Private manifest differs from externally pinned digest.")
    task = manifest["task"]
    if task not in VALID_TASKS:
        raise ValueError("Invalid task.")
    if manifest["source_coverage"] not in ("sampled", "full"):
        raise ValueError("Unrecognized source coverage.")
    if type(manifest["exhaustive_event_annotations"]) is not bool:
        raise ValueError("Invalid exhaustive-event annotation declaration.")
    if type(manifest["near_duplicate_screened"]) is not bool:
        raise ValueError("Invalid near-duplicate status.")
    rights_ref = manifest["rights_evidence_ref"]
    if not isinstance(rights_ref, str) or len(rights_ref) > 1024:
        raise ValueError("Invalid rights evidence reference.")
    records = manifest["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError("Expected nonempty, bounded image manifest.")
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Source root must be a real private directory.")
    root = source_root.resolve()
    errors: set[str] = set()
    identities: set[tuple[str, int]] = set()
    per_exam: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    patient_to_splits: dict[str, set[str]] = defaultdict(set)
    patient_missing = False
    splits: set[str] = set()
    counts = Counter()
    for row in records:
        if not isinstance(row, dict) or set(row) != {
            "examination_id", "source_index", "split", "blood_label",
            "image_sha256", "image_path", "patient_group"
        }:
            raise ValueError("Unexpected source record fields.")
        ex, index, split = row["examination_id"], row["source_index"], row["split"]
        label, hash_value = row["blood_label"], row["image_sha256"]
        patient = row["patient_group"]
        if (not isinstance(ex, str) or not 0 < len(ex.strip()) <= 96
            or type(index) is not int or not 0 <= index <= 10**10
            or split not in VALID_SPLITS or label not in VALID_LABELS
            or not isinstance(hash_value, str) or not SHA_RE.fullmatch(hash_value)
            or (patient is not None and (not isinstance(patient, str)
                or not 0 < len(patient.strip()) <= 96))):
            raise ValueError("Malformed source identifier, label, group or hash.")
        key = (ex, index)
        if key in identities:
            errors.add("duplicate_source_identity")
        identities.add(key)
        counts["images"] += 1
        counts["label_"+label] += 1
        counts["split_"+split] += 1
        counts[split+"_"+label] += 1
        splits.add(split)
        state = per_exam.setdefault(ex, {"splits":set(), "groups":set(), "positive":0,
                                         "n":0})
        state["splits"].add(split)
        state["n"] += 1
        state["positive"] += label == "positive"
        if patient is None:
            patient_missing = True
        else:
            state["groups"].add(patient)
            patient_to_splits[patient].add(split)
        if label == "unknown":
            errors.add("unknown_label_not_eligible_as_negative")
        if hash_value in hashes and hashes[hash_value] != ex:
            errors.add("identical_source_image_across_examinations")
        hashes[hash_value] = ex
        rel = row["image_path"]
        if not isinstance(rel, str) or not rel or len(rel)>500:
            raise ValueError("Invalid private relative image path.")
        posix = PurePosixPath(rel)
        if posix.is_absolute() or ".." in posix.parts or posix.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("Unsafe or unsupported relative source path.")
        path = root.joinpath(*posix.parts)
        if not path.resolve().is_relative_to(root):
            raise ValueError("Image path escapes private root.")
        # Refuse symlinks in the path, not just a symlink final filename.
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
            raise ValueError("Image source path includes a symlink.")
        if not path.is_file():
            errors.add("source_image_missing")
            continue
        if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
            errors.add("source_image_out_of_bounds")
            continue
        digest = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != hash_value:
            errors.add("source_image_sha256_mismatch")
        else:
            counts["bytes_reverified"] += 1
    if "fit" not in splits or "evaluate" not in splits:
        errors.add("missing_disjoint_fit_and_evaluation_splits")
    if any(len(state["splits"]) != 1 for state in per_exam.values()):
        errors.add("examination_split_leakage")
    if any(len(parts) > 1 for parts in patient_to_splits.values()):
        errors.add("patient_group_split_leakage")
    if counts["fit_positive"] < 1 or counts["fit_negative"] < 1:
        errors.add("fit_split_missing_binary_class")
    if counts["evaluate_positive"] < 1 or counts["evaluate_negative"] < 1:
        errors.add("evaluation_split_missing_binary_class")
    if any(len(state["groups"]) > 1 for state in per_exam.values()):
        errors.add("examination_maps_to_multiple_patient_groups")
    if not rights_ref.strip():
        errors.add("data_rights_evidence_missing")
    if task == "complete_event_retrieval":
        if manifest["source_coverage"] != "full":
            errors.add("sampled_images_not_complete_video")
        if not manifest["exhaustive_event_annotations"]:
            errors.add("event_annotations_not_exhaustive")
    if len(hashes) != len(records):
        errors.add("exact_duplicate_source_images")
    # An unperformed near-duplicate screen cannot be described as complete.
    if not manifest["near_duplicate_screened"]:
        errors.add("near_duplicate_screen_missing")
    # Patient grouping is checked separately so examination-only development
    # is not falsely called a fully independent evaluation.
    if errors:
        status = "BLOCKED"
    elif patient_missing:
        status = "INSUFFICIENT_GROUP_INFORMATION"
    else:
        status = "PASS"
    # No clinical data, names, frame IDs, per-frame labels, group IDs,
    # source image SHA values or local paths appear in this report.
    return {
        "schema_version":1,
        "decision":status,
        "task":task,
        "source_manifest_verified":True,
        "source_images_declared":len(records),
        "source_images_sha256_reverified":counts["bytes_reverified"],
        "examination_count":len(per_exam),
        "fit_images":counts["split_fit"],
        "evaluation_images":counts["split_evaluate"],
        "positive_images":counts["label_positive"],
        "explicit_negative_images":counts["label_negative"],
        "unknown_label_images":counts["label_unknown"],
        "issues":sorted(errors) + (["patient_group_not_verified"] if patient_missing else []),
        "patient_independence_proven":False,
        "medical_outcome_access_approved":False,
        "clinically_validated":False,
        "human_review_required":True
    }
