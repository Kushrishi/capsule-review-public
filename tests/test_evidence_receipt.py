"""App-to-ZIP-to-offline-receipt validation, including adversarial history edits.

Uses generated PNG pixels only. No real medical images or labels in GitHub CI.
"""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from PIL import Image

from capsule_review.evidence_receipt import (
    account_review_evidence,
    audit_review_export_zip,
)
from capsule_review.importer import import_sources
from capsule_review.interval_evidence import read_review_export


def _png(n: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (36, 32), ((n * 13) % 255, (n * 23) % 255, 49)).save(out, "PNG")
    return out.getvalue()


def _fixture(app, client, headers, tmp_path, *, numbered=True, synthetic=False):
    sources = (
        (f"frame_{i:06d}.PNG" if numbered else f"photo_{i:06d}.png", _png(i))
        for i in range(12)
    )
    study = import_sources(
        app.state.store, sources,
        title="Generated offline evidence test",
        source="Generated pixels only; no human medical data",
        synthetic=synthetic,
    )
    base = f"/api/studies/{study['id']}"
    for position, change in (
        (0, {"revision": 0, "bookmarked": True, "note": "", "label": ""}),
        (0, {"revision": 1, "bookmarked": False, "note": "", "label": ""}),
        (1, {"revision": 0, "bookmarked": True, "note": "Synthetic saved note", "label": ""}),
        (7, {"revision": 0, "bookmarked": False, "note": "", "label": "Synthetic label"}),
    ):
        response = client.put(f"{base}/frames/{position}/review", headers=headers, json=change)
        assert response.status_code == 200, response.text
    response = client.post(
        f"{base}/intervals", headers=headers,
        json={"start_position": 2, "end_position": 10, "note": "Synthetic interval note"},
    )
    assert response.status_code == 201, response.text
    exported = client.get(f"{base}/export")
    assert exported.status_code == 200, exported.text
    review_file = tmp_path / "review.zip"
    review_file.write_bytes(exported.content)
    manifest_file = tmp_path / "study.json"
    manifest = client.get(f"{base}/manifest").json()
    manifest_file.write_text(json.dumps(manifest))
    return read_review_export(review_file), manifest, review_file, manifest_file


@pytest.mark.parametrize("numbered,synthetic", [(True, False), (False, True)])
def test_real_app_export_and_history_reconstruction(
        app, client, headers, tmp_path, numbered, synthetic):
    review, manifest, archive, manifest_file = _fixture(
        app, client, headers, tmp_path, numbered=numbered, synthetic=synthetic
    )
    receipt = account_review_evidence(review, manifest)
    assert receipt["audit_passed"] is True
    assert receipt["imported_images"] == 12
    assert receipt["selected_export_images"] == 4
    assert receipt["explicitly_saved_images"] == 2
    assert receipt["interval_boundary_images"] == 2
    assert receipt["images_both_saved_and_interval_boundary"] == 0
    assert receipt["images_only_selected_as_interval_boundary"] == 2
    assert receipt["selected_export_fraction_of_imported"] == pytest.approx(4 / 12, abs=1e-8)
    assert receipt["imported_images_not_selected_for_export"] == 8
    assert receipt["marked_image_intervals"] == 1
    assert receipt["unique_imported_positions_in_marked_spans"] == 9
    assert receipt["unique_imported_interval_interior_positions"] == 7
    assert receipt["interval_interior_images_not_exported"] == 6
    assert receipt["longest_consecutive_imported_position_gap_inside_intervals"] == 4
    assert receipt["review_event_revisions_replayed"] == 4
    assert receipt["reviewer_interval_event_revisions_replayed"] == 1
    assert receipt["numbered_imported_images"] == (12 if numbered else 0)
    assert receipt["observed_source_index_assessment"] == (
        "consecutive-imported-indices" if numbered else "unknown"
    )
    assert receipt["pathology_labels_or_run_recall_evaluated"] is False
    assert receipt["reader_time_savings_measured"] is False
    assert receipt["original_full_video_completeness_verified"] is False
    encoded = json.dumps(receipt)
    assert "Synthetic saved note" not in encoded
    assert "Synthetic interval note" not in encoded
    assert "Synthetic label" not in encoded
    assert "frame_000" not in encoded
    assert "source_sha256" not in encoded
    assert '"source_index":' not in encoded
    assert "study_id" not in encoded
    with zipfile.ZipFile(archive) as z:
        assert sorted(i["position"] for i in review["frames"]) == [1, 2, 7, 10]
        assert "images/frame_000003.png" not in z.namelist()
    output = tmp_path / "aggregate-only.json"
    assert audit_review_export_zip(
        review_zip=archive, study_manifest_path=manifest_file, output=output
    ) == receipt
    assert json.loads(output.read_text()) == receipt
    with pytest.raises(FileExistsError):
        audit_review_export_zip(
            review_zip=archive, study_manifest_path=manifest_file, output=output
        )


def test_reject_missing_saved_image_and_mutated_reviewer_history(app, client, headers, tmp_path):
    review, manifest, _, _ = _fixture(app, client, headers, tmp_path)
    changed = deepcopy(review)
    changed["frames"] = [f for f in changed["frames"] if f["position"] != 7]
    with pytest.raises(ValueError, match="incomplete"):
        account_review_evidence(changed, manifest)
    changed = deepcopy(review)
    next(f for f in changed["frames"] if f["position"] == 1)["review"]["note"] = "FORGED"
    with pytest.raises(ValueError, match="last audited revision"):
        account_review_evidence(changed, manifest)
    changed = deepcopy(review)
    changed["review_history"] = changed["review_history"][1:]
    with pytest.raises(ValueError, match="revision history"):
        account_review_evidence(changed, manifest)
    changed = deepcopy(review)
    changed["frames"][0]["review"]["revision"] = 77
    with pytest.raises(ValueError, match="last audited revision"):
        account_review_evidence(changed, manifest)


def test_reject_orphan_interval_create_and_mismatched_original_manifest(app, client, headers, tmp_path):
    review, manifest, _, _ = _fixture(app, client, headers, tmp_path)
    changed = deepcopy(review)
    changed["interval_history"].append({
        "interval_id": 999, "action": "created", "start_position": 3, "end_position": 6,
        "note": "orphan creation", "created_at": "2026-11-03",
    })
    with pytest.raises(ValueError, match="unaccounted creation"):
        account_review_evidence(changed, manifest)
    changed_manifest = deepcopy(manifest)
    changed_manifest["frames"][4]["source_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="identity manifest SHA-256"):
        account_review_evidence(review, changed_manifest)
    changed_manifest = deepcopy(manifest)
    changed_manifest["frames"][4]["display_sha256"] = "a" * 64
    # The ZIP contains no unexported display PNG bytes. Its saved hash can be
    # checked only for selected rows. We deliberately do NOT claim otherwise.
    assert account_review_evidence(review, changed_manifest)["audit_passed"] is True


def test_reject_changed_export_metadata_or_unverified_input_zip(app, client, headers, tmp_path):
    review, manifest, archive, manifest_file = _fixture(app, client, headers, tmp_path)
    altered = deepcopy(review)
    altered["synthetic"] = True
    with pytest.raises(ValueError, match="provenance"):
        account_review_evidence(altered, manifest)
    altered = deepcopy(review)
    altered["frames"][0]["source_filename"] = "other.PNG"
    with pytest.raises(ValueError, match="verified imported source"):
        account_review_evidence(altered, manifest)
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("unlisted.txt", "injected extra member")
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError, match="Extra or unlisted"):
        audit_review_export_zip(
            review_zip=archive, study_manifest_path=manifest_file, output=output
        )
    assert not output.exists()


def test_documented_cli_is_executable(app, client, headers, tmp_path):
    _, _, archive, manifest_file = _fixture(app, client, headers, tmp_path)
    output = tmp_path / "receipt.json"
    script = Path(__file__).resolve().parents[1] / "scripts/audit_review_evidence.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--review-zip", str(archive),
         "--study-manifest", str(manifest_file), "--output", str(output)],
        text=True, capture_output=True, check=True,
    )
    assert "NOT included in the export" in proc.stdout
    saved = json.loads(output.read_text())
    assert saved["interval_interior_images_not_exported"] == 6
    assert "Synthetic" not in output.read_text()
    again = subprocess.run(
        [sys.executable, str(script), "--review-zip", str(archive),
         "--study-manifest", str(manifest_file), "--output", str(output)],
        text=True, capture_output=True, check=False,
    )
    assert again.returncode != 0
