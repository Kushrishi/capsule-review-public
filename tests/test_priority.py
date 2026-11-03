"""Complete-score, label-blind, read-only review queues on synthetic PNGs."""
from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from capsule_review.importer import import_sources
from capsule_review.priority import (
    ordinal_coverage, priority_queue, select_positions, uniform_midpoints,
)


def test_fixed_methods_exact_k_and_deterministic_across_all_workloads():
    scores = [((i * 7) % 11) / 10 for i in range(37)]
    for k in (1, 2, 4, 11, 20, 36, 37):
        baseline = uniform_midpoints(37, k)
        assert len(baseline) == k
        for method in ("uniform", "score", "score_diverse", "score_bin"):
            result = select_positions(scores, k, method)
            assert result == select_positions(scores, k, method)
            assert len(result) == len(set(result)) == k
            assert all(0 <= p < 37 for p in result)
            assert ordinal_coverage(37, result)["maximum_nearest_selected_imported_positions"] >= 0
        assert set(select_positions(scores, k, "uniform")) == set(baseline)
        if k == 37:
            assert set(select_positions(scores, k, "score_diverse")) == set(range(37))
    assert select_positions([1, 1, 1, 1], 2, "score") == [0, 1]
    assert select_positions([1, 1, 1, 1], 2, "score_bin") == [0, 2]
    assert uniform_midpoints(12, 3) == [2, 6, 10]


@pytest.mark.parametrize("n,k,method", [
    (0, 1, "score"), (3, 0, "uniform"), (3, 4, "score"),
    (3, True, "score"), (3, 2, "unknown"),
])
def test_invalid_workloads_or_methods_rejected(n, k, method):
    with pytest.raises(ValueError):
        select_positions([.5] * n, k, method)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.01, 1.01, "0.5", True])
def test_nonfinite_invalid_and_boolean_scores_fail_closed(bad):
    with pytest.raises(ValueError, match="scores"):
        select_positions([.5, bad, .2], 2, "score_diverse")


def _generated_png(position: int) -> bytes:
    data = io.BytesIO()
    Image.new("RGB", (40, 40), (position % 256, (position * 5) % 256, 70)).save(data, "PNG")
    return data.getvalue()


def _fixture(app, client, headers, *, n=24, incomplete=False):
    study = import_sources(
        app.state.store,
        ((f"frame_{pos:06d}.PNG", _generated_png(pos)) for pos in range(n)),
        title="Purely generated image geometry", source="Generated software fixtures",
        synthetic=True,
    )
    base = f"/api/studies/{study['id']}"
    manifest = client.get(base + "/manifest").json()["frames"]
    points = range(n - 1 if incomplete else n)
    data = {
        "schema_version": 1,
        "study_id": study["id"],
        "model": {
            "name": "Synthetic sequence intensity", "version": "1",
            "run_id": "test-run-1", "description": "Not a medical classifier.",
        },
        "predictions": [
            {"position": pos, "image_sha256": manifest[pos]["source_sha256"],
             "label": "test-pattern", "score": 0.98 if 6 <= pos <= 12 else .01}
            for pos in points
        ],
    }
    imported = client.post(base + "/predictions", headers=headers, json=data)
    assert imported.status_code == 201, imported.text
    return study, imported.json()["run_id"], base


def test_real_api_readonly_queue_multiple_methods_paging_and_labels(client, app, headers):
    study, run, base = _fixture(app, client, headers, n=24)
    review = client.put(
        base + "/frames/0/review", headers=headers,
        json={"revision": 0, "bookmarked": True,
              "note": "Must remain human-authored", "label": ""}
    )
    assert review.status_code == 200
    source_info = client.get(base + "/priority-runs")
    assert source_info.status_code == 200, source_info.text
    assert len(source_info.json()) == 1
    assert source_info.json()[0]["labels"] == [
        {"name": "test-pattern", "scored_images": 24, "complete": True}
    ]
    outputs = {}
    for method in ("score", "score_diverse", "score_bin", "uniform"):
        r = client.get(base + "/priority", params={
            "run": run, "label": "test-pattern", "selected_count": 8,
            "method": method, "page_size": 3
        })
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["selected_images"] == 8 and payload["imported_images"] == 24
        assert len(payload["items"]) == 3 and payload["items"][0]["rank"] == 1
        assert payload["no_reference_labels_read"] is True
        assert payload["reviewer_notes_and_selection_unchanged"] is True
        assert payload["not_diagnostic"] is True
        assert "not calibrated" in payload["interpretation"]
        assert set(payload["selected_ordinal_coverage"]) == {
            "mean_nearest_selected_imported_positions",
            "p95_nearest_selected_imported_positions",
            "maximum_nearest_selected_imported_positions",
        }
        assert all(item["score"] in (.98, .01) for item in payload["items"])
        outputs[method] = payload
        next_page = client.get(base + "/priority", params={
            "run": run, "label": "test-pattern", "selected_count": 8,
            "method": method, "offset": 3, "page_size": 5,
        })
        assert next_page.status_code == 200
        items = payload["items"] + next_page.json()["items"]
        assert len({item["position"] for item in items}) == 8
        assert [item["rank"] for item in items] == list(range(1, 9))
        assert client.get(base + "/priority", params={
            "run": run, "label": "test-pattern", "selected_count": 8,
            "method": method, "offset": 8
        }).json()["items"] == []
    assert outputs["score"]["items"][0]["position"] == 6
    assert outputs["score"]["items"][1]["position"] == 7
    assert outputs["score"]["selected_ordinal_coverage"]["maximum_nearest_selected_imported_positions"] > (
        outputs["uniform"]["selected_ordinal_coverage"]["maximum_nearest_selected_imported_positions"]
    )
    assert outputs["uniform"]["selected_ordinal_coverage"] == outputs["uniform"]["uniform_ordinal_coverage_at_equal_workload"]
    assert client.get(base + "/frames/0").json()["review"]["note"] == "Must remain human-authored"
    assert client.get(base + "/saved").json()[0]["position"] == 0
    assert len(client.get(base + "/saved").json()) == 1
    with app.state.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM review_events WHERE study_id=?", (study["id"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM review_intervals WHERE study_id=?", (study["id"],)).fetchone()[0] == 0


def test_partial_run_other_study_and_invalid_selection_cannot_be_queued(client, app, headers):
    incomplete, run, base = _fixture(app, client, headers, n=12, incomplete=True)
    info = client.get(base + "/priority-runs").json()
    assert info[0]["labels"][0]["complete"] is False
    assert client.get(base + "/priority", params={
        "run": run, "label": "test-pattern", "selected_count": 6,
        "method": "score"
    }).status_code == 422
    complete, run2, base2 = _fixture(app, client, headers, n=10)
    for case, status in [
        ({"run": run, "label": "test-pattern", "selected_count": 6, "method": "score"}, 404),
        ({"run": run2, "label": "nonexistent", "selected_count": 3, "method": "uniform"}, 422),
        ({"run": run2, "label": "test-pattern", "selected_count": 11, "method": "score"}, 422),
        ({"run": run2, "label": "test-pattern", "selected_count": 0, "method": "score"}, 422),
        ({"run": run2, "label": "test-pattern", "selected_count": 3, "method": "bogus"}, 422),
        ({"run": run2, "label": "test-pattern", "selected_count": 3, "method": "uniform", "page_size": 51}, 422),
    ]:
        assert client.get(base2 + "/priority", params=case).status_code == status
    assert client.get("/api/studies/unknown-study/priority-runs").status_code == 404


def test_annotated_source_fields_cannot_change_queue_predictions(client, app, headers):
    study, run, base = _fixture(app, client, headers, n=15)
    params = {"run": run, "label": "test-pattern", "selected_count": 7, "method": "score_diverse"}
    initial = client.get(base + "/priority", params=params).json()
    with app.state.store.connect() as db:
        db.execute(
            "UPDATE frames SET reference_labels=? WHERE study_id=? AND position=6",
            ('{"blood": 1, "private_ground_truth": "never used"}', study["id"])
        )
        db.execute(
            "UPDATE reviews SET note=? WHERE study_id=? AND position=0",
            ("Private reviewer note, selection must ignore this", study["id"])
        )
    result = client.get(base + "/priority", params=params).json()
    assert result == initial
    assert "private_ground_truth" not in str(result)
    assert "Private reviewer note" not in str(result)


def test_large_100_percent_budget_and_constant_score_detection(client, app, headers):
    _, run, base = _fixture(app, client, headers, n=24)
    for method in ("score_diverse", "score_bin", "score", "uniform"):
        outcome = client.get(base + "/priority", params={
            "run": run, "label": "test-pattern", "selected_count": 24, "method": method
        })
        assert outcome.status_code == 200
        positions = [item["position"] for item in outcome.json()["items"]]
        assert len(positions) == len(set(positions)) == 20
        last_page = client.get(base + "/priority", params={
            "run": run, "label": "test-pattern", "selected_count": 24,
            "method": method, "offset": 20
        }).json()["items"]
        assert len(positions + [x["position"] for x in last_page]) == 24
        assert outcome.json()["selected_ordinal_coverage"]["maximum_nearest_selected_imported_positions"] == 0
    with app.state.store.connect() as db:
        db.execute("UPDATE predictions SET score=0.5 WHERE study_id=?", (_.get("id"),))
    constant = client.get(base + "/priority", params={
        "run": run, "label": "test-pattern", "selected_count": 3, "method": "score"
    })
    assert constant.status_code == 200
    assert constant.json()["scores_constant"] is True
