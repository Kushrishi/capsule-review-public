"""Synthetic demo scoring is nonmedical, opt-in via authenticated POST, and idempotent."""
from __future__ import annotations

from capsule_review.demo_scores import DEMO_FRAMES, DEMO_LABEL, DEMO_MODEL_NAME, DEMO_RUN_ID
from capsule_review.importer import create_demo, import_sources
from capsule_review.priority import select_positions


def _study_url(study):
    return "/api/studies/" + study["id"]


def test_api_demo_scores_are_complete_nonmedical_and_comparable(client, headers, app):
    created = client.post("/api/demo", headers=headers)
    assert created.status_code == 201, created.text
    study = created.json()
    assert study["synthetic"] is True and study["frame_count"] == DEMO_FRAMES
    assert len(study["runs"]) == 1
    model = study["runs"][0]["model"]
    assert model["name"] == DEMO_MODEL_NAME
    assert model["run_id"] == DEMO_RUN_ID
    assert model["weights_sha256"] is None
    assert "not trained" in model["description"].lower()
    base = _study_url(study)
    available = client.get(base + "/priority-runs").json()
    assert len(available) == 1 and available[0]["labels"] == [
        {"name": DEMO_LABEL, "scored_images": DEMO_FRAMES, "complete": True}
    ]
    run = available[0]["run"]
    with app.state.store.connect() as db:
        rows = db.execute(
            "SELECT position,score FROM predictions WHERE study_id=? AND run_id=? "
            "ORDER BY position", (study["id"], run)
        ).fetchall()
        assert [x["position"] for x in rows] == list(range(DEMO_FRAMES))
        scores = [x["score"] for x in rows]
        assert len(set(scores)) > 2
        assert all(0 <= x <= 1 for x in scores)
        assert db.execute(
            "SELECT COUNT(*) FROM review_events WHERE study_id=?", (study["id"],)
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM review_intervals WHERE study_id=?", (study["id"],)
        ).fetchone()[0] == 0
    for method in ("score", "score_diverse", "score_bin", "uniform"):
        response = client.get(base + "/priority", params={
            "run": run, "label": DEMO_LABEL, "selected_count": 6,
            "method": method, "page_size": 20,
        })
        assert response.status_code == 200, response.text
        result = response.json()
        selected = [x["position"] for x in result["items"]]
        assert len(set(selected)) == len(selected) == 6
        assert selected == select_positions(scores, 6, method)
        assert result["no_reference_labels_read"]
    comparison = client.get(base + "/priority-comparison", params={
        "run": run, "label": DEMO_LABEL, "selected_count": 6,
    })
    assert comparison.status_code == 200
    methods = {x["method"]: x for x in comparison.json()["methods"]}
    assert set(methods) == {"score", "score_diverse", "score_bin", "uniform"}
    assert methods["score"]["largest_unselected_span"]["imported_images_not_in_queue"] > (
        methods["uniform"]["largest_unselected_span"]["imported_images_not_in_queue"]
    )
    for i in range(DEMO_FRAMES):
        frame = client.get(base + f"/frames/{i}").json()
        assert frame["reference_labels"] == {}
        assert frame["review"]["revision"] == 0
        assert len(frame["predictions"]) == 1
        assert frame["predictions"][0]["label"] == DEMO_LABEL
    assert client.get(base + "/manifest").json()["synthetic"] is True


def test_preexisting_demo_is_upgraded_once_without_changing_human_review(client, headers, app):
    legacy = create_demo(app.state.store)
    assert legacy["runs"] == []
    base = _study_url(legacy)
    review = client.put(base + "/frames/4/review", headers=headers, json={
        "revision": 0, "bookmarked": True,
        "note": "Human note must stay exactly as written", "label": "Revisit",
    })
    assert review.status_code == 200
    first = client.post("/api/demo", headers=headers, params={"study_id": legacy["id"]})
    assert first.status_code == 201, first.text
    assert first.json()["id"] == legacy["id"]
    assert len(first.json()["runs"]) == 1
    second = client.post("/api/demo", headers=headers, params={"study_id": legacy["id"]})
    assert second.status_code == 201
    assert len(second.json()["runs"]) == 1
    assert second.json()["runs"][0]["id"] == first.json()["runs"][0]["id"]
    frame = client.get(base + "/frames/4").json()
    assert frame["review"]["note"] == "Human note must stay exactly as written"
    assert frame["review"]["label"] == "Revisit"
    assert frame["review"]["bookmarked"] is True
    assert frame["review"]["revision"] == 1


def test_demo_scoring_cannot_modify_ordinary_or_other_synthetic_studies(
    client, headers, app, study, image_bytes
):
    custom = import_sources(
        app.state.store, [("frame_000000.png", image_bytes)],
        title="Other synthetic fixture", source="Generated test elsewhere", synthetic=True,
    )
    for target in (study, custom):
        response = client.post("/api/demo", headers=headers, params={"study_id": target["id"]})
        assert response.status_code == 422, response.text
        assert app.state.store.study(target["id"])["runs"] == []
    assert client.post("/api/demo", headers=headers, params={"study_id": "missing"}).status_code == 422
    assert client.post("/api/demo").status_code == 403


def test_cli_demo_builds_and_reopens_same_complete_synthetic_fixture(tmp_path, monkeypatch, capsys):
    """The documented no-clinical-data CLI path matches the browser demo."""
    import json
    import sys
    from capsule_review.cli import main
    from capsule_review.store import Store

    workspace = tmp_path / "supervisor-demo"
    monkeypatch.setattr(sys, "argv", [
        "capsule-review", "--data-dir", str(workspace), "demo",
    ])
    main()
    first = json.loads(capsys.readouterr().out)
    assert first["synthetic"] is True
    assert first["frame_count"] == DEMO_FRAMES
    assert len(first["runs"]) == 1
    assert first["runs"][0]["model"]["run_id"] == DEMO_RUN_ID
    main()
    second = json.loads(capsys.readouterr().out)
    assert second["id"] == first["id"]
    assert len(second["runs"]) == 1
    assert second["runs"][0]["id"] == first["runs"][0]["id"]

    store = Store(workspace)
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM predictions WHERE study_id=?", (first["id"],)
        ).fetchone()[0] == DEMO_FRAMES
        assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM review_intervals").fetchone()[0] == 0
    for i in range(DEMO_FRAMES):
        frame = store.frame(first["id"], i)
        assert frame["reference_labels"] == {}
        assert len(frame["predictions"]) == 1
