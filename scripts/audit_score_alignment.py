"""Private-only replay of fixed retrospective chronology controls.

No acquisition, inference, checkpoint deserialization or fitting. Output contains
only examination aggregates. Source labels/scores never enter public Actions.
See docs/CHRONOLOGY_CONTROL_LOCK_20261106.md for the analysis boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np

from capsule_review.exam_balance import ARMS, HELDOUT_FOLDS, EXACT_K
from capsule_review.score_alignment import alignment_controls, summarize_alignment

ARCHIVE_SHA = "9dd1cca41d07299191cd867886ddfa7c1d84d8b188a9ff349b8067ca541f1ea1"
LOCK_COMMIT = "52ddf6e56560fae0ce54f62650cacec9d89f3f9d"
METHODS = ("score", "score_bin", "uniform")
ROOT = Path(__file__).resolve().parents[1]


def verified_reference_scores(archive: Path):
    """Reconcile fixed archive, source roles, folds and previous positive hits.

    The retained source-byte verification is inherited, not repeated: this
    package contains no medical pixels. It does not authenticate patient IDs.
    """
    if archive.stat().st_size != 949542 or hashlib.sha256(
        archive.read_bytes()
    ).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Wrong retained private prediction package.")
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError("Duplicate archive members.")
        hashes = json.loads(z.read("SHA256SUMS.json"))
        for name, receipt in hashes.items():
            raw = z.read(name)
            if (len(raw) != receipt["bytes"]
                    or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
                raise ValueError("Private package member integrity failure.")
        source_bytes = z.read("PRIVATE_selected_source_metadata.json")
        rows = json.loads(source_bytes)
        old = json.loads(z.read("PRIVATE_results.json"))
        if (hashlib.sha256(source_bytes).hexdigest() != old["data_metadata_sha"]
                or len(rows) != 11147 or len(old["folds"]) != 4
                or old["patient_independence_verified"] is not False
                or old["excluded_original_11_to_20"] is not True
                or old["reserved_original_61_to_80_unopened"] is not True):
            raise ValueError("Private cohort commitment or protected boundary changed.")
        allowed = {e for fold in HELDOUT_FOLDS for e in fold}
        if set(r["exam"] for r in rows) != allowed:
            raise ValueError("Unexpected or protected examination.")
        identities = set()
        for r in rows:
            key = (r["exam"], r["frame"])
            if (type(r["exam"]) is not int or type(r["frame"]) is not int
                    or r["frame"] < 0 or key in identities
                    or type(r["blood"]) is not int or r["blood"] not in (0, 1)
                    or type(r["reference"]) is not int or r["reference"] not in (0, 1)):
                raise ValueError("Unknown labels, duplicate identities or invalid reference roles.")
            identities.add(key)
        public_old = json.loads((ROOT / "experiments/galar-exam-tempered-cnn-20261105/aggregate.json").read_text())
        result = {arm: {} for arm in ARMS}
        for i, heldout in enumerate(HELDOUT_FOLDS, 1):
            fold = old["folds"][i - 1]
            test = sorted((r for r in rows if r["exam"] in heldout and r["reference"] == 1),
                          key=lambda r: (r["exam"], r["frame"]))
            fit = [r for r in rows if r["exam"] not in heldout]
            if (fold["fold"] != i or fold["heldout_examinations"] != list(heldout)
                    or set(fold["train_examinations"]) != allowed - set(heldout)
                    or len(test) != 2048 or len(fit) != fold["n_train"]
                    or sum(r["blood"] for r in fit) != fold["n_train_pos"]
                    or sum(r["blood"] for r in test) != fold["n_test_pos"]):
                raise ValueError("Historical examination-exclusion contract changed.")
            for arm in ARMS:
                raw = z.read(f"PRIVATE_scores_fold{i}_{arm}.npy")
                prior = fold["arms"][arm]
                if hashlib.sha256(raw).hexdigest() != prior["saved_prediction_sha256"]:
                    raise ValueError("Prediction commitment changed.")
                scores = np.load(io.BytesIO(raw), allow_pickle=False)
                if scores.shape != (2048,) or not np.isfinite(scores).all() or (
                    (scores < 0).any() or (scores > 1).any()
                ):
                    raise ValueError("Invalid held-out score array.")
                for exam in heldout:
                    positions = [p for p, r in enumerate(test) if r["exam"] == exam]
                    y = [test[p]["blood"] for p in positions]
                    s = [float(scores[p]) for p in positions]
                    if len(y) != 512:
                        raise ValueError("Incomplete original reference population.")
                    hist = public_old["per_examination"][str(exam)]
                    if sum(y) != hist["positive_reference_images"]:
                        raise ValueError("Historical positive support changed.")
                    ranked = sorted(range(512), key=lambda p: (-s[p], p))
                    for k in EXACT_K:
                        hits = sum(y[p] for p in ranked[:k])
                        if (hits != prior["exam_results"][str(exam)]["positive_hits"][str(k)]
                                or hits != hist["methods"][arm]["hits"][str(k)]):
                            raise ValueError("Historical retrieval failed independent reconciliation.")
                    result[arm][str(exam)] = (y, s)
        if any(len(cases) != 16 for cases in result.values()):
            raise ValueError("Missing examination.")
        return result


def run(archive: Path) -> dict:
    inputs = verified_reference_scores(archive)
    cases, summaries = {}, {}
    for arm, examinations in inputs.items():
        cases[arm] = {}
        summaries[arm] = {}
        for method in METHODS:
            summaries[arm][method] = {}
            for k in EXACT_K:
                records = []
                for exam, (y, s) in sorted(examinations.items(), key=lambda x: int(x[0])):
                    record = alignment_controls(y, s, k, method)
                    cases[arm].setdefault(exam, {}).setdefault(method, {})[str(k)] = record
                    records.append(record)
                summaries[arm][method][str(k)] = summarize_alignment(records)
    return {
        "schema_version": 1, "analysis": "retrospective-chronology-conditioned-score-alignment",
        "preanalysis_commit": LOCK_COMMIT, "input_archive_sha256": ARCHIVE_SHA,
        "source_reference_images_per_arm": 8192, "chronological_blocks": 16,
        "reference_positions_per_block": 32,
        "new_training_or_inference": False, "patient_independence_verified": False,
        "complete_sequence_event_endpoint": False, "clinical_model_promoted": False,
        "galar35_repeated": False, "protected_11_20_or_61_80_accessed": False,
        "per_examination": cases, "summary": summaries,
        "primary": summaries[ARMS[0]]["score"]["51"],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if (args.output.exists() or args.output.is_symlink()
            or args.output.resolve().is_relative_to(ROOT)):
        p.error("Use a fresh private output outside public Git; release requires review.")
    result = run(args.private_archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    print(json.dumps(result["primary"], sort_keys=True))


if __name__ == "__main__":
    main()
