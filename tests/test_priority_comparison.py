"""Generated-only regression for transparent, label-blind omission inspection."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from capsule_review.importer import import_sources
from capsule_review.priority import (
    METHODS, compare_priority_methods, largest_unselected_span,
    ordinal_coverage, select_positions,
)


def test_exact_longest_skipped_span_uses_ordinal_not_video_time():
    assert largest_unselected_span(12, [2, 6, 10]) == {
        "start_position": 3, "end_position": 5,
        "imported_images_not_in_queue": 3, "inspect_position": 4,
    }
    assert largest_unselected_span(9, [0, 4, 8]) == {
        "start_position": 1, "end_position": 3,
        "imported_images_not_in_queue": 3, "inspect_position": 2,
    }
    assert largest_unselected_span(8, [0, 1]) == {
        "start_position": 2, "end_position": 7,
        "imported_images_not_in_queue": 6, "inspect_position": 4,
    }
    assert largest_unselected_span(5, [0, 1, 2, 3, 4]) is None
    for length, selection in ((0, [0]), (3, []), (3, [1, 1]), (3, [3]), (3, [True])):
        with pytest.raises(ValueError):
            largest_unselected_span(length, selection)


def _png(position: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (48, 40), (position * 13 % 256, 30, 60)).save(out, "PNG")
    return out.getvalue()


def _ready(app, client, headers, *, n=24, partial=False):
    study = import_sources(
        app.state.store,
        ((f"f_{i:04d}.png", _png(i)) for i in range(n)),
        title="Synthetic omission policy test", source="Generated test imagery",
        synthetic=True,
    )
    base = f"/api/studies/{study['id']}"
    hashes = client.get(base + "/manifest").json()["frames"]
    payload = {
        "schema_version": 1, "study_id": study["id"],
        "model": {"name": "Synthetic score", "version": "1",
                  "run_id": "synthetic-audit-1", "description": "Not a diagnosis"},
        "predictions": [
            {"position": i, "image_sha256": hashes[i]["source_sha256"],
             "label": "synthetic", "score": .99 if 7 <= i <= 13 else .01}
            for i in range(n - (1 if partial else 0))
        ],
    }
    posted = client.post(base + "/predictions", headers=headers, json=payload)
    assert posted.status_code == 201, posted.text
    return base, posted.json()["run_id"], study["id"]


def test_same_k_api_matches_every_live_queue_without_reading_labels(client, app, headers):
    base, run, study_id = _ready(app, client, headers)
    review = client.put(
        base + "/frames/0/review", headers=headers,
        json={"revision": 0, "bookmarked": True,
              "note": "Human-authored: do not mutate", "label": ""},
    )
    assert review.status_code == 200
    params = {"run": run, "label": "synthetic", "selected_count": 7}
    before = client.get(base + "/priority-comparison", params=params)
    assert before.status_code == 200, before.text
    result = before.json()
    assert result["selected_images_per_method"] == 7
    assert result["imported_images"] == 24
    assert result["no_reference_labels_read"] and result["not_diagnostic"]
    assert result["reviewer_notes_and_selection_unchanged"]
    assert {item["method"] for item in result["methods"]} == set(METHODS)
    for method in METHODS:
        by_method = next(item for item in result["methods"] if item["method"] == method)
        current = client.get(base + "/priority", params={**params, "method": method})
        assert current.status_code == 200, current.text
        data = current.json()
        assert data["largest_unselected_span"] == by_method["largest_unselected_span"]
        assert data["selected_ordinal_coverage"] == by_method["selected_ordinal_coverage"]
        span = by_method["largest_unselected_span"]
        assert span is not None
        assert 0 <= span["start_position"] <= span["inspect_position"] <= span["end_position"] < 24
        assert span["end_position"] - span["start_position"] + 1 == span["imported_images_not_in_queue"]
    assert len(client.get(base + "/saved").json()) == 1

    # Source labels and notes can change, but queue proposals cannot read them.
    with app.state.store.connect() as db:
        db.execute(
            "UPDATE frames SET reference_labels=? WHERE study_id=? AND position=7",
            ('{"blood":1,"do_not_use_for_ranking":"private"}', study_id),
        )
        db.execute(
            "UPDATE reviews SET note=? WHERE study_id=? AND position=0",
            ("Changed private human note", study_id),
        )
    after = client.get(base + "/priority-comparison", params=params)
    assert after.status_code == 200
    assert after.json() == result
    assert "private" not in str(after.json())


def test_full_workload_incomplete_scores_and_invalid_selection_fail_closed(client, app, headers):
    base, run, study_id = _ready(app, client, headers, n=15)
    complete = client.get(base + "/priority-comparison", params={
        "run": run, "label": "synthetic", "selected_count": 15,
    })
    assert complete.status_code == 200, complete.text
    assert all(
        item["largest_unselected_span"] is None and
        item["selected_ordinal_coverage"]["maximum_nearest_selected_imported_positions"] == 0
        for item in complete.json()["methods"]
    )
    for count in (0, 16):
        response = client.get(base + "/priority-comparison", params={
            "run": run, "label": "synthetic", "selected_count": count,
        })
        assert response.status_code == 422
    incomplete_base, incomplete_run, _ = _ready(app, client, headers, n=12, partial=True)
    incomplete = client.get(incomplete_base + "/priority-comparison", params={
        "run": incomplete_run, "label": "synthetic", "selected_count": 6,
    })
    assert incomplete.status_code == 422
    other_study_run = client.get(incomplete_base + "/priority-comparison", params={
        "run": run, "label": "synthetic", "selected_count": 6,
    })
    assert other_study_run.status_code == 404
    assert client.get("/api/studies/not-real/priority-comparison", params={
        "run": run, "label": "synthetic", "selected_count": 6,
    }).status_code == 404


def test_same_k_does_not_silently_change_review_budget():
    scores = [((i * 9) % 19) / 18 for i in range(101)]
    for k in (1, 2, 11, 51, 100, 101):
        for method in METHODS:
            selected = select_positions(scores, k, method)
            span = largest_unselected_span(101, selected)
            assert len(selected) == len(set(selected)) == k
            assert ordinal_coverage(101, selected)["maximum_nearest_selected_imported_positions"] >= 0
            if k == 101:
                assert span is None
            else:
                assert span and span["imported_images_not_in_queue"] >= 1
