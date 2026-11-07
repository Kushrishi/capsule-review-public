"""Protect the complete controlled comparison and its negative primary record."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_frozen_contract_and_all_models_retained():
    lock=json.loads((ROOT/'docs/MATCHED_DIVERSITY_ABLATION_LOCK_20261107.json').read_text())
    for name,key in [('matched_diversity_ablation.py','harness_sha256'),
                     ('evaluate_matched_diversity.py','evaluation_code_sha256'),
                     ('independent_matched_diversity_replay.py','independent_code_sha256')]:
        assert hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()==lock[key]
    result=json.loads((ROOT/'experiments/matched-diversity-20261107/aggregate.json').read_text())
    assert len(result['records'])==42 and result['model_promoted'] is False
    assert result['patient_independence_verified'] is False
    assert result['reserved61_80_opened'] is False
    primary=result['macro']['10']
    assert [x['seed'] for x in primary['all_paired_seeds']]==[17,29,43]
    assert primary['positive_paired_seeds']==1
    assert abs(primary['mean_paired_change_pp'])<1e-12
    assert primary['seed_range_pp'][0]<-7 and primary['seed_range_pp'][1]>11
    for arm in ['original_population','diverse_population']:
        assert sum(x[arm]['raw_run_recall'] for x in primary['all_paired_seeds'])/3 < .62
    for exam in (31,34):
        rows=[r for r in result['records'] if r['exam']==exam and r['percent']==10]
        sums={arm:sum(r['policies']['score_bin']['runs_reached'] for r in rows if r['arm']==arm)
              for arm in ['original_population','diverse_population']}
        assert sums['original_population']==sums['diverse_population']
    zero=[r for r in result['records'] if r['exam']==37]
    assert all(r['positive_runs']==0 and r['policies']['score_bin']['run_recall'] is None for r in zero)


def test_independent_replay_scope_and_source_canary():
    base=ROOT/'experiments/matched-diversity-20261107'
    proof=json.loads((base/'independent-check.json').read_text())
    assert proof['exam_budget_model_records']==42
    assert proof['policy_sets_replayed']==168
    assert proof['exact_null_expectations_replayed']==84
    assert proof['production_selector_or_evaluator_imported'] is False
    canary=json.loads((base/'source-score-canary.json').read_text())
    assert canary['new_model_canary_forward_passes']==144
    assert canary['historical_model_rescored'] is False
    assert max(r['maximum_absolute_score_difference'] for r in canary['records'])==0
