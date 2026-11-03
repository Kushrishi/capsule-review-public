"""Real local-app export verification endpoint with synthetic-only fixtures.

No actual endoscopy images or private reviewer notes are placed in public CI.
"""
from __future__ import annotations

import json
from pathlib import Path

from capsule_review.evidence_receipt import audit_review_export_zip


def base(study):
    return f"/api/studies/{study['id']}"


def save_and_mark(client, headers, study):
    response = client.put(base(study) + "/frames/0/review", headers=headers, json={
        "revision": 0, "bookmarked": True,
        "note": "Private-like synthetic note: should not appear in the audit",
        "label": "Synthetic reviewer label",
    })
    assert response.status_code == 200, response.text
    response = client.post(base(study) + "/intervals", headers=headers, json={
        "start_position": 0, "end_position": 2,
        "note": "Private-like interval text: not an annotated lesion",
    })
    assert response.status_code == 201, response.text


def test_local_one_click_endpoint_agrees_with_offline_zip_auditor(
        client, headers, study, app, tmp_path):
    save_and_mark(client, headers, study)
    response = client.get(base(study) + "/evidence-audit")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["audit_passed"] is True
    assert data["imported_images"] == 3
    assert data["selected_export_images"] == 2
    assert data["explicitly_saved_images"] == 1
    assert data["interval_boundary_images"] == 2
    assert data["images_both_saved_and_interval_boundary"] == 1
    assert data["images_only_selected_as_interval_boundary"] == 1
    assert data["interval_interior_images_not_exported"] == 1
    assert data["imported_images_not_selected_for_export"] == 1
    assert data["review_event_revisions_replayed"] == 1
    assert data["reviewer_interval_event_revisions_replayed"] == 1
    assert data["selected_position_coverage"]["maximum_nearest_selected_imported_positions"] == 1
    assert data["uniform_reference_position_coverage_at_exact_same_workload"]["maximum_nearest_selected_imported_positions"] == 1
    assert data["pathology_labels_or_run_recall_evaluated"] is False
    assert data["reader_time_savings_measured"] is False

    # A second independent invocation through the existing offline CLI core
    # must return exactly the same aggregate, despite separate ZIP export times.
    archive = tmp_path / "review.zip"
    archive.write_bytes(client.get(base(study) + "/export").content)
    manifest = tmp_path / "study.json"
    manifest.write_text(json.dumps(client.get(base(study) + "/manifest").json()))
    output = tmp_path / "local-verified-aggregate.json"
    assert audit_review_export_zip(
        review_zip=archive, study_manifest_path=manifest, output=output
    ) == data
    assert json.loads(output.read_text()) == data
    assert not list(app.state.store.root.glob(".evidence-audit-*"))

    serialized = response.text
    for forbidden in (study["id"], "Private-like synthetic note",
                      "Private-like interval text", "Synthetic reviewer label",
                      "frame_000002", "frame_000009", "source_sha256",
                      '"frames"', '"review_history"', '"interval_history"'):
        assert forbidden not in serialized


def test_one_click_audit_fails_closed_with_no_selection_or_missing_saved_history(
        client, headers, study, app):
    path = base(study) + "/evidence-audit"
    assert client.get(path).status_code == 422
    save_and_mark(client, headers, study)
    assert client.get(path).status_code == 200
    with app.state.store.connect() as db:
        db.execute("DELETE FROM review_events WHERE study_id=?", (study["id"],))
    broken = client.get(path)
    assert broken.status_code == 422
    assert "incomplete" in broken.text.lower()
    assert not list(app.state.store.root.glob(".evidence-audit-*"))


def test_one_click_audit_fails_closed_on_changed_png_and_source_identity(
        client, headers, study, app):
    save_and_mark(client, headers, study)
    base_url = base(study) + "/evidence-audit"
    assert client.get(base_url).status_code == 200
    image = app.state.store.images / study["id"] / "0.png"
    original = image.read_bytes()
    image.write_bytes(b"forged display bytes")
    corrupt = client.get(base_url)
    assert corrupt.status_code == 422
    assert "sha-256" in corrupt.text.lower()
    image.write_bytes(original)
    with app.state.store.connect() as db:
        db.execute("UPDATE frames SET source_sha256=? WHERE study_id=? AND position=1",
                   ("a" * 64, study["id"]))
    broken_manifest = client.get(base_url)
    assert broken_manifest.status_code == 422
    assert "identity manifest sha-256" in broken_manifest.text.lower()
    assert not list(app.state.store.root.glob(".evidence-audit-*"))


def test_one_click_audit_recomputes_after_saved_frame_is_cleared(client, headers, study):
    save_and_mark(client, headers, study)
    before = client.get(base(study) + "/evidence-audit").json()
    assert before["explicitly_saved_images"] == 1
    cleared = client.put(base(study) + "/frames/0/review", headers=headers, json={
        "revision": 1, "bookmarked": False, "note": "", "label": "",
    })
    assert cleared.status_code == 200
    after = client.get(base(study) + "/evidence-audit").json()
    assert after["audit_passed"] is True
    assert after["review_event_revisions_replayed"] == 2
    assert after["explicitly_saved_images"] == 0
    assert after["interval_boundary_images"] == 2
    assert after["selected_export_images"] == 2
    assert after["interval_interior_images_not_exported"] == 1
    interval_id = client.get(base(study) + "/intervals").json()[0]["id"]
    assert client.delete(base(study) + f"/intervals/{interval_id}", headers=headers).status_code == 200
    assert client.get(base(study) + "/evidence-audit").status_code == 422
