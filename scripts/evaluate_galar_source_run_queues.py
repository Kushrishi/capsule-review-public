"""Galar source-annotation-run retrieval under four exact-K review queues.

RESEARCH ONLY. Reads the exact publisher-corrected label ZIP and two previously
source-verified PRIVATE score packages from user-supplied local paths. Reads
ONLY examined source CSVs 21/23/25/27/29/30, never 11–20 or 61–80. Source
labels are for *evaluation only*: selection calls the production label-blind
priority selector with numerical scores, never the labels.

A run is a maximal consecutive stretch of corrected blood=1 annotation rows
with source-frame increment exactly 5; NOT an adjudicated distinct lesion.
This is a post-hoc previously inspected cohort, NOT independent validation.

Usage:
  python scripts/evaluate_galar_source_run_queues.py \
    --corrected-labels /private/20251215_Labels_Updated.zip \
    --frozen-scores /private/capsule-galar-frozen-transfer-private-repro.zip \
    --appearance-scores /private/galar-appearance-audit-private.zip \
    --prior-aggregate experiments/galar-run-coverage-2026-11-02/aggregate.json \
    --output /private/galar-source-run-four-policy-audit.json

Requires exact original SHA-256s. No image identifiers, patient metadata,
individual labels/scores, or source-run memberships are written to output.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

from capsule_review.priority import select_positions

# Historical November 3 source-run audit was frozen to these four policies.
# Never import the growing set of live product options into its replay.
METHODS = ("score", "score_diverse", "score_bin", "uniform")

SOURCE_SHA256 = "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
PRIOR_SHA256 = "8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07"
SCORE_SOURCES = {
    "frozen": {
        "sha": "9dff0dd9ff38e17353bb6e1a9b343dd0b6a8906f1171bc481a842b74142fce83",
        "member": "private/source-scores.csv",
        "member_sha": "caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812",
        "exams": (21, 23, 30), "expected_rows": 3000,
        "image_sha": "source_image_sha256", "model_score": "cnn_score",
        "has_reference_flag": True,
    },
    "appearance": {
        "sha": "2738a64b47d0be4fecfd89fd8aea9a345ce86e237899e4e423d4d7de8ac36eaa",
        "member": "PRIVATE/private-per-image-features.csv",
        "member_sha": "c07db3c66d027d730eaef82566e1c3a4d210a312e4b5926ee871381f5d608597",
        "exams": (25, 27, 29), "expected_rows": 1536,
        "image_sha": "source_sha256", "model_score": "original_checkpoint",
        "has_reference_flag": False,
    },
}
EXAMS = (21, 23, 25, 27, 29, 30)
SOURCE_RUNS = {21: 3, 23: 28, 25: 53, 27: 4, 29: 107, 30: 47}
REACHABLE_RUNS = {21: 1, 23: 4, 25: 3, 27: 4, 29: 47, 30: 20}
POSITIVE_REFERENCE = {21: 1, 23: 4, 25: 14, 27: 26, 29: 122, 30: 120}
WORKLOADS = (25, 51, 128, 256, 384, 512)
STRATA = ("1-5", "6-25", "26+")


def sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or not (0 < path.stat().st_size <= 40 * 1024 * 1024):
        raise ValueError("Absent, symlinked, empty or oversized pinned research input.")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_rows(archive: Path, expected_sha: str, member: str,
                  max_bytes: int = 20 * 1024 * 1024) -> list[dict]:
    if sha_file(archive) != expected_sha:
        raise ValueError("Research package SHA-256 differs from locked original.")
    with zipfile.ZipFile(archive) as z:
        # Deliberately do NOT traverse any other members (especially heldouts).
        info = z.getinfo(member)
        if info.file_size <= 0 or info.file_size > max_bytes:
            raise ValueError("Unexpected corrected/source score CSV size.")
        blob = z.read(info)  # Reads and CRC-checks one approved member only.
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or ()
    if len(fields) != len(set(fields)):
        raise ValueError("Duplicate CSV fields.")
    records = list(reader)
    if any(None in row for row in records):
        raise ValueError("Malformed original CSV row.")
    return records


def _read_csv_bytes(archive: Path, expected_sha: str, member: str,
                    member_sha: str, max_bytes: int = 3 * 1024 * 1024) -> list[dict]:
    if sha_file(archive) != expected_sha:
        raise ValueError("Private score package SHA-256 mismatch.")
    with zipfile.ZipFile(archive) as z:
        info = z.getinfo(member)
        if not 0 < info.file_size <= max_bytes:
            raise ValueError("Score CSV exceeds locked size envelope.")
        blob = z.read(info)
    if hashlib.sha256(blob).hexdigest() != member_sha:
        raise ValueError("Score CSV SHA-256 mismatch.")
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or ()
    if len(fields) != len(set(fields)):
        raise ValueError("Duplicate score CSV header.")
    result = list(reader)
    if any(None in row for row in result):
        raise ValueError("Malformed score CSV row.")
    return result


def source_runs(rows: list[dict]) -> tuple[dict[int, int], list[str], dict[int, str]]:
    """Full corrected positive-row stretches, not lesions or all raw footage."""
    if len(rows) < 512:
        raise ValueError("Full original source annotations missing.")
    previous = None
    active = []
    map_to_run: dict[int, int] = {}
    lengths: list[int] = []
    source_labels: dict[int, str] = {}
    strides = Counter()
    for row in rows:
        if not {"frame", "blood"} <= row.keys():
            raise ValueError("Corrected publisher CSV header changed.")
        frame_raw, blood = row["frame"], row["blood"]
        if not frame_raw or not frame_raw.isdecimal() or blood not in ("0", "1", ""):
            raise ValueError("Malformed/unknown corrected annotation value.")
        frame = int(frame_raw)
        if previous is not None:
            if frame <= previous:
                raise ValueError("Corrected source frames not strictly chronological.")
            strides[frame - previous] += 1
        if active and (blood != "1" or frame - previous != 5):
            run_id = len(lengths)
            lengths.append(len(active))
            map_to_run.update({x: run_id for x in active})
            active = []
        if blood == "1":
            active.append(frame)
        source_labels[frame] = blood
        previous = frame
    if active:
        run_id = len(lengths)
        lengths.append(len(active))
        map_to_run.update({x: run_id for x in active})
    if strides[5] / (len(rows) - 1) < .95 or strides.most_common(1)[0][0] != 5:
        raise ValueError("Unsupported original corrected annotation source stride.")
    categories = [("1-5" if length <= 5 else "6-25" if length <= 25 else "26+")
                  for length in lengths]
    if sum(lengths) != len(map_to_run):
        raise ValueError("Source runs overlap or are incompletely counted.")
    return map_to_run, categories, source_labels


def load_sources(official: Path) -> dict[int, dict]:
    if sha_file(official) != SOURCE_SHA256:
        raise ValueError("Official corrected source release SHA-256 changed.")
    sources = {}
    with zipfile.ZipFile(official) as z:
        for exam in EXAMS:
            info = z.getinfo(f"{exam}.csv")
            if not 0 < info.file_size <= 20 * 1024 * 1024:
                raise ValueError("Unexpected corrected source annotation CSV size.")
            blob = z.read(info)  # Does not read any heldout member.
            reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or not {"frame", "blood"} <= set(fields):
                raise ValueError("Corrected publisher CSV schema differs.")
            rows = list(reader)
            if any(None in row for row in rows):
                raise ValueError("Malformed corrected source CSV.")
            run_map, categories, labels = source_runs(rows)
            if len(categories) != SOURCE_RUNS[exam]:
                raise ValueError("Publisher source-run count no longer reconciles with prior audit.")
            sources[exam] = {"runs": run_map, "strata": categories, "labels": labels}
    return sources


def load_scores(frozen: Path, appearance: Path, sources: dict[int, dict]) -> dict[int, list[dict]]:
    result = {exam: [] for exam in EXAMS}
    for key, path in (("frozen", frozen), ("appearance", appearance)):
        spec = SCORE_SOURCES[key]
        raw = _read_csv_bytes(path, spec["sha"], spec["member"], spec["member_sha"])
        if len(raw) != spec["expected_rows"]:
            raise ValueError("Historical private reference score package row count changed.")
        required = {"exam", "frame", spec["image_sha"], "blood", spec["model_score"]}
        if spec["has_reference_flag"]:
            required.add("reference_uniform")
        for row in raw:
            if not required <= row.keys():
                raise ValueError("Missing pinned score file columns.")
            if row["exam"] not in tuple(map(str, spec["exams"])):
                raise ValueError("Unexpected unapproved source examination in private score CSV.")
            if spec["has_reference_flag"] and row["reference_uniform"] not in ("0", "1"):
                raise ValueError("Unknown reference selection indicator.")
            if spec["has_reference_flag"] and row["reference_uniform"] != "1":
                continue
            if not row["frame"].isdecimal() or row["blood"] not in ("0", "1"):
                raise ValueError("Unverifiable original image annotation/identity.")
            source_id = int(row["frame"])
            exam = int(row["exam"])
            image_hash = row[spec["image_sha"]]
            if len(image_hash) != 64 or any(c not in "0123456789abcdef" for c in image_hash):
                raise ValueError("Invalid source-image SHA-256 in prior verified stream.")
            if sources[exam]["labels"].get(source_id) != row["blood"]:
                raise ValueError("Private score record contradicts exact corrected publisher source label.")
            try:
                score = float(row[spec["model_score"]])
            except (TypeError, ValueError) as exc:
                raise ValueError("Unparseable prior original model score.") from exc
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("Uncalibrated model score is invalid/nonfinite.")
            result[exam].append({"frame": source_id, "label": row["blood"], "score": score})
    for exam, rows in result.items():
        rows.sort(key=lambda r: r["frame"])
        if len(rows) != 512 or any(rows[i]["frame"] >= rows[i + 1]["frame"] for i in range(511)):
            raise ValueError("The expected exact 512 reference images are incomplete or duplicate.")
        if sum(r["label"] == "1" for r in rows) != POSITIVE_REFERENCE[exam]:
            raise ValueError("Historical source-verified reference label count changed.")
    return result


def _cat_counts(hits: set[int], categories: list[str]) -> dict[str, int]:
    return {stratum: sum(categories[run_id] == stratum for run_id in hits) for stratum in STRATA}


def evaluate_case(rows: list[dict], source: dict, *, workloads: tuple[int, ...] = WORKLOADS) -> dict:
    """Only source annotation-run coverage enters the evaluation AFTER selection."""
    if not rows or len({r["frame"] for r in rows}) != len(rows):
        raise ValueError("Duplicated or missing reference identities.")
    for r in rows:
        if r["label"] not in ("0", "1") or type(r["frame"]) is not int:
            raise ValueError("Nonbinary or missing verified reference annotations.")
    scores = [r["score"] for r in rows]
    all_runs = source["runs"]
    strata = source["strata"]
    source_total = len(strata)
    reachable = {all_runs[r["frame"]] for r in rows if r["label"] == "1"}
    if not reachable <= set(range(source_total)):
        raise ValueError("Accessible source-run membership is corrupt.")
    result = {
        "full_source_positive_annotation_runs": source_total,
        "source_runs_reachable_in_saved_reference": len(reachable),
        "source_run_length_strata": _cat_counts(set(range(source_total)), strata),
        "reference_reachable_strata": _cat_counts(reachable, strata),
        "reference_positive_image_count": sum(r["label"] == "1" for r in rows),
        "budgets": {},
    }
    for k in workloads:
        if not 1 <= k <= len(rows):
            raise ValueError("Review workload is not an exact positive imported image count.")
        block = {"selected_reference_images": k, "methods": {}}
        for method in METHODS:
            selection = select_positions(scores, k, method)
            if len(selection) != len(set(selection)) or len(selection) != k:
                raise ValueError("Selection method did not honor exactly K references.")
            positive = [rows[i] for i in selection if rows[i]["label"] == "1"]
            run_ids = {all_runs[r["frame"]] for r in positive}
            block["methods"][method] = {
                "distinct_full_source_positive_annotation_runs_hit": len(run_ids),
                "source_annotation_run_recall": (
                    round(len(run_ids) / source_total, 8) if source_total else None
                ),
                "reference_accessible_run_fraction": (
                    round(len(run_ids) / len(reachable), 8) if reachable else None
                ),
                "positive_reference_images_hit": len(positive),
                "source_run_strata_hit": _cat_counts(run_ids, strata),
            }
        result["budgets"][str(k)] = block
    return result


def audited_summary(exams: dict[int, dict], prior: dict) -> dict:
    if prior.get("source_corrected_release_sha256") != SOURCE_SHA256:
        raise ValueError("Previous source-run verification has different source identity.")
    if prior.get("reference_per_exam") != 512:
        raise ValueError("Prior frozen audit does not use the same 512-frame reference workload.")
    if set(prior.get("examinations", {})) != {"9", "10", *[str(e) for e in EXAMS]}:
        raise ValueError("Original audit examination set unexpectedly changed.")
    result = {
        "schema_version": 1,
        "study": "Previously inspected Galar four-policy distinct original blood annotation-run retrieval",
        "source_corrected_release_sha256": SOURCE_SHA256,
        "input_score_package_sha256": {key: s["sha"] for key, s in SCORE_SOURCES.items()},
        "source_data_role": "Previously inspected fitting/transfer examinations; NO fresh blinded evaluation",
        "examinations": {},
        "summary_by_budget": {},
        "method_names": list(METHODS),
        "not_clinical_validation": True,
        "patient_independence_verified": False,
        "new_unseen_evaluation": False,
        "model_promoted": False,
        "run_not_lesion": True,
        "raw_labels_images_and_per_frame_scores_committed": False,
        "limits": [
            "Distinct original corrected positive annotation stretches are not adjudicated lesions or time-stamped episodes.",
            "Sparse 512-image reference inputs miss original source runs even at 100% workload.",
            "Selection and experimental CNN scores come from previously inspected Galar studies.",
            "Source indexing is not elapsed video time; reserved studies 11–20 and 61–80 stay unopened.",
        ],
    }
    for exam, record in exams.items():
        prior_case = prior["examinations"][str(exam)]
        if (record["full_source_positive_annotation_runs"] != prior_case["source_blood_annotation_runs"]
            or record["source_runs_reachable_in_saved_reference"] != prior_case["reference_run_ceiling_hits"]
            or record["reference_positive_image_count"] != prior_case["reference_blood_positive"]):
            raise ValueError("New policy input fails the original source-run reference ceiling.")
        for k, trial in record["budgets"].items():
            previous = prior_case["budgets"][str(next(
                pct for pct, selected in ((5,25),(10,51),(25,128),(50,256),(75,384),(100,512))
                if selected == int(k)
            ))]
            for new, old in (("score", "original_checkpoint"), ("uniform", "uniform")):
                now = trial["methods"][new]
                earlier = previous["methods"][old]
                if (now["distinct_full_source_positive_annotation_runs_hit"]
                        != earlier["source_annotation_runs_hit"]
                    or now["positive_reference_images_hit"]
                        != earlier["blood_positive_reference_images_found"]):
                    raise ValueError("Previous independently verified CNN/uniform outcomes do not replay.")
        result["examinations"][str(exam)] = record
    for k in WORKLOADS:
        positives = [record for record in exams.values()
                     if record["full_source_positive_annotation_runs"] > 0]
        total_source = sum(record["full_source_positive_annotation_runs"] for record in positives)
        method_stats = {}
        for method in METHODS:
            hit_counts = [
                record["budgets"][str(k)]["methods"][method]["distinct_full_source_positive_annotation_runs_hit"]
                for record in positives
            ]
            macro = statistics.fmean([
                hits / record["full_source_positive_annotation_runs"]
                for hits, record in zip(hit_counts, positives)
            ])
            comparison = [
                (record["budgets"][str(k)]["methods"][method]["distinct_full_source_positive_annotation_runs_hit"]
                 - record["budgets"][str(k)]["methods"]["uniform"]["distinct_full_source_positive_annotation_runs_hit"])
                / record["full_source_positive_annotation_runs"]
                for record in positives
            ]
            method_stats[method] = {
                "unique_runs_hit_across_exams": sum(hit_counts),
                "micro_source_run_recall": round(sum(hit_counts) / total_source, 8),
                "macro_source_run_recall": round(macro, 8),
                "macro_difference_from_uniform": round(statistics.fmean(comparison), 8),
                "exam_wins_vs_uniform": sum(x > 0 for x in comparison),
                "exam_ties_vs_uniform": sum(x == 0 for x in comparison),
                "exam_losses_vs_uniform": sum(x < 0 for x in comparison),
                "leave_one_exam_out_difference": {
                    str(case): round(statistics.fmean(
                        value for i, value in enumerate(comparison) if i != omit
                    ), 8)
                    for omit, case in enumerate(EXAMS)
                },
            }
        result["summary_by_budget"][str(k)] = method_stats
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corrected-labels", type=Path, required=True)
    parser.add_argument("--frozen-scores", type=Path, required=True)
    parser.add_argument("--appearance-scores", type=Path, required=True)
    parser.add_argument("--prior-aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite a research results artifact.")
    if sha_file(args.prior_aggregate) != PRIOR_SHA256:
        raise ValueError("Original independently checked run-coverage aggregate identity changed.")
    sources = load_sources(args.corrected_labels)
    scores = load_scores(args.frozen_scores, args.appearance_scores, sources)
    exams = {}
    for exam in EXAMS:
        rec = evaluate_case(scores[exam], sources[exam])
        if rec["full_source_positive_annotation_runs"] != SOURCE_RUNS[exam]:
            raise ValueError("Source-run counts differ from the verified earlier experiment.")
        if rec["source_runs_reachable_in_saved_reference"] != REACHABLE_RUNS[exam]:
            raise ValueError("Reference source-run ceiling differs from verified earlier experiment.")
        exams[exam] = rec
    prior = json.loads(args.prior_aggregate.read_text(encoding="utf-8"))
    out = audited_summary(exams, prior)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(out, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print("Completed 144 exact-K source-run comparisons; retrospective exploratory, not clinical validation.")


if __name__ == "__main__":
    main()
