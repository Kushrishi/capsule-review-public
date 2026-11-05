"""Private-only, bounded original-image acquisition of Galar development exam 35.

This script MUST run on a private, authorized machine with sufficient storage.
Never run it in a public GitHub Actions job, publish its outputs, or repurpose
Galar 35 as untouched evaluation. No fallback to whole-archive downloads.
All original images and frame-level label/identity manifests remain PRIVATE.

Two modes: --check-only (offline metadata/label/resource gate) and --acquire
(exactly one 3,453,334,016-byte Figshare HTTP 206 source block). Neither
mode reads examinations 11-20 or the authors' reserved 61-80.
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

from probe_galar_archive import APPROVED_SOURCES, RangeClient, inspect, allowed_redirect
from summarize_galar_archive_layout import get_exam, records

EXAM = 35
PROFILE = APPROVED_SOURCES["fitting-31-40"]
SOURCE_URL = PROFILE["url"]
ARCHIVE_SIZE = PROFILE["size"]
BLOCK = 5
BLOCK_START = 17_802_009_149
BLOCK_BYTES = 3_453_334_016
BLOCK_STOP_EXCLUSIVE = BLOCK_START + BLOCK_BYTES
EXPECTED_IMAGES = 9_643
LABEL_ARCHIVE_BYTES = 17_931_138
EXPECTED_BLOCK_IMAGE_MEMBERS = {34: 2876, 35: 9643, 36: 3098}
EXPECTED_POSITIVE_IMAGES = 1_534
EXPECTED_ANNOTATION_RUNS = 29
NATIVE_STRIDE = 5
MAX_SOURCE_REQUEST_BYTES = BLOCK_BYTES
MIN_PRIVATE_AVAILABLE_BYTES = 12_000_000_000
LABEL_ARCHIVE_SHA256 = "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
SOURCE_INDEX_PART_HASHES = {
    "signature-header.bin": "05eb906d331a7cc125e68c788f763f33823df8c77c0c33b0757c4ede962c6f70",
    "next-header.bin": "d6a0390870886df9c664d1bc877245644912c0ff026a55aff293cb6f6f5e24dd",
    "encoded-index-0.bin": "3f6f88fd9eba4ba356c8da8b8750a095250f1a3d9b6498ff6b646718aaa89730",
}
NAME = re.compile(r"frame_(\d+)\.PNG\Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_public_index(aggregate: dict) -> dict:
    """Public, aggregate-only index: never trust a claimed cost without source match."""
    source = aggregate.get("official_source", {})
    verification = aggregate.get("verification", {})
    block = aggregate.get("blocks", [])
    studies = aggregate.get("studies", {})
    entry = studies.get(str(EXAM), {})
    if (aggregate.get("schema_version") != 1
        or aggregate.get("record_type") != "galar-31-40-published-metadata-index-aggregate-v1"
        or source.get("file_id") != PROFILE["id"]
        or source.get("declared_archive_bytes") != ARCHIVE_SIZE
        or source.get("expected_publisher_md5_unverified") != PROFILE["md5"]
        or verification.get("index_only_transferred_bytes") != 3_629_193
        or verification.get("full_archive_md5_verified") is not False
        or verification.get("original_image_pixels_acquired") != 0
        or verification.get("source_image_counts_match_previous_corrected_label_rows") is not True
        or verification.get("all_internal_native_export_grids_contiguous") is not True
        or not isinstance(block, list) or len(block) != 18
        or not all(type(b.get("compressed_bytes")) is int for b in block)
        or sum(b["compressed_bytes"] for b in block) + 3_629_193 != ARCHIVE_SIZE
        or block[BLOCK].get("block_id") != BLOCK
        or block[BLOCK].get("compressed_bytes") != BLOCK_BYTES
        or block[BLOCK].get("image_members_by_exam") != {"34": 2876, "35": 9643, "36": 3098}
        or 32+sum(b["compressed_bytes"] for b in block[:BLOCK]) != BLOCK_START
        or entry.get("image_members") != EXPECTED_IMAGES
        or entry.get("previous_label_positive_rows") != EXPECTED_POSITIVE_IMAGES
        or entry.get("previous_label_positive_runs") != EXPECTED_ANNOTATION_RUNS
        or entry.get("native_source_stride") != NATIVE_STRIDE
        or entry.get("internal_native_grid_gaps") != 0
        or entry.get("required_block_ids_for_complete_export") != [BLOCK]
        or entry.get("compressed_bytes_if_full_solid_blocks_required") != BLOCK_BYTES):
        raise ValueError("Frozen publisher source-index contract mismatch; transfer blocked.")
    return {"exam": EXAM, "byte_start": BLOCK_START,
            "byte_end_inclusive": BLOCK_STOP_EXCLUSIVE-1,
            "compressed_bytes": BLOCK_BYTES, "expected_source_images": EXPECTED_IMAGES}


def verified_label_rows(labels_zip: Path) -> dict[int, str]:
    """Read ONLY 35.csv from a SHA-verified official archive. Unknowns fail closed."""
    if labels_zip.stat().st_size != LABEL_ARCHIVE_BYTES or sha256_file(labels_zip) != LABEL_ARCHIVE_SHA256:
        raise ValueError("Corrected official annotation archive SHA/size mismatch.")
    with zipfile.ZipFile(labels_zip) as z:
        # Only opening 35.csv checks its CRC; testzip() would read protected
        # 11–20 / 61–80 members and is expressly forbidden here.
        info = z.getinfo("35.csv")  # Does not read 11-20, 61-80 contents.
        if info.is_dir() or info.file_size <= 0 or info.file_size > 64 * 1024 * 1024:
            raise ValueError("Unexpected corrected examination-35 label CSV.")
        with z.open(info) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", newline=""))
            if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
                raise ValueError("Duplicate source annotation column.")
            if not {"frame", "blood"}.issubset(reader.fieldnames or []):
                raise ValueError("Required source label columns missing.")
            values = {}
            last = None
            positive_runs = 0
            preceding_positive = False
            for row in reader:
                if None in row or not re.fullmatch(r"[0-9]+", row.get("frame") or ""):
                    raise ValueError("Malformed original source frame index.")
                frame = int(row["frame"])
                blood = row.get("blood")
                if blood not in ("0", "1"):
                    raise ValueError("Unknown/invalid blood label; do not coerce to negative.")
                if frame in values or (last is not None and frame-last != NATIVE_STRIDE):
                    raise ValueError("Incomplete or duplicate source annotation export grid.")
                if blood == "1" and not preceding_positive:
                    positive_runs += 1
                preceding_positive = blood == "1"
                values[frame] = blood
                last = frame
    if (len(values) != EXPECTED_IMAGES
        or sum(v == "1" for v in values.values()) != EXPECTED_POSITIVE_IMAGES
        or positive_runs != EXPECTED_ANNOTATION_RUNS):
        raise ValueError("Corrected examination-35 positive support/annotation-run count changed.")
    return values


def index_members(listing: str, labels: dict[int, str]) -> list[tuple[int, str]]:
    """Verify exact source filenames AND complete one-block membership, privately."""
    members = []
    seen = set()
    counts = {34: 0, 35: 0, 36: 0}
    for entry in records(listing):
        if entry.get("Folder") == "+" or entry.get("Attributes", "").startswith("D"):
            continue
        block = entry.get("Block", "").strip()
        if block != str(BLOCK):
            continue
        path = entry["Path"].replace("\\", "/")
        exam = get_exam(path, allowed_exams=frozenset(range(31, 41)))
        if exam not in counts:
            raise ValueError("Unexpected source examination member in requested block.")
        basename = PurePosixPath(path).name
        if PurePosixPath(path).suffix.upper() != ".PNG":
            continue
        match = NAME.fullmatch(basename)
        if not match:
            raise ValueError("Unexpected original Galar PNG member name.")
        counts[exam] += 1
        frame = int(match.group(1))
        if exam == EXAM:
            if frame not in labels or frame in seen:
                raise ValueError("Original source index missing annotation or duplicate.")
            seen.add(frame)
            members.append((frame, path))
    if counts != EXPECTED_BLOCK_IMAGE_MEMBERS:
        raise ValueError("Source solid block member partition changed.")
    if seen != set(labels):
        raise ValueError("Original published image/export label join incomplete.")
    return sorted(members)


def verified_index_receipt(receipt: dict) -> None:
    actual = {p.get("name"): p.get("sha256") for p in receipt.get("parts", [])}
    if (receipt.get("official_file_id") != PROFILE["id"]
        or receipt.get("official_full_archive_bytes") != ARCHIVE_SIZE
        or receipt.get("actual_index_only_bytes_transferred") != 3_629_193
        or receipt.get("record_type") != PROFILE["receipt_type"]
        or receipt.get("full_archive_downloaded") is not False
        or receipt.get("pixels_acquired") != 0
        or actual != SOURCE_INDEX_PART_HASHES):
        raise ValueError("Source index CRC/hash receipt differs from frozen independently verified source.")


def download_one_block(sparse: Path, *, url: str = SOURCE_URL, test_range=None) -> dict:
    """Exact 206, no redirect/mirror improvisation, byte-counted stream, SHA256."""
    start, count = (BLOCK_START, BLOCK_BYTES) if test_range is None else test_range
    if test_range is None and url != SOURCE_URL:
        raise ValueError("Unapproved source URL.")
    if count <= 0 or count > MAX_SOURCE_REQUEST_BYTES or start < 0 or start + count > ARCHIVE_SIZE:
        raise ValueError("Original-image transfer exceeds pinned byte bounds.")
    request = urllib.request.Request(url, headers={
        "Range": f"bytes={start}-{start+count-1}", "Accept-Encoding": "identity",
        "User-Agent": "capsule-review/0.2 source-verified research acquisition"})
    h=hashlib.sha256()
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 206:
            raise ValueError("HTTP 206 required; full-file response rejected before body.")
        if test_range is None and not allowed_redirect(response.geturl()):
            raise ValueError("Untrusted original-image archive redirect.")
        expected_range = f"bytes {start}-{start+count-1}/{ARCHIVE_SIZE}"
        if response.headers.get("Content-Range") != expected_range:
            raise ValueError("Source Content-Range mismatch.")
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("Unexpected response compression.")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) != count):
            raise ValueError("Untrusted source Content-Length.")
        with sparse.open("r+b") as out:
            out.seek(start)
            left = count
            while left:
                chunk = response.read(min(1024*1024, left))
                if not chunk:
                    raise ValueError("Incomplete bounded source transfer.")
                h.update(chunk)
                out.write(chunk)
                left -= len(chunk)
            if response.read(1):
                raise ValueError("Unexpected bytes beyond source range.")
    return {
        "official_file_id": PROFILE["id"], "block": BLOCK,
        "range_start": start, "range_stop_exclusive": start+count,
        "source_block_sha256": h.hexdigest(), "compressed_bytes_received": count,
        "full_source_md5_verified": False,
    }


def package_original_images(sparse: Path, stage: Path, archive: Path,
                            members: list[tuple[int, str]], labels: dict[int, str],
                            block_receipt: dict) -> dict:
    """Extract each original PNG, verify, retain private original bytes and manifest."""
    if stage.exists() or archive.exists():
        raise FileExistsError("Refusing to overwrite private source artifacts.")
    stage.mkdir(parents=True)
    extracted = stage / "extracted"
    extracted.mkdir()
    paths = stage / "source-member-paths-private.txt"
    paths.write_text("\n".join(path for _,path in members) + "\n", encoding="utf8")
    result = subprocess.run(
        ["7z", "x", "-y", "-bso0", "-bse2", f"-o{extracted}", f"-i@{paths}", str(sparse)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=2100, check=False)
    if result.returncode != 0:
        raise ValueError("Source 7z decompression/CRC verification failed.")
    manifest=[]
    total=0
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for frame,path in members:
            rel=PurePosixPath(path)
            if rel.is_absolute() or any(x in ("..","") for x in rel.parts):
                raise ValueError("Unsafe original-image member path.")
            file=(extracted/Path(*rel.parts)).resolve(strict=True)
            if not file.is_relative_to(extracted.resolve()) or not file.is_file():
                raise ValueError("Source image extraction escaped private destination.")
            with Image.open(file) as img:
                if img.format != "PNG":
                    raise ValueError("Original source image is not a PNG.")
                img.verify()
            digest=sha256_file(file)
            size=file.stat().st_size
            total+=size
            # Keep the publisher's *exact original basename*, including
            # any nonuniform zero padding; frame numbers are not filenames.
            original_basename = rel.name
            manifest.append({"examination":35,"source_frame":frame,
                "original_filename":original_basename,
                "original_png_sha256":digest,"original_png_bytes":size,
                "blood_label":int(labels[frame])})
            z.write(file,arcname=f"images/035/{original_basename}")
        z.writestr("source-frame-private-manifest.json",
                   json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        z.writestr("source-block-private-receipt.json",
                   json.dumps(block_receipt,indent=2,sort_keys=True)+"\n")
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("Original image private package ZIP CRC failure.")
    if len(manifest)!=EXPECTED_IMAGES or sum(x["blood_label"] for x in manifest)!=EXPECTED_POSITIVE_IMAGES:
        raise ValueError("Source image pack counts disagree with certified annotation support.")
    return {
        "verified_original_source_images":len(manifest),"exam":EXAM,
        "positive_annotation_images":sum(x["blood_label"] for x in manifest),
        "total_original_png_bytes":total,
        "private_package_bytes":archive.stat().st_size,
        "private_package_sha256":sha256_file(archive),
        "archive_complete_full_publisher_md5_verified":False,
        "clinical_model_improvement_measured":False,
        "all_source_images_and_frame_labels_private":True
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index-aggregate",type=Path,required=True)
    p.add_argument("--labels-zip",type=Path,required=True)
    p.add_argument("--workdir",type=Path,required=True)
    p.add_argument("--private-package",type=Path,required=True)
    p.add_argument("--check-only",action="store_true")
    p.add_argument("--acquire",action="store_true")
    args=p.parse_args()
    if args.check_only == args.acquire:
        p.error("Specify exactly one of --check-only or --acquire.")
    root=Path(__file__).resolve().parents[1]
    for target in (args.workdir,args.private_package):
        if target.resolve(strict=False).is_relative_to(root):
            p.error("Original medical data must never be written inside public Git.")
    if args.private_package.exists() or args.workdir.exists():
        p.error("Private output already exists: refuse overwrite.")
    if args.workdir.resolve(strict=False)==args.private_package.resolve(strict=False):
        p.error("Private package must not equal staging path.")
    validate_public_index(json.loads(args.index_aggregate.read_text("utf8")))
    labels=verified_label_rows(args.labels_zip)
    free=shutil.disk_usage(args.workdir.parent).free
    if free < MIN_PRIVATE_AVAILABLE_BYTES:
        p.error("Insufficient free PRIVATE storage for source block, decompression, and archive.")
    # Offline preflight requires source hashes and adequate private storage,
    # but no archive extraction tool or network access.
    if args.check_only:
        print(json.dumps({
            "decision":"PRIVATE_SOURCE_PRECHECK_READY",
            "exam": EXAM, "source_block":BLOCK,"compressed_bytes":BLOCK_BYTES,
            "indexed_images":len(labels),"full_source_md5_verified":False,
            "images_downloaded":0,"needs_separate_image_transfer":True},sort_keys=True))
        return
    if shutil.which("7z") is None:
        p.error("7z command unavailable for --acquire.")
    args.workdir.mkdir(parents=True)
    index_dir=args.workdir/"index"
    receipt=inspect(
        RangeClient(SOURCE_URL,ARCHIVE_SIZE,source="fitting-31-40"),
        index_dir,sparse_path=index_dir/"headers-only.7z")
    verified_index_receipt(receipt)
    sparse=index_dir/"headers-only.7z"
    listing_file=args.workdir/"private-source-list.txt"
    with listing_file.open("wb") as out:
        result=subprocess.run(["7z","l","-slt",str(sparse)],stdout=out,
                              stderr=subprocess.PIPE,timeout=200,check=False)
    if result.returncode:
        raise ValueError("Source 7z index cannot be verified.")
    members=index_members(listing_file.read_text(encoding="utf8"),labels)
    block_receipt=download_one_block(sparse)
    packaged=package_original_images(sparse,args.workdir/"images-stage",
                                     args.private_package,members,labels,block_receipt)
    (args.workdir/"private-acquisition-receipt.json").write_text(
        json.dumps({"package":packaged,"source_block":block_receipt},
                   indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "exam": EXAM, "verified_original_images":packaged["verified_original_source_images"],
        "compressed_source_bytes":block_receipt["compressed_bytes_received"],
        "private_package_sha256":packaged["private_package_sha256"],
        "original_source_full_md5_verified":False,
        "model_evaluation_performed":False},sort_keys=True))


if __name__=="__main__":
    main()
