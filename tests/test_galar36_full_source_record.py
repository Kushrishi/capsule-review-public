"""Source-free reconciliation of the complete Galar36 development record."""
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'experiments/galar36-full-source-20261106'

def test_all_equal_workloads_reconcile_and_preserve_early_global_failure():
    a=json.loads((DIR/'aggregate.json').read_text())
    b=json.loads((DIR/'independent-check.json').read_text())
    assert a['original_source_images_verified']==13326
    assert a['blood_positive_original_annotated_images']==209
    assert a['positive_annotation_runs_not_adjudicated_lesions']==59
    assert b['annotation_run_length_counts']=={'1-5':44,'6-25':15,'26+':0}
    assert b['independent_queue_and_metric_replay_passed'] is True
    for r,s in zip(a['review_results'],b['review_results'],strict=True):
        assert r['review_images']==(13326*r['review_percent']+50)//100==s['review_images']
        for name,p in r['policies'].items():
            q=s['policies'][name]
            assert p['positive_annotated_images_hit']==q['positive_images_hit']
            assert p['distinct_positive_annotation_runs_hit']==q['annotation_runs_hit']
            assert sum(p['run_lengths_hit'].values())==q['annotation_runs_hit']
            assert p['run_lengths_hit']['26+']==0
            assert 0<=q['annotation_runs_hit']<=59
            assert q['annotation_runs_hit']<=q['positive_images_hit']<=min(209,r['review_images'])
            if r['review_percent']==100:
                assert (q['positive_images_hit'],q['annotation_runs_hit'])==(209,59)
    assert a['review_results'][0]['policies']['score']['positive_annotated_images_hit']==0
    ten=a['review_results'][1]['policies']
    assert ten['score']['positive_annotated_images_hit']<ten['uniform']['positive_annotated_images_hit']
    assert ten['score_bin']['distinct_positive_annotation_runs_hit']>ten['uniform']['distinct_positive_annotation_runs_hit']

def test_temporal_gains_do_not_hide_net_losses_or_promote_a_model():
    a=json.loads((DIR/'aggregate.json').read_text())
    b=json.loads((DIR/'independent-check.json').read_text())
    c=json.loads((DIR/'omission-mechanism.json').read_text())
    for r,s,t in zip(a['review_results'],b['review_results'],c['results'],strict=True):
        p=r['policies'];changes=s['temporal_vs_raw_run_transitions'];m=t['temporal_vs_raw']
        assert (changes['lost'],changes['gained'])==(m['lost'],m['gained'])
        assert changes['gained']-changes['lost']==p['temporal_window3_score_bin']['distinct_positive_annotation_runs_hit']-p['score_bin']['distinct_positive_annotation_runs_hit']
        if r['review_percent']<100:assert changes['lost']>changes['gained']
    assert a['model_promoted'] is False
    assert a['independent_patient_validation'] is False
    assert a['protected_11_20_reopened'] is False and a['authors_61_80_accessed'] is False
    assert a['execution_provenance']['original_galar35_inference_repeated'] is False
    old=json.loads((ROOT/'experiments/galar-unseen-11-20-20261104/aggregate.json').read_text())['budget_summary']['10']['policies']
    assert 100*(old['score_bin']['mean_defined_examination_run_recall']-old['uniform']['mean_defined_examination_run_recall'])==pytest.approx(-1.2668765,abs=1e-6)
