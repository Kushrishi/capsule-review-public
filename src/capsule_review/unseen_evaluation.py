"""Pure, label-blind queue freeze and source-run outcome accounting.

A *synthetic-testable core* for the future unseen-examination study. The two
phases are deliberately separate: freeze selections before reading labels;
then evaluate only a separately approved corrected annotation CSV.

This module cannot verify external publisher ZIP identity, image pixels,
checkpoint provenance, when a commitment was deposited, or patient identity.
Those are mandatory private preflight gates, not inferred from this code.
Never commit the returned frozen object: it contains source frame identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

from capsule_review.interval_evidence import (
    parse_corrected_source_rows,
    segment_positive_runs,
)
from capsule_review.priority import (
    MAX_FRAMES,
    largest_unselected_span,
    ordinal_coverage,
    select_positions,
)

# Frozen November 4 Galar study was explicitly a *four-policy* evaluation.
# Never import the live product METHODS list: adding exploratory policies must
# not change historical queue contents or break independent numeric replay.
LOCKED_METHODS = ("score", "score_diverse", "score_bin", "uniform")
# Keep the original four-method module API for existing synthetic replay tests.
METHODS = LOCKED_METHODS
WORKLOAD_PERCENTS = (5, 10, 25, 50, 100)
RUN_STRATA = ("1-5", "6-25", "26+")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class FrozenQueues:
    """Private in-memory source identities and label-blind selected positions."""

    source_frames: tuple[int, ...]
    selection_by_percent: tuple[
        tuple[int, int, tuple[tuple[str, tuple[int, ...]], ...]], ...
    ]
    input_commitment_sha256: str

    # FrozenQueues is NOT public aggregate output; do not serialize it.


def exact_k(n: int, percent: int) -> int:
    """Integer half-up rounding, exactly as locked on November 3."""
    if type(n) is not int or not 1 <= n <= MAX_FRAMES:
        raise ValueError("Invalid imported annotated-source count.")
    if type(percent) is not int or percent not in WORKLOAD_PERCENTS:
        raise ValueError("Unrecognized locked review workload.")
    return min(n, max(1, (n * percent + 50) // 100))


def freeze_queues(
    source_frames: list[int],
    source_image_sha256: list[str],
    scores: list[float],
) -> FrozenQueues:
    """Select using identity and scores only; accepts NO annotations or labels.

    A caller must independently rehash original PNGs and verify the model
    checkpoint; a supplied hex string alone does not prove image provenance.
    Persist an immutable, timestamped private commitment BEFORE label access.
    """
    n = len(source_frames)
    if not 1 <= n <= MAX_FRAMES or len(scores) != n or len(source_image_sha256) != n:
        raise ValueError("Incomplete or oversized frozen candidate stream.")
    if any(type(f) is not int or f < 0 for f in source_frames):
        raise ValueError("Invalid original annotated source index.")
    if any(b <= a for a, b in zip(source_frames, source_frames[1:])):
        raise ValueError("Original candidate indices must increase strictly.")
    if any(type(h) is not str or _SHA256.fullmatch(h) is None for h in source_image_sha256):
        raise ValueError("Missing or malformed original PNG SHA-256.")
    if any(type(s) not in (int, float) or not math.isfinite(s) or not 0 <= s <= 1
           for s in scores):
        raise ValueError("Incomplete or invalid frozen score stream.")

    # Only the checksum is intended for a non-identifying public receipt.
    # Source indices, hashes, scores and queues remain in private memory.
    payload = json.dumps(
        {"schema": 1, "frames": source_frames,
         "source_sha256": source_image_sha256, "scores": scores},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    groups = []
    for percent in WORKLOAD_PERCENTS:
        k = exact_k(n, percent)
        methods = tuple(
            (method, tuple(select_positions(scores, k, method)))
            for method in LOCKED_METHODS
        )
        if any(len(positions) != k or len(set(positions)) != k
               for _, positions in methods):
            raise ValueError("A production policy broke its exact-K contract.")
        groups.append((percent, k, methods))
    return FrozenQueues(tuple(source_frames), tuple(groups), sha256(payload).hexdigest())


def evaluate_frozen_queues(frozen: FrozenQueues, corrected_source_csv: bytes) -> dict:
    """Evaluate after freeze; return aggregate-only annotation-run outcomes.

    Reject missing labels and incomplete original *annotated positions*.
    Do not silently select a new K after inspecting label availability.
    """
    if not isinstance(frozen, FrozenQueues):
        raise ValueError("A label-blind frozen selection is required.")
    rows = parse_corrected_source_rows(corrected_source_csv)
    if any(row["blood"] == "" for row in rows):
        raise ValueError("Unknown labels require a prespecified missingness decision.")
    if tuple(row["frame"] for row in rows) != frozen.source_frames:
        raise ValueError("Missing, extra or differently ordered original annotated positions.")

    positive_runs, membership = segment_positive_runs(rows)
    total_runs = len(positive_runs)
    n = len(rows)
    if len(frozen.selection_by_percent) != len(WORKLOAD_PERCENTS):
        raise ValueError("The frozen workload set changed.")
    results = []
    for (percent, k, selections), expected_percent in zip(
        frozen.selection_by_percent, WORKLOAD_PERCENTS
    ):
        if percent != expected_percent or k != exact_k(n, percent):
            raise ValueError("The frozen exact-K workload definition changed.")
        if tuple(method for method, _ in selections) != LOCKED_METHODS:
            raise ValueError("A frozen selection policy was changed.")
        methods = {}
        for method, positions in selections:
            if len(positions) != k or len(set(positions)) != k or any(
                type(p) is not int or p < 0 or p >= n for p in positions
            ):
                raise ValueError("The frozen image selection was corrupted.")
            hit = {membership[rows[p]["frame"]] for p in positions
                   if rows[p]["frame"] in membership}
            run_length_counts = {
                stratum: sum(positive_runs[i]["stratum"] == stratum for i in hit)
                for stratum in RUN_STRATA
            }
            methods[method] = {
                "distinct_positive_annotation_runs_hit": len(hit),
                "positive_annotated_images_hit": sum(
                    rows[p]["blood"] == "1" for p in positions
                ),
                "annotation_run_recall": (
                    round(len(hit) / total_runs, 8) if total_runs else None
                ),
                "run_lengths_hit": run_length_counts,
                "imported_position_coverage": ordinal_coverage(n, list(positions)),
                "largest_unselected_imported_span": (
                    largest_unselected_span(n, list(positions)) or {}
                ).get("imported_images_not_in_queue", 0),
            }
        base = methods["uniform"]["annotation_run_recall"]
        bin_recall = methods["score_bin"]["annotation_run_recall"]
        results.append({
            "review_percent": percent,
            "review_images": k,
            "policies": methods,
            "score_bin_minus_uniform_run_recall": (
                round(bin_recall - base, 8)
                if base is not None and bin_recall is not None else None
            ),
        })
    return {
        "schema_version": 1,
        "source_type": "original_corrected_annotated_positions_only",
        "imported_annotated_images": n,
        "positive_annotated_images": len(membership),
        "positive_annotation_runs": total_runs,
        "source_run_lengths": {
            stratum: sum(run["stratum"] == stratum for run in positive_runs)
            for stratum in RUN_STRATA
        },
        "score_identity_commitment_sha256": frozen.input_commitment_sha256,
        "review_results": results,
        "primary_workload_percent": 10,
        "independent_patient_validation": False,
        "clinical_validation": False,
        "annotation_runs_are_not_lesions": True,
        "original_image_pixels_rehashed_by_this_module": False,
        "source_zip_and_checkpoint_verified_by_this_module": False,
    }
