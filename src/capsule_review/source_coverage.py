"""Describe *observed* imported source-index spacing without claiming capture coverage.

A regular +5 stride between imported images can be perfectly consistent within a
sparse selection. It is not consecutive source footage, a frame rate or evidence
that unimported index positions were medically reviewed.
"""

from collections import Counter


def summarize_source_spacing(indices: list[int | None]) -> dict:
    """Audit adjacent *imported* IDs; never infer unseen image contents or times."""
    numbered = sum(index is not None for index in indices)
    gaps = 0
    nonincreasing = 0
    steps = []
    for previous, current in zip(indices, indices[1:]):
        if previous is None or current is None:
            continue
        difference = current - previous
        steps.append(difference)
        if difference > 1:
            gaps += 1
        elif difference <= 0:
            nonincreasing += 1

    # Preserve the existing assessment semantics for older clients.
    if numbered != len(indices) or len(indices) < 2:
        assessment = 'unknown'
    elif nonincreasing:
        assessment = 'nonmonotonic'
    elif gaps:
        assessment = 'index-jumps'
    else:
        assessment = 'consecutive-imported-indices'

    positive_steps = [step for step in steps if step > 0]
    observed = len(positive_steps)
    common_step = None
    common_pairs = 0
    if assessment not in ('unknown', 'nonmonotonic') and observed >= 2:
        frequencies = Counter(positive_steps)
        highest = max(frequencies.values())
        winners = [step for step, count in frequencies.items() if count == highest]
        # Tied modes and a single observed transition do not establish a
        # dominant imported-source stride.
        if len(winners) == 1:
            common_step = winners[0]
            common_pairs = highest

    return {
        'imported_frames': len(indices),
        'numbered_frames': numbered,
        'unnumbered_frames': len(indices) - numbered,
        'adjacent_index_jumps': gaps,
        'nonincreasing_index_steps': nonincreasing,
        'maximum_forward_index_step': max(positive_steps, default=None),
        'assessment': assessment,
        # These describe observed *imported pairs*, never device sampling rate.
        'observed_forward_index_steps': observed,
        'common_forward_index_step': common_step,
        'common_step_pairs': common_pairs,
        'unusual_forward_index_steps': (
            observed - common_pairs if common_step is not None else None
        ),
        'regular_observed_source_stride': bool(
            common_step is not None and common_pairs == observed
            and numbered == len(indices) and nonincreasing == 0
        ),
        'capture_time_verified': False,
        'complete_original_sequence_verified': False,
    }
