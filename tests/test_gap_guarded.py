"""Property and API tests for the experimental *ordinal* gap-guarded policy.

These tests use generated score arrays and software-test images only.
They do not train a medical model or use Galar outcome labels.
"""
from __future__ import annotations

import random

import pytest

from capsule_review.priority import (
    METHODS, gap_guarded_positions, largest_unselected_span,
    select_positions, uniform_midpoints,
)


def _max_omitted(n: int, selected: list[int]) -> int:
    span = largest_unselected_span(n, selected)
    return span["imported_images_not_in_queue"] if span else 0


def test_guard_invariants_cover_thousands_of_n_and_k_combinations():
    rng = random.Random(20261104)
    assert METHODS[:4] == ("score", "score_diverse", "score_bin", "uniform")
    assert METHODS[4:] == ("score_guarded",)
    checks = 0
    for n in range(1, 96):
        # Every workload, including K=1, K=N, very narrow bins and bad N/K ratios.
        scores = [rng.randrange(0, 19) / 18 for _ in range(n)]
        for k in range(1, n + 1):
            uniform = uniform_midpoints(n, k)
            actual = select_positions(scores, k, "score_guarded")
            assert actual == select_positions(scores, k, "score_guarded")
            assert len(actual) == len(set(actual)) == k
            assert all(0 <= p < n for p in actual)
            assert _max_omitted(n, actual) <= _max_omitted(n, uniform)
            assert sum(scores[p] for p in actual) + 1e-12 >= sum(
                scores[p] for p in uniform
            )
            if k == n:
                assert set(actual) == set(range(n))
            checks += 1
    assert checks == 4560


def test_constant_scores_do_not_displace_uniform_midpoint_anchors():
    for n, k in ((1, 1), (4, 3), (24, 6), (101, 51), (102, 101)):
        assert gap_guarded_positions([0.5] * n, k) == uniform_midpoints(n, k)


def test_clustered_high_scores_improve_score_without_worse_ordinal_gaps():
    n, k = 24, 6
    scores = [0.1] * n
    scores[3] = 0.95
    scores[7] = 0.85
    original = uniform_midpoints(n, k)
    guarded = select_positions(scores, k, "score_guarded")
    top = select_positions(scores, k, "score")
    assert set(guarded) != set(original)
    assert sum(scores[p] for p in guarded) > sum(scores[p] for p in original)
    assert _max_omitted(n, guarded) <= _max_omitted(n, original)
    assert _max_omitted(n, top) > _max_omitted(n, original)


def test_gap_bound_cannot_guarantee_true_annotation_or_pathology_coverage():
    # Artificial hidden event at uniform anchor 2. Favoring frame 3 improves
    # the score while preserving gap bounds, but the event itself is missed.
    # Ground-truth is deliberately NOT an argument to the selection policy.
    scores = [0.1] * 24
    scores[3] = 0.99
    uniform = uniform_midpoints(24, 6)
    guarded = select_positions(scores, 6, "score_guarded")
    hidden_positive = {2}
    assert hidden_positive & set(uniform)
    assert not hidden_positive & set(guarded)
    assert _max_omitted(24, guarded) <= _max_omitted(24, uniform)


def test_guard_rejects_all_invalid_inputs_via_validated_dispatcher():
    for scores, k in (([], 1), ([0.1, 0.2], 0),
                      ([0.1, 0.2], 3), ([0.1, 0.2], True),
                      ([0.1, float("nan")], 1),
                      ([0.1, float("inf")], 1),
                      ([-0.01, 0.3], 1), ([1.01, 0.3], 1),
                      ([True, 0.5], 1)):
        with pytest.raises(ValueError):
            select_positions(scores, k, "score_guarded")


def test_guarded_policy_live_api_is_label_blind_and_does_not_edit_reviews(
    app, client, headers
):
    from capsule_review.importer import import_sources
    from PIL import Image
    import io

    def frames():
        for i in range(24):
            buffer = io.BytesIO()
            Image.new("RGB", (16, 16), (i * 5, 20, 70)).save(buffer, "PNG")
            yield f"synthetic_{i:04d}.png", buffer.getvalue()

    study = import_sources(
        app.state.store, frames(), title="Generated guarded-rank test",
        source="Synthetic only", synthetic=True,
    )
    base = f"/api/studies/{study['id']}"
    frame_hashes = client.get(base + "/manifest").json()["frames"]
    scores = [0.1] * 24
    scores[3] = 0.95
    scores[7] = 0.85
    posted = client.post(base + "/predictions", headers=headers, json={
        "schema_version": 1, "study_id": study["id"],
        "model": {"name": "Generated ordinal-score fixture", "version": "1",
                  "run_id": "guarded-synthetic-v1"},
        "predictions": [
            {"position": i, "image_sha256": frame_hashes[i]["source_sha256"],
             "label": "software-test", "score": scores[i]}
            for i in range(24)
        ],
    })
    assert posted.status_code == 201, posted.text
    run = posted.json()["run_id"]
    saved = client.put(base + "/frames/0/review", headers=headers, json={
        "revision": 0, "bookmarked": True,
        "note": "Unchanged human note", "label": "Review later",
    })
    assert saved.status_code == 200, saved.text
    params = {"run": run, "label": "software-test", "selected_count": 6}
    for method in METHODS:
        response = client.get(base + "/priority", params={**params, "method": method,
                                                          "page_size": 50})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["no_reference_labels_read"] is True
        assert data["reviewer_notes_and_selection_unchanged"] is True
        assert len(data["items"]) == 6
    baseline = client.get(base + "/priority", params={**params, "method": "uniform"})
    guarded = client.get(base + "/priority",
                         params={**params, "method": "score_guarded"})
    assert guarded.json()["largest_unselected_span"]["imported_images_not_in_queue"] <= (
        baseline.json()["largest_unselected_span"]["imported_images_not_in_queue"]
    )
    comparison = client.get(base + "/priority-comparison", params=params)
    assert comparison.status_code == 200, comparison.text
    assert {item["method"] for item in comparison.json()["methods"]} == set(METHODS)
    with app.state.store.connect() as db:
        db.execute(
            "UPDATE frames SET reference_labels=? WHERE study_id=? AND position=2",
            ('{"secret_blood_annotation": 1}', study["id"]),
        )
    unchanged = client.get(base + "/priority",
                           params={**params, "method": "score_guarded"})
    assert unchanged.json() == guarded.json()
    assert "secret_blood_annotation" not in str(unchanged.json())
    assert client.get(base + "/frames/0").json()["review"]["note"] == "Unchanged human note"


def test_large_workload_is_bounded_without_quadratic_scan():
    # 200k positions are supported by the existing selector API. Two linear
    # coordinate sweeps should remain practical even with sparse high scores.
    n = 200_000
    scores = [0.1] * n
    for i in range(0, n, 97):
        scores[i] = 0.9
    k = 2000
    baseline = uniform_midpoints(n, k)
    guarded = select_positions(scores, k, "score_guarded")
    assert len(guarded) == len(set(guarded)) == k
    assert _max_omitted(n, guarded) <= _max_omitted(n, baseline)
    assert sum(scores[i] for i in guarded) >= sum(scores[i] for i in baseline)
