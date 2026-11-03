"""Post-hoc examination-level robustness of the public Galar negative-expansion comparison.

Reads ONLY an already-published aggregate JSON: never loads medical images,
individual annotations, model predictions, checkpoints, or private archives.
This is exploratory sensitivity analysis, not confirmatory inference.
"""
from __future__ import annotations

import argparse
from itertools import product
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "experiments/galar-negative-expansion-cv-2026-11-02/paired_comparison.json"
ORIGINAL_EVALUATED = (1, 2, 3, 4, 5, 6, 7, 8, 21, 23, 25, 27, 29, 30)
HIGH_SUPPORT = (1, 7, 25, 27, 29, 30)
# These are the frozen model-fitting folds intersected with HIGH_SUPPORT.
FOLDS = {"A": (1, 27, 29), "B": (25, 30), "C": (7,)}


def _number(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Invalid numeric {name}.")
    return float(value)


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("Cannot average an empty examination group.")
    return sum(values) / len(values)


def _percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        raise ValueError("No bootstrap values.")
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def analyze(paired: dict) -> dict:
    """Recompute descriptive uncertainty using whole examinations, never frames."""
    if not isinstance(paired, dict):
        raise ValueError("Expected a public aggregate JSON object.")
    if (paired.get("clinical_validity") is not False
        or paired.get("model_promotion_authorized") is not False
        or paired.get("no_reserved_exams_accessed") is not True
        or paired.get("additional_training_only_examinations") != [22, 24]
        or paired.get("heldout_examinations_exactly_the_original_14") != list(ORIGINAL_EVALUATED)):
        raise ValueError("This comparison differs from the published exploratory protocol.")
    rows = paired.get("per_exam")
    if not isinstance(rows, dict) or set(rows) != {str(x) for x in ORIGINAL_EVALUATED}:
        raise ValueError("Missing, extra, or protected evaluation examination in the aggregate.")
    differences: dict[int, float] = {}
    hits: dict[int, tuple[int, int]] = {}
    support: list[int] = []
    for exam in ORIGINAL_EVALUATED:
        r = rows[str(exam)]
        if not isinstance(r, dict) or r.get("n") != 512:
            raise ValueError("Changed or malformed reference examination.")
        positives = r.get("blood_positive_reference_images")
        if type(positives) is not int or not 0 <= positives <= 512:
            raise ValueError("Invalid labelled positive count.")
        old, new, delta = (
            r.get("baseline_roc_auc"),
            r.get("expanded_training_roc_auc"),
            r.get("auc_difference"),
        )
        if positives == 0:
            if old is not None or new is not None or delta is not None:
                raise ValueError("Undefined zero-positive ROC-AUC was replaced with a number.")
        else:
            old = _number(old, "old ROC-AUC")
            new = _number(new, "new ROC-AUC")
            delta = _number(delta, "paired ROC-AUC difference")
            if not 0 <= old <= 1 or not 0 <= new <= 1 or abs((new - old) - delta) > 1e-12:
                raise ValueError("Changed or inconsistent published paired AUC values.")
            differences[exam] = delta
        if positives >= 10:
            support.append(exam)
        old_hits = r.get("baseline_topk_positive")
        new_hits = r.get("expanded_topk_positive")
        if not isinstance(old_hits, dict) or not isinstance(new_hits, dict):
            raise ValueError("Missing published top-K comparison.")
        o, n = old_hits.get("51"), new_hits.get("51")
        if type(o) is not int or type(n) is not int or not (0 <= o <= min(51, positives)) or not (0 <= n <= min(51, positives)):
            raise ValueError("Invalid top-51 positive-image counts.")
        hits[exam] = (o, n)

    if tuple(support) != HIGH_SUPPORT:
        raise ValueError("High-support evaluation examination set changed.")
    old_sum = sum(old for old, _ in hits.values())
    new_sum = sum(new for _, new in hits.values())
    paired_k = paired.get("all_14_exam_positive_image_hits_by_k", {}).get("51", {})
    if paired_k.get("old") != old_sum or paired_k.get("new") != new_sum:
        raise ValueError("Published top-51 aggregate does not match examination rows.")

    high_old = _mean([_number(rows[str(e)]["baseline_roc_auc"], "old high-support AUC") for e in HIGH_SUPPORT])
    high_new = _mean([_number(rows[str(e)]["expanded_training_roc_auc"], "new high-support AUC") for e in HIGH_SUPPORT])
    reported = paired.get("macro_roc_auc_high_support_6", {})
    if any(abs(_number(reported.get(k), k) - v) > 1e-12
           for k, v in (("old", high_old), ("new", high_new), ("delta", high_new - high_old))):
        raise ValueError("Reported six-examination macro AUC does not match its rows.")

    values = [differences[e] for e in HIGH_SUPPORT]
    n = len(values)
    # Enumerate ALL 6^6 equally weighted bootstrap sequences. No frame
    # resampling, random seed, hidden patient independence, or MC approximation.
    bootstrap = sorted(_mean([values[i] for i in draw]) for draw in product(range(n), repeat=n))
    leave_one_exam = {
        str(e): _mean([differences[other] for other in HIGH_SUPPORT if other != e])
        for e in HIGH_SUPPORT
    }
    leave_one_fold = {
        name: _mean([differences[e] for e in HIGH_SUPPORT if e not in fold])
        for name, fold in FOLDS.items()
    }
    return {
        "schema_version": 1,
        "study": "post-hoc-public-aggregate-examination-robustness-audit",
        "source": "experiments/galar-negative-expansion-cv-2026-11-02/paired_comparison.json",
        "high_support_examinations": list(HIGH_SUPPORT),
        "sampled_unit": "whole previously inspected examination, not image or patient",
        "exam_level_auc_differences": {str(e): differences[e] for e in HIGH_SUPPORT},
        "examinations_improved": sum(d > 0 for d in values),
        "mean_auc_difference": _mean(values),
        "minimum_auc_difference": min(values),
        "maximum_auc_difference": max(values),
        "bootstrap_descriptive": {
            "method": "exhaustive equal-probability examination resampling with replacement; linear-interpolated percentile",
            "enumerated_draws": len(bootstrap),
            "lower_2_5_percent": _percentile(bootstrap, 0.025),
            "upper_97_5_percent": _percentile(bootstrap, 0.975),
            "not_a_confirmatory_patient_or_clinical_confidence_interval": True,
        },
        "leave_one_examination_out_mean_auc_difference": leave_one_exam,
        "leave_one_fitting_fold_out_mean_auc_difference": leave_one_fold,
        "top_51_all_14_exams": {"old_positive_labelled_images": old_sum,
                                "expanded_positive_labelled_images": new_sum,
                                "difference": new_sum - old_sum},
        "unresolved_hard_examinations": {
            str(e): {"old_top_51_positive_images": hits[e][0],
                     "expanded_top_51_positive_images": hits[e][1]}
            for e in (23, 25)
        },
        "no_private_source_rows_or_model_records_read": True,
        "model_promotion_authorized": False,
        "clinical_validity": False,
        "interpretation": (
            "Exploratory post-hoc sensitivity analysis over six previously examined studies, "
            "some sharing a trained fold model. Patient independence is unverified, "
            "ROC-AUC is not distinct-lesion sensitivity, and 51 frames is an experimental "
            "review-budget point rather than a product restriction. The bootstrap interval "
            "is descriptive and cannot establish patient-level or clinical generalization."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="Optional aggregate-only JSON file; never overwrite")
    args = parser.parse_args()
    # Avoid arbitrary sensitive JSON input and unbounded reads; use the public
    # paired aggregate only, with a strict size limit.
    if not args.input.is_file() or args.input.stat().st_size > 256 * 1024:
        raise ValueError("Missing or oversized public aggregate input.")
    result = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            out.write(encoded)


if __name__ == "__main__":
    main()
