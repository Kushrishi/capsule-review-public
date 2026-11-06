"""Metadata-only, incremental Galar 31-40 source-block acquisition planner.

No source image pixels, individual labels, model scores, patients, image IDs,
or network requests are handled here. The public verified archive index is the
only input. This is an estimate for already-inspected DEVELOPMENT exams, NOT
approval to download original medical data or evidence of patient independence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

SOURCE_FILE_ID = 44755700
SOURCE_ARCHIVE_BYTES = 69_219_317_963
INDEX_TRANSFER_BYTES = 3_629_193
REQUIRED_BLOCKS = 18
EXAMS = frozenset(range(31, 41))
KNOWN_BLOCK_5_BYTES = 3_453_334_016
KNOWN_SOURCE_IMAGES = 381_787
PNG_DATA_START = 32


class InvalidSourcePlan(ValueError):
    """Untrusted metadata, unsafe cohort scope or inconsistent source layout."""


def validate_index(data: dict) -> tuple[dict[int, dict], dict[int, dict]]:
    """Reject an altered index instead of planning unsafe HTTP ranges."""
    if not isinstance(data, dict):
        raise InvalidSourcePlan("Published source-index aggregate must be an object.")
    source = data.get("official_source")
    receipt = data.get("verification")
    if (not isinstance(source, dict) or not isinstance(receipt, dict)
            or source.get("file_id") != SOURCE_FILE_ID
            or source.get("declared_archive_bytes") != SOURCE_ARCHIVE_BYTES
            or source.get("expected_publisher_md5_unverified")
            != "3bd4f9c9132e32d1a15d1ead5d96d0e2"
            or receipt.get("index_only_transferred_bytes") != INDEX_TRANSFER_BYTES
            or receipt.get("header_crc_verified") is not True
            or receipt.get("publisher_metadata_exactly_matched") is not True
            or receipt.get("exact_http_206_range_required") is not True
            or receipt.get("original_image_pixels_acquired") != 0
            or receipt.get("full_archive_md5_verified") is not False
            or receipt.get("source_image_counts_match_previous_corrected_label_rows") is not True
            or receipt.get("all_internal_native_export_grids_contiguous") is not True):
        raise InvalidSourcePlan("Original official publisher and index receipt mismatch.")

    block_list = data.get("blocks")
    study_map = data.get("studies")
    if (not isinstance(block_list, list) or len(block_list) != REQUIRED_BLOCKS
            or not isinstance(study_map, dict)
            or set(study_map) != {str(e) for e in EXAMS}):
        raise InvalidSourcePlan("Expected exactly 18 blocks and source exams 31-40.")
    blocks = {}
    offset = PNG_DATA_START
    image_total_by_exam = {e: 0 for e in EXAMS}
    for idx, block in enumerate(block_list):
        if (not isinstance(block, dict) or type(block.get("block_id")) is not int
                or block["block_id"] != idx
                or type(block.get("compressed_bytes")) is not int
                or block["compressed_bytes"] < 1
                or not isinstance(block.get("image_members_by_exam"), dict)
                or not block["image_members_by_exam"]):
            raise InvalidSourcePlan("Invalid or reordered original 7z solid block.")
        members = block["image_members_by_exam"]
        if any(not str(k).isdecimal() or int(k) not in EXAMS
               or type(v) is not int or v < 1 for k, v in members.items()):
            raise InvalidSourcePlan("Unexpected study or image membership in block.")
        for key, count in members.items():
            image_total_by_exam[int(key)] += count
        bytes_ = block["compressed_bytes"]
        blocks[idx] = {
            "block_id": idx,
            "compressed_bytes": bytes_,
            "range_start": offset,
            "range_end_inclusive": offset + bytes_ - 1,
            "examinations_with_members": {int(k): v for k, v in members.items()},
        }
        offset += bytes_
    if (offset + INDEX_TRANSFER_BYTES - PNG_DATA_START != SOURCE_ARCHIVE_BYTES
            or blocks[5]["compressed_bytes"] != KNOWN_BLOCK_5_BYTES):
        raise InvalidSourcePlan("Source compressed blocks/verified header fail size reconciliation.")

    studies = {}
    for key, raw in study_map.items():
        e = int(key)
        if not isinstance(raw, dict):
            raise InvalidSourcePlan("Study metadata is malformed.")
        expected_blocks = sorted(
            i for i, block in blocks.items() if e in block["examinations_with_members"]
        )
        n = raw.get("image_members")
        pos = raw.get("previous_label_positive_rows")
        runs = raw.get("previous_label_positive_runs")
        stride = raw.get("native_source_stride")
        declared = raw.get("required_block_ids_for_complete_export")
        if (type(n) is not int or n < 1
                or type(pos) is not int or not 0 <= pos <= n
                or type(runs) is not int or not 0 <= runs <= pos
                or (pos == 0) != (runs == 0)
                or stride != (5 if e <= 38 else 1)
                or raw.get("internal_native_grid_gaps") != 0
                or declared != expected_blocks
                or n != image_total_by_exam[e]
                or raw.get("compressed_bytes_if_full_solid_blocks_required")
                   != sum(blocks[i]["compressed_bytes"] for i in expected_blocks)):
            raise InvalidSourcePlan("Study annotation support or original source membership mismatch.")
        studies[e] = {
            "examination": e,
            "published_image_members": n,
            "previously_inspected_blood_positive_rows": pos,
            "previously_inspected_positive_annotation_runs": runs,
            "positive_image_fraction": round(pos / n, 8),
            "required_compressed_blocks": expected_blocks,
            "native_export_stride_not_elapsed_time": stride,
        }
    if sum(s["published_image_members"] for s in studies.values()) != KNOWN_SOURCE_IMAGES:
        raise InvalidSourcePlan("Full source image member total no longer matches verified index.")
    if (blocks[4]["range_end_inclusive"] != blocks[5]["range_start"] - 1
            or blocks[6]["range_start"] != blocks[5]["range_end_inclusive"] + 1
            or blocks[5]["examinations_with_members"] != {34:2876,35:9643,36:3098}):
        raise InvalidSourcePlan("Previously verified block 5 and adjacent original-image membership changed.")
    return blocks, studies


def build_plan(data: dict, targets: Iterable[int], *, presumed_retained: Iterable[int] = (),
               incremental_limit_bytes: int | None = None) -> dict:
    """Estimate exact *incremental* compressed bytes; never authorize acquisition."""
    blocks, studies = validate_index(data)
    selected = list(targets)
    retained = list(presumed_retained)
    if (not selected or any(type(x) is not int or x not in EXAMS for x in selected)
            or len(set(selected)) != len(selected)):
        raise InvalidSourcePlan("Requested complete exams must be unique and restricted to 31-40.")
    if (any(type(x) is not int or x not in blocks for x in retained)
            or len(set(retained)) != len(retained)):
        raise InvalidSourcePlan("Presumed retained block IDs must be unique and within the official archive.")
    if (incremental_limit_bytes is not None
            and (type(incremental_limit_bytes) is not int or incremental_limit_bytes < 0)):
        raise InvalidSourcePlan("Maximum new transfer bytes must be a nonnegative integer.")
    required = sorted({b for e in selected for b in studies[e]["required_compressed_blocks"]})
    new_blocks = [b for b in required if b not in retained]
    new_bytes = sum(blocks[b]["compressed_bytes"] for b in new_blocks)
    budget_ok = incremental_limit_bytes is None or new_bytes <= incremental_limit_bytes
    return {
        "record_type": "galar-31-40-incremental-complete-exam-development-source-plan-v1",
        "official_file_id": SOURCE_FILE_ID,
        "official_source_full_md5_verified": False,
        "index_only_plan": True,
        "requested_complete_published_export_exams": sorted(selected),
        "published_source_complete_membership_is_not_device_exposure_completeness": True,
        "presumed_retained_block_ids_NOT_reverified_in_this_plan": sorted(retained),
        "all_required_block_ids": required,
        "additional_block_ids": new_blocks,
        "additional_compressed_bytes": new_bytes,
        "estimated_additional_gib": round(new_bytes / (1024**3), 3),
        "incremental_limit_bytes": incremental_limit_bytes,
        "fits_incremental_limit": budget_ok,
        "additional_exact_http_ranges": [
            {k: blocks[b][k] for k in
             ("block_id","range_start","range_end_inclusive","compressed_bytes")}
            for b in new_blocks
        ],
        "complete_exam_source_support": [studies[e] for e in sorted(selected)],
        "positive_exam_count_from_inspected_labels": sum(
            studies[e]["previously_inspected_blood_positive_rows"] > 0 for e in selected
        ),
        "source_bytes_downloaded_by_planner": 0,
        "original_pngs_or_annotations_accessed": False,
        "authentic_patient_grouping_verified": False,
        "device_site_metadata_for_all_selected_exams_verified": False,
        "independent_clinical_validation_supported": False,
        "development_results_are_already_outcome_inspected": True,
        "decision": ("BLOCKED_BY_INCREMENTAL_BYTE_BUDGET" if not budget_ok
                     else "FEASIBILITY_ONLY_GROUP_RIGHTS_AND_PRIVATE_SOURCE_GATES_PENDING"),
        "required_before_transfer": [
            "independently reverify retained block 5 original-byte SHA256 and all part checksums",
            "authenticate source dataset permissions and private durable storage capacity",
            "qualify examination-level metadata; do not assert unique patient groups",
            "authorize each additional exact source-block byte range separately",
            "verify every new downloaded block HTTP 206, byte count, SHA256 and original PNG integrity",
            "join all completed source images against previously inspected official labels privately",
            "freeze examination-separated DEVELOPMENT design before any candidate model fitting",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=(
        Path(__file__).resolve().parents[1] /
        "experiments/galar-31-40-index-20261105/aggregate.json"
    ))
    ap.add_argument("--exam", type=int, action="append", required=True)
    ap.add_argument("--presumed-retained-block", type=int, action="append", default=[])
    ap.add_argument("--max-additional-bytes", type=int)
    args = ap.parse_args()
    if (args.index.is_symlink() or not args.index.is_file()
            or not 0 < args.index.stat().st_size < 2_000_000):
        ap.error("Expected existing small non-symlink verified source-index aggregate.")
    try:
        report = build_plan(
            json.loads(args.index.read_text(encoding="utf8")),
            args.exam, presumed_retained=args.presumed_retained_block,
            incremental_limit_bytes=args.max_additional_bytes,
        )
    except (ValueError, KeyError, TypeError, UnicodeError) as e:
        ap.error(str(e))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if report["decision"] == "BLOCKED_BY_INCREMENTAL_BYTE_BUDGET" else 0


if __name__ == "__main__":
    raise SystemExit(main())
