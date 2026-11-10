"""Independent, read-only replay of sealed Galar development-resolution counts.

Does not import the primary resolution audit. All image identities and private
source receipts stay in private inputs; returns only pass/fail and aggregate counts.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, Counter
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib

AUDIT_HASH = "5cf828dd0288364bfe0bb2a5e3a6615b9e5ddaac91dec51b1a7765923fd04709"
ARCHIVE_FILES = (
    "galar-exam21-verified-frames-private.zip",
    "galar-negative-22-24-verified-frames-private.zip",
    "galar-exam23-verified-frames-private.zip",
    "galar-exam25-verified-frames-private.zip",
    "galar-exam27-verified-frames-private.zip",
    "galar-exam29-verified-frames-private.zip",
    "galar-exam30-verified-frames-private.zip",
)
EXAMS = (21, 22, 23, 24, 25, 27, 29, 30)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def replay(audit_file: Path, folder: Path, aggregate_file: Path, *, pinned_audit: str = AUDIT_HASH,
           archive_names: tuple[str, ...] = ARCHIVE_FILES, exams: tuple[int, ...] = EXAMS,
           all_selected: int = 11147, dev_selected: int = 7051,
           repo_root: Path | None = None) -> dict:
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    if any(x.resolve().is_relative_to(root) for x in (audit_file, folder)):
        raise ValueError("Private source input inside public repository")
    if sha(audit_file) != pinned_audit:
        raise ValueError("Changed private audit reference")
    with zipfile.ZipFile(audit_file) as source:
        data = json.loads(source.read("PRIVATE_selected_source_metadata.json"))
        receipts = json.loads(source.read("PRIVATE_source_archive_dependencies.json"))
    if len(data) != all_selected:
        raise ValueError("Changed complete selected-source population")
    expected = {(x["exam"], x["frame"]) for x in data if x["exam"] in exams}
    if len(expected) != dev_selected:
        raise ValueError("Changed development source membership")
    receipt_by_name = {x["archive"]: x for x in receipts}
    found: set[tuple[int, int]] = set()
    counts: dict[int, Counter] = defaultdict(Counter)
    for archive in archive_names:
        row = receipt_by_name[archive]
        p = folder / archive
        if p.stat().st_size != row["size_bytes"] or sha(p) != row["sha256"]:
            raise ValueError("Private source checksum mismatch")
        with zipfile.ZipFile(p) as outer:
            inner = [x for x in outer.namelist() if x.endswith(".zip")]
            if len(inner) != 1:
                raise ValueError("Unexpected nested archive")
            payload = outer.read(inner[0])
        with zipfile.ZipFile(io.BytesIO(payload)) as content:
            for info in content.infolist():
                if not info.filename.upper().endswith(".PNG"):
                    continue
                path = re.fullmatch(r"images/(\d{3})/frame_(\d{6})\.PNG", info.filename)
                if not path:
                    raise ValueError("Noncanonical source PNG")
                identity = int(path[1]), int(path[2])
                if identity not in expected or identity in found:
                    raise ValueError("Unrecognized source image")
                found.add(identity)
                with content.open(info) as stream:
                    header = stream.read(33)
                if (len(header) != 33 or header[0:8] != b"\x89PNG\r\n\x1a\n" or
                        header[8:16] != b"\x00\x00\x00\rIHDR" or
                        zlib.crc32(header[12:29]) != int.from_bytes(header[29:33], "big")):
                    raise ValueError("Changed or invalid original PNG IHDR")
                width, height = struct.unpack_from(">II", header, 16)
                depth, color = header[24], header[25]
                counts[identity[0]][(width, height, depth, color)] += 1
    if found != expected:
        raise ValueError("Incomplete source identity coverage")
    published_bytes = aggregate_file.read_bytes()
    pub = json.loads(published_bytes)
    if pub["original_png_header_count"] != len(found) or len(pub["per_exam"]) != len(exams):
        raise ValueError("Incorrect public aggregate population")
    for row in pub["per_exam"]:
        exam = row["exam"]
        if exam not in exams or row["selected_image_count"] != sum(counts[exam].values()):
            raise ValueError("Public per-examination total inconsistent")
        got_res = Counter()
        got_encoding = Counter()
        for (w, h, d, c), n in counts[exam].items():
            got_res[(w,h)] += n
            got_encoding[(d,c)] += n
        if ({(d["width"], d["height"]): d["count"] for d in row["native_dimensions"]} != got_res or
            {(d["bit_depth"], d["color_type"]): d["count"] for d in row["png_encodings"]} != got_encoding):
            raise ValueError("Public per-examination dimensions/encoding inconsistent")
    return {"status": "PASS", "audit": "independent standard-library PNG header replay",
            "independent_source_members_replayed": len(found), "matched_aggregate_exam_count": len(exams),
            "published_aggregate_sha256": hashlib.sha256(published_bytes).hexdigest(),
            "private_source_sha_checked": True, "individual_source_identity_values_published": False,
            "patient_independence_established": False}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-audit-zip", type=Path, required=True)
    p.add_argument("--private-archives", type=Path, required=True)
    p.add_argument("--public-aggregate", type=Path, required=True)
    p.add_argument("--private-receipt-output", type=Path, required=True)
    a = p.parse_args()
    if a.private_receipt_output.exists():
        p.error("Refusing to overwrite independent evidence")
    if a.private_receipt_output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        p.error("Private receipt cannot be written inside public source repository")
    check = replay(a.private_audit_zip, a.private_archives, a.public_aggregate)
    a.private_receipt_output.parent.mkdir(parents=True, exist_ok=True)
    a.private_receipt_output.write_text(json.dumps(check, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": check["status"], "replayed": check["independent_source_members_replayed"]}))


if __name__ == "__main__":
    main()
