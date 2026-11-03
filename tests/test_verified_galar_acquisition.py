"""Reconcile the new real-image acquisition records with frozen training-only planning.

No medical images or private identities are accessed in repository CI.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "experiments/galar-21-30-source-index"
PLAN = ROOT / "experiments/galar-21-30-selection/aggregate.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_new_source_receipts_match_frozen_source_layout_and_selection():
    actual = read_json(RECEIPTS / "verified-acquisition-summary.json")
    layout = read_json(RECEIPTS / "layout.json")
    original = read_json(PLAN)
    assert actual["record_type"] == "galar-fitting-image-acquisition-verification-v1"
    assert actual["original_archive_bytes"] == layout["archive_bytes"] == 31_989_399_751
    assert actual["corrected_label_zip_sha256"] == original["official_corrected_labels_sha256"]
    assert actual["private_selection_sha256"] == original["private_request_sha256"]
    assert actual["original_archive_md5_expected_not_verified"] == "dedad47ee55c83a4b991ca60d26fb6ee"
    assert actual["future_test_untouched"].startswith("Exams 11–20")
    assert actual["role"].startswith("fitting-candidate")

    count = positive = source_bytes = compressed_bytes = 0
    for exam in (21, 23):
        entry = actual[f"exam_{exam}"]
        frozen = original["per_examination"][str(exam)]
        block = layout["blocks"][entry["source_block_id"]]
        assert exam in (21, 23)
        assert entry["verified_png_images"] == frozen["unique_requested_images"]
        assert entry["enriched_fit_candidates"] == frozen["enriched_training_candidates"] == 512
        assert entry["uniform_reference_candidates"] == frozen["label_blind_reference_candidates"] == 512
        assert entry["sampled_frame_overlap"] == frozen["dual_purpose_overlap"]
        assert entry["verified_png_images"] == 1024 - entry["sampled_frame_overlap"]
        assert entry["explicit_blood_positive_images"] == frozen["enriched_positive_candidates"]
        assert block["examinations"][str(exam)] == layout["image_members_by_exam"][str(exam)]
        assert entry["source_compressed_bytes_transferred"] == block["compressed_bytes"]
        assert entry["source_block_offset"] == 32 + sum(
            previous["compressed_bytes"] for previous in layout["blocks"][:entry["source_block_id"]]
        )
        for field in ("source_block_sha256", "inner_source_zip_sha256", "private_manifest_sha256",
                      "retained_github_artifact_outer_zip_sha256"):
            digest = entry[field]
            assert len(digest) == 64
            assert all(char in "0123456789abcdef" for char in digest)
        assert entry["source_ci_run"].startswith("https://github.com/Kushrishi/capsule-review/actions/runs/")
        count += entry["verified_png_images"]
        positive += entry["explicit_blood_positive_images"]
        source_bytes += entry["saved_png_bytes"]
        compressed_bytes += entry["source_compressed_bytes_transferred"]
    combined = actual["combined"]
    assert combined["new_examinations"] == 2
    assert combined["unique_png_images"] == count == 1994
    assert combined["explicit_blood_positive_images"] == positive == 148
    assert combined["total_saved_png_bytes"] == source_bytes == 616_688_367
    assert combined["original_source_compressed_bytes_transferred"] == compressed_bytes == 6_950_241_873
    assert combined["unique_png_images"] < original["overall"]["unique_frames_requested"] == 8075


def test_only_nonidentifying_receipts_present_in_repository():
    target = RECEIPTS
    actual = read_json(target / "verified-acquisition-summary.json")
    assert "private_storage" in actual
    assert not any(path.suffix.lower() in {".png", ".jpg", ".zip", ".7z", ".pt", ".csv"}
                   for path in target.rglob("*") if path.is_file())
    for exam in (21, 23):
        entry = actual[f"exam_{exam}"]
        assert "filename" not in entry
        assert "frame" not in entry
        assert "blood" not in entry
        # aggregate blood-positive counts are permitted, but no per-frame label records
        assert isinstance(entry["explicit_blood_positive_images"], int)
