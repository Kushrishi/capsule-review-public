"""Synthetic video/frame IDs only. No original medical material."""
from __future__ import annotations

import pytest

from scripts.audit_kvasir_official_splits import audit


def write(tmp_path, name, rows):
    path = tmp_path / name
    path.write_text("filename,label\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_video_leakage_without_frame_overlap_and_multiple_labels(tmp_path):
    a = write(tmp_path, "split_0.csv", [
        "vidA_0001.jpg,Blood", "vidA_0002.jpg,Normal", "vidB_0001.jpg,Ulcer",
    ])
    b = write(tmp_path, "split_1.csv", [
        "vidA_0003.jpg,Normal", "vidC_0009.jpg,Blood", "vidC_0009.jpg,Ulcer",
    ])
    out = audit(a, b)
    assert out["combined_rows"] == 6
    assert out["combined_unique_video_ids"] == 3
    assert out["shared_video_ids_across_files"] == 1
    assert out["shared_source_frame_ids_across_files"] == 0
    assert out["inputs"][1]["extra_rows_for_already_seen_frame_ids"] == 1
    assert out["category_distinct_video_counts"]["Blood"] == 2
    assert out["category_row_counts"]["Blood"] == 2
    assert out["eligible_for_patient_independent_study"] is False
    assert out["eligible_for_complete_event_recall"] is False
    assert all(token not in str(out) for token in ("vidA", "vidB", "vidC", "0009"))


def test_exact_frame_overlap_across_files_is_counted(tmp_path):
    a = write(tmp_path, "a.csv", ["vidA_001.jpg,Normal"])
    b = write(tmp_path, "b.csv", ["vidA_001.jpg,Blood"])
    out = audit(a, b)
    assert out["shared_source_frame_ids_across_files"] == 1
    assert out["combined_unique_source_frame_ids"] == 1


@pytest.mark.parametrize("bad", [
    "vidA_001.jpg,Blood\nvidA_001.jpg,Blood",
    "../sensitive_001.jpg,Blood",
    "vidA_001.jpg,Blood,leak",
    "vidA_001.jpg,",
])
def test_invalid_rows_fail_closed_without_identifier_output(tmp_path, bad):
    a = write(tmp_path, "a.csv", [bad])
    b = write(tmp_path, "b.csv", ["vidB_002.jpg,Normal"])
    with pytest.raises(ValueError):
        audit(a, b)


def test_identical_file_and_empty_inputs_fail_closed(tmp_path):
    p = write(tmp_path, "a.csv", ["vidA_0001.jpg,Normal"])
    with pytest.raises(ValueError):
        audit(p, p)
    empty = write(tmp_path, "b.csv", [])
    with pytest.raises(ValueError):
        audit(p, empty)


def test_output_shas_are_exact_input_file_digests(tmp_path):
    from hashlib import sha256
    a = write(tmp_path, "a.csv", ["vidA_1.jpg,Blood"])
    b = write(tmp_path, "b.csv", ["vidB_2.jpg,Normal"])
    out = audit(a, b)
    assert out["inputs"][0]["sha256"] == sha256(a.read_bytes()).hexdigest()
    assert out["inputs"][1]["sha256"] == sha256(b.read_bytes()).hexdigest()
