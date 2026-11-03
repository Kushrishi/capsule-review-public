"""Regression checks for the complete non-identifying Galar23 original-PNG experiment."""
import json
from pathlib import Path

SUMMARY = (Path(__file__).resolve().parents[1] / "experiments"
           / "galar23-pixel-density-2026-11-02" / "summary.json")


def data():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_original_source_provenance_and_no_clinical_claims():
    record = data()
    assert record["source_exam"] == 23
    assert record["frozen_protocol_git_blob_sha1"] == "1eb7c7e6ee9578800de2c15bcfec9ba520a63e97"
    assert record["source_corrected_labels_zip_sha256"] == "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
    assert record["source_original_7z_file_id"] == 45258019
    assert record["source_original_7z_block_id"] == 1
    assert record["source_original_block_sha256"] == "b5086f018b7e88c57db7562af624c468796a7b1e812101d07236c184131b08f6"
    assert record["source_original_block_compressed_bytes"] == 3475743781
    assert record["original_pngs_verified"] == 4608
    assert record["original_pngs_verified_bytes"] == 1376046128
    assert record["original_annotation_rows"] == 11785
    assert record["original_blood_positive_annotation_runs"] == 28
    assert record["full_private_aggregate_sha256"] == "648423b1735f1e1a265946805a9ad7386a9ad0fdc2104641cc0dcb4e93fe10de"
    assert record["no_new_model_fit"] is True
    assert record["no_reserved_studies_accessed"] is True
    assert record["clinical_validity"] is False
    assert record["full_publisher_archive_md5_verified"] is False
    assert record["extra_pngs_not_persisted_as_a_second_source_archive"] is True


def test_full_predeclared_method_budget_matrix_present():
    variants = data()["methods"]
    assert set(variants) == {"512", "4096"}
    for size, result in variants.items():
        assert result["candidate_images"] == int(size)
        assert set(result["methods_at_fixed_workload"]) == {"51", "128", "256", "512"}
        for budget, methods in result["methods_at_fixed_workload"].items():
            assert set(methods) == {"uniform", "global_red", "bin_stratified_red"}
            for values in methods.values():
                assert values["reviewed_frames"] == int(budget)
                assert 0 <= values["distinct_source_annotation_runs_hit"] <= result["source_annotation_positive_runs_represented"]
                assert 0 <= values["blood_label_positive_image_hits"] <= result["candidate_positive_labelled_images"]
                assert values["distinct_source_annotation_runs_hit"] <= values["blood_label_positive_image_hits"]
                assert 0 <= values["source_annotation_row_nearest_review_max_gap"] < 11785


def test_prior_512_reference_is_exactly_replayed():
    original = data()["methods"]["512"]
    assert original["candidate_positive_labelled_images"] == 4
    assert original["source_annotation_positive_runs_represented"] == 4
    assert abs(original["original_red_roc_auc"] - 0.4173228346456693) < 1e-12
    assert original["methods_at_fixed_workload"]["51"]["global_red"]["blood_label_positive_image_hits"] == 0
    assert original["methods_at_fixed_workload"]["51"]["bin_stratified_red"]["distinct_source_annotation_runs_hit"] == 0


def test_preserved_full_density_negative_result_and_no_selected_winner():
    dense = data()["methods"]["4096"]
    assert dense["candidate_positive_labelled_images"] == 48
    assert dense["source_annotation_positive_runs_represented"] == 21
    assert abs(dense["original_red_roc_auc"] - 0.36380620059288155) < 1e-12
    assert all(v["distinct_source_annotation_runs_hit"] == 0 for v in dense["methods_at_fixed_workload"]["51"].values())
    for budget, expected in {
        "128": {"uniform": 2, "global_red": 0, "bin_stratified_red": 0},
        "256": {"uniform": 4, "global_red": 0, "bin_stratified_red": 1},
        "512": {"uniform": 3, "global_red": 0, "bin_stratified_red": 6}
    }.items():
        actual = dense["methods_at_fixed_workload"][budget]
        assert {method: v["distinct_source_annotation_runs_hit"] for method, v in actual.items()} == expected


def test_public_record_is_not_per_frame_private_data():
    text = SUMMARY.read_text(encoding="utf-8")
    for sensitive in ('"source_image_sha256"', '"pixel_sha256"', '"source_frame_ids"',
                      '"individual_predictions"', '"model_weights"', '"blood_labels"'):
        assert sensitive not in text
    assert "private_original_image_and_score_fingerprint_sha256" not in text
