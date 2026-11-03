"""Opt-in full-span ZIP: actual FastAPI export, verifier, and tamper failures.

Only generated geometric PNGs and non-medical fixture descriptions are used.
The older boundary-only review export remains byte/schema compatible.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from capsule_review.full_span_evidence import verify_full_span_evidence
from capsule_review.importer import import_sources


def _base(study):
    return f"/api/studies/{study['id']}"


def _add_interval(client, headers, study, start, end):
    r = client.post(_base(study) + "/intervals", headers=headers,
                    json={"start_position": start, "end_position": end,
                          "note": "Generated software-test span, not a lesion."})
    assert r.status_code == 201, r.text


def _review(client, headers, study, position):
    r = client.put(_base(study) + f"/frames/{position}/review", headers=headers,
                   json={"revision": 0, "bookmarked": True,
                         "note": "Generated test bookmark", "label": ""})
    assert r.status_code == 200, r.text


def _zip_info(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return json.loads(z.read("evidence.json")), sorted(z.namelist())


def test_full_span_export_and_standalone_verifier_match_real_api(client, app, headers, study, tmp_path):
    _review(client, headers, study, 0)
    _add_interval(client, headers, study, 0, 2)
    base = _base(study)
    default = client.get(base + "/export")
    assert default.status_code == 200
    with zipfile.ZipFile(io.BytesIO(default.content)) as z:
        assert [f["position"] for f in json.loads(z.read("review.json"))["frames"]] == [0, 2]
        assert "evidence.json" not in z.namelist()

    full = client.get(base + "/full-span-export")
    assert full.status_code == 200, full.text
    assert full.headers["content-type"].startswith("application/zip")
    record, names = _zip_info(full.content)
    assert [f["position"] for f in record["frames"]] == [0, 1, 2]
    assert record["kind"] == "full-imported-span-evidence"
    assert record["frames"][0]["reason"] == {
        "explicit_saved": True, "interval_boundary": True, "marked_span_interior": False,
    }
    assert record["frames"][1]["reason"] == {
        "explicit_saved": False, "interval_boundary": False, "marked_span_interior": True,
    }
    assert "images/frame_000001.png" in names
    assert "index.html" in names and "evidence.json" in names
    assert record["review_history"][0]["content"]["note"] == "Generated test bookmark"
    assert "reference_labels" not in json.dumps(record)
    assert "predictions" not in json.dumps(record)

    p = tmp_path / "full.zip"
    p.write_bytes(full.content)
    manifest = client.get(base + "/manifest").json()
    verified = verify_full_span_evidence(p, manifest)
    assert verified["audit_passed"] is True
    assert verified["imported_images"] == 3
    assert verified["exported_images"] == 3
    assert verified["interval_interior_images_retained"] == 1
    assert verified["additional_images_beyond_boundary_only_export"] == 1
    assert verified["imported_images_not_in_full_span_export"] == 0
    assert verified["pathology_labels_or_clinical_sensitivity_evaluated"] is False
    assert study["id"] not in json.dumps(verified)
    assert not list(app.state.store.root.glob(".full-span-evidence-*"))

    source_path = tmp_path / "trusted-study.json"
    source_path.write_text(json.dumps(manifest))
    receipt = tmp_path / "receipt.json"
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/verify_full_span_evidence.py"),
        "--archive", str(p), "--study-manifest", str(source_path),
        "--output", str(receipt),
    ]
    run = subprocess.run(cmd, check=True, text=True, capture_output=True)
    assert "Full-span evidence verified" in run.stdout
    assert json.loads(receipt.read_text()) == verified
    assert subprocess.run(cmd, check=False, capture_output=True).returncode != 0


def test_full_span_missing_interval_and_corrupted_pixels_fail_closed(client, headers, study, app, tmp_path):
    base = _base(study)
    assert client.get(base + "/full-span-export").status_code == 422
    _add_interval(client, headers, study, 0, 2)
    data = client.get(base + "/full-span-export").content
    manifest = client.get(base + "/manifest").json()
    bad_zip = tmp_path / "tampered.zip"
    with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(bad_zip, "w") as bad:
        for item in original.namelist():
            raw = original.read(item)
            if item == "images/frame_000001.png":
                raw = b"corrupt image"
            bad.writestr(item, raw)
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_full_span_evidence(bad_zip, manifest)
    bad_zip.unlink()
    with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(bad_zip, "w") as bad:
        for item in original.namelist():
            if item != "images/frame_000001.png":
                bad.writestr(item, original.read(item))
    with pytest.raises((KeyError, ValueError)):
        verify_full_span_evidence(bad_zip, manifest)

    # Original stored bytes changed after import must be rejected by exporter;
    # temporary folders and half-written files must not survive.
    image = app.state.store.images / study["id"] / "1.png"
    image.write_bytes(b"changed stored normalized image")
    response = client.get(base + "/full-span-export")
    assert response.status_code == 422
    assert not list(app.state.store.root.glob(".full-span-evidence-*"))


def test_512_imported_frame_realistic_scripted_plan_has_no_missing_interval_interiors(
        client, app, headers, image_bytes, tmp_path):
    study = import_sources(
        app.state.store, (
            (f"frame_{n:06d}.PNG", image_bytes) for n in range(512)
        ), title="Generated 512-frame interval test",
        source="Generated fixture, not endoscopy images", synthetic=True,
    )
    # This reproduces the publicly documented label-blind *position plan*
    # for an already inspected study. It contains no original private pixels.
    bookmark_positions = {(2 * i + 1) * 512 // (2 * 51) for i in range(51)}
    for position in sorted(bookmark_positions):
        _review(client, headers, study, position)
    spans = [(32 * i, 32 * i + 16) for i in range(16)]
    for start, end in spans:
        _add_interval(client, headers, study, start, end)

    standard = client.get(_base(study) + "/export")
    assert standard.status_code == 200, standard.text
    with zipfile.ZipFile(io.BytesIO(standard.content)) as z:
        ordinary = json.loads(z.read("review.json"))
    assert len(ordinary["frames"]) == 79

    full = client.get(_base(study) + "/full-span-export")
    assert full.status_code == 200, full.text
    archive = tmp_path / "full-512.zip"
    archive.write_bytes(full.content)
    data = verify_full_span_evidence(archive, client.get(_base(study) + "/manifest").json())
    assert data["imported_images"] == 512
    assert data["marked_intervals"] == 16
    assert data["exported_images"] == 295
    assert data["retained_images_in_marked_spans"] == 272
    assert data["interval_interior_images_retained"] == 240
    assert data["additional_images_beyond_boundary_only_export"] == 216
    assert data["imported_images_not_in_full_span_export"] == 217
    assert data["image_bytes_in_export_rehashed"] == 295
    assert data["human_review_of_every_retained_image_verified"] is False
    assert not list(app.state.store.root.glob(".full-span-evidence-*"))
