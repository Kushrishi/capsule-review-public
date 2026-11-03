"""Local, outcome-blind prioritization of complete imported prediction scores.

Scores are model outputs, NOT calibrated pathology probabilities. No source
annotations, reviewer notes, bookmarks, or original image pixels influence
selection. No database writes or automatic saved frames.
"""
from __future__ import annotations

import json
import math

from .store import Store

METHODS = ("score", "score_diverse", "score_bin", "uniform")
MAX_FRAMES = 200_000


def uniform_midpoints(length: int, selected_count: int) -> list[int]:
    """Select exactly K independently spaced ordinal imported positions."""
    if type(length) is not int or type(selected_count) is not int or not 1 <= selected_count <= length:
        raise ValueError("Review count must be within the imported image count.")
    selected = [(2 * i + 1) * length // (2 * selected_count) for i in range(selected_count)]
    if len(set(selected)) != selected_count:
        raise ValueError("Uniform midpoint selection yielded duplicate positions.")
    return selected


def select_positions(scores: list[float], selected_count: int, method: str) -> list[int]:
    """Deterministic exactly-K review queue using scores, not ground-truth.

    Score method: descending raw score. Diverse method: greedy score ranking
    suppressing nearby imported positions; fill any shortfall by score.
    Bin method: select highest score in each of K chronological bins.
    Uniform: independent midpoint sample, recomputed at each K.
    """
    n = len(scores)
    if not 1 <= n <= MAX_FRAMES or type(selected_count) is not int or not 1 <= selected_count <= n:
        raise ValueError("Requested review workload exceeds imported frames.")
    if method not in METHODS:
        raise ValueError("Unrecognized selection method.")
    if any(type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1
           for score in scores):
        raise ValueError("Prediction scores must be finite numbers from zero to one.")
    if method == "uniform":
        return uniform_midpoints(n, selected_count)

    ranked = sorted(range(n), key=lambda p: (-scores[p], p))
    if method == "score":
        return ranked[:selected_count]
    if method == "score_bin":
        result = []
        for bin_id in range(selected_count):
            start = bin_id * n // selected_count
            end = (bin_id + 1) * n // selected_count
            result.append(min(range(start, end), key=lambda p: (-scores[p], p)))
        return sorted(result, key=lambda p: (-scores[p], p))

    # Fixed and explainable, not optimized on pathology labels. Sorting
    # O(N log N), suppression O(N) total, exact K despite any score ties.
    radius = n // (2 * selected_count)
    blocked = bytearray(n)
    chosen: list[int] = []
    already = bytearray(n)
    for position in ranked:
        if not blocked[position]:
            chosen.append(position)
            already[position] = 1
            left = max(0, position - radius)
            right = min(n, position + radius + 1)
            blocked[left:right] = b"\x01" * (right - left)
        if len(chosen) == selected_count:
            return chosen
    for position in ranked:
        if not already[position]:
            chosen.append(position)
            if len(chosen) == selected_count:
                break
    if len(chosen) != selected_count or len(set(chosen)) != selected_count:
        raise ValueError("Selection did not retain the exact requested workload.")
    return chosen


def ordinal_coverage(length: int, selected: list[int]) -> dict:
    """Technical imported-position spacing; NOT source video elapsed time."""
    if (length < 1 or not selected or len(set(selected)) != len(selected)
        or not all(type(p) is int and 0 <= p < length for p in selected)):
        raise ValueError("Invalid imported-position coverage selection.")
    positions = sorted(selected)
    distances: list[int] = []
    j = 0
    for pos in range(length):
        while j + 1 < len(positions) and positions[j + 1] <= pos:
            j += 1
        distance = abs(pos - positions[j])
        if j + 1 < len(positions):
            distance = min(distance, positions[j + 1] - pos)
        distances.append(distance)
    sorted_distances = sorted(distances)
    return {
        "mean_nearest_selected_imported_positions": round(sum(distances) / length, 8),
        "p95_nearest_selected_imported_positions": sorted_distances[math.ceil(.95 * length) - 1],
        "maximum_nearest_selected_imported_positions": sorted_distances[-1],
    }


def list_prioritizable_runs(store: Store, study_id: str) -> list[dict]:
    """Only fully scored label streams are eligible for a complete queue."""
    with store.connect() as db:
        study = db.execute("SELECT frame_count FROM studies WHERE id=?", (study_id,)).fetchone()
        if study is None:
            raise LookupError("Examination not found.")
        runs = db.execute(
            "SELECT id,run_id,model_json,created_at FROM prediction_runs "
            "WHERE study_id=? ORDER BY id DESC", (study_id,)
        ).fetchall()
        result = []
        for run in runs:
            model = json.loads(run["model_json"])
            labels = [
                {
                    "name": item["label"],
                    "scored_images": item["scored_images"],
                    "complete": item["scored_images"] == study["frame_count"],
                } for item in db.execute(
                    "SELECT label, COUNT(*) AS scored_images FROM predictions "
                    "WHERE study_id=? AND run_id=? GROUP BY label ORDER BY label",
                    (study_id, run["id"])
                )
            ]
            result.append({
                "run": run["id"], "model_run_id": run["run_id"],
                "model_name": model["name"], "model_version": model["version"],
                "model_description": model.get("description", ""),
                "created_at": run["created_at"],
                "imported_images": study["frame_count"], "labels": labels,
            })
        return result


def priority_queue(store: Store, study_id: str, run: int, label: str,
                   selected_count: int, method: str, *, offset: int = 0,
                   page_size: int = 20) -> dict:
    if type(run) is not int or run <= 0 or type(label) is not str or not label or len(label) > 120:
        raise ValueError("Choose a valid installed prediction run and label.")
    if type(offset) is not int or offset < 0 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError("Invalid review queue page.")
    with store.connect() as db:
        study = db.execute("SELECT frame_count FROM studies WHERE id=?", (study_id,)).fetchone()
        if study is None:
            raise LookupError("Examination not found.")
        found = db.execute(
            "SELECT id,model_json FROM prediction_runs WHERE study_id=? AND id=?",
            (study_id, run),
        ).fetchone()
        if found is None:
            raise LookupError("The selected prediction run is not part of this examination.")
        n = study["frame_count"]
        if not 1 <= n <= MAX_FRAMES or type(selected_count) is not int or not 1 <= selected_count <= n:
            raise ValueError("Review workload must be between 1 and every imported image.")
        values = db.execute(
            "SELECT position,score FROM predictions "
            "WHERE study_id=? AND run_id=? AND label=? ORDER BY position",
            (study_id, run, label),
        ).fetchall()
        if len(values) != n or any(row["position"] != position
                                   for position, row in enumerate(values)):
            raise ValueError("The prediction label lacks a score for every imported image; no gaps are treated as negative.")
        scores = [item["score"] for item in values]
    chosen = select_positions(scores, selected_count, method)
    uniform = uniform_midpoints(n, selected_count)
    return {
        "schema_version": 1, "run": run,
        "model_name": json.loads(found["model_json"])["name"],
        "label": label, "method": method, "selected_images": selected_count,
        "imported_images": n, "offset": offset,
        "items": [{"rank": rank + 1, "position": p, "score": scores[p]}
                  for rank, p in enumerate(chosen[offset:offset + page_size], start=offset)],
        "selected_ordinal_coverage": ordinal_coverage(n, chosen),
        "uniform_ordinal_coverage_at_equal_workload": ordinal_coverage(n, uniform),
        "scores_constant": min(scores) == max(scores),
        "no_reference_labels_read": True,
        "not_diagnostic": True,
        "reviewer_notes_and_selection_unchanged": True,
        "interpretation": (
            "This is a label-blind queue of previously imported model scores "
            "on imported image positions, not calibrated pathology probabilities. "
            "Chronological distance is imported-image order, not elapsed capture time. "
            "No source annotations, patient outcomes or original-video completeness "
            "are evaluated. All frames remain available; no review is saved automatically."
        ),
    }
