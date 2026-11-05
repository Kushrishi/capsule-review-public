"""Experimental source-contiguous, label-blind temporal score baselines.

Not connected to the local viewer or promoted as an AI model. Requires an
explicit, individually verified one-step source-index vector; sampled Galar
512-frame references are ineligible. Source indexes represent acquisition
order, NOT guaranteed elapsed time or clinical outcome. Original raw model
scores must exist at every supplied position. This code never reads labels.
"""
from __future__ import annotations

from collections import deque
import math

from capsule_review.priority import select_positions

MAX_LENGTH = 200_000


def _validate(scores: list[float], source_indices: list[int], window: int) -> None:
    if (not isinstance(scores, list) or not isinstance(source_indices, list)
        or not 1 <= len(scores) == len(source_indices) <= MAX_LENGTH):
        raise ValueError("A bounded full score and source-index stream is required.")
    if type(window) is not int or window < 1 or window % 2 == 0 or window > len(scores):
        raise ValueError("Choose an odd window within the source stream.")
    for score in scores:
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Scores must be finite uncalibrated values in [0,1].")
    if any(type(i) is not int or i < 0 or i > 10**12 for i in source_indices):
        raise ValueError("Verified nonnegative integer source indices are required.")
    if any(b - a != 1 for a, b in zip(source_indices, source_indices[1:])):
        raise ValueError("Nonconsecutive source frames: do not smooth across missing source positions.")


def temporal_max_scores(scores: list[float], source_indices: list[int], *,
                        window: int = 3) -> list[float]:
    """Return a fixed centred rolling maximum, without crossing source gaps.

    A score for frame i becomes the maximum RAW model score among verified
    positions [i-window//2, i+window//2]. At edges the window truncates.
    O(N) monotonic deque. A short signal can therefore lift its neighbours;
    this is an experimental heuristic, not pathology detection or proof of
    improved distinct-event retention.
    """
    _validate(scores, source_indices, window)
    n = len(scores)
    half = window // 2
    ranked: deque[int] = deque()
    result = []
    right_end = 0
    for i in range(n):
        right = min(n - 1, i + half)
        while right_end <= right:
            while ranked and scores[ranked[-1]] <= scores[right_end]:
                ranked.pop()
            ranked.append(right_end)
            right_end += 1
        left = max(0, i - half)
        while ranked and ranked[0] < left:
            ranked.popleft()
        result.append(float(scores[ranked[0]]))
    return result


def temporal_selection(scores: list[float], source_indices: list[int], *,
                       window: int, selected_count: int,
                       policy: str = "score_bin") -> list[int]:
    """Build exactly-K queue positions using existing policy; no label access.

    Only the established, transparent score_bin/score/score_diverse policies
    may be used offline. This is not a new viewer default and is NOT a
    clinician-validated policy.
    """
    if policy not in ("score", "score_diverse", "score_bin"):
        raise ValueError("Select a documented, fixed score-based policy.")
    values = temporal_max_scores(scores, source_indices, window=window)
    return select_positions(values, selected_count, policy)
