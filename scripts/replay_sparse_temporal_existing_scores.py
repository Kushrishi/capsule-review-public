"""Replay a fixed gap-aware temporal control on PREVIOUSLY EXAMINED Galar scores.

Input is a user-provided, PRIVATE frozen original-image score package.
Output is a NONIDENTIFYING aggregate only. No images or new inference run.
Reference samples were selected label-blind but have no adjacent source
positions; enriched unions are pathology-label-selected and unsuitable as
independent or unbiased tests. Sample-positive streaks are not the complete
original annotation runs or physician-adjudicated lesions.

This script must not be used to re-evaluate the locked Galar 11-20 results.
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

from capsule_review.priority import select_positions
from capsule_review.temporal_baseline import temporal_max_scores

PACKAGE_SHA256 = "9dff0dd9ff38e17353bb6e1a9b343dd0b6a8906f1171bc481a842b74142fce83"
MEMBER = "private/source-scores.csv"
MEMBER_SHA256 = "caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812"
EXAMS = (21, 23, 30)
EXPECTED_TOTAL = {21: 993, 23: 1001, 30: 1006}
EXPECTED_UNION_POSITIVES = {21: 13, 23: 135, 30: 366}
REFERENCE_PER_EXAM = 512
NATIVE_STRIDE = 5
WORKLOADS = (5, 10, 25)
_SHA = re.compile(r"[a-f0-9]{64}\Z")
REQUIRED = frozenset({
    "exam", "frame", "source_image_sha256", "pixel_sha256", "blood",
    "fit_enriched", "reference_uniform", "cnn_score", "red_excess_score",
})


def _sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 5_000_000:
        raise ValueError("Missing, unsafe or unexpected private score package.")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def private_rows(path: Path) -> dict[int, list[dict]]:
    if _sha_file(path) != PACKAGE_SHA256:
        raise ValueError("Original private score package SHA-256 changed.")
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(MEMBER)
        if not 0 < info.file_size <= 1_000_000:
            raise ValueError("Source-score member unexpectedly large.")
        raw = z.read(info)  # ZIP CRC checked; do not read other private members.
    if hashlib.sha256(raw).hexdigest() != MEMBER_SHA256:
        raise ValueError("Private score member SHA-256 mismatch.")
    rdr = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if len(rdr.fieldnames or []) != len(set(rdr.fieldnames or [])) or set(rdr.fieldnames or []) != REQUIRED:
        raise ValueError("Unexpected private score schema.")
    grouped: dict[int, list[dict]] = {e: [] for e in EXAMS}
    for row in rdr:
        if None in row or not (row["exam"].isdecimal() and row["frame"].isdecimal()):
            raise ValueError("Malformed original source row.")
        exam = int(row["exam"])
        if exam not in grouped or row["blood"] not in ("0", "1"):
            raise ValueError("Forbidden case or invalid blood indicator.")
        if row["fit_enriched"] not in ("0","1") or row["reference_uniform"] not in ("0","1"):
            raise ValueError("Unknown original sampling role.")
        if not _SHA.fullmatch(row["source_image_sha256"]) or not _SHA.fullmatch(row["pixel_sha256"]):
            raise ValueError("Missing previously verified image hashes.")
        for key in ("cnn_score", "red_excess_score"):
            try:
                val = float(row[key])
            except (TypeError,ValueError) as exc:
                raise ValueError("Invalid original score.") from exc
            if not math.isfinite(val) or not 0 <= val <= 1:
                raise ValueError("Nonfinite/out-of-range original score.")
        if row["fit_enriched"] != "1" and row["reference_uniform"] != "1":
            raise ValueError("Source image had no original sampling role.")
        grouped[exam].append(row)
    for exam, rows in grouped.items():
        rows.sort(key=lambda row:int(row["frame"]))
        if (len(rows) != EXPECTED_TOTAL[exam]
            or sum(x["reference_uniform"]=="1" for x in rows) != REFERENCE_PER_EXAM
            or sum(x["blood"]=="1" for x in rows) != EXPECTED_UNION_POSITIVES[exam]):
            raise ValueError("Original source examination support changed.")
        source=[int(x["frame"]) for x in rows]
        if any(b-a < NATIVE_STRIDE or (b-a)%NATIVE_STRIDE != 0
               for a,b in zip(source,source[1:])):
            raise ValueError("Duplicate, off-grid or reversed original frame indices.")
    return grouped


def gap_aware_max(source: list[int], scores: list[float], *, stride: int = 5) -> list[float]:
    """Never interpolate scores or smooth across absent published source IDs.

    Explicitly separate each maximal source-contiguous segment, then apply
    the exact existing temporal_max_scores control to segments >= 3.
    At a two-frame segment, both see the same maximum under truncated
    window-3 semantics. A singleton retains its original score.
    """
    if len(source)!=len(scores) or not source:
        raise ValueError("Source and scores must form a nonempty paired sequence.")
    if type(stride) is not int or stride < 1:
        raise ValueError("Native source stride must be verified and positive.")
    if any(type(x) is not int or x<0 for x in source):
        raise ValueError("Invalid source identities.")
    if any(b-a < stride or (b-a)%stride for a,b in zip(source,source[1:])):
        raise ValueError("Invalid source grid ordering or stride.")
    if any(type(s) not in (int,float) or not math.isfinite(s) or not 0<=s<=1
           for s in scores):
        raise ValueError("Invalid raw model score.")
    answer=[]
    begin=0
    for end in range(1,len(source)+1):
        if end == len(source) or source[end]-source[end-1] != stride:
            run=scores[begin:end]
            if len(run)==1:
                answer.extend(run)
            elif len(run)==2:
                answer.extend([max(run),max(run)])
            else:
                answer.extend(temporal_max_scores(
                    run,source[begin:end],window=3,source_stride=stride))
            begin=end
    return answer


def sampled_streak_ids(source: list[int], positives: list[bool],
                       *, stride: int = 5) -> tuple[dict[int,int],int]:
    """Label-only outcome accounting, AFTER label-blind selected queues."""
    membership={}
    previous_positive=False
    streak=-1
    for i, (frame, positive) in enumerate(zip(source,positives)):
        if positive:
            if not previous_positive or i==0 or frame-source[i-1]!=stride:
                streak+=1
            membership[i]=streak
        previous_positive=positive
    return membership,streak+1


def replay_case(rows: list[dict]) -> dict:
    """No labels are passed to either scoring or queue construction."""
    source=[int(r["frame"]) for r in rows]
    raw=[float(r["cnn_score"]) for r in rows]
    # Freeze both label-blind score streams before reading outcomes.
    smoothed=gap_aware_max(source,raw,stride=NATIVE_STRIDE)
    selections={}
    for percent in WORKLOADS:
        k=min(len(rows),max(1,(len(rows)*percent+50)//100))
        selections[percent]={
            "uniform":select_positions(raw,k,"uniform"),
            "original_score_bin":select_positions(raw,k,"score_bin"),
            "temporal_gap_aware_score_bin":select_positions(smoothed,k,"score_bin"),
        }
    # Outcome labels are accessed only after all queues exist.
    positives=[r["blood"]=="1" for r in rows]
    membership,total_streaks=sampled_streak_ids(source,positives)
    adjacency=sum(b-a==NATIVE_STRIDE for a,b in zip(source,source[1:]))
    budgets={}
    for percent, methods in selections.items():
        k=len(methods["uniform"])
        results={}
        for name,selected in methods.items():
            if len(selected)!=k or len(set(selected))!=k:
                raise ValueError("One policy violated exact-K.")
            results[name]={
                "blood_positive_sample_images_selected":sum(i in membership for i in selected),
                "sampled_positive_streaks_hit":len({membership[i] for i in selected if i in membership}),
            }
        results["temporal_gap_aware_score_bin"]["changed_selected_positions_vs_original"]=(
            len(set(methods["original_score_bin"])^set(methods["temporal_gap_aware_score_bin"]))//2
        )
        budgets[str(percent)]={
            "review_percent":percent,"exact_selected_images":k,"methods":results,
        }
    return {
        "imported_source_images":len(rows),
        "blood_positive_sample_images":sum(positives),
        "sampled_positive_streaks_total_not_complete_source_runs":total_streaks,
        "consecutive_source_index_pairs":adjacency,
        "scores_changed_by_truncated_window_three":sum(
            abs(a-b)>1e-12 for a,b in zip(raw,smoothed)),
        "budgets":budgets,
    }


def build_report(path: Path) -> dict:
    private=private_rows(path)
    cases={}
    for exam in EXAMS:
        original=private[exam]
        cases[str(exam)]={
            "previously_eligible_enriched_union_NOT_unbiased":replay_case(original),
            "original_label_blind_512_frame_reference":replay_case(
                [r for r in original if r["reference_uniform"]=="1"]),
        }
    return {
        "schema_version":1,
        "record_type":"retrospective-galar-sparse-temporal-control-v1",
        "private_input_package_sha256":PACKAGE_SHA256,
        "private_source_score_csv_sha256":MEMBER_SHA256,
        "model":"historical unchanged CNN uncalibrated score",
        "evaluated_examinations":list(EXAMS),
        "original_examination_labels_previously_seen":True,
        "new_training_or_original_image_inference":False,
        "protected_11_20_evaluation_reopened":False,
        "author_reserved_61_80_opened":False,
        "source_frame_grid_native_stride":5,
        "score_control":"fixed window 3 maximum on verified adjacent published source positions only",
        "exact_k_queue":"existing score_bin/uniform policies",
        "report_scope":"sampled positive image and sampled positive streaks ONLY, not all annotated-source runs",
        "patient_independent_or_clinical_validation":False,
        "cases":cases,
        "conclusion":(
            "All 1536 label-blind reference positions lack adjacent published source positions, "
            "so gap-aware temporal scores cannot change their selections. Enriched unions "
            "contain adjacent positions but were explicitly selected using labels; "
            "their modest mixed differences cannot validate clinical benefit."
        ),
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-scores",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():
        p.error("Refuse to overwrite any research record.")
    output=build_report(a.private_scores)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "record_type":output["record_type"],
        "exam_count":len(output["cases"]),
        "individual_source_identifiers_disclosed":False,
        "source_pixels_accessed":False,
        "new_model_training":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
