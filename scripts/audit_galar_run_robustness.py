"""Examination-paired robustness audit of already-frozen Galar run-count results.

This analyzes only the PUBLIC, previously verified run-coverage aggregate.
No pixels, original frame IDs, individual labels, scores, or source archive are
read. Descriptive/post-hoc only: no patient independence, p-values or promotion.

Example:
  python scripts/audit_galar_run_robustness.py \
    --input experiments/galar-run-coverage-2026-11-02/aggregate.json \
    --output experiments/galar-run-robustness-2026-11-03/aggregate.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = "8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07"
LABELS_SHA256 = "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
EXAMS = ("9", "10", "21", "23", "25", "27", "29", "30")
BUDGET_IMAGES = {"5": 25, "10": 51, "25": 128, "50": 256, "75": 384, "100": 512}
METHODS = ("original_checkpoint", "red_excess", "uniform")
STRATA = ("1-5", "6-25", "26+")


def count(value: object, label: str, maximum: int | None = None) -> int:
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        raise ValueError("Invalid " + label + ".")
    return value


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("No source-positive examinations available.")
    return sum(values) / len(values)


def _rounded(value: float) -> float:
    return round(value, 8)


def audit(source: dict) -> dict:
    """Recalculate the case-weighted and sensitivity summary, checking input invariants."""
    if not isinstance(source, dict):
        raise ValueError("Source audit must be a JSON object.")
    if source.get("source_corrected_release_sha256") != LABELS_SHA256:
        raise ValueError("Corrected-source identity is not pinned.")
    if source.get("reference_per_exam") != 512:
        raise ValueError("Expected 512 reference images per previously inspected exam.")
    exams = source.get("examinations")
    if not isinstance(exams, dict) or set(exams) != set(EXAMS):
        raise ValueError("Unexpected case IDs: cannot include reserved or new examinations.")
    if source.get("clinical_validation") is not False or source.get("medical_images_or_frame_scores_committed") is not False:
        raise ValueError("Public-only/nonclinical source provenance mismatch.")

    positive_ids = []
    total_runs = total_reachable = 0
    full_source_by_stratum = {name: 0 for name in STRATA}
    reachable_by_stratum = {name: 0 for name in STRATA}
    for exam_id in EXAMS:
        exam = exams[exam_id]
        if not isinstance(exam, dict) or exam.get("reference_count") != 512:
            raise ValueError("Unexpected imported source reference count.")
        runs = count(exam.get("source_blood_annotation_runs"), "source annotation runs")
        reachable = count(exam.get("reference_run_ceiling_hits"), "reference run ceiling", runs)
        positives = count(exam.get("reference_blood_positive"), "positive reference images", 512)
        if positives and (not runs or not reachable):
            raise ValueError("Positive reference annotations without accessible source runs.")
        if runs == 0 and (reachable or positives):
            raise ValueError("Source-negative-labelled exam contradicts positive references.")
        if runs:
            positive_ids.append(exam_id)
        total_runs += runs
        total_reachable += reachable
        source_strata = exam.get("source_run_length_categories")
        reachable_strata = exam.get("reference_ceiling_by_length")
        if not isinstance(source_strata, dict) or not isinstance(reachable_strata, dict):
            raise ValueError("Missing full source run-length strata.")
        if set(source_strata) != set(STRATA) or set(reachable_strata) != set(STRATA):
            raise ValueError("Unexpected run-length strata.")
        if sum(count(source_strata[k], "source stratum") for k in STRATA) != runs:
            raise ValueError("Source run lengths do not reconcile.")
        if sum(count(reachable_strata[k], "reachable stratum", source_strata[k]) for k in STRATA) != reachable:
            raise ValueError("Reference run ceiling strata do not reconcile.")
        for label in STRATA:
            full_source_by_stratum[label] += source_strata[label]
            reachable_by_stratum[label] += reachable_strata[label]
        records = exam.get("budgets")
        if not isinstance(records, dict) or set(records) != set(BUDGET_IMAGES):
            raise ValueError("Missing one or more frozen review workloads.")
        previous_hits = {name: -1 for name in METHODS}
        for percent, k in BUDGET_IMAGES.items():
            record = records[percent]
            if not isinstance(record, dict) or record.get("selected_reference_images") != k:
                raise ValueError("Not an identical imported-image workload across cases.")
            method_records = record.get("methods")
            if not isinstance(method_records, dict) or not set(METHODS) <= set(method_records):
                raise ValueError("A required fixed baseline is missing.")
            for method in METHODS:
                m = method_records[method]
                if not isinstance(m, dict):
                    raise ValueError("Malformed baseline result.")
                hits = count(m.get("source_annotation_runs_hit"), "distinct source runs", reachable)
                image_hits = count(m.get("blood_positive_reference_images_found"), "positive reference images", min(k, positives))
                count(m.get("blood_annotation_negative_images_selected"), "nonpositive selected images", k)
                if hits > image_hits or (hits == 0) != (image_hits == 0):
                    raise ValueError("Positive images and source annotation runs contradict each other.")
                if image_hits + m["blood_annotation_negative_images_selected"] != k:
                    raise ValueError("Selected image hit counts do not sum to fixed workload.")
                # Ranked top-K prefixes are nested. Midpoint-uniform picks are
                # independently re-spaced at each K and need NOT be nested:
                # a small source run can disappear at a larger uniform budget.
                if method != "uniform" and hits < previous_hits[method]:
                    raise ValueError("A ranked top-K prefix lost an already reached source run.")
                previous_hits[method] = hits
                length_results = m.get("by_run_length_category")
                if not isinstance(length_results, dict) or set(length_results) != set(STRATA):
                    raise ValueError("Missing run-length coverage details.")
                if sum(count(length_results[label], "retained run stratum", reachable_strata[label])
                       for label in STRATA) != hits:
                    raise ValueError("Method source-run strata do not sum to selected runs.")
                if percent == "100" and (hits != reachable or image_hits != positives):
                    raise ValueError("The full-reference ceiling must match every baseline.")
    if not positive_ids or len(positive_ids) < 2 or total_runs == 0:
        raise ValueError("Insufficient positive-source examinations for paired audit.")

    out = {
        "schema_version": 1,
        "study": "Post-hoc examination-paired source annotation-run robustness audit",
        "source_aggregate_sha256": SOURCE_SHA256,
        "corrected_source_archive_sha256_from_prior_verified_audit": LABELS_SHA256,
        "source_data_access": "Existing public source-locked aggregate only; no new pixels, original labels, per-frame scores, or reserved studies read",
        "scientific_design": {
            "exam_ids_previously_inspected": list(EXAMS),
            "positive_source_exam_count": len(positive_ids),
            "blood_negative_label_exam_ids": [k for k in EXAMS if exams[k]["source_blood_annotation_runs"] == 0],
            "one_exam_one_unit": True,
            "patient_independence_verified": False,
            "independent_holdout_or_blinded_test": False,
            "clinical_validation": False,
            "selection_model_promoted": False,
            "primary_descriptive_metric": "macro average of per-exam (distinct blood-positive source annotation runs retrieved / original source positive annotation runs)",
            "macro_mean_equal_weight_per_positive_exam": True,
            "micro_ratio_is_case_mix_weighted": True,
            "run_is_not_adjudicated_lesion": True,
            "fixed_review_workload_each_exam": BUDGET_IMAGES,
            "methods_present_all_exams": list(METHODS),
            "excluded_unmatched_methods": "continued-model arms available only for some fitting/transfer exams; do not pool as though tested on every case",
            "zero_positive_exams_excluded_from_run_recall_denominator": True,
            "source_index_spacing_is_not_capture_time": True,
            "no_significance_tests": "Seven positive-source examinations, prior case inspection and unverified patient independence preclude confirmatory p-values.",
        },
        "source_run_coverage_ceiling": {
            "full_source_annotation_runs": total_runs,
            "runs_reachable_by_all_512_reference_images": total_reachable,
            "unreachable_even_at_full_reference_workload": total_runs - total_reachable,
            "short_1_to_5_source_runs": full_source_by_stratum["1-5"],
            "short_1_to_5_reachable_runs": reachable_by_stratum["1-5"],
        },
        "review_budgets": {},
    }
    for percent, k in BUDGET_IMAGES.items():
        result = {
            "selected_imported_images_per_exam": k,
            "methods": {},
            "paired_against_uniform": {},
        }
        for method in METHODS:
            counts = [exams[case]["budgets"][percent]["methods"][method]["source_annotation_runs_hit"]
                      for case in positive_ids]
            total_hits = sum(counts)
            macro = _mean([n / exams[case]["source_blood_annotation_runs"]
                           for case, n in zip(positive_ids, counts)])
            conditional = _mean([n / exams[case]["reference_run_ceiling_hits"]
                                 for case, n in zip(positive_ids, counts)])
            stratified = {label: sum(exams[case]["budgets"][percent]["methods"][method]["by_run_length_category"][label]
                                     for case in positive_ids) for label in STRATA}
            result["methods"][method] = {
                "sum_distinct_source_annotation_runs_hit": total_hits,
                "micro_source_run_recall": _rounded(total_hits / total_runs),
                "macro_per_exam_source_run_recall": _rounded(macro),
                "macro_per_exam_accessible_run_fraction": _rounded(conditional),
                "short_1_to_5_run_hits": stratified["1-5"],
                "medium_6_to_25_run_hits": stratified["6-25"],
                "long_26_plus_run_hits": stratified["26+"],
                "selected_image_count_in_blood_negative_label_exams": k * (len(EXAMS) - len(positive_ids)),
            }
        for method in METHODS:
            if method == "uniform":
                continue
            paired = []
            for case in positive_ids:
                source_runs = exams[case]["source_blood_annotation_runs"]
                candidate_hits = exams[case]["budgets"][percent]["methods"][method]["source_annotation_runs_hit"]
                uniform_hits = exams[case]["budgets"][percent]["methods"]["uniform"]["source_annotation_runs_hit"]
                paired.append((case, (candidate_hits - uniform_hits) / source_runs))
            differences = [difference for _, difference in paired]
            macro_delta = _mean(differences)
            leave_out = {case: _rounded(_mean([diff for other, diff in paired if other != case]))
                         for case, _ in paired}
            wins = sum(value > 0 for value in differences)
            losses = sum(value < 0 for value in differences)
            ties = len(differences) - wins - losses
            sign = lambda x: (x > 1e-12) - (x < -1e-12)
            flipped = [case for case, value in leave_out.items() if sign(value) != sign(macro_delta)]
            result["paired_against_uniform"][method] = {
                "macro_source_run_recall_difference": _rounded(macro_delta),
                "positive_exam_wins": wins,
                "positive_exam_ties": ties,
                "positive_exam_losses": losses,
                "minimum_leave_one_exam_out_difference": min(leave_out.values()),
                "maximum_leave_one_exam_out_difference": max(leave_out.values()),
                "leave_one_exam_out_difference_by_exam": leave_out,
                "cases_whose_removal_changes_effect_direction": flipped,
                "variance_warning": (
                    "Uncertainty unit is examination, not individual images or runs. "
                    "Leave-one-exam-out ranges are descriptive stability checks, not 95% CIs."
                ),
            }
        out["review_budgets"][percent] = result
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file() or args.input.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Missing or oversized previously frozen public aggregate.")
    if hashlib.sha256(args.input.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The frozen verified public aggregate identity changed.")
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite a previous robustness receipt.")
    report = audit(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(report, destination, sort_keys=True, indent=2, allow_nan=False)
        destination.write("\n")
    print("Audited equal-workload, per-examination run retrieval; exploratory, no model promotion.")


if __name__ == "__main__":
    main()
