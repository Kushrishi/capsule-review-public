"""Synthetic checks of probability calculus and source-run safeguards."""
import itertools
import math
import pytest
from capsule_review.geometry_control import (annotation_runs,bins,expected_metrics,
    metrics,winner_probabilities,analyze)

def test_tie_distribution_matches_exhaustive_permutations():
    for n in range(1,7):
        for m in range(1,n+1):
            winners=[min(c) for c in itertools.combinations(range(n),m)]
            p=winner_probabilities(n,m)
            assert sum(p)==pytest.approx(1)
            assert p==pytest.approx([winners.count(i)/len(winners) for i in range(n)])

def test_exact_expectation_spanning_bins_matches_enumeration():
    y=[0,1,1,1,0,1];s=[.1,.4,.3,.2,.9,.6]
    r=annotation_runs(y,list(range(6)),1)
    samples=[metrics(y,r,list(c)) for c in itertools.product(range(3),range(3,6))]
    e=expected_metrics(y,r,s,2,permuted_scores=True)
    assert e['runs_reached']==pytest.approx(sum(x['runs_reached'] for x in samples)/9)
    assert e['positive_images']==pytest.approx(sum(x['positive_images'] for x in samples)/9)
    # A run crossing bins must not be double counted.
    assert e['runs_reached']<sum(y)/3

def test_ties_preserve_earliest_rule_in_expectation():
    y=[0,0,1];s=[1,1,0];r=[[2]]
    assert expected_metrics(y,r,s,1,permuted_scores=True)['runs_reached']==0
    assert expected_metrics(y,r,s,1,permuted_scores=False)['runs_reached']==pytest.approx(1/3)

def test_gaps_split_runs_and_unknown_is_not_negative():
    assert annotation_runs([1,1,1],[10,15,25],5)==[[0,1],[2]]
    for labels in ([1,None,1],[1,-1,1],[True,0,1]):
        with pytest.raises(ValueError):annotation_runs(labels,[1,2,3],1)
    with pytest.raises(ValueError):bins(4,5)
    with pytest.raises(ValueError):metrics([1],[[0]],[0,0])
    assert metrics([0,0],[],[0])['run_recall'] is None

def test_unique_max_permutation_is_geometry_and_reproducible():
    pytest.importorskip('numpy')
    s=[(i%7)/7 for i in range(40)];y=[int(i in (2,3,4,19,30)) for i in range(40)]
    kw=dict(stride=1,percent=10,exam=123,repetitions=500,shift_repetitions=20)
    a,p=analyze(s,y,list(range(40)),**kw)
    b,q=analyze(s,y,list(range(40)),**kw)
    assert a==b and p==q
    assert a['k']==4
    assert p['permutation']==p['geometry']
    for key in ('positive_images','runs_reached'):
        c=a['controls']['within_bin_permuted_scores'][key]
        expected=a['controls']['within_bin_permuted_scores']['analytic_expected_counts'][key]
        assert abs(c['mean']-expected)<6*c['mean_mc_se']+.01
