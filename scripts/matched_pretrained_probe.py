"""Replay a fixed frozen MobileNetV3-Small blood-label probe on *private* features.

Exploratory previously examined Galar reference examinations only (23,25,27).
The original feature extractor and its 10,123-image embedding cache were
verified in the 2026-11-02 MobileNetV3 project. This program fits no backbone
and never reads any source PNG, annotation runs or Galar 11-20/61-80 images.

Example (PRIVATE output directory outside this repository):
    python scripts/matched_pretrained_probe.py \
      --feature-archive /private/galar-frozen-mobilenet-private-repro.zip \
      --prior-cv-archive /private/Capsule_Review_Private_Exam_Excluded_CV_COMPLETE_20261104.zip \
      --private-output /private/matched-pretrained-probe

The outcome values are exploratory; do not promote a clinical model based
on this code or its original previously inspected development cases.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib
import json
import warnings
import zipfile

FEATURE_FILE = "features/features-10123-float32.bin"
META_FILE = "original-private-source-identity/private_source_metadata.json"
FEATURE_SHA = "611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae"
META_SHA = "78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2"
PRIOR_CV_SHA = "fd6d6c0bdd3ba8feb7838fd88d31674573b4a6fde18c69f2fe945992240124a2"
DESIGN_COMMIT = "b9be0f9f0fe16e4bf5de32257995693ec05ee021"
EXAMS = (23, 25, 27)
BASE = tuple(range(1, 9))
K_VALUES = (51, 128, 256)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_verified_private_features(feature_archive: Path, prior_cv_archive: Path):
    """Refuse unverified source identities, feature data or cohort changes."""
    import numpy as np
    if _sha(prior_cv_archive.read_bytes()) != PRIOR_CV_SHA:
        raise ValueError("Previous exact-examination CNN reference package changed.")
    with zipfile.ZipFile(feature_archive) as archive:
        expected = json.loads(archive.read("SHA256SUMS.json"))
        for name, sha in ((FEATURE_FILE, FEATURE_SHA), (META_FILE, META_SHA)):
            if expected.get(name) != sha or _sha(archive.read(name)) != sha:
                raise ValueError(f"Feature-source integrity mismatch: {name}")
        blob = archive.read(FEATURE_FILE)
        if len(blob) != 10123 * 576 * 4:
            raise ValueError("Unrecognized pretrained feature tensor.")
        features = np.frombuffer(blob, dtype="<f4").reshape(10123, 576)
        metadata = json.loads(archive.read(META_FILE))
        verify = json.loads(archive.read("features/feature-source-verification.json"))
        if (verify.get("all_original_images_sha256_reverified") is not True
            or verify.get("feature_bank_sha256") != FEATURE_SHA
            or verify.get("features_dim") != 576):
            raise ValueError("The original image/embedding verification is absent.")
    if len(metadata) != len(features) or not np.isfinite(features).all():
        raise ValueError("Feature bank is corrupted or nonfinite.")
    if any(int(r["exam"]) in {*range(11, 21), *range(61, 81)} for r in metadata):
        raise ValueError("Protected evaluation sources must not be touched.")
    with zipfile.ZipFile(prior_cv_archive) as previous:
        original_reference = json.loads(previous.read(
            "PRIVATE_reference_frame_labels_and_model_scores.json"))
        for ex in EXAMS:
            current = sorted((r for r in metadata if r["reference"] == 1
                              and r["exam"] == ex), key=lambda r: r["frame"])
            prior = original_reference[str(ex)]
            if len(current) != 512 or len(prior) != 512 or any(
                a["frame"] != b["frame"] or a["blood"] != b["blood"]
                for a, b in zip(current, prior)
            ):
                raise ValueError("Evaluation source frames/labels differ from previous fold.")
    indices = [i for i, r in enumerate(metadata)
               if r["reference"] == 1 and r["exam"] in (*BASE, *EXAMS)]
    if len(indices) != 5632:
        raise ValueError("Incorrect exact reference-only fitting/evaluation population.")
    x = features[indices]
    y = np.array([metadata[i]["blood"] for i in indices], dtype=np.int8)
    exam = np.array([metadata[i]["exam"] for i in indices], dtype=np.int16)
    frame = np.array([metadata[i]["frame"] for i in indices], dtype=np.int64)
    if (set(exam.tolist()) != set((*BASE, *EXAMS))
        or any((exam == e).sum() != 512 for e in (*BASE, *EXAMS))
        or y[np.isin(exam, BASE)].sum() != 239
        or [int(y[exam == e].sum()) for e in EXAMS] != [4, 14, 26]):
        raise ValueError("The source reference split or label support has changed.")
    return x, y, exam, frame


def fit_one_fold(x, y, exam, heldout: int):
    """Fixed training-fold-only scaling and C=0.1 linear probe, one fit."""
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, average_precision_score
    if heldout not in EXAMS:
        raise ValueError("Only the three previously inspected cases are permitted.")
    fit_exams = (*BASE, *(e for e in EXAMS if e != heldout))
    train = np.isin(exam, fit_exams)
    test = (exam == heldout)
    if (train.sum() != 5120 or test.sum() != 512 or (train & test).any()
        or int(y[train].sum()) != {23: 279, 25: 269, 27: 257}[heldout]):
        raise ValueError("Training-fold examination exclusion failed.")
    scaler = StandardScaler(with_mean=True, with_std=True)
    train_x = scaler.fit_transform(x[train])
    test_x = scaler.transform(x[test])
    probe = LogisticRegression(C=.1, class_weight="balanced", solver="lbfgs",
                               max_iter=300, tol=1e-6, fit_intercept=True,
                               random_state=37)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        probe.fit(train_x, y[train])
    predictions = probe.predict_proba(test_x)[:, 1]
    if len(predictions) != 512 or not np.isfinite(predictions).all():
        raise ValueError("Invalid held-out predictions.")
    order = np.lexsort((np.arange(len(predictions)), -predictions))
    metrics = {
        "evaluated_exam": heldout, "fitted_examinations": list(fit_exams),
        "training_images": int(train.sum()), "positive_training_images": int(y[train].sum()),
        "test_images": int(test.sum()), "test_positive": int(y[test].sum()),
        "roc_auc": float(roc_auc_score(y[test], predictions)),
        "average_precision": float(average_precision_score(y[test], predictions)),
        "positive_hits": {str(k): int(y[test][order[:k]].sum()) for k in K_VALUES},
        "iterations": int(probe.n_iter_[0]),
        "convergence_warnings": [str(w.message) for w in seen],
    }
    private = {"coefficients": probe.coef_, "intercept": probe.intercept_,
               "mean": scaler.mean_, "scale": scaler.scale_,
               "predictions": predictions, "reference_labels": y[test],
               "reference_ordinals": np.flatnonzero(test)}
    return metrics, private


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-archive", required=True, type=Path)
    parser.add_argument("--prior-cv-archive", required=True, type=Path)
    parser.add_argument("--private-output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.private_output.resolve()
    if output.is_relative_to(root) or output.exists():
        raise ValueError("Use a new private output directory OUTSIDE the public source tree.")
    x, y, exam, frame = read_verified_private_features(args.feature_archive,
                                                        args.prior_cv_archive)
    output.mkdir(parents=True, exist_ok=False)
    import numpy as np
    private_receipt = {"design_commit": DESIGN_COMMIT, "status":"development-only",
                       "model_promoted": False, "cases": {}}
    for heldout in EXAMS:
        metric, sensitive = fit_one_fold(x, y, exam, heldout)
        selected = exam == heldout
        # Source ordinals, image-derived probabilities and coefficient vectors
        # always remain in private files.
        np.savez_compressed(output / f"PRIVATE_examination_{heldout}.npz",
                            frame=frame[selected], **sensitive)
        private_receipt["cases"][str(heldout)] = metric
        print(f"Exam {heldout}: AUC={metric['roc_auc']:.4f}, "
              f"AP={metric['average_precision']:.4f}, "
              f"top51={metric['positive_hits']['51']}")
    (output / "PRIVATE_receipt.json").write_text(
        json.dumps(private_receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
