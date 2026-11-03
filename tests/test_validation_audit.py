"""Synthetic sequence tests; never evidence of anatomy-model accuracy."""

import importlib.util
from pathlib import Path
import pytest

pytest.importorskip('torch')

script = Path(__file__).resolve().parents[1] / 'scripts/audit_validation.py'
spec = importlib.util.spec_from_file_location('validation_audit', script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_boundary_window_and_error_streak_are_counted():
    # A sparse three-region sequence, with one class transition at position 3.
    result = audit.summarize_sequence([0, 0, 0, 1, 1, 1], [0, 1, 0, 0, 1, 1],
                                      [.8, .7, .9, .6, .8, .9], ['a', 'b'], radius=1)
    assert result['reference_transitions_in_sparse_sample'] == 1
    assert result['near_transition_frames'] == 2
    assert result['near_transition_error_rate'] == .5
    assert result['elsewhere_error_rate'] == .25
    assert result['longest_consecutive_error_run_in_sampled_frames'] == 1
    assert sum(x['frames'] for x in result['most_common_misclassifications']) == 2


def test_no_transitions_and_one_long_error_run():
    result = audit.summarize_sequence([0] * 5, [1] * 5, [.4] * 5, ['a', 'b'])
    assert result['near_transition_frames'] == 0
    assert result['near_transition_error_rate'] is None
    assert result['elsewhere_error_rate'] == 1
    assert result['longest_consecutive_error_run_in_sampled_frames'] == 5


def test_empty_or_misaligned_sequence_rejected():
    with pytest.raises(ValueError, match='Aligned'):
        audit.summarize_sequence([], [], [], ['a', 'b'])
    with pytest.raises(ValueError, match='Aligned'):
        audit.summarize_sequence([0, 1], [0], [.5, .5], ['a', 'b'])
