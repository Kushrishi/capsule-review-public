"""Regression: old study SQLite can be opened by current app without losing scores.

Synthetic-generated PNGs only. The actual original-Galar23 private workspace
was replayed separately with an earlier preserved application snapshot.
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from capsule_review.app import create_app
from capsule_review.importer import import_sources


def _generated_image(index: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (48, 40), (index * 9 % 256, 21, 74)).save(out, "PNG")
    return out.getvalue()


def test_pre_interval_workspace_migrates_without_erasing_scores(tmp_path: Path):
    root = tmp_path / "private-but-synthetic-workspace"
    original = create_app(root)
    study = import_sources(
        original.state.store,
        ((f"frame_{i * 5:06d}.PNG", _generated_image(i)) for i in range(12)),
        title="Synthetic historical workspace",
        source="Software-only nonmedical regression fixture",
        synthetic=True,
    )
    study_id = study["id"]
    with TestClient(original, base_url="http://127.0.0.1") as client:
        token = client.get("/api/config").json()["token"]
        manifest = client.get(f"/api/studies/{study_id}/manifest").json()["frames"]
        response = client.put(
            f"/api/studies/{study_id}/frames/0/review",
            headers={"X-Review-Token": token},
            json={
                "revision": 0, "bookmarked": True,
                "note": "Author note must survive schema upgrade",
                "label": "Independent review label",
            },
        )
        assert response.status_code == 200, response.text
        response = client.post(
            f"/api/studies/{study_id}/predictions",
            headers={"X-Review-Token": token},
            json={
                "schema_version": 1, "study_id": study_id,
                "model": {
                    "name": "Old saved synthetic prediction stream",
                    "version": "1",
                    "run_id": "historical-model-run",
                    "description": "Software regression; not real medicine",
                },
                "predictions": [
                    {
                        "position": i,
                        "image_sha256": frame["source_sha256"],
                        "label": "synthetic test score",
                        "score": i / 11,
                    }
                    for i, frame in enumerate(manifest)
                ],
            },
        )
        assert response.status_code == 201, response.text
        run_id = response.json()["run_id"]

    # Simulate the important difference between an older workspace and the
    # current application: pre-interval workspaces lack these additive tables.
    with original.state.store.connect() as db:
        db.execute("DROP TABLE review_interval_events")
        db.execute("DROP TABLE review_intervals")
        assert db.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 12

    reopened = create_app(root)
    with TestClient(reopened, base_url="http://127.0.0.1") as client:
        assert client.get(f"/api/studies/{study_id}").json()["frame_count"] == 12
        frame = client.get(f"/api/studies/{study_id}/frames/0").json()
        assert frame["review"]["note"] == "Author note must survive schema upgrade"
        assert frame["review"]["label"] == "Independent review label"
        assert frame["review"]["bookmarked"] is True
        assert frame["predictions"][0]["score"] == 0
        assert len(client.get(f"/api/studies/{study_id}/saved").json()) == 1
        available = client.get(f"/api/studies/{study_id}/priority-runs")
        assert available.status_code == 200, available.text
        run = available.json()[0]
        assert run["run"] == run_id
        assert run["labels"] == [
            {"name": "synthetic test score", "scored_images": 12, "complete": True}
        ]
        for method in ("score", "score_diverse", "score_bin", "uniform"):
            response = client.get(f"/api/studies/{study_id}/priority", params={
                "run": run_id, "label": "synthetic test score",
                "selected_count": 5, "method": method, "page_size": 5,
            })
            assert response.status_code == 200, response.text
            assert len(response.json()["items"]) == 5
            assert response.json()["reviewer_notes_and_selection_unchanged"]
        with reopened.state.store.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 12
            assert db.execute(
                "SELECT COUNT(*) FROM review_intervals"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM review_interval_events"
            ).fetchone()[0] == 0
