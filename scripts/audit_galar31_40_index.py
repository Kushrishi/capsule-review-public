"""Aggregate-only safety gate for Galar studies 31–40 source-archive index.

Input: official 7z HEADER-ONLY receipt plus PRIVATE '7z l -slt' listing.
Output: anonymous study counts, native-grid gaps, solid block footprints.
Does not read source image pixels, clinical labels or patient identifiers.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_galar_archive import APPROVED_SOURCES
from summarize_galar_archive_layout import records, get_exam

PROFILE = APPROVED_SOURCES["fitting-31-40"]
EXAMS = frozenset(range(31, 41))
# From immutable public Nov 2 corrected-label aggregate; NOT a new label read.
REFERENCE_ROWS = {
    31: 24919, 32: 23421, 33: 13297, 34: 10867, 35: 9643,
    36: 13326, 37: 18125, 38: 6209, 39: 130776, 40: 131204,
}
STRIDE = {e: 5 if e <= 38 else 1 for e in EXAMS}
PATTERN = re.compile(r"frame_(\d+)\.PNG\Z")


def audit(listing: str, receipt: dict) -> dict:
    if (not isinstance(receipt, dict)
        or receipt.get("record_type") != PROFILE["receipt_type"]
        or receipt.get("official_file_id") != PROFILE["id"]
        or receipt.get("official_full_archive_bytes") != PROFILE["size"]
        or receipt.get("official_full_archive_md5_expected_not_verified") != PROFILE["md5"]
        or receipt.get("full_archive_downloaded") is not False
        or receipt.get("pixels_acquired") != 0
        or receipt.get("no_automatic_large_transfer") is not True):
        raise ValueError("Missing matching verified zero-image archive receipt.")
    n = receipt.get("actual_index_only_bytes_transferred")
    parts = receipt.get("parts")
    if (type(n) is not int or not 34 <= n <= 8*1024*1024
        or not isinstance(parts, list) or not 2 <= len(parts) <= 6
        or any(not isinstance(p, dict) or type(p.get("length")) is not int
               or p["length"] < 1 or type(p.get("offset")) is not int
               or p["offset"] < 0 or not isinstance(p.get("sha256"), str)
               or not re.fullmatch(r"[a-f0-9]{64}", p["sha256"])
               for p in parts)
        or sum(p["length"] for p in parts) != n):
        raise ValueError("Invalid bounded index part accounting.")
    source_ids = defaultdict(set)
    blocks = {}
    non_images = 0
    for item in records(listing):
        path = item["Path"]
        if item.get("Folder") == "+" or item.get("Attributes", "").startswith("D"):
            get_exam(path, allowed_exams=EXAMS)  # Reject traversal.
            continue
        block = item.get("Block", "")
        uncompressed = item.get("Size", "")
        if not block.isdecimal() or not uncompressed.isdecimal():
            raise ValueError("Invalid 7z block metadata.")
        block = int(block)
        state = blocks.setdefault(block, {
            "compressed_bytes": None, "member_count": 0,
            "image_count": 0, "examinations": Counter()
        })
        state["member_count"] += 1
        packed = item.get("Packed Size", "").strip()
        if packed:
            if not packed.isdecimal() or state["compressed_bytes"] is not None:
                raise ValueError("Invalid compressed block size.")
            state["compressed_bytes"] = int(packed)
        if Path(path).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            non_images += 1
            continue
        exam = get_exam(path, allowed_exams=EXAMS)
        if exam is None:
            raise ValueError("Image outside selected Galar 31–40 development cohort.")
        match = PATTERN.fullmatch(PurePosixPath(path.replace("\\", "/")).name)
        if match is None:
            raise ValueError("Unexpected source image filename.")
        index = int(match.group(1))
        if index in source_ids[exam]:
            raise ValueError("Duplicate source-frame index.")
        source_ids[exam].add(index)
        state["image_count"] += 1
        state["examinations"][exam] += 1
    if set(source_ids) != EXAMS:
        raise ValueError("One or more required development exams missing.")
    if not blocks or sorted(blocks) != list(range(len(blocks))):
        raise ValueError("Unrecognized compression block sequence.")
    if any(x["compressed_bytes"] is None or x["compressed_bytes"] < 1
           for x in blocks.values()):
        raise ValueError("Missing solid block compressed byte sizes.")
    compressed = sum(x["compressed_bytes"] for x in blocks.values())
    if compressed > PROFILE["size"]:
        raise ValueError("Compressed blocks exceed publisher file size.")

    by_exam = {}
    for e in sorted(EXAMS):
        ordered = sorted(source_ids[e])
        gap = [b-a for a,b in zip(ordered, ordered[1:])]
        if any(d < 1 or d % STRIDE[e] for d in gap):
            raise ValueError("Source indices violate the independently verified native stride.")
        ids = [b for b,x in sorted(blocks.items()) if x["examinations"][e]]
        by_exam[str(e)] = {
            "image_members": len(ordered),
            "previously_audited_annotation_rows": REFERENCE_ROWS[e],
            "source_image_count_matches_reference": len(ordered) == REFERENCE_ROWS[e],
            "native_export_stride": STRIDE[e],
            "internal_native_grid_gaps": sum(d != STRIDE[e] for d in gap),
            "missing_internal_native_grid_positions": sum(d // STRIDE[e] - 1 for d in gap),
            "required_whole_solid_blocks": ids,
            "whole_block_compressed_bytes_estimate": sum(blocks[b]["compressed_bytes"] for b in ids),
        }
    matches = all(x["source_image_count_matches_reference"] for x in by_exam.values())
    result = {
        "record_type": "galar-31-40-metadata-only-source-feasibility-v1",
        "official_file_id": PROFILE["id"],
        "official_archive_bytes": PROFILE["size"],
        "original_full_source_md5_verified": False,
        "metadata_index_only": True,
        "source_image_pixels_acquired": 0,
        "private_source_ids_disclosed": False,
        "patient_independence_verified": False,
        "complete_clinical_outcomes_verified": False,
        "index_only_bytes_transferred": n,
        "compressed_solid_block_bytes_total": compressed,
        "block_count": len(blocks),
        "non_image_member_count": non_images,
        "all_images_match_corrected_label_row_counts": matches,
        "all_internal_export_grids_contiguous": all(
            x["internal_native_grid_gaps"] == 0 for x in by_exam.values()),
        "examinations": by_exam,
        "blocks": [{
            "id": b, "compressed_bytes": x["compressed_bytes"],
            "members": x["member_count"],
            "images": x["image_count"],
            "exam_image_counts": {str(k):v for k,v in sorted(x["examinations"].items())},
        } for b,x in sorted(blocks.items())],
        "decision": "INDEX_ONLY_SOURCE_FEASIBLE" if matches else "BLOCKED_INDEX_COUNT_MISMATCH",
        "warning": (
            "Source filename indexing does not establish original device capture continuity, "
            "patient independence, exhaustive outcome labels, full source archive integrity "
            "or approval for any compressed-image-block transfer."
        ),
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--listing", required=True, type=Path)
    p.add_argument("--receipt", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.exists() or args.output.is_symlink():
        p.error("Refuse to overwrite prior audit.")
    if (args.listing.is_symlink() or not args.listing.is_file()
        or not 0 < args.listing.stat().st_size <= 256*1024*1024
        or args.receipt.is_symlink() or not args.receipt.is_file()
        or not 0 < args.receipt.stat().st_size <= 64*1024):
        p.error("Missing or oversized private index input.")
    try:
        out = audit(args.listing.read_text(encoding="utf8"),
                    json.loads(args.receipt.read_text(encoding="utf8")))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        p.error("Index source gate failed; private source identities withheld.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
    print(json.dumps({
        "decision": out["decision"], "official_file_id": out["official_file_id"],
        "examinations": len(out["examinations"]), "blocks": out["block_count"],
        "index_bytes": out["index_only_bytes_transferred"],
        "original_images_acquired": 0,
    }, sort_keys=True))
    return 0 if out["decision"] == "INDEX_ONLY_SOURCE_FEASIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
