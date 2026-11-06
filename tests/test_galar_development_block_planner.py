"""Metadata-only regression tests for Galar 31-40 incremental source planning.

No medical images, original frame IDs, private annotations, model scores,
patient metadata or network access appear in these fixtures.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import plan_galar31_40_development_blocks as planner


def official_index():
    return json.loads(
        (Path(__file__).resolve().parents[1] /
         "experiments/galar-31-40-index-20261105/aggregate.json").read_text()
    )


def test_exact_verified_index_and_reusable_plan():
    b, cases = planner.validate_index(official_index())
    assert len(b) == 18
    assert len(cases) == 10
    assert b[5]["compressed_bytes"] == 3_453_334_016
    assert cases[35]["published_image_members"] == 9_643
    assert cases[35]["previously_inspected_blood_positive_rows"] == 1_534
    assert cases[35]["previously_inspected_positive_annotation_runs"] == 29
    assert sum(c["published_image_members"] for c in cases.values()) == 381_787


def test_complete_source_36_is_one_incremental_block_if_5_retained():
    p = planner.build_plan(
        official_index(), [35,36], presumed_retained=[5],
        incremental_limit_bytes=3_500_000_000,
    )
    assert p["all_required_block_ids"] == [5,6]
    assert p["additional_block_ids"] == [6]
    assert p["additional_compressed_bytes"] == 3_430_870_954
    assert p["additional_exact_http_ranges"] == [{
        "block_id":6,
        "range_start":21_255_343_165,
        "range_end_inclusive":24_686_214_118,
        "compressed_bytes":3_430_870_954,
    }]
    assert p["positive_exam_count_from_inspected_labels"] == 2
    assert p["complete_exam_source_support"][1]["previously_inspected_blood_positive_rows"] == 209
    assert p["complete_exam_source_support"][1]["previously_inspected_positive_annotation_runs"] == 59
    assert p["decision"] == "FEASIBILITY_ONLY_GROUP_RIGHTS_AND_PRIVATE_SOURCE_GATES_PENDING"
    assert p["original_pngs_or_annotations_accessed"] is False
    assert p["authentic_patient_grouping_verified"] is False
    assert p["source_bytes_downloaded_by_planner"] == 0


def test_34_has_different_and_more_expensive_adjacent_block():
    p = planner.build_plan(official_index(), [34,35], presumed_retained=[5])
    assert p["additional_block_ids"] == [4]
    assert p["additional_compressed_bytes"] == 3_509_951_715
    assert p["additional_exact_http_ranges"] == [{
        "block_id":4,
        "range_start":14_292_057_434,
        "range_end_inclusive":17_802_009_148,
        "compressed_bytes":3_509_951_715,
    }]
    assert p["complete_exam_source_support"][0]["previously_inspected_blood_positive_rows"] == 49
    assert p["complete_exam_source_support"][0]["previously_inspected_positive_annotation_runs"] == 9


def test_both_new_positive_exams_need_only_two_new_blocks():
    p=planner.build_plan(official_index(), [34,35,36], presumed_retained=[5])
    assert p["additional_block_ids"] == [4,6]
    assert p["additional_compressed_bytes"] == 6_940_822_669
    assert p["positive_exam_count_from_inspected_labels"] == 3
    assert sum(s["previously_inspected_positive_annotation_runs"] for s in p["complete_exam_source_support"]) == 97


def test_metadata_plan_does_not_treat_partial_neighbors_as_complete():
    p=planner.build_plan(official_index(), [35], presumed_retained=[5])
    assert p["all_required_block_ids"] == [5]
    assert p["additional_block_ids"] == []
    assert p["requested_complete_published_export_exams"] == [35]
    assert p["positive_exam_count_from_inspected_labels"] == 1
    # Partial image members from studies 34 and 36 in block 5 do not count
    # as full original exported source examinations.
    assert len(p["complete_exam_source_support"]) == 1


def test_zero_retained_claim_requires_real_source_block_cost():
    p=planner.build_plan(official_index(), [35,36], presumed_retained=[])
    assert p["additional_block_ids"] == [5,6]
    assert p["additional_compressed_bytes"] == 6_884_204_970


def test_strict_limit_blocks_acquisition_and_never_overrides_budget():
    p=planner.build_plan(official_index(), [35,36],
                         presumed_retained=[5],incremental_limit_bytes=3_400_000_000)
    assert p["decision"] == "BLOCKED_BY_INCREMENTAL_BYTE_BUDGET"
    assert p["fits_incremental_limit"] is False
    assert p["source_bytes_downloaded_by_planner"] == 0


@pytest.mark.parametrize("bad_targets,bad_retained,bad_budget",[
    ([],[],None),([11],[],None),([61],[],None),([35,35],[],None),
    (["35"],[],None),([35],[18],None),([35],[-1],None),
    ([35],[5,5],None),([35],[True],None),([35],[],True),
    ([35],[],-1)
])
def test_never_allow_unauthorized_examinations_or_bad_limits(
    bad_targets,bad_retained,bad_budget
):
    with pytest.raises(planner.InvalidSourcePlan):
        planner.build_plan(official_index(),bad_targets,
                           presumed_retained=bad_retained,
                           incremental_limit_bytes=bad_budget)


@pytest.mark.parametrize("modify",[
    lambda x:x["official_source"].update(file_id=44725302),
    lambda x:x["official_source"].update(declared_archive_bytes=10),
    lambda x:x["verification"].update(full_archive_md5_verified=True),
    lambda x:x["verification"].update(original_image_pixels_acquired=1),
    lambda x:x["verification"].update(header_crc_verified=False),
    lambda x:x["blocks"][5].update(compressed_bytes=3_400_000_000),
    lambda x:x["blocks"][6].update(block_id=99),
    lambda x:x["blocks"][6]["image_members_by_exam"].update({"61":1}),
    lambda x:x["blocks"][5]["image_members_by_exam"].update({"36":3000}),
    lambda x:x["studies"]["36"].update(required_block_ids_for_complete_export=[5]),
    lambda x:x["studies"]["34"].update(previous_label_positive_rows=999999),
    lambda x:x["studies"]["35"].update(native_source_stride=1),
    lambda x:x["studies"].update({"61":{"image_members":1}})
])
def test_tampered_source_index_and_outcome_support_fail_closed(modify):
    raw=official_index()
    modify(raw)
    with pytest.raises(planner.InvalidSourcePlan):
        planner.validate_index(raw)


def test_exact_retained_source_byte_boundaries_do_not_overlap():
    blocks,_=planner.validate_index(official_index())
    assert blocks[4]["range_end_inclusive"]+1==blocks[5]["range_start"]
    assert blocks[5]["range_end_inclusive"]+1==blocks[6]["range_start"]
    assert blocks[0]["range_start"]==32
    assert blocks[17]["range_end_inclusive"]+1+3_629_193-32 ==69_219_317_963
