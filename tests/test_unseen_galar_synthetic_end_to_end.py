"""Generated-only, end-to-end tests of the frozen research selection/evaluation seam.

No medical images, checkpoints, source archives or real Galar labels are read.
The input identities are hashes of literal strings prefixed 'synthetic'.
"""
from __future__ import annotations

from dataclasses import replace
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from capsule_review import unseen_evaluation as locked


SPEC = Path(__file__).resolve().parents[1] / "docs/GALAR_UNSEEN_11_20_EVALUATION_LOCK.json"


def synthetic_inputs(n: int = 600):
    frame_ids = [5 * i for i in range(n)]
    hashes = [hashlib.sha256(f"synthetic-only-frame:{i}".encode()).hexdigest()
              for i in range(n)]
    # Deliberately wrong ranking: high scores on early negative rows.
    scores = [(n - i) / n for i in range(n)]
    return frame_ids, hashes, scores


def synthetic_labels(n: int = 600, positive_positions=(305, 306, 505, 506)):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=("frame", "blood"))
    writer.writeheader()
    for i in range(n):
        writer.writerow({"frame": i * 5,
                         "blood": "1" if i in positive_positions else "0"})
    return out.getvalue().encode("utf-8")


def test_frozen_methods_and_review_budgets_match_original_lock():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["methods"]["primary_review_percent"] == 10
    assert spec["methods"]["secondary_review_percents"] == [5, 25, 50, 100]
    assert set(spec["methods"]["policies"]) == set(locked.METHODS)
    assert spec["methods"]["selection_uses_labels"] is False
    assert tuple(spec["scope"]["locked_evaluation_examination_ids"]) == tuple(range(11, 21))
    assert tuple(spec["scope"]["authors_original_reserved_examination_ids"]) == tuple(range(61, 81))
    assert locked.WORKLOAD_PERCENTS == (5, 10, 25, 50, 100)
    assert [locked.exact_k(600, p) for p in locked.WORKLOAD_PERCENTS] == [
        30, 60, 150, 300, 600,
    ]
    assert locked.exact_k(7, 5) == 1
    assert locked.exact_k(7, 100) == 7
    assert locked.exact_k(15, 10) == 2  # Half-up, not bankers rounding.


def test_generated_stream_freeze_then_open_labels_and_record_negative_result():
    frames, hashes, scores = synthetic_inputs()
    frozen = locked.freeze_queues(frames, hashes, scores)
    assert len(frozen.input_commitment_sha256) == 64

    # Only after the commitment exists is this synthetic annotation CSV read.
    report = locked.evaluate_frozen_queues(frozen, synthetic_labels())
    assert report["imported_annotated_images"] == 600
    assert report["positive_annotated_images"] == 4
    assert report["positive_annotation_runs"] == 2
    assert report["source_run_lengths"] == {"1-5": 2, "6-25": 0, "26+": 0}
    assert [r["review_images"] for r in report["review_results"]] == [
        30, 60, 150, 300, 600,
    ]

    ten = next(x for x in report["review_results"] if x["review_percent"] == 10)
    assert ten["policies"]["uniform"]["distinct_positive_annotation_runs_hit"] == 2
    assert ten["policies"]["score"]["distinct_positive_annotation_runs_hit"] == 0
    assert ten["policies"]["score_bin"]["distinct_positive_annotation_runs_hit"] == 0
    assert ten["score_bin_minus_uniform_run_recall"] == -1.0
    for budget in report["review_results"]:
        assert set(budget["policies"]) == set(locked.METHODS)
        for result in budget["policies"].values():
            assert result["distinct_positive_annotation_runs_hit"] <= 2
            assert result["positive_annotated_images_hit"] <= 4
            assert sum(result["run_lengths_hit"].values()) == result[
                "distinct_positive_annotation_runs_hit"
            ]
            assert result["largest_unselected_imported_span"] <= 600

    final = report["review_results"][-1]
    for result in final["policies"].values():
        assert result["distinct_positive_annotation_runs_hit"] == 2
        assert result["annotation_run_recall"] == 1.0
        assert result["positive_annotated_images_hit"] == 4
        assert result["largest_unselected_imported_span"] == 0

    # Only non-identifying counts and the score identity commitment leave the evaluator.
    published = json.dumps(report, sort_keys=True)
    assert "source_frames" not in published
    assert "source_image_sha256" not in published
    assert "patient_id" not in published
    assert "scores" not in report
    assert report["independent_patient_validation"] is False
    assert report["clinical_validation"] is False
    assert report["annotation_runs_are_not_lesions"] is True
    assert report["original_image_pixels_rehashed_by_this_module"] is False
    assert report["source_zip_and_checkpoint_verified_by_this_module"] is False


def test_zero_positive_examination_has_undefined_not_zero_run_recall():
    frozen = locked.freeze_queues(*synthetic_inputs())
    result = locked.evaluate_frozen_queues(frozen, synthetic_labels(positive_positions=()))
    assert result["positive_annotated_images"] == 0
    assert result["positive_annotation_runs"] == 0
    for budget in result["review_results"]:
        assert budget["score_bin_minus_uniform_run_recall"] is None
        for method in budget["policies"].values():
            assert method["annotation_run_recall"] is None
            assert method["distinct_positive_annotation_runs_hit"] == 0


def test_missing_label_and_incomplete_source_position_fail_closed():
    frozen = locked.freeze_queues(*synthetic_inputs())
    original = synthetic_labels().decode("utf-8").splitlines()
    original[150] = original[150].split(",")[0] + ","  # unknown, not negative
    with pytest.raises(ValueError, match="Unknown labels"):
        locked.evaluate_frozen_queues(frozen, ("\n".join(original) + "\n").encode())

    original = synthetic_labels().decode("utf-8").splitlines()
    original.pop(150)  # source-index gap; never assume complete image coverage
    with pytest.raises(ValueError, match="Missing, extra"):
        locked.evaluate_frozen_queues(frozen, ("\n".join(original) + "\n").encode())

    # No well-intentioned fallback to a 512-frame sparse selection.
    frames, hashes, scores = synthetic_inputs()
    sparse = locked.freeze_queues(frames[:512], hashes[:512], scores[:512])
    with pytest.raises(ValueError, match="Missing, extra"):
        locked.evaluate_frozen_queues(sparse, synthetic_labels())


def test_invalid_score_ids_hashes_and_frozen_policies_are_rejected():
    frames, hashes, scores = synthetic_inputs()
    with pytest.raises(ValueError, match="candidate stream"):
        locked.freeze_queues(frames, hashes[:-1], scores)
    with pytest.raises(ValueError, match="strictly"):
        locked.freeze_queues([frames[1], frames[0], *frames[2:]], hashes, scores)
    with pytest.raises(ValueError, match="PNG SHA-256"):
        locked.freeze_queues(frames, ["not-a-sha", *hashes[1:]], scores)
    with pytest.raises(ValueError, match="score"):
        locked.freeze_queues(frames, hashes, [float("nan"), *scores[1:]])
    with pytest.raises(ValueError, match="score"):
        locked.freeze_queues(frames, hashes, [True, *scores[1:]])

    frozen = locked.freeze_queues(frames, hashes, scores)
    with pytest.raises(ValueError, match="workload set"):
        locked.evaluate_frozen_queues(
            replace(frozen, selection_by_percent=frozen.selection_by_percent[:-1]),
            synthetic_labels(),
        )
    changed = list(frozen.selection_by_percent)
    pct, n, methods = changed[0]
    changed[0] = (pct, n + 1, methods)
    with pytest.raises(ValueError, match="exact-K"):
        locked.evaluate_frozen_queues(
            replace(frozen, selection_by_percent=tuple(changed)),
            synthetic_labels(),
        )


def test_synthetic_label_changes_do_not_change_frozen_queue_identity():
    frozen = locked.freeze_queues(*synthetic_inputs())
    one = locked.evaluate_frozen_queues(frozen, synthetic_labels())
    two = locked.evaluate_frozen_queues(
        frozen, synthetic_labels(positive_positions=(15, 16, 17))
    )
    assert one["score_identity_commitment_sha256"] == two["score_identity_commitment_sha256"]
    assert one["positive_annotation_runs"] == 2
    assert two["positive_annotation_runs"] == 1
    assert frozen == locked.freeze_queues(*synthetic_inputs())
