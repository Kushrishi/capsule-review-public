"""Conservative development-fold feasibility audit, not a clinical study.

Reads ONLY the already-public, verified Galar selected-source aggregate.
Optionally accepts a PRIVATE, human-supplied study-level metadata worksheet;
never reads medical pixels, per-image annotation rows or protected outcomes.

The generated four folds are illustrative retrospective development partitions
and are NOT a new untouched holdout, a validated patient grouping, or permission
to train or promote a model. Positive support is measured ONLY on the
source-uniform reference subset, never the outcome-enriched extra frames.

Run: python scripts/audit_development_fold_readiness.py [--json]
     python scripts/audit_development_fold_readiness.py \
       --private-metadata /private/galar-study-metadata.json --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/galar-development-source-audit-20261105/aggregate.json"
EXPECTED = (16, 11147, 8192, 526, 1663)
PRIVATE_KEYS = frozenset(("exam_id", "capsule_system", "collection_site",
                          "patient_group", "patient_mapping_evidence_sha256"))
MAX_METADATA_BYTES = 128 * 1024


def _exam_key(key):
    if not isinstance(key, str) or not key.isdecimal() or int(key) < 1:
        raise ValueError("Malformed source examination key.")
    return int(key)


def _clean_private(metadata, study_ids: set[str]):
    if metadata is None:
        return {}
    if not isinstance(metadata, list) or len(metadata) > len(study_ids):
        raise ValueError("Private study metadata must be a bounded list.")
    verified = {}
    for row in metadata:
        if not isinstance(row, dict) or set(row) != PRIVATE_KEYS:
            raise ValueError("Unrecognized private study-level metadata fields.")
        exam = row["exam_id"]
        if exam not in study_ids or exam in verified:
            raise ValueError("Private study ID unknown or duplicated.")
        for field in ("capsule_system", "collection_site", "patient_group"):
            value = row[field]
            if value is not None and (
                not isinstance(value, str) or not 0 < len(value.strip()) <= 96
            ):
                raise ValueError("Malformed private group/domain field.")
        sha = row["patient_mapping_evidence_sha256"]
        if sha is not None and (
            not isinstance(sha, str) or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise ValueError("Invalid private patient-mapping evidence fingerprint.")
        if row["patient_group"] is not None and sha is None:
            raise ValueError("Patient mapping without source evidence is forbidden.")
        verified[exam] = row
    return verified


def _concentration(values):
    positive = [n for n in values if n > 0]
    if not positive:
        raise ValueError("No positive source examinations to analyze.")
    total = sum(positive)
    return {
        "positive_examinations": len(positive),
        "top_four_positive_image_share": round(sum(sorted(positive, reverse=True)[:4]) / total, 9),
        "effective_positive_exam_count": round(total * total / sum(n*n for n in positive), 6),
    }


def audit(aggregate: dict, private_studies: list | None = None, n_folds: int = 4) -> dict:
    if not isinstance(aggregate, dict) or aggregate.get("schema_version") != 1:
        raise ValueError("Invalid source-integrity aggregate.")
    if (aggregate.get("original_image_sha256_reverified") != 11147
        or aggregate.get("source_byte_mismatch_count") != 0
        or aggregate.get("exact_original_png_sha256_duplicate_count") != 0
        or aggregate.get("patient_independence_verified") is not False
        or aggregate.get("source_complete_original_video_coverage_verified") is not False
        or aggregate.get("authors_reserved_61_80_unopened") is not True
        or aggregate.get("original_locked_11_20_result_unchanged") is not True):
        raise ValueError("The prior audited source population or boundaries changed.")
    rows = aggregate.get("per_examination")
    if not isinstance(rows, dict) or len(rows) != 16 or type(n_folds) is not int:
        raise ValueError("Unexpected source examination inventory.")
    exams = []
    for k, v in rows.items():
        eid = _exam_key(k)
        if eid in (*range(11,21), *range(61,81)):
            raise ValueError("Protected evaluation examination in development pool.")
        if not isinstance(v, dict):
            raise ValueError("Malformed source examination aggregate.")
        fields = ("reference_images", "reference_blood_positive_images",
                  "selected_images", "blood_positive_selected_images",
                  "additional_enrichment_images")
        if any(type(v.get(name)) is not int or v[name] < 0 for name in fields):
            raise ValueError("Missing nonnegative integer source counts.")
        reference, ref_positive, selected, selected_positive, extra = (
            v[k] for k in fields
        )
        if (reference != 512 or selected != reference+extra
            or ref_positive > reference or selected_positive > selected
            or selected_positive < ref_positive):
            raise ValueError("Reference/enrichment accounting is inconsistent.")
        exams.append({
            "id": k, "positive_reference": ref_positive,
            "positive_all_selected": selected_positive, "n_selected": selected,
        })
    totals = (len(exams), sum(e["n_selected"] for e in exams),
              512 * len(exams), sum(e["positive_reference"] for e in exams),
              sum(e["positive_all_selected"] for e in exams))
    if totals != EXPECTED:
        raise ValueError("The verified original development cohort has changed.")
    if n_folds != 4:
        raise ValueError("Only the fixed four-fold FEASIBILITY audit is supported.")

    # Each of the four most positive reference examinations starts in a
    # different fold. Later cases are placed by lowest current positive
    # reference support, subject to exactly 4 exam groups per fold.
    # This uses *previously inspected development labels* to create a
    # descriptive retrospective plan, NOT an untouched prospective test.
    ordered = sorted(exams, key=lambda e: (-e["positive_reference"], int(e["id"])))
    folds = [{"id": i, "groups": [], "positive_reference": 0} for i in range(4)]
    for i, item in enumerate(ordered):
        available = (folds[i],) if i < 4 else (
            f for f in folds if len(f["groups"]) < 4
        )
        dest = min(available, key=lambda f: (
            f["positive_reference"], len(f["groups"]), f["id"]))
        dest["groups"].append(item["id"])
        dest["positive_reference"] += item["positive_reference"]
    if any(len(f["groups"]) != 4 or f["positive_reference"] < 1 for f in folds):
        raise ValueError("Four-fold exploratory partition has insufficient support.")

    source = _clean_private(private_studies, set(rows))
    unknown_device = sum(not source.get(e["id"],{}).get("capsule_system") for e in exams)
    unknown_site = sum(not source.get(e["id"],{}).get("collection_site") for e in exams)
    unknown_group = sum(not source.get(e["id"],{}).get("patient_group") for e in exams)
    reported_devices = Counter(
        source[e["id"]]["capsule_system"] for e in exams
        if e["id"] in source and source[e["id"]]["capsule_system"]
    )
    source_groups = defaultdict(set)
    source_group_is_study_id = False
    for f in folds:
        for eid in f["groups"]:
            record = source.get(eid)
            if record and record["patient_group"]:
                source_groups[record["patient_group"]].add(f["id"])
                source_group_is_study_id |= record["patient_group"] == eid
    cross_fold_group_overlap = sum(len(folds_) > 1 for folds_ in source_groups.values())

    ref = _concentration(e["positive_reference"] for e in exams)
    enriched = _concentration(e["positive_all_selected"] for e in exams)
    return {
        "schema_version": 1,
        "purpose": "retrospective, examination-separated TRAINING feasibility only",
        "source_integrity": "11147 selected original PNGs SHA-verified in previous private audit",
        "source_examinations": 16,
        "selected_images": totals[1],
        "uniform_reference_images": totals[2],
        "uniform_reference_positive": totals[3],
        "selected_positive_including_enrichment": totals[4],
        "enriched_positive_images_excluded_from_reference_metrics": True,
        "reference_concentration": ref,
        "enriched_selection_concentration": enriched,
        "proposed_illustrative_folds": [
            {
                "fold": f["id"]+1, "heldout_exam_count": 4,
                "heldout_uniform_reference_images": 2048,
                "heldout_positive_reference_images": f["positive_reference"],
                "fit_positive_reference_images": totals[3]-f["positive_reference"],
                "patient_disjoint_confirmed": False,
            } for f in folds
        ],
        "fold_generation_used_inspected_development_outcomes": True,
        "new_prospective_holdout_created": False,
        "studies_with_device_information": 16-unknown_device,
        "studies_with_site_information": 16-unknown_site,
        "studies_with_patient_mapping": 16-unknown_group,
        "distinct_reported_devices": len(reported_devices),
        "cross_fold_group_id_collisions": cross_fold_group_overlap,
        "group_id_equals_study_id_seen": source_group_is_study_id,
        "patient_group_evidence_requires_manual_authentication": True,
        "patient_independence_proven": False,
        "source_site_independence_proven": False,
        "clinical_model_promotion_allowed": False,
        "independent_event_coverage_allowed": False,
        "readiness": "EXAMINATION_ONLY_EXPLORATORY_DESIGN",
        "critical_blockers": [
            *([] if unknown_group == 0 else ["patient_group_mapping_missing"]),
            *([] if unknown_device == 0 else ["device_metadata_partial"]),
            *([] if unknown_site == 0 else ["collection_site_metadata_missing"]),
            *(["cross_fold_group_leakage"] if cross_fold_group_overlap else []),
            *(["patient_group_copied_from_study_id"] if source_group_is_study_id else []),
            "complete_source_event_labels_unavailable",
            "all_development_labels_previously_inspected",
            "group_mapping_needs_independent_human_verification",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="Emit safe nonidentifying JSON.")
    p.add_argument("--private-metadata", type=Path,
                   help="Optional private, pseudonymous device/site/group worksheet; never displayed.")
    args = p.parse_args()
    aggregate = json.loads(SOURCE.read_text(encoding="utf-8"))
    private = None
    if args.private_metadata:
        path = args.private_metadata
        if (path.is_symlink() or not path.is_file()
            or path.resolve().is_relative_to(ROOT)
            or not 0 < path.stat().st_size <= MAX_METADATA_BYTES):
            p.error("Private metadata must be a small regular file outside the public repository.")
        try:
            private = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            p.error("Cannot parse private metadata worksheet.")
    try:
        result = audit(aggregate, private)
    except (ValueError, TypeError, KeyError):
        # Never print private metadata contents, source IDs, paths or group tokens.
        p.error("Study metadata or source audit failed strict validation.")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    else:
        a = result["reference_concentration"]
        print("Capsule Review | already inspected development data: EXPLORATORY ONLY")
        print(f"Source-verified selected images: {result['selected_images']:,}, "
              f"but only {result['uniform_reference_images']:,} reference frames")
        print(f"Reference positives: {result['uniform_reference_positive']}; "
              f"top-four-exam share {a['top_four_positive_image_share']:.1%}; "
              f"effective positive examinations {a['effective_positive_exam_count']:.2f}")
        print("Four illustrative held-out groups: reference positives:",
              [f["heldout_positive_reference_images"] for f in result["proposed_illustrative_folds"]])
        print("Patient independence: UNVERIFIED. Clinical model promotion: BLOCKED.")
        print("Unknown grouping/device/site counts:", result["studies_with_patient_mapping"],
              "with patient mapping,", result["studies_with_device_information"],
              "with device,", result["studies_with_site_information"], "with site.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
