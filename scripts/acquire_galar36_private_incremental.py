"""PRIVATE source-complete Galar36 acquisition, reusing verified Galar35 block 5.

This operation reads only allowed previously inspected DEVELOPMENT study 36,
never the historical Galar11-20 or authors' reserved 61-80 outcomes.

Requires an independently restored, exact-SHA-verified Galar35 source block 5
from the existing private Drive inventory. Request ONLY official Figshare
Galar31-40 7z block 6 (3,430,870,954 bytes, strict HTTP 206). Reconstruct
a PRIVATE sparse 7z from the previously retained pinned source-index parts,
verified block 5, and newly transferred block 6. Extract only all 13,326
original Galar36 PNGs; join exact source IDs against official corrected 36.csv.

--check-only: no network, no extraction, no new outputs.
--acquire: explicitly authorized bounded download; PRIVATE outputs only.

This source acquisition does NOT train or evaluate an AI model and does not
create a patient-independent cohort or complete in-device video.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

from PIL import Image

from plan_galar31_40_development_blocks import validate_index, InvalidSourcePlan
from probe_galar_archive import APPROVED_SOURCES, allowed_redirect
from summarize_galar_archive_layout import records, get_exam

PROFILE = APPROVED_SOURCES["fitting-31-40"]
ARCHIVE_SIZE = 69_219_317_963
FILE_ID = 44755700
SOURCE_URL = "https://ndownloader.figshare.com/files/44755700"
OLD_BLOCK = 5
NEW_BLOCK = 6
OLD_START = 17_802_009_149
OLD_BYTES = 3_453_334_016
OLD_SHA256 = "0b24a245d8f7e72b69ad1e1295d757ce43a03ccaa87e73795423804c5e70d225"
NEW_START = 21_255_343_165
NEW_BYTES = 3_430_870_954
END_EXCLUSIVE = NEW_START + NEW_BYTES
LABEL_ARCHIVE_BYTES = 17_931_138
LABEL_ARCHIVE_SHA256 = "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
EXAM = 36
EXPECTED_SOURCE_IMAGES = 13_326
EXPECTED_POSITIVE_IMAGES = 209
EXPECTED_POSITIVE_RUNS = 59
NATIVE_STRIDE = 5
EXPECTED_BLOCK_MEMBERS = {5: {34: 2876,35: 9643,36: 3098},
                          6: {36: 10228,37: 5454}}
SOURCE_INDEX_NAMES = {
    "signature-header.bin": ("05eb906d331a7cc125e68c788f763f33823df8c77c0c33b0757c4ede962c6f70", 0, 32),
    "next-header.bin": ("d6a0390870886df9c664d1bc877245644912c0ff026a55aff293cb6f6f5e24dd", 69_219_317_920, 43),
    "encoded-index-0.bin": ("3f6f88fd9eba4ba356c8da8b8750a095250f1a3d9b6498ff6b646718aaa89730", 69_215_688_802, 3_629_118),
}
PRIVATE_RECEIPT_ROOT = "galar35-stage/index/"
MIN_PRIVATE_AVAILABLE = 22_000_000_000
MAX_PNG_BYTES = 16 * 1024 * 1024
NAME = re.compile(r"frame_(\d+)\.PNG\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


def sha256_file(path: Path, max_size: int | None = None) -> str:
    if (path.is_symlink() or not path.is_file() or
            (max_size is not None and not 0 < path.stat().st_size <= max_size)):
        raise ValueError("Missing or unsafe source checksum file.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_plan(index: dict) -> dict:
    blocks, studies = validate_index(index)
    source = studies[EXAM]
    if (PROFILE["id"] != FILE_ID or PROFILE["url"] != SOURCE_URL
            or PROFILE["size"] != ARCHIVE_SIZE
            or blocks[OLD_BLOCK]["range_start"] != OLD_START
            or blocks[OLD_BLOCK]["compressed_bytes"] != OLD_BYTES
            or blocks[NEW_BLOCK]["range_start"] != NEW_START
            or blocks[NEW_BLOCK]["compressed_bytes"] != NEW_BYTES
            or blocks[NEW_BLOCK]["range_end_inclusive"] + 1 != END_EXCLUSIVE
            or source["required_compressed_blocks"] != [OLD_BLOCK, NEW_BLOCK]
            or source["published_image_members"] != EXPECTED_SOURCE_IMAGES
            or source["previously_inspected_blood_positive_rows"] != EXPECTED_POSITIVE_IMAGES
            or source["previously_inspected_positive_annotation_runs"] != EXPECTED_POSITIVE_RUNS
            or source["native_export_stride_not_elapsed_time"] != NATIVE_STRIDE):
        raise ValueError("Frozen Galar36 official source/index eligibility changed.")
    for block, members in EXPECTED_BLOCK_MEMBERS.items():
        if blocks[block]["examinations_with_members"] != members:
            raise ValueError("Frozen neighboring 7z source-block membership changed.")
    return {"complete_source_examination": 36,
            "source_file_id": FILE_ID,
            "reused_block": 5, "new_block": 6,
            "new_exact_range": [NEW_START, END_EXCLUSIVE-1],
            "new_compressed_bytes": NEW_BYTES}


def verified_labels36(labels_zip: Path) -> dict[int, str]:
    # Hashing the ZIP itself does NOT open protected member contents.
    if (labels_zip.stat().st_size != LABEL_ARCHIVE_BYTES
            or sha256_file(labels_zip) != LABEL_ARCHIVE_SHA256):
        raise ValueError("Official corrected Galar annotation ZIP SHA256/size mismatch.")
    rows = {}
    prior = None
    in_run = False
    runs = 0
    with zipfile.ZipFile(labels_zip) as z:
        info = z.getinfo("36.csv")
        if not 0 < info.file_size <= 32 * 1024 * 1024:
            raise ValueError("Unexpected corrected Galar36 CSV size.")
        with z.open(info) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
            if (len(reader.fieldnames or []) != len(set(reader.fieldnames or []))
                    or not {"frame","blood"}.issubset(reader.fieldnames or [])):
                raise ValueError("Invalid corrected source-label CSV columns.")
            for row in reader:
                if (None in row or not (row.get("frame") or "").isdecimal()
                        or row.get("blood") not in ("0","1")):
                    raise ValueError("Unknown, malformed or missing development labels.")
                frame = int(row["frame"])
                if frame in rows or (prior is not None and frame-prior != NATIVE_STRIDE):
                    raise ValueError("Duplicate or incomplete original 36 source-index label grid.")
                if row["blood"] == "1" and not in_run:
                    runs += 1
                in_run = row["blood"] == "1"
                rows[frame] = row["blood"]
                prior = frame
    if (len(rows) != EXPECTED_SOURCE_IMAGES
            or sum(label=="1" for label in rows.values()) != EXPECTED_POSITIVE_IMAGES
            or runs != EXPECTED_POSITIVE_RUNS):
        raise ValueError("Galar36 published-source annotation support changed.")
    return rows


def retained_index_parts(receipts_zip: Path) -> list[tuple[int, bytes]]:
    """Read only the pinned metadata index and metadata receipt; not labels."""
    if receipts_zip.is_symlink() or not receipts_zip.is_file():
        raise ValueError("Private Galar35 source-index receipts ZIP missing or unsafe.")
    with zipfile.ZipFile(receipts_zip) as z:
        receipt_info = z.getinfo(PRIVATE_RECEIPT_ROOT + "receipt.json")
        if not 0 < receipt_info.file_size <= 64 * 1024:
            raise ValueError("Unexpected private index receipt size.")
        receipt_blob = z.read(receipt_info)
        receipt = json.loads(receipt_blob)
        if (receipt.get("official_file_id") != FILE_ID
                or receipt.get("official_full_archive_bytes") != ARCHIVE_SIZE
                or receipt.get("actual_index_only_bytes_transferred") != 3_629_193
                or receipt.get("full_archive_downloaded") is not False
                or receipt.get("pixels_acquired") != 0
                or receipt.get("record_type") != "galar-31-40-7z-index-only-v1"):
            raise ValueError("Previously acquired official source index receipt mismatch.")
        part_receipts = receipt.get("parts")
        if (not isinstance(part_receipts, list) or
                {p.get("name") for p in part_receipts} != set(SOURCE_INDEX_NAMES)):
            raise ValueError("Missing pinned index range part from private receipt.")
        parts = []
        for name,(expected_sha, offset, count) in SOURCE_INDEX_NAMES.items():
            if not any(p.get("name")==name and p.get("offset")==offset
                       and p.get("length")==count and p.get("sha256")==expected_sha
                       for p in part_receipts):
                raise ValueError("Source-index byte range receipt does not match official pin.")
            info = z.getinfo(PRIVATE_RECEIPT_ROOT + name)
            if info.file_size != count:
                raise ValueError("Unexpected indexed source header size.")
            part = z.read(info)
            if hashlib.sha256(part).hexdigest()!=expected_sha:
                raise ValueError("Corrupted retained source index part.")
            parts.append((offset, part))
    return parts


def verify_retained_block(block5: Path) -> None:
    if (block5.stat().st_size != OLD_BYTES
            or sha256_file(block5) != OLD_SHA256):
        raise ValueError("Retained original source block5 SHA256/size mismatch; no new download.")


def download_block6(sparse: Path, *, url: str = SOURCE_URL, test_range=None) -> dict:
    """Strictly bounded HTTP206 transfer; reject full archive and unsafe mirrors."""
    start, count = (NEW_START, NEW_BYTES) if test_range is None else test_range
    if test_range is None and url != SOURCE_URL:
        raise ValueError("Unapproved Galar official original-image URL.")
    if (start < 0 or count < 1 or count > NEW_BYTES
            or start+count > ARCHIVE_SIZE):
        raise ValueError("Disallowed original compressed-image request size.")
    req = urllib.request.Request(url, headers={
        "Range": f"bytes={start}-{start+count-1}",
        "Accept-Encoding": "identity",
        "User-Agent": "capsule-review/0.2 bounded-private-original-source"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req,timeout=120) as response:
        if response.status != 206:
            raise ValueError("HTTP 206 partial source response mandatory.")
        if test_range is None and not allowed_redirect(response.geturl()):
            raise ValueError("Original source redirect host not approved.")
        if response.headers.get("Content-Range") != (
                f"bytes {start}-{start+count-1}/{ARCHIVE_SIZE}"):
            raise ValueError("Untrusted original source Content-Range.")
        if response.headers.get("Content-Encoding","identity") != "identity":
            raise ValueError("Unexpected source response compression.")
        length=response.headers.get("Content-Length")
        if length is not None and (not length.isdecimal() or int(length)!=count):
            raise ValueError("Original source HTTP content-length mismatch.")
        with sparse.open("r+b") as out:
            out.seek(start)
            remaining=count
            while remaining:
                chunk=response.read(min(1024*1024,remaining))
                if not chunk:
                    raise ValueError("Original source block6 transfer truncated.")
                digest.update(chunk)
                out.write(chunk)
                remaining-=len(chunk)
            if response.read(1):
                raise ValueError("Original server returned bytes outside the requested block.")
    return {"official_file_id":FILE_ID,"block":6,
            "range_start":start,"range_stop_exclusive":start+count,
            "compressed_bytes_received":count,"source_block_sha256":digest.hexdigest(),
            "full_source_md5_verified":False}


def assemble_private_sparse(block5: Path, parts: list[tuple[int,bytes]], sparse: Path) -> None:
    if sparse.exists() or sparse.is_symlink():
        raise FileExistsError("Do not overwrite private sparse original-source archives.")
    sparse.parent.mkdir(parents=True, exist_ok=True)
    with sparse.open("xb") as out:
        out.truncate(ARCHIVE_SIZE)
        for offset, part in parts:
            out.seek(offset)
            out.write(part)
        old_digest=hashlib.sha256()
        with block5.open("rb") as stream:
            out.seek(OLD_START)
            n=0
            while n<OLD_BYTES:
                chunk=stream.read(min(1024*1024,OLD_BYTES-n))
                if not chunk:
                    raise ValueError("Existing block5 shorter than verified source.")
                out.write(chunk)
                old_digest.update(chunk)
                n+=len(chunk)
        if old_digest.hexdigest()!=OLD_SHA256:
            raise ValueError("Existing private source block5 changed during copy.")


def list_complete_exam36(sparse: Path, labels: dict[int,str]) -> list[tuple[int,str]]:
    """Check all source-index members before extraction; never reveal original IDs."""
    listing = subprocess.run(["7z","l","-slt",str(sparse)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,check=False,timeout=220)
    if listing.returncode:
        raise ValueError("7z cannot read the pinned full original source index.")
    seen={}
    per_block={5:0,6:0}
    all_members={5:{},6:{}}
    for item in records(listing.stdout.decode("utf-8",errors="replace")):
        if item.get("Folder") == "+" or item.get("Attributes","").startswith("D"):
            continue
        blk=item.get("Block","").strip()
        if blk not in ("5","6"):
            continue
        path=item.get("Path","").replace("\\","/")
        ex=get_exam(path,allowed_exams=frozenset(range(31,41)))
        if ex is None:
            raise ValueError("Unrecognized examination in original source blocks.")
        basename=PurePosixPath(path).name
        if not path.upper().endswith(".PNG"):
            continue
        match=NAME.fullmatch(basename)
        if match is None:
            raise ValueError("Unexpected original publisher PNG name.")
        all_members[int(blk)][ex] = all_members[int(blk)].get(ex,0)+1
        if ex==EXAM:
            frame=int(match.group(1))
            if frame in seen or frame not in labels:
                raise ValueError("Duplicate/unlabelled Galar36 original source frame.")
            seen[frame]=path
            per_block[int(blk)]+=1
    if (per_block != {block: members[EXAM] for block, members in EXPECTED_BLOCK_MEMBERS.items()}
            or all_members != EXPECTED_BLOCK_MEMBERS or set(seen) != set(labels)):
        raise ValueError("Complete Galar36 original source image membership not verified.")
    return sorted(seen.items())


def private_package36(sparse: Path, members: list[tuple[int,str]],
                      labels: dict[int,str], stage: Path, output: Path,
                      receipts: dict) -> dict:
    if stage.exists() or output.exists() or output.is_symlink():
        raise FileExistsError("Original medical image package cannot overwrite existing private files.")
    if (len(members) != EXPECTED_SOURCE_IMAGES or
            {frame for frame,_ in members} != set(labels)):
        raise ValueError("Incomplete or duplicated private original image selection.")
    stage.mkdir(parents=True)
    listing=stage/"original-galar36-member-paths-PRIVATE.txt"
    listing.write_text("\n".join(p for _,p in members)+"\n",encoding="utf-8")
    extracted=stage/"original-source-images-PRIVATE"
    extracted.mkdir()
    command=["7z","x","-y","-bso0","-bse2",f"-o{extracted}",f"-i@{listing}",str(sparse)]
    result=subprocess.run(command, stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                          check=False,timeout=3600)
    if result.returncode:
        raise ValueError("Galar36 source image 7z extraction/CRC failed.")
    images=[]
    total=0
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_STORED,allowZip64=True) as dst:
        for frame,name in members:
            path=PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "" in path.parts:
                raise ValueError("Unexpected/unsafe original member path.")
            original=(extracted/Path(*path.parts)).resolve(strict=True)
            if not original.is_file() or not original.is_relative_to(extracted.resolve()):
                raise ValueError("Source extraction escaped private destination.")
            size=original.stat().st_size
            if not 0 < size <= MAX_PNG_BYTES:
                raise ValueError("Original source PNG exceeds declared private file bound.")
            with Image.open(original) as im:
                if im.format!="PNG":
                    raise ValueError("Galar36 publisher image is not an original PNG.")
                im.verify()
            digest=sha256_file(original)
            images.append({"examination":EXAM,"source_frame":frame,
                           "original_filename":path.name,"original_png_sha256":digest,
                           "original_png_bytes":size,"blood_label":int(labels[frame])})
            dst.write(original,arcname="images/036/"+path.name)
            total+=size
        dst.writestr("source-frame-private-manifest.json",
                     json.dumps(images,sort_keys=True)+"\n")
        dst.writestr("source-block-private-receipt.json",
                     json.dumps(receipts,sort_keys=True)+"\n")
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError("Private original image ZIP CRC verification failed.")
    if (len(images)!=EXPECTED_SOURCE_IMAGES
            or sum(x["blood_label"] for x in images)!=EXPECTED_POSITIVE_IMAGES):
        raise ValueError("Original Galar36 PNG package count/label join mismatch.")
    return {"exam":EXAM,"verified_original_source_images":len(images),
            "positive_annotated_images":EXPECTED_POSITIVE_IMAGES,
            "positive_annotated_runs":EXPECTED_POSITIVE_RUNS,
            "original_png_bytes":total,
            "private_package_bytes":output.stat().st_size,
            "private_package_sha256":sha256_file(output),
            "clinical_model_trained_or_evaluated":False,
            "all_individual_original_images_and_labels_private":True}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only",action="store_true")
    mode.add_argument("--acquire",action="store_true")
    p.add_argument("--index-aggregate",type=Path,required=True)
    p.add_argument("--retained-block5",type=Path,required=True)
    p.add_argument("--retained-index-receipts-zip",type=Path,required=True)
    p.add_argument("--corrected-labels-zip",type=Path,required=True)
    p.add_argument("--workdir",type=Path,required=True)
    p.add_argument("--private-output-zip",type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    for path in (args.workdir,args.private_output_zip):
        if path.is_symlink() or path.exists() or path.resolve(strict=False).is_relative_to(root):
            p.error("Never overwrite or place medical-image outputs inside public source Git.")
    if args.private_output_zip.resolve(strict=False).is_relative_to(args.workdir.resolve(strict=False)):
        p.error("Keep the durable private image package separate from the temporary workdir.")
    if not args.workdir.parent.is_dir() or not args.private_output_zip.parent.is_dir():
        p.error("Both private output parent directories must exist first.")
    if shutil.disk_usage(args.workdir.parent).free < MIN_PRIVATE_AVAILABLE:
        p.error("Insufficient private storage for the two solid source blocks and original PNGs.")
    plan=verify_source_plan(json.loads(args.index_aggregate.read_text(encoding="utf-8")))
    verify_retained_block(args.retained_block5)
    parts=retained_index_parts(args.retained_index_receipts_zip)
    labels=verified_labels36(args.corrected_labels_zip)
    if args.check_only:
        print(json.dumps({"decision":"SOURCE_REUSE_PREFLIGHT_READY",
                          "exam":EXAM,"verified_source_block5_sha256":OLD_SHA256,
                          "new_compressed_bytes":NEW_BYTES,
                          "new_range":plan["new_exact_range"],
                          "original_images_acquired":0,"new_network_requests":0},sort_keys=True))
        return
    if shutil.which("7z") is None:
        p.error("7z required for actual PRIVATE image acquisition.")
    args.workdir.mkdir()
    sparse=args.workdir/"source-index-and-only-blocks-5-6.7z"
    assemble_private_sparse(args.retained_block5,parts,sparse)
    receipt6=download_block6(sparse)
    selected=list_complete_exam36(sparse,labels)
    receipts={"source":"official-Galar31-40-v2","official_file_id":FILE_ID,
              "full_source_md5_verified":False,
              "retained_block5_sha256":OLD_SHA256,
              "retained_block5_compressed_bytes":OLD_BYTES,
              "source_block6":receipt6,"all_other_image_blocks_absent":True}
    packaged=private_package36(sparse,selected,labels,
                                args.workdir/"stage-original36",args.private_output_zip,receipts)
    (args.workdir/"PRIVATE-galar36-acquisition-receipt.json").write_text(
        json.dumps({"package":packaged,"source_blocks":receipts},indent=2,sort_keys=True)+"\n",
        encoding="utf-8")
    print(json.dumps({"exam":36,"original_images_verified":packaged["verified_original_source_images"],
                      "private_package_sha256":packaged["private_package_sha256"],
                      "new_official_compressed_bytes":NEW_BYTES,
                      "new_model_inference_executed":False,
                      "patient_independent_validation_claimed":False},sort_keys=True))


if __name__=="__main__":
    main()
