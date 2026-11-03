"""Acquire exactly the two preregistered Rhode Island VCE studies, without a full download.

Cloud runner use only. Range requests are never retried or replaced by a full GET.
Images are staged outside Git and must never be uploaded as GitHub artifacts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import urllib.request
import zlib
from zipfile import ZIP_STORED, ZipFile
import sys

from ranged_zip import HTTPRangeReader

URL = "https://ndownloader.figshare.com/files/37560007"
OUTER_BYTES = 5_987_150_542
EXISTING_TRANSFER_UPPER_BOUND = 191_022_493  # from verified s288 acquisition receipt
TOTAL_DATA_BUDGET = 512 * 1024 * 1024
SPEC_SHA256 = "c92500af677a12323ea5b8ebf43feb1b17f41bcf44ccfa80e94f28a19289399e"
MEMBERS = {
    "s280": ("Study 276-300/s280.zip", 103_418_092, 0x1A870799),
    "s284": ("Study 276-300/s284.zip", 115_960_292, 0x6F1947E6),
}


def prepared_members(spec: dict) -> dict:
    frozen = spec["future_studies_selected_without_examining_images_or_labels"]
    if {d["study"] for d in frozen} != set(MEMBERS) or len(frozen) != len(MEMBERS):
        raise ValueError("Frozen future study membership changed")
    for d in frozen:
        name, size, _ = MEMBERS[d["study"]]
        if (d["source_member"], d["source_member_bytes"]) != (name, size):
            raise ValueError("Frozen study path or size changed")
    return {d["study"]: MEMBERS[d["study"]] for d in frozen}


def member_offsets(max_index_bytes=8*1024*1024) -> tuple[dict, int]:
    """Index-only, fail closed if server fails exact Range or selected metadata."""
    with HTTPRangeReader(URL, max_transfer_bytes=max_index_bytes) as reader:
        if reader.size != OUTER_BYTES:
            raise ValueError("Official archive byte length changed")
        with ZipFile(reader) as archive:
            results = {}
            for study, (member, size, crc) in MEMBERS.items():
                info = archive.getinfo(member)
                if (info.compress_type != ZIP_STORED or info.file_size != size or
                        info.compress_size != size or info.CRC != crc or info.flag_bits & 1):
                    raise ValueError(f"{study} outer ZIP member identity/format changed")
                reader.seek(info.header_offset)
                local = reader.read(30)
                if len(local) != 30 or local[:4] != b"PK\x03\x04":
                    raise ValueError("Malformed ZIP local header")
                header = struct.unpack("<4s5H3I2H", local)
                method, filename_bytes, extra_bytes = header[3], header[-2], header[-1]
                if method != ZIP_STORED or reader.read(filename_bytes).decode("utf-8") != member:
                    raise ValueError("Local header does not match frozen file")
                offset = info.header_offset + 30 + filename_bytes + extra_bytes
                if offset < 0 or offset + size > OUTER_BYTES:
                    raise ValueError("ZIP source offsets outside official file")
                results[study] = {"name": member, "offset": offset, "size": size, "crc32":f"{crc:08x}"}
        return results, reader.transferred_bytes


def download_member(study: str, entry: dict, dest: Path) -> dict:
    """Make exactly one bounded HTTP 206 request; no retry or full GET fallback."""
    size = entry["size"]
    start, end = entry["offset"], entry["offset"] + size - 1
    req = urllib.request.Request(URL, headers={
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
        "User-Agent": "CapsuleReviewResearch/0.2 prespecified studies",
    })
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.with_suffix(".part").exists():
        raise ValueError("Refusing to overwrite existing research archive")
    temp = dest.with_suffix(".part")
    digest = sha256()
    crc = 0
    count = 0
    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            if (resp.status != 206 or
                resp.headers.get("Content-Range") != f"bytes {start}-{end}/{OUTER_BYTES}" or
                resp.headers.get("Content-Length") != str(size) or
                resp.headers.get("Content-Encoding", "identity").lower() != "identity" or
                not resp.geturl().startswith("https://")):
                raise ValueError("Official server did not return exact byte Range 206")
            selected_headers = {key: resp.headers.get(key) for key in
                ("ETag", "Last-Modified", "x-amz-version-id", "Content-Range")}
            with temp.open("xb") as f:
                while count < size:
                    b = resp.read(min(1024 * 1024, size-count))
                    if not b:
                        raise ValueError("Selected member truncated")
                    f.write(b)
                    count += len(b)
                    digest.update(b)
                    crc = zlib.crc32(b, crc)
                if resp.read(1):
                    raise ValueError("Selected member exceeded declared byte range")
        if count != size or crc != int(entry["crc32"],16):
            raise ValueError("Selected study size / official ZIP CRC mismatch")
        with ZipFile(temp) as z:
            infos = z.infolist()
            if not infos or any(i.is_dir() for i in infos) or z.testzip() is not None:
                raise ValueError("Inner study ZIP corrupted")
        temp.replace(dest)
        return {"study": study, "source_member": entry["name"], "member_bytes": count,
                "sha256":digest.hexdigest(),"source_crc32":entry["crc32"],
                "inner_zip_crc_passed":True,"remote_headers":selected_headers}
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def acquire(spec_path: Path, output: Path) -> dict:
    raw_spec=spec_path.read_bytes()
    if sha256(raw_spec).hexdigest() != SPEC_SHA256:
        raise ValueError("Prespecified protocol SHA-256 changed")
    spec=json.loads(raw_spec)
    prepared_members(spec)
    paths, index_bytes = member_offsets()
    expected_selected = sum(x["size"] for x in paths.values())
    # One remote request per selected member, charged in full even on failure.
    bound = EXISTING_TRANSFER_UPPER_BOUND + index_bytes + expected_selected
    if bound > TOTAL_DATA_BUDGET:
        raise ValueError("Cumulative research data budget exceeded")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory contains existing data")
    output.mkdir(parents=True,exist_ok=True)
    entries=[]
    for study in ("s280","s284"):
        entry=download_member(study,paths[study],output / f"{study}.zip")
        entries.append(entry)
        print(f"Verified {study}, {entry['member_bytes']} bytes, sha256={entry['sha256']}",flush=True)
    return {"source_url":URL,"outer_archive_bytes":OUTER_BYTES,
            "outer_md5_verified":False,"spec_sha256":SPEC_SHA256,
            "previous_acquisition_conservative_upper_bound_bytes":EXISTING_TRANSFER_UPPER_BOUND,
            "index_bytes":index_bytes,"new_data_transfer_bytes_upper_bound":index_bytes+expected_selected,
            "cumulative_data_transfer_upper_bound_bytes":bound,"cumulative_budget_bytes":TOTAL_DATA_BUDGET,
            "studies":entries,"unverified_patient_independence":True,
            "timestamp_status":"Unknown original capture times"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    args=p.parse_args()
    if args.receipt.exists():
        p.error("Receipt exists: refusing overwrite")
    rec=acquire(args.spec,args.output_dir)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(rec,sort_keys=True,indent=2)+"\n")

if __name__=="__main__":
    main()
