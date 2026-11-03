"""Synthetic-only full-source annotation-run and saved-score evaluation gate.

No corrected Galar source label ZIP, patient images or individual research scores
are committed to Git. Every fixture is generated during testing.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from scripts import evaluate_galar_source_run_queues as gate


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def zip_file(path, members):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for filename, contents in members.items():
            zipped.writestr(filename, contents)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_sources(tmp_path, monkeypatch):
    # 600 original annotation rows; subset of 512 imported frames.
    # Two genuine *annotation stretches*, not six separate lesions.
    labels = [
        {"frame": str(i * 5), "blood": "1" if i in (15, 16, 17, 400, 401, 402) else "0"}
        for i in range(600)
    ]
    corrected = tmp_path / "synthetic-corrected.zip"
    corrected_sha = zip_file(corrected, {
        "21.csv": csv_bytes(labels),
        "23.csv": csv_bytes(labels),
        "11.csv": b"RESERVED CASE - NEVER PARSE THIS",
        "61.csv": b"RESERVED AUTHORS HOLDOUT - NEVER PARSE THIS",
    })
    monkeypatch.setattr(gate, "SOURCE_SHA256", corrected_sha)
    monkeypatch.setattr(gate, "EXAMS", (21, 23))
    monkeypatch.setattr(gate, "SOURCE_RUNS", {21: 2, 23: 2})
    monkeypatch.setattr(gate, "REACHABLE_RUNS", {21: 2, 23: 2})
    monkeypatch.setattr(gate, "POSITIVE_REFERENCE", {21: 6, 23: 6})
    return corrected, labels


def fake_score_zip(path, member, exam, labels, include_reference=True):
    rows = []
    for i, source_row in enumerate(labels[:512]):
        row = {
            "exam": str(exam), "frame": source_row["frame"],
            "blood": source_row["blood"], "source_image_sha256": f"{i:064x}",
            "cnn_score": str((511 - i) / 511),
            "original_checkpoint": str((511 - i) / 511),
        }
        if include_reference:
            row["reference_uniform"] = "1"
        rows.append(row)
    member_contents = csv_bytes(rows)
    archive_sha = zip_file(path, {member: member_contents})
    return {
        "sha": archive_sha, "member": member,
        "member_sha": hashlib.sha256(member_contents).hexdigest(),
        "expected_rows": len(rows), "exams": (exam,),
        "image_sha": "source_image_sha256",
        "model_score": "cnn_score" if include_reference else "original_checkpoint",
        "has_reference_flag": include_reference,
    }


def loaded_fixture(tmp_path, monkeypatch):
    labels_zip, labels = synthetic_sources(tmp_path, monkeypatch)
    frozen_zip = tmp_path / "synthetic-frozen.zip"
    appearance_zip = tmp_path / "synthetic-appearance.zip"
    specs = {
        "frozen": fake_score_zip(frozen_zip, "private/source-scores.csv", 21, labels),
        "appearance": fake_score_zip(
            appearance_zip, "PRIVATE/private-per-image-features.csv", 23,
            labels, include_reference=False,
        ),
    }
    monkeypatch.setattr(gate, "SCORE_SOURCES", specs)
    sources = gate.load_sources(labels_zip)
    references = gate.load_scores(frozen_zip, appearance_zip, sources)
    return labels_zip, frozen_zip, appearance_zip, sources, references


def test_original_annotation_stretches_not_fake_sample_adjacency(tmp_path, monkeypatch):
    _, _, _, sources, refs = loaded_fixture(tmp_path, monkeypatch)
    assert set(sources) == {21, 23}
    assert [len(sources[e]["strata"]) for e in (21, 23)] == [2, 2]
    assert sources[21]["strata"] == ["1-5", "1-5"]
    assert len(sources[21]["runs"]) == 6
    assert len(refs[21]) == 512
    assert refs[21][15]["label"] == "1"
    assert refs[21][17]["label"] == "1"
    assert refs[21][400]["label"] == "1"
    assert refs[21][402]["label"] == "1"
    rec = gate.evaluate_case(refs[21], sources[21], workloads=(51, 128, 512))
    assert rec["full_source_positive_annotation_runs"] == 2
    assert rec["source_runs_reachable_in_saved_reference"] == 2
    assert rec["reference_positive_image_count"] == 6
    assert rec["source_run_length_strata"] == {"1-5": 2, "6-25": 0, "26+": 0}
    assert set(rec["budgets"]) == {"51", "128", "512"}
    for k, block in rec["budgets"].items():
        assert block["selected_reference_images"] == int(k)
        assert set(block["methods"]) == set(gate.METHODS)
        for result in block["methods"].values():
            assert result["distinct_full_source_positive_annotation_runs_hit"] <= 2
            assert result["positive_reference_images_hit"] <= 6
            assert sum(result["source_run_strata_hit"].values()) == result[
                "distinct_full_source_positive_annotation_runs_hit"
            ]
    for method in gate.METHODS:
        data = rec["budgets"]["512"]["methods"][method]
        assert data["distinct_full_source_positive_annotation_runs_hit"] == 2
        assert data["positive_reference_images_hit"] == 6


def test_mismatched_source_image_label_and_zip_hash_fail_closed(tmp_path, monkeypatch):
    labels_zip, frozen, appearance, sources, _ = loaded_fixture(tmp_path, monkeypatch)
    frozen.write_bytes(frozen.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        gate.load_scores(frozen, appearance, sources)
    labels_zip.write_bytes(labels_zip.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        gate.load_sources(labels_zip)


def test_original_annotation_source_gaps_create_distinct_runs():
    rows = [
        {"frame": "0", "blood": "1"},
        {"frame": "5", "blood": "1"},
        {"frame": "15", "blood": "1"},
        {"frame": "20", "blood": "0"},
    ]
    # The full-source reader requires at least 512 rows; test the boundary
    # using a full permitted series with one deliberately missing position.
    full = [
        {"frame": str(i * 5), "blood": "1" if i in (5, 6, 8, 9) else "0"}
        for i in range(600)
    ]
    full.pop(7)
    runs, categories, _ = gate.source_runs(full)
    assert len(categories) == 2
    assert len(set(runs.values())) == 2
    assert runs[25] != runs[40]
    assert 35 not in runs
    with pytest.raises(ValueError):
        gate.source_runs([{"frame": "0", "blood": "1"}] * 512)


def test_previous_cnn_uniform_sanity_reconciliation_on_generated_counts(tmp_path, monkeypatch):
    _, _, _, sources, refs = loaded_fixture(tmp_path, monkeypatch)
    exams = {e: gate.evaluate_case(refs[e], sources[e]) for e in gate.EXAMS}
    prior = {"source_corrected_release_sha256": gate.SOURCE_SHA256,
             "reference_per_exam": 512, "examinations": {
                 "9": {}, "10": {},
             }}
    for exam, case in exams.items():
        source = {
            "source_blood_annotation_runs": case["full_source_positive_annotation_runs"],
            "reference_run_ceiling_hits": case["source_runs_reachable_in_saved_reference"],
            "reference_blood_positive": case["reference_positive_image_count"],
            "budgets": {},
        }
        for percent, k in ((5, 25), (10, 51), (25, 128), (50, 256), (75, 384), (100, 512)):
            record = case["budgets"][str(k)]["methods"]
            source["budgets"][str(percent)] = {"methods": {
                "original_checkpoint": {
                    "source_annotation_runs_hit": record["score"]["distinct_full_source_positive_annotation_runs_hit"],
                    "blood_positive_reference_images_found": record["score"]["positive_reference_images_hit"],
                },
                "uniform": {
                    "source_annotation_runs_hit": record["uniform"]["distinct_full_source_positive_annotation_runs_hit"],
                    "blood_positive_reference_images_found": record["uniform"]["positive_reference_images_hit"],
                },
            }}
        prior["examinations"][str(exam)] = source
    summary = gate.audited_summary(exams, prior)
    assert not summary["new_unseen_evaluation"]
    assert summary["raw_labels_images_and_per_frame_scores_committed"] is False
    assert not summary["patient_independence_verified"]
    assert not summary["model_promoted"]
    assert set(summary["summary_by_budget"]) == set(str(x) for x in gate.WORKLOADS)
    assert set(summary["method_names"]) == set(gate.METHODS)
    assert sum(summary["summary_by_budget"]["512"][method]["unique_runs_hit_across_exams"]
               for method in gate.METHODS) == 16
    prior["examinations"]["21"]["budgets"]["10"]["methods"]["uniform"]["source_annotation_runs_hit"] = 999
    with pytest.raises(ValueError, match="do not replay"):
        gate.audited_summary(exams, prior)


def test_production_pins_are_exact_and_protected_cases_excluded():
    assert gate.SOURCE_SHA256 == "2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f"
    assert gate.PRIOR_SHA256 == "8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07"
    assert gate.EXAMS == (21, 23, 25, 27, 29, 30)
    assert not set(gate.EXAMS) & set(range(11, 21))
    assert not set(gate.EXAMS) & set(range(61, 81))
    assert set(gate.METHODS) == {"score", "score_diverse", "score_bin", "uniform"}
    assert gate.WORKLOADS == (25, 51, 128, 256, 384, 512)
