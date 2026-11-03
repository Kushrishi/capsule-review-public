"""Use synthetic PNGs to test private original-score reconstruction/import.

The medical images, per-frame originals and any trained weights are never used
in public tests. The pinned public production source SHA must remain unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from capsule_review.importer import import_sources
from capsule_review.priority import priority_queue
from scripts import import_private_galar_original_scores as replay


def _png(i: int) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (34, 30), (i % 256, (i * 7) % 256, 72)).save(output, "PNG")
    return output.getvalue()


def _private_test_source(app, tmp_path, monkeypatch, *, n=512, tamper=None, synthetic=False):
    study = import_sources(
        app.state.store,
        ((f"frame_{i:06d}.PNG", _png(i)) for i in range(n)),
        title="Generated software fixture (NOT Galar or clinical data)",
        source="Software-only image pattern test", synthetic=synthetic,
    )
    with app.state.store.connect() as db:
        sources = [dict(row) for row in db.execute(
            "SELECT source_index,source_sha256 FROM frames "
            "WHERE study_id=? ORDER BY position", (study["id"],)
        )]
    rows = []
    for i, original in enumerate(sources):
        rows.append({
            "exam": "23", "frame": str(original["source_index"]),
            "source_image_sha256": original["source_sha256"],
            "pixel_sha256": "f" * 64, "blood": "PRIVATE-NOT-TO-USE",
            "fit_enriched": "0", "reference_uniform": "1",
            "cnn_score": str(((i * 7) % 101) / 100),
            "red_excess_score": "0.3",
        })
    if tamper:
        tamper(rows)
    out = io.StringIO()
    fieldnames = list(rows[0])
    writer = csv.DictWriter(out, fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    data = out.getvalue().encode()
    archive = tmp_path / "test-only-private-scores.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("private/source-scores.csv", data)
        z.writestr("unused-private-source-annotations.csv", "untouched protected fixture")
    spec = {
        "exams": (23,),
        "archive_sha256": replay.file_sha256(archive),
        "member": "private/source-scores.csv",
        "member_sha256": hashlib.sha256(data).hexdigest(),
        "original_sha_column": "source_image_sha256",
        "score_column": "cnn_score",
        "reference_only_column": "reference_uniform",
    }
    # Only the test harness supplies this signed synthetic identity. Production
    # constants still pin two known original private research artifacts.
    monkeypatch.setitem(replay.SOURCES, "synthetic-fixture", spec)
    return study, archive


def test_exact_hash_verified_512_image_import_used_by_real_queue(client, app, headers, tmp_path, monkeypatch):
    study, archive = _private_test_source(app, tmp_path, monkeypatch)
    base = "/api/studies/" + study["id"]
    review = client.put(base + "/frames/0/review", headers=headers, json={
        "revision": 0, "bookmarked": True, "note": "Researcher note stays human-authored", "label": ""
    })
    assert review.status_code == 200
    result = replay.import_verified_original_scores(
        app.state.store, study["id"], "synthetic-fixture", 23, archive
    )
    assert result["imported_reference_images"] == 512
    assert result["all_imported_original_source_hashes_matched"]
    assert result["all_normalized_local_display_hashes_rechecked"]
    assert result["private_reference_labels_excluded_from_model_output"]
    assert not result["clinical_validation"]
    assert not result["source_annotation_run_coverage_measured"]
    assert "research" in result["interpretation"]
    assert set(result) <= {
        "schema_version", "study_type", "examination_id",
        "imported_reference_images", "model_prediction_run_id",
        "source_package_sha256", "original_score_csv_sha256",
        "all_imported_original_source_hashes_matched",
        "all_normalized_local_display_hashes_rechecked",
        "private_reference_labels_excluded_from_model_output",
        "reviewer_notes_and_bookmarks_unmodified",
        "clinical_validation", "source_annotation_run_coverage_measured",
        "interpretation",
    }
    runs = client.get(base + "/priority-runs")
    assert runs.status_code == 200, runs.text
    chosen = runs.json()
    assert len(chosen) == 1
    assert chosen[0]["labels"] == [{
        "name": replay.LABEL, "scored_images": 512, "complete": True
    }]
    assert "blood-positive" not in chosen[0]["model_description"].lower()
    for method in ("score", "score_diverse", "score_bin", "uniform"):
        response = client.get(base + "/priority", params={
            "run": result["model_prediction_run_id"], "label": replay.LABEL,
            "selected_count": 51, "method": method,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["selected_images"] == 51
        assert data["imported_images"] == 512
        assert data["not_diagnostic"]
        assert data["no_reference_labels_read"]
        assert data["reviewer_notes_and_selection_unchanged"]
        assert data["items"][0]["rank"] == 1
        assert len(data["items"]) == 20
        assert "PRIVATE-NOT-TO-USE" not in str(data)
    assert client.get(base + "/frames/0").json()["review"]["note"] == "Researcher note stays human-authored"
    assert len(client.get(base + "/saved").json()) == 1
    with app.state.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM review_events WHERE study_id=?", (study["id"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM predictions WHERE study_id=?", (study["id"],)).fetchone()[0] == 512
    with pytest.raises(ValueError, match="already exists"):
        replay.import_verified_original_scores(app.state.store, study["id"],
                                               "synthetic-fixture", 23, archive)


@pytest.mark.parametrize("tamper,expected", [
    (lambda rows: rows.pop(), "512-image"),
    (lambda rows: rows[17].update({"frame": rows[16]["frame"]}), "Duplicate"),
    (lambda rows: rows[11].update({"source_image_sha256": "0" * 64}), "identities"),
    (lambda rows: rows[19].update({"cnn_score": "nan"}), "invalid research score"),
    (lambda rows: rows[19].update({"cnn_score": "1.1"}), "invalid research score"),
    (lambda rows: rows[20].update({"reference_uniform": "0"}), "512-image"),
])
def test_modified_private_sources_fail_before_any_prediction_write(
        client, app, tmp_path, monkeypatch, tamper, expected):
    study, archive = _private_test_source(app, tmp_path, monkeypatch, tamper=tamper)
    with pytest.raises(ValueError, match=expected):
        replay.import_verified_original_scores(app.state.store, study["id"],
                                               "synthetic-fixture", 23, archive)
    with app.state.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0] == 0


def test_outer_zip_tampering_wrong_exam_and_image_modification_fail_closed(
        client, app, tmp_path, monkeypatch):
    study, archive = _private_test_source(app, tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="six previously examined"):
        replay.import_verified_original_scores(app.state.store, study["id"],
                                               "synthetic-fixture", 11, archive)
    archive.write_bytes(archive.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        replay.import_verified_original_scores(app.state.store, study["id"],
                                               "synthetic-fixture", 23, archive)
    study, archive = _private_test_source(app, tmp_path, monkeypatch)
    image = app.state.store.images / study["id"] / "4.png"
    image.write_bytes(b"tampered display PNG")
    with pytest.raises(ValueError, match="changed"):
        replay.import_verified_original_scores(app.state.store, study["id"],
                                               "synthetic-fixture", 23, archive)


def test_partial_or_synthetic_examination_rejected(app, tmp_path, monkeypatch):
    for n, is_synthetic in ((511, False), (512, True)):
        study, archive = _private_test_source(
            app, tmp_path, monkeypatch, n=n, synthetic=is_synthetic
        )
        with pytest.raises(ValueError):
            replay.import_verified_original_scores(app.state.store, study["id"],
                                                   "synthetic-fixture", 23, archive)


def test_command_refuses_existing_private_receipt(client, app, tmp_path, monkeypatch):
    study, archive = _private_test_source(app, tmp_path, monkeypatch)
    output = tmp_path / "aggregate-only.json"
    import sys
    arguments = [
        "import_private_galar_original_scores.py",
        "--data-dir", str(app.state.store.root), "--study-id", study["id"],
        "--source", "synthetic-fixture", "--examination", "23",
        "--private-archive", str(archive), "--receipt", str(output),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    replay.main()
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["imported_reference_images"] == 512
    assert receipt["all_normalized_local_display_hashes_rechecked"]
    assert "PRIVATE-NOT-TO-USE" not in json.dumps(receipt)
    assert "source_index" not in json.dumps(receipt)
    with pytest.raises(FileExistsError, match="overwrite"):
        replay.main()
    assert json.loads(output.read_text(encoding="utf-8")) == receipt


def test_real_production_sources_are_pinned_to_frozen_archive_identities():
    assert set(replay.SOURCES).issuperset({"frozen-transfer", "appearance-audit"})
    assert replay.SOURCES["frozen-transfer"]["exams"] == (21, 23, 30)
    assert replay.SOURCES["appearance-audit"]["exams"] == (25, 27, 29)
    assert all(len(item["archive_sha256"]) == 64 for item in replay.SOURCES.values())
