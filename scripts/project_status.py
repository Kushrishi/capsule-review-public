"""Show the current *verified public scientific record* without opening private data.

This intentionally reads the authoritative, already published aggregate JSONs,
rather than duplicating results in an increasingly long README.

Usage:
    python scripts/project_status.py
    python scripts/project_status.py --json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKED = ROOT / "experiments/galar-unseen-11-20-20261104/aggregate.json"
DEVELOPMENT = ROOT / "experiments/galar-matched-pretrained-probe-20261104/aggregate.json"


def load(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size < 512 * 1024:
        raise ValueError("Required public aggregate is missing or not a small regular JSON file.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if type(data) is not dict:
        raise ValueError("Invalid public aggregate.")
    return data


def summarize(locked: dict, development: dict) -> dict:
    """Verify completed-study boundaries before presenting numerical outcomes."""
    if (locked.get("source_images") != 163161
        or locked.get("primary_review_percent") != 10
        or locked.get("defined_primary_examinations") != 6
        or sorted(map(int, locked.get("undefined_zero_positive_examinations", []))) != [13,14,16,18]
        or locked.get("authors_reserved_61_to_80_opened") is not False
        or locked.get("clinical_validation") is not False
        or locked.get("model_tuned_on_evaluation_outcomes") is not False
        or locked.get("patient_independence_verified") is not False
        or locked.get("reading_time_benefit_measured") is not False):
        raise ValueError("Locked Galar study identities or scientific boundaries changed.")

    ten = locked["budget_summary"]["10"]["policies"]
    twenty_five = locked["budget_summary"]["25"]["policies"]
    delta_10 = (ten["score_bin"]["mean_defined_examination_run_recall"]
                - ten["uniform"]["mean_defined_examination_run_recall"]) * 100
    delta_25 = (twenty_five["score_bin"]["mean_defined_examination_run_recall"]
                - twenty_five["uniform"]["mean_defined_examination_run_recall"]) * 100
    if (not math.isclose(delta_10, -1.2668765, abs_tol=1e-6)
        or not math.isclose(delta_25, 9.5106442, abs_tol=1e-6)
        or not math.isclose(locked["mean_examination_level_score_bin_minus_uniform_run_recall"] * 100,
                             delta_10, abs_tol=1e-6)
        or ten["score"]["positive_annotated_images_hit"] != 305
        or ten["score"]["pooled_annotation_runs_hit"] != 28
        or ten["uniform"]["positive_annotated_images_hit"] != 170
        or ten["uniform"]["pooled_annotation_runs_hit"] != 63):
        raise ValueError("Published negative primary or distinct-run comparison changed.")

    if (development.get("clinical_validity") is not False
        or development.get("model_promoted") is not False
        or development.get("galar_locked_11_20_reused") is not False
        or development.get("galar_reserved_61_80_opened") is not False
        or development.get("evaluation", {}).get("examinations") != [23,25,27]):
        raise ValueError("Development results have been misrepresented as validation.")
    results = development["aggregate"]
    original = results["original_checkpoint"]
    pretrained = results["frozen_mobilenet_v3_linear_probe"]
    if (original["total_positive_images_hit"]["51"] != 22
        or pretrained["total_positive_images_hit"]["51"] != 15
        or not 0.49 < original["mean_examination_roc_auc"] < 0.50
        or not 0.60 < pretrained["mean_examination_roc_auc"] < 0.62
        or not pretrained["mean_examination_average_precision"]
            < original["mean_examination_average_precision"]):
        raise ValueError("Latest development trade-off was changed or erased.")

    return {
        "evidence_state": "completed retrospective research, not clinical validation",
        "viewer": "functional local research software; no public pathology checkpoint",
        "locked_study": {
            "source_images": locked["source_images"],
            "examinations": 10,
            "defined_positive_run_examinations": 6,
            "primary_workload_percent": 10,
            "uniform_macro_run_recall_percent": round(
                ten["uniform"]["mean_defined_examination_run_recall"] * 100, 3),
            "score_bin_macro_run_recall_percent": round(
                ten["score_bin"]["mean_defined_examination_run_recall"] * 100, 3),
            "primary_paired_difference_pp": round(delta_10, 7),
            "secondary_25_percent_difference_pp": round(delta_25, 7),
            "primary_demonstrated_benefit": False,
        },
        "latest_development": {
            "status": "exploratory, previously inspected examination references",
            "examinations": [23, 25, 27],
            "original_cnn_macro_auc": round(original["mean_examination_roc_auc"], 3),
            "pretrained_probe_macro_auc": round(pretrained["mean_examination_roc_auc"], 3),
            "original_cnn_positive_hits_at_51_total": 22,
            "pretrained_probe_positive_hits_at_51_total": 15,
            "model_promoted": False,
        },
        "external_evaluation": "blocked: no independent, fully annotated cohort qualified",
        "reserved_galar_61_80": "unopened",
        "next_gate": "verify development cohort groups, label coverage, source rights and stable training/evaluation splits before more model comparisons",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit the nonidentifying status JSON.")
    args = parser.parse_args()
    state = summarize(load(LOCKED), load(DEVELOPMENT))
    if args.json:
        print(json.dumps(state, indent=2, sort_keys=True))
    else:
        l, d = state["locked_study"], state["latest_development"]
        print("CAPSULE REVIEW | public evidence, not clinical validation")
        print("Software: functional local viewer; no publicly distributed pathology model")
        print(f"Locked Galar {l['source_images']:,} images: 10% primary score-bin "
              f"{l['score_bin_macro_run_recall_percent']:.2f}% vs uniform "
              f"{l['uniform_macro_run_recall_percent']:.2f}%, "
              f"delta {l['primary_paired_difference_pp']:+.2f} pp (negative)")
        print(f"25% secondary delta {l['secondary_25_percent_difference_pp']:+.2f} pp; nonconfirmatory")
        print(f"Exploratory cases {d['examinations']}: AUC "
              f"{d['original_cnn_macro_auc']:.3f} -> {d['pretrained_probe_macro_auc']:.3f}, "
              f"but top-51 positive hits {d['original_cnn_positive_hits_at_51_total']} "
              f"-> {d['pretrained_probe_positive_hits_at_51_total']}; NO promotion")
        print("External clinical cohort: NOT QUALIFIED. Reserved Galar 61–80: unopened.")
        print("Next: verify development cohort and independent event labels before model claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
