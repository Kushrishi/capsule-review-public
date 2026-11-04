"""Do not silently turn exploratory appearance stress tests into validation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/galar-photo-robustness-20261104/aggregate.json"


def test_three_exam_source_and_privacy_boundary():
    x = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert x["schema_version"] == 1
    assert x["clinical_validity"] is False
    assert x["independent_evaluation"] is False
    assert x["model_promoted"] is False
    assert x["locked_galar_11_20_not_reused"] is True
    assert x["authors_reserved_61_80_unopened"] is True
    assert x["no_original_images_labels_individual_scores_or_model_weights_published"] is True
    assert x["fitting_examinations"] == list(range(1, 9))
    assert x["previously_inspected_examinations"] == [23, 25, 27]
    assert x["total_evaluation_reference_images"] == 1536
    assert x["verified_original_image_hashes"] == 1536
    assert x["original_model_weights_sha256"] == (
        "f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3"
    )
    assert x["unpromoted_candidate_weights_sha256"] == (
        "16dff266f242d3bce7a510a0f13f158500776bd2f9ea8626809866ce337cacdb"
    )


def test_original_model_replay_and_case_specific_deterioration_preserved():
    x = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = x["per_examination"]
    assert set(rows) == {"23", "25", "27"}
    assert [rows[str(e)]["positive_annotated_images"] for e in (23, 25, 27)] == [4, 14, 26]
    original = [rows[str(e)]["original_model"]["roc_auc"] for e in (23, 25, 27)]
    candidate = [rows[str(e)]["color_augmented_candidate"]["roc_auc"] for e in (23, 25, 27)]
    assert all(abs(a-b) < 0.00001 for a, b in zip(original, (.202756, .304504, .969848)))
    assert candidate[0] > original[0] and candidate[1] > original[1]
    assert candidate[2] < original[2]  # Negative transfer must NOT be omitted.
    assert [rows[str(e)]["original_model"]["top_51_positive_images"] for e in (23, 25, 27)] == [0, 0, 22]
    assert [rows[str(e)]["color_augmented_candidate"]["top_51_positive_images"] for e in (23, 25, 27)] == [1, 1, 21]
    for exam, record in rows.items():
        assert record["images"] == 512
        assert record["original_score_replay_max_abs_difference"] < 0.000003
        assert set(record["repeat_inference"]) == {
            "original", "brightness_075", "brightness_125",
            "contrast_080", "saturation_070", "saturation_130",
        }
        for name, value in record["repeat_inference"].items():
            assert 0 <= value["roc_auc"] <= 1
            assert 0 <= value["top_51_positive_images"] <= min(
                51, record["positive_annotated_images"]
            )
            assert -1 <= value["rank_spearman_to_original"] <= 1
            assert 0 <= value["top_51_changed_positions"] <= 51


def test_examination_27_color_stress_failure_remains_visible():
    x = json.loads(SOURCE.read_text(encoding="utf-8"))["per_examination"]["27"]
    base = x["repeat_inference"]["original"]
    lower = x["repeat_inference"]["saturation_070"]
    assert base["top_51_positive_images"] == 22
    assert lower["top_51_positive_images"] == 7
    assert lower["roc_auc"] < base["roc_auc"] - 0.20
    assert lower["top_51_changed_positions"] == 39


def test_no_per_frame_records_in_public_aggregate():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = data["per_examination"]
    for record in rows.values():
        assert "frames" not in record and "source_image_sha256" not in record
        assert "predictions" not in record and "source_indices" not in record
        assert "pixel_values" not in record
    assert data["candidate_training"]["trained_on_held_out_examinations"] is False
