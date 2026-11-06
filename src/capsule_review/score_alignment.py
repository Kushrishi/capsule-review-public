"""Retrospective score-alignment diagnostics, never a selection or fitting policy.

Inputs must already be an authenticated, chronological reference population.
Ordinal blocks are not anatomy/time, displacements are not exchangeable trials,
and this diagnostic cannot identify causal pathology signals or patient identity.
Only aggregate counts leave these functions.
"""
from __future__ import annotations

import math

from .priority import select_positions


def alignment_controls(labels: list[int], scores: list[float], k: int,
                       method: str, *, blocks: int = 16) -> dict:
    """Compare a fixed queue to allocation-matched and circular controls.

Block expectation is exact under uniform placement of k_b selections in each
block, conditional on its observed positive count. Circular shifts preserve the
queue geometry and the complete observed label stream; identity is included.
The orbit fraction is descriptive, not a randomization-test p-value.
"""
    n = len(labels)
    if (n != len(scores) or n < 2
            or any(type(y) is not int or y not in (0, 1) for y in labels)
            or type(blocks) is not int or not 1 <= blocks <= n
            or n % blocks or method not in ("score", "score_bin", "uniform")):
        raise ValueError("Require aligned known binary labels and equal ordinal blocks.")
    chosen = select_positions(scores, k, method)
    chosen_set = set(chosen)
    positives = sum(labels)
    observed = sum(labels[p] for p in chosen)
    width = n // blocks
    expected = sum(
        sum(p in chosen_set for p in range(start, start + width))
        * sum(labels[start:start + width]) / width
        for start in range(0, n, width)
    )
    rotations = [sum(labels[(p + shift) % n] for p in chosen)
                 for shift in range(n)]
    global_expected = k * positives / n
    if not math.isclose(sum(rotations) / n, global_expected, abs_tol=1e-12):
        raise AssertionError("Complete circular orbit must equal prevalence expectation.")
    return {
        "images": n, "positive_images": positives, "selected_images": k,
        "positive_hits": observed,
        "positive_image_recall": observed / positives if positives else None,
        "global_random_expected_hits": global_expected,
        "block_conditioned_expected_hits": expected,
        "block_conditioned_excess_recall": (
            (observed - expected) / positives if positives else None
        ),
        "circular_alignment": {
            "offset_count_including_identity": n,
            "mean_hits": sum(rotations) / n,
            "minimum_hits": min(rotations), "maximum_hits": max(rotations),
            "fraction_offsets_at_least_observed": sum(
                value >= observed for value in rotations
            ) / n,
            "inferential_p_value": False,
        },
    }


def summarize_alignment(records: list[dict]) -> dict:
    """Equal-positive-exam summaries, with a concentration sensitivity range."""
    if not records:
        raise ValueError("No examination records supplied.")
    defined = [r for r in records if r["positive_images"] > 0]
    excess = [r["block_conditioned_excess_recall"] for r in defined]
    count = len(defined)
    mean = lambda values: sum(values) / len(values) if values else None
    return {
        "examinations": len(records), "positive_examinations": count,
        "positive_images": sum(r["positive_images"] for r in records),
        "positive_hits": sum(r["positive_hits"] for r in records),
        "block_conditioned_expected_hits": sum(
            r["block_conditioned_expected_hits"] for r in records
        ),
        "global_random_expected_hits": sum(
            r["global_random_expected_hits"] for r in records
        ),
        "macro_positive_image_recall": mean(
            [r["positive_image_recall"] for r in defined]
        ),
        "macro_block_conditioned_expected_recall": mean([
            r["block_conditioned_expected_hits"] / r["positive_images"]
            for r in defined
        ]),
        "macro_block_conditioned_excess_recall": mean(excess),
        "excess_positive_negative_tied_examinations": {
            "positive": sum(x > 0 for x in excess),
            "negative": sum(x < 0 for x in excess),
            "tied": sum(x == 0 for x in excess),
        },
        "leave_one_positive_exam_out_excess_range": (
            [min((sum(excess) - x)/(count - 1) for x in excess),
             max((sum(excess) - x)/(count - 1) for x in excess)]
            if count > 1 else None
        ),
    }
