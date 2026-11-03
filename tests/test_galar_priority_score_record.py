"""Scientific record safeguards for previously examined real CNN queue replay.

Only aggregated historical results in the public tree; private score rows,
original images, reference labels and model checkpoints are NOT in Git.
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "experiments/galar-priority-score-2026-11-03/aggregate.json"
REPORT = ROOT / "docs/GALAR_PRIORITY_SCORE_REPLAY.md"


def test_six_exam_aggregate_all_workloads_and_comparator_denominators():
    result = json.loads(AGG.read_text(encoding="utf-8"))
    expected = {"21": 1, "23": 4, "25": 14, "27": 26, "29": 122, "30": 120}
    assert result["explicit_blood_positive_reference_images_by_exam"] == expected
    assert sum(expected.values()) == result["total_explicit_blood_positive_reference_images_available"] == 287
    assert result["exam_ids_previously_inspected"] == list(expected)
    assert result["reference_images_per_exam"] == 512
    assert result["private_independent_verification"]["verified_exact_K_case_budget_method_combinations"] == 144
    assert result["private_independent_verification"]["independent_selection_implementations"] == 2
    assert result["private_independent_verification"]["passed"]
    assert set(result["workloads"]) == {"25", "51", "128", "256", "384", "512"}
    for workload, methods in result["workloads"].items():
        count = int(workload)
        assert methods["selected_images_per_exam"] == count
        assert set(methods) == {
            "selected_images_per_exam", "uniform", "score", "score_diverse", "score_bin"
        }
        for key in ("uniform", "score", "score_diverse", "score_bin"):
            record = methods[key]
            assert 0 <= record["blood_positive_reference_images_retained"] <= 287
            assert 0 <= record["macro_examination_positive_image_fraction"] <= 1
            assert (
                record["examinations_better_than_uniform"] +
                record["examinations_tied_with_uniform"] +
                record["examinations_worse_than_uniform"]
            ) == 6
            assert count >= 1 and count <= 512
        baseline = methods["uniform"]
        assert baseline["examinations_better_than_uniform"] == 0
        assert baseline["examinations_tied_with_uniform"] == 6
        assert baseline["examinations_worse_than_uniform"] == 0
    assert all(
        data["blood_positive_reference_images_retained"] == 287
        for method, data in result["workloads"]["512"].items()
        if method != "selected_images_per_exam"
    )


def test_positive_image_versus_source_run_clinical_gate():
    r = json.loads(AGG.read_text(encoding="utf-8"))
    assert r["endpoint"].startswith("Retained source-verified explicit blood=1 reference IMAGES")
    assert r["clinical_validation"] is False
    assert r["patient_independence_verified"] is False
    assert r["model_promoted"] is False
    assert r["source_positive_run_recall_measured"] is False
    assert "New locked examination-separated" in r["future_gate"]
    at51 = r["workloads"]["51"]
    assert at51["score"]["blood_positive_reference_images_retained"] == 95
    assert at51["uniform"]["blood_positive_reference_images_retained"] == 27
    assert at51["score_diverse"]["blood_positive_reference_images_retained"] == 43
    assert at51["score_bin"]["blood_positive_reference_images_retained"] == 31
    assert at51["score"]["examinations_better_than_uniform"] == 3
    assert at51["score"]["examinations_worse_than_uniform"] == 2
    assert r["workloads"]["128"]["score"]["blood_positive_reference_images_retained"] == 201
    assert r["workloads"]["384"]["score"]["blood_positive_reference_images_retained"] == 271
    assert "Case 23" in " ".join(r["limitations"])
    assert "Case 25" in " ".join(r["limitations"])


def test_no_private_frame_level_data_or_accidental_software_claims():
    raw = AGG.read_text(encoding="utf-8")
    for private in (
        '"source_index"', '"frame_index"', '"frame_id"',
        '"image_sha256"', '"pixel_sha256"', '"source_filename"',
        '"blood_label"', '"review_note"', '"model_scores"',
        '"per_frame"', '"raw_images"', '"checkpoint"',
    ):
        assert private not in raw
    report = REPORT.read_text(encoding="utf-8")
    for phrase in (
        "95", "27", "43", "31", "186.8", "9.3",
        "zero of four", "zero of fourteen",
        "previously inspected", "not",
        "not a pathology lesion detector",
    ):
        assert phrase.casefold() in report.casefold()
    assert "model_promoted" not in raw or '"model_promoted": false' in raw
    assert "private" in report.lower()
