"""Synthetic-only tests: never load private medical sources in public CI."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from diagnose_representation_transfer import sign_margin, summarise_consensus


def test_margin_positive_and_wrong_and_tie():
    ix = {100: 0, 200: 1}
    assert sign_margin([[0., 2.], [0., 1.]], ix, 100, 200) == 1.
    assert sign_margin([[0., 1.], [0., 2.]], ix, 100, 200) == 0.
    assert sign_margin([[0., 1.], [1., 2.]], ix, 100, 200) == .5


def test_margin_is_class_logit_difference_not_raw_positive_logit():
    # The larger positive-class logit is not necessarily the larger class margin.
    assert sign_margin([[10., 11.], [0., 2.]], {10: 0, 20: 1}, 10, 20) == 0.


def test_margin_missing_source_endpoint_fails():
    with pytest.raises(ValueError, match='source-supported'):
        sign_margin([[0., 1.], [1., 0.]], {1: 0, 2: 1}, 1, 3)


def test_margin_mismatched_index_count_fails():
    with pytest.raises(ValueError, match='indices'):
        sign_margin([[0., 1.], [1., 0.]], {1: 0}, 1, 2)


def test_margin_nonfinite_fails():
    with pytest.raises(ValueError, match='logits'):
        sign_margin([[0., float('nan')], [1., 0.]], {1: 0, 2: 1}, 1, 2)


def test_consensus_counts_all_three_and_singletons():
    seeds = [[1, 0, 1, 0], [1, 0, 0, 1], [1, 0, 1, 1]]
    out = summarise_consensus(seeds, [1, 1, 0, 0])
    assert out == {'runs': 4, 'all_three_correct': 1, 'all_three_wrong': 1,
                   'mixed_seed_decisions': 2, 'singleton_runs': 2,
                   'singleton_all_three_wrong': 1, 'singleton_mixed_seed_decisions': 0}


def test_consensus_rejects_a_mismatched_run_count():
    with pytest.raises(ValueError, match='same distinct runs'):
        summarise_consensus([[1, 0], [1], [1, 1]], [True, False])


def test_consensus_rejects_nonbinary_ties():
    with pytest.raises(ValueError, match='Non-binary'):
        summarise_consensus([[.5], [1], [0]], [True])


def test_consensus_rejects_any_missing_seed():
    with pytest.raises(ValueError, match='same distinct runs'):
        summarise_consensus([[1], [1]], [True])
