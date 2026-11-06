"""PRIVATE two-stage fixed-policy Galar36 full original-source CNN replication.

Stage 1 --score reads ALL 13,326 PNGs and never reads the embedded outcome
manifest nor corrected label archive. It freezes unchanged original CNN scores
and prespecified exact-K review queues in a PRIVATE exclusive-create snapshot.

Stage 2 --audit first checks snapshot SHA256, prelabel score commitments and
all frozen queues, then verifies original PNGs against the private manifest
and corrected official 36.csv. It reports development-only aggregate positive-
image and distinct annotated-run coverage. No new model, tuning, or promotion.
No protected 11-20 or reserved 61-80 data are read.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

from PIL import Image, ImageOps
import numpy as np
import torch

from capsule_review.interval_evidence import segment_positive_runs
from capsule_review.priority import (
    largest_unselected_span, ordinal_coverage, select_positions,
)
from capsule_review.temporal_baseline import temporal_max_scores
from capsule_review.unseen_evaluation import evaluate_frozen_queues, freeze_queues

from acquire_galar36_private_incremental import (
    EXAM, EXPECTED_SOURCE_IMAGES, EXPECTED_POSITIVE_IMAGES,
    EXPECTED_POSITIVE_RUNS, NATIVE_STRIDE, FILE_ID,
    OLD_BYTES, OLD_SHA256, NEW_BYTES, NEW_START, END_EXCLUSIVE,
    verified_labels36,
)
from run_galar35_full_sequence_private import (
    WEIGHTS_SHA, MAX_ZIP_BYTES, MAX_SNAPSHOT_BYTES, MAX_MANIFEST_BYTES,
    IMAGE_LIMIT, HEX, load_original_model, sha256_file, verify_original_package,
)

IMAGE_RE = re.compile(r"images/036/frame_(\d+)\.PNG\Z")
SCHEMA = "private-galar36-frozen-original-scores-v1"
PRIMARY = 10
TEMPORAL_WINDOW = 3
TEMPORAL_POLICY = "score_bin"


def source_members(z: zipfile.ZipFile) -> list[tuple[int, zipfile.ZipInfo]]:
    """Only ZIP directory metadata; outcome-labelled manifest is never read."""
    allowed = {"source-frame-private-manifest.json", "source-block-private-receipt.json"}
    names = set()
    frames = set()
    originals = []
    for member in z.infolist():
        if member.is_dir() or member.filename in names:
            raise ValueError("Private original study36 ZIP has duplicate/unsafe members.")
        names.add(member.filename)
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Original-study ZIP must not contain symlinks.")
        if member.filename in allowed:
            if not 0 < member.file_size <= MAX_MANIFEST_BYTES:
                raise ValueError("Unexpected private manifest or receipt byte count.")
            continue
        match = IMAGE_RE.fullmatch(member.filename)
        if match is None or not 0 < member.file_size <= IMAGE_LIMIT:
            raise ValueError("Unexpected original clinical source-image path or size.")
        frame = int(match.group(1))
        if frame in frames:
            raise ValueError("Duplicated publisher source frame index.")
        frames.add(frame)
        originals.append((frame, member))
    if names != allowed | {member.filename for _,member in originals}:
        raise ValueError("Incomplete private original-source package.")
    originals.sort(key=lambda item: item[0])
    if (len(originals) != EXPECTED_SOURCE_IMAGES
            or any(b[0]-a[0] != NATIVE_STRIDE for a,b in zip(originals,originals[1:]))):
        raise ValueError("Complete native +5 publisher Galar36 source grid required.")
    return originals


def expected_queues(frames: list[int], hashes: list[str],
                    scores: list[float]) -> tuple[object,list[dict]]:
    frozen = freeze_queues(frames, hashes, scores)
    temporal = temporal_max_scores(
        scores, frames, window=TEMPORAL_WINDOW, source_stride=NATIVE_STRIDE
    )
    queues = [{
        "review_percent": p,
        "k": k,
        "policies": {name: list(positions) for name,positions in methods},
        "temporal_window3_score_bin": list(select_positions(temporal,k,TEMPORAL_POLICY)),
    } for p,k,methods in frozen.selection_by_percent]
    return frozen, queues


def score_originals(
    originals: Path, package_sha: str, model_zip: Path, *, batch_size: int=32
) -> dict:
    """Stage 1: load only original PNG bytes; score-label separation is enforced."""
    if type(batch_size) is not int or not 1 <= batch_size <= 64:
        raise ValueError("Invalid bounded original-model inference batch size.")
    source_sha=verify_original_package(originals,package_sha)
    model=load_original_model(model_zip)
    complete=[]
    with zipfile.ZipFile(originals) as z, torch.inference_mode():
        members=source_members(z)
        pending=[]
        def flush_batch() -> None:
            if not pending:
                return
            tensor=torch.stack([item[2] for item in pending])
            values=torch.softmax(model(tensor),dim=1)[:,1].cpu().tolist()
            if len(values)!=len(pending):
                raise ValueError("Incomplete original CNN inference batch.")
            for (frame,image_sha,_),score in zip(pending,values):
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError("Non-finite/invalid original CNN output.")
                complete.append({"source_frame":frame,
                                 "original_png_sha256":image_sha,
                                 "original_cnn_score":float(score)})
            pending.clear()
        for frame, member in members:
            raw=z.read(member)
            image_sha=hashlib.sha256(raw).hexdigest()
            with Image.open(io.BytesIO(raw)) as im:
                if im.format!="PNG":
                    raise ValueError("Source image is not PNG.")
                image=ImageOps.exif_transpose(im).convert("RGB")
                image=ImageOps.pad(image,(96,96),method=Image.Resampling.BILINEAR,
                                   color=(0,0,0))
                pixels=np.asarray(image,dtype=np.float32)/255.0
            pending.append((frame,image_sha,torch.from_numpy(
                pixels.transpose(2,0,1).copy()
            )))
            if len(pending)>=batch_size:
                flush_batch()
        flush_batch()
    if len(complete)!=EXPECTED_SOURCE_IMAGES:
        raise ValueError("Incomplete original study36 CNN inference.")
    frames=[item["source_frame"] for item in complete]
    hashes=[item["original_png_sha256"] for item in complete]
    scores=[item["original_cnn_score"] for item in complete]
    frozen,queues=expected_queues(frames,hashes,scores)
    return {
        "schema_version":1,"record_type":SCHEMA,"exam":EXAM,
        "development_only":True,
        "unchanged_original_checkpoint_sha256":WEIGHTS_SHA,
        "source_originals_package_sha256":source_sha,
        "native_source_stride":NATIVE_STRIDE,
        "prelabel_original_queues_commitment_sha256":frozen.input_commitment_sha256,
        "complete_original_scores":complete,"frozen_queues":queues,
        "outcome_annotations_accessed_during_scoring":False,
        "protected_galar11_20_reopened":False,
        "authors_galar61_80_opened":False,
    }


def audit_frozen(
    snapshot: dict, originals: Path, package_sha: str, label_archive: Path
) -> dict:
    """Stage 2: refuse premature outcome reads if score freeze is inconsistent."""
    if (not isinstance(snapshot,dict)
            or snapshot.get("schema_version")!=1
            or snapshot.get("record_type")!=SCHEMA
            or snapshot.get("exam")!=EXAM
            or snapshot.get("development_only") is not True
            or snapshot.get("unchanged_original_checkpoint_sha256")!=WEIGHTS_SHA
            or snapshot.get("source_originals_package_sha256")!=package_sha
            or snapshot.get("native_source_stride")!=NATIVE_STRIDE
            or snapshot.get("outcome_annotations_accessed_during_scoring") is not False):
        raise ValueError("Untrusted original-study36 prelabel inference snapshot.")
    entries=snapshot.get("complete_original_scores")
    if not isinstance(entries,list) or len(entries)!=EXPECTED_SOURCE_IMAGES:
        raise ValueError("Frozen source-image scores are incomplete.")
    frames,hashes,scores=[],[],[]
    for entry in entries:
        if (not isinstance(entry,dict) or type(entry.get("source_frame")) is not int
                or not isinstance(entry.get("original_png_sha256"),str)
                or not isinstance(entry.get("original_cnn_score"),float)):
            raise ValueError("Invalid source-image score row.")
        frames.append(entry["source_frame"])
        hashes.append(entry["original_png_sha256"])
        scores.append(entry["original_cnn_score"])
    frozen,queues=expected_queues(frames,hashes,scores)
    if (frozen.input_commitment_sha256!=snapshot.get(
            "prelabel_original_queues_commitment_sha256")
            or queues!=snapshot.get("frozen_queues")):
        raise ValueError("Frozen Galar36 score commitment or exact-K queues changed.")

    verify_original_package(originals,package_sha)
    with zipfile.ZipFile(originals) as z:
        members=source_members(z)
        if [frame for frame,_ in members]!=frames:
            raise ValueError("Scored source frames differ from original-source ZIP.")
        # ONLY AFTER both score + exact-K queue commitments match, read labels.
        raw=z.read("source-frame-private-manifest.json")
        manifest=json.loads(raw)
        receipt=json.loads(z.read("source-block-private-receipt.json"))
        part6=receipt.get("source_block6",{}) if isinstance(receipt,dict) else {}
        if (not isinstance(receipt,dict)
                or receipt.get("official_file_id")!=FILE_ID
                or receipt.get("retained_block5_sha256")!=OLD_SHA256
                or receipt.get("retained_block5_compressed_bytes")!=OLD_BYTES
                or receipt.get("full_source_md5_verified") is not False
                or receipt.get("all_other_image_blocks_absent") is not True
                or not isinstance(part6,dict)
                or part6.get("official_file_id")!=FILE_ID
                or part6.get("block")!=6
                or part6.get("range_start")!=NEW_START
                or part6.get("range_stop_exclusive")!=END_EXCLUSIVE
                or part6.get("compressed_bytes_received")!=NEW_BYTES
                or part6.get("full_source_md5_verified") is not False
                or not isinstance(part6.get("source_block_sha256"),str)
                or HEX.fullmatch(part6["source_block_sha256"]) is None):
            raise ValueError("Unverified or unexpected original source-block receipt.")
        if not isinstance(manifest,list) or len(manifest)!=EXPECTED_SOURCE_IMAGES:
            raise ValueError("Original source36 manifest is incomplete.")
        by_frame={}
        for entry in manifest:
            if (not isinstance(entry,dict) or entry.get("examination")!=EXAM
                    or type(entry.get("source_frame")) is not int
                    or entry["source_frame"] in by_frame
                    or type(entry.get("blood_label")) is not int
                    or entry["blood_label"] not in (0,1)
                    or type(entry.get("original_png_bytes")) is not int
                    or entry["original_png_bytes"]<=0
                    or not isinstance(entry.get("original_png_sha256"),str)
                    or HEX.fullmatch(entry["original_png_sha256"]) is None):
                raise ValueError("Private original-image manifest row invalid.")
            by_frame[entry["source_frame"]]=entry
        if set(by_frame)!=set(frames):
            raise ValueError("Private original-image manifest missing source position.")
        for i,(frame,member) in enumerate(members):
            entry=by_frame[frame]
            raw=z.read(member)
            image_sha=hashlib.sha256(raw).hexdigest()
            if (entry.get("original_filename")!=PurePosixPath(member.filename).name
                    or len(raw)!=entry["original_png_bytes"]
                    or image_sha!=entry["original_png_sha256"]
                    or image_sha!=hashes[i]):
                raise ValueError("Source PNG identity changed after model score freeze.")

    labels=verified_labels36(label_archive)
    if any(labels.get(frame)!=str(by_frame[frame]["blood_label"]) for frame in frames):
        raise ValueError("Official corrected 36.csv contradicts original-source manifest.")
    with zipfile.ZipFile(label_archive) as z:
        labelinfo=z.getinfo("36.csv")
        if not 0 < labelinfo.file_size <= 32*1024*1024:
            raise ValueError("Official original source annotation member oversized.")
        original_csv=z.read(labelinfo)
    base=evaluate_frozen_queues(frozen,original_csv)
    if (base["imported_annotated_images"]!=EXPECTED_SOURCE_IMAGES
            or base["positive_annotated_images"]!=EXPECTED_POSITIVE_IMAGES
            or base["positive_annotation_runs"]!=EXPECTED_POSITIVE_RUNS):
        raise ValueError("Official Galar36 annotation run support changed.")
    rows=[{"frame":frame,"blood":labels[frame]} for frame in frames]
    runs,membership=segment_positive_runs(rows)
    if len(runs)!=EXPECTED_POSITIVE_RUNS:
        raise ValueError("Source annotation run segmentation changed.")
    results=[]
    for original,q in zip(base["review_results"],queues):
        p,k=q["review_percent"],q["k"]
        if original["review_percent"]!=p or original["review_images"]!=k:
            raise ValueError("Original development review workload mismatch.")
        selected=q["temporal_window3_score_bin"]
        if len(selected)!=k or len(set(selected))!=k:
            raise ValueError("Temporal queue is not exact K.")
        positives=[pos for pos in selected if labels[frames[pos]]=="1"]
        hits={membership[frames[pos]] for pos in positives}
        policies=dict(original["policies"])
        policies["temporal_window3_score_bin"]={
            "positive_annotated_images_hit":len(positives),
            "distinct_positive_annotation_runs_hit":len(hits),
            "annotation_run_recall":round(len(hits)/len(runs),8),
            "run_lengths_hit":{
                stratum:sum(runs[run_id]["stratum"]==stratum for run_id in hits)
                for stratum in ("1-5","6-25","26+")
            },
            "imported_position_coverage":ordinal_coverage(len(frames),selected),
            "largest_unselected_imported_span":(
                largest_unselected_span(len(frames),selected) or {}
            ).get("imported_images_not_in_queue",0),
        }
        results.append({
            "review_percent":p,"review_images":k,"policies":policies,
            "temporal_minus_raw_score_bin_run_recall":round(
                policies["temporal_window3_score_bin"]["annotation_run_recall"]
                -policies["score_bin"]["annotation_run_recall"],8),
            "score_bin_minus_uniform_run_recall":
                original["score_bin_minus_uniform_run_recall"],
        })
    return {
        "schema_version":1,
        "record_type":"galar36-complete-original-image-development-replication-v1",
        "exam":EXAM,"original_source_images_verified":EXPECTED_SOURCE_IMAGES,
        "blood_positive_original_annotated_images":EXPECTED_POSITIVE_IMAGES,
        "positive_annotation_runs_not_adjudicated_lesions":EXPECTED_POSITIVE_RUNS,
        "scoring_checkpoint_sha256":WEIGHTS_SHA,
        "unchanged_original_cnn":True,
        "all_source_images_rescored":True,
        "all_original_png_hashes_checked_against_private_manifest":True,
        "model_promoted":False,
        "previously_inspected_development_only":True,
        "independent_patient_validation":False,
        "clinical_validation":False,
        "protected_11_20_reopened":False,"authors_61_80_accessed":False,
        "primary_descriptive_workload_percent":PRIMARY,
        "review_results":results,
        "limitations":(
            "Complete published source grid is not entire device exposure. "
            "Already inspected study36 cannot be an independent held-out test; "
            "patient linkage/site/device provenance unverified; annotated runs "
            "are not clinical adjudicated lesions or proof of time savings."
        ),
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--score",action="store_true")
    mode.add_argument("--audit",action="store_true")
    p.add_argument("--source-originals",type=Path,required=True)
    p.add_argument("--expected-originals-sha256",required=True)
    p.add_argument("--model-zip",type=Path)
    p.add_argument("--score-snapshot",type=Path,required=True)
    p.add_argument("--score-snapshot-sha256")
    p.add_argument("--corrected-labels-zip",type=Path)
    p.add_argument("--private-output",type=Path)
    p.add_argument("--batch-size",type=int,default=32)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    outputs=[args.score_snapshot] if args.score else [args.private_output]
    if any(x is None or x.is_symlink() or x.exists()
           or x.resolve(strict=False).is_relative_to(root) for x in outputs):
        p.error("Private analysis output must not overwrite or enter public Git.")
    if args.score:
        if args.model_zip is None or args.corrected_labels_zip is not None:
            p.error("Scoring cannot receive any clinical annotations.")
        snapshot=score_originals(args.source_originals,args.expected_originals_sha256,
                                 args.model_zip,batch_size=args.batch_size)
        args.score_snapshot.parent.mkdir(parents=True,exist_ok=True)
        with args.score_snapshot.open("x",encoding="utf8") as stream:
            json.dump(snapshot,stream,sort_keys=True,allow_nan=False)
            stream.write("\n")
        print(json.dumps({"stage":"galar36-original-model-predictions-frozen",
                          "original_images_scored":len(snapshot["complete_original_scores"]),
                          "private_score_snapshot_sha256":sha256_file(
                              args.score_snapshot,MAX_SNAPSHOT_BYTES),
                          "outcome_annotations_accessed":False,
                          "model_promoted":False},sort_keys=True))
        return
    if (args.model_zip is not None or args.corrected_labels_zip is None
            or not isinstance(args.score_snapshot_sha256,str)
            or HEX.fullmatch(args.score_snapshot_sha256) is None):
        p.error("Outcome audit needs an independently sealed SHA256 snapshot and labels.")
    if sha256_file(args.score_snapshot,MAX_SNAPSHOT_BYTES)!=args.score_snapshot_sha256:
        p.error("Score snapshot SHA256 mismatch: refuse clinical outcome access.")
    snapshot=json.loads(args.score_snapshot.read_text(encoding="utf8"))
    aggregate=audit_frozen(snapshot,args.source_originals,args.expected_originals_sha256,
                           args.corrected_labels_zip)
    args.private_output.parent.mkdir(parents=True,exist_ok=True)
    with args.private_output.open("x",encoding="utf8") as stream:
        json.dump(aggregate,stream,sort_keys=True,allow_nan=False,indent=2)
        stream.write("\n")
    print(json.dumps({"stage":"galar36-fixed-policy-development-replication",
                      "original_images_verified":EXPECTED_SOURCE_IMAGES,
                      "annotation_runs":EXPECTED_POSITIVE_RUNS,
                      "new_independent_validation":False,
                      "model_promoted":False},sort_keys=True))


if __name__=="__main__":
    main()
