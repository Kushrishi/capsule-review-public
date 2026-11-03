"""Describe source-index continuity without inferring capture time or clinical coverage."""


def summarize_source_spacing(indices: list[int | None]) -> dict:
    """Audit only adjacent *imported* source IDs; never infer unseen image contents."""
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
    if numbered != len(indices) or len(indices) < 2:
        assessment = 'unknown'
    elif nonincreasing:
        assessment = 'nonmonotonic'
    elif gaps:
        assessment = 'index-jumps'
    else:
        assessment = 'consecutive-imported-indices'
    return {
        'imported_frames': len(indices),
        'numbered_frames': numbered,
        'unnumbered_frames': len(indices) - numbered,
        'adjacent_index_jumps': gaps,
        'nonincreasing_index_steps': nonincreasing,
        'maximum_forward_index_step': max((step for step in steps if step > 0), default=None),
        'assessment': assessment,
        'capture_time_verified': False,
        'complete_original_sequence_verified': False,
    }
