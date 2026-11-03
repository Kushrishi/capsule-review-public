"""Arithmetic and evaluation-role checks for frozen real (non-clinical) results."""
import json
from pathlib import Path

import pytest


def record():
    p=Path(__file__).resolve().parents[1]/'experiments/galar-v2-2026-11-01/blood_image_pilot_metrics.json'
    return json.loads(p.read_text(encoding='utf-8'))


def test_original_historical_split_and_unopened_future_exam_ids():
    a=record()
    assert a['fitting_examinations']==list(range(1,9))
    assert a['development_examinations']==[9,10]
    assert a['future_unopened_evaluation_examinations']==list(range(11,21))
    assert a['training']['epochs']==10 and a['training']['seed']==17
    assert a['training']['best_epoch']==8
    assert a['status'].startswith('exploratory historical development')
    assert a['per_examination_support']=={'9':{'positive':0,'total':512},'10':{'positive':213,'total':512}}


def test_scores_and_comparators_do_not_conflate_absent_classes():
    a=record()
    assert a['cnn']['aggregate']['positive']==213
    assert a['cnn']['aggregate']['negative']==811
    assert a['cnn']['by_examination']['9']['roc_auc'] is None
    assert a['cnn']['by_examination']['9']['average_precision'] is None
    assert a['cnn']['by_examination']['10']['roc_auc']==pytest.approx(0.7079152731)
    assert a['cnn']['aggregate']['roc_auc']==pytest.approx(0.72618861546)
    assert a['cnn']['aggregate']['average_precision']==pytest.approx(0.62253786937)
    assert a['fixed_red_excess_comparator']['aggregate']['roc_auc']==pytest.approx(0.54529561256)
    assert a['fixed_red_excess_comparator']['aggregate']['average_precision']==pytest.approx(0.21220618507)


def test_review_budget_counts_and_all_selected_workload():
    a=record()
    cnn=a['cnn']['budgets']; red=a['fixed_red_excess_comparator']['budgets']
    assert cnn['10']['per_examination']['10']['model_positive_hits']==47
    assert red['10']['per_examination']['10']['model_positive_hits']==26
    assert cnn['10']['per_examination']['10']['uniform_positive_hits']==21
    assert cnn['10']['per_examination']['10']['random_mean_positive_hits']==pytest.approx(21.07)
    for key,expected in [('5',25),('10',51),('25',128)]:
        for exam in ['9','10']:
            v=cnn[key]['per_examination'][exam]
            assert v['selected']==expected
            assert v['model_positive_hits']<=expected
            assert v['model_positive_hits']+v['model_false_positive_selections']==expected
    assert cnn['10']['per_examination']['9']['model_false_positive_selections']==51
    assert cnn['10']['examination_macro_positive_frame_recall']==cnn['10']['pooled_positive_frame_recall']
