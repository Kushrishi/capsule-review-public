"""Aggregate and design integrity for the fixed exam29 fitting-cohort comparison.

No original images, patient information, model weights or private scores used.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPERIMENT=ROOT/'experiments/galar-fixed-expanded-2026-11-02'
SPEC=ROOT/'docs/GALAR_EXPANDED_FIT_SPEC.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def git_blob(data:bytes)->str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def test_frozen_spec_and_training_inputs_have_disjoint_examination_roles():
    spec=read(SPEC)
    report=read(EXPERIMENT/'training-aggregate.json')
    assert git_blob(SPEC.read_bytes())=='ac042de43b22d33a2860df06fbac03e80a1cb331'
    assert spec['frozen_before_first_new_optimization_step'] is True
    allowed=set(spec['training_data']['original_training_exam_ids'])|set(spec['training_data']['additional_fitting_exam_ids'])
    forbidden=set(spec['training_data']['strictly_forbidden_for_fitting'])|set(range(61,81))
    assert allowed==set(range(1,9))|{21,23,30}
    assert not allowed & forbidden
    assert spec['source_identity']['new_eval_exam']==29
    assert report['source_checkpoint_sha256']==spec['source_identity']['original_blood_cnn_checkpoint_sha256']
    assert report['optimization']['updates']==spec['frozen_training']['steps']==666
    assert report['optimization']['batch_size']==spec['frozen_training']['batch_size']==32
    assert report['optimization']['seed']==spec['frozen_training']['seed']==37
    assert report['optimization']['lr']==spec['frozen_training']['learning_rate']==0.0001
    assert report['optimization']['weight_decay']==spec['frozen_training']['weight_decay']==0.0001
    arm_a,arm_b=report['new_model_results']
    assert arm_a['arm']=='original_only_continued' and arm_b['arm']=='expanded_continued'
    assert set(arm_a['fitting_examinations'])==set(range(1,9))
    assert set(arm_b['fitting_examinations'])==allowed
    assert (arm_a['training_images'],arm_a['blood_positive'])==(4096,239)
    assert (arm_b['training_images'],arm_b['blood_positive'])==(7096,753)
    for arm in (arm_a,arm_b):
        assert arm['optimizer_updates']==666 and arm['sampled_instances_with_replacement'] is True
        assert [x['step'] for x in arm['training_loss_checkpoints']]==[111,222,333,444,555,666]
        assert len(arm['weights_sha256'])==64
        assert all(w>0 for w in arm['class_weights'])


def test_exam29_locked_reference_metrics_and_all_review_budgets():
    d=read(EXPERIMENT/'exam29-comparison.json')
    plan=read(ROOT/'experiments/galar-21-30-selection/aggregate.json')
    source=read(ROOT/'experiments/galar-21-30-source-index/verified-exam29.json')
    assert d['evaluation_examination']==29 and d['patient_independence_confirmed'] is False
    assert (d['primary_reference_images'],d['primary_reference_blood_positive'])==(512,122)
    assert (d['secondary_enriched_union_images'],d['secondary_enriched_union_blood_positive'])==(1009,372)
    assert d['primary_reference_blood_positive']==plan['per_examination']['29']['reference_positive_candidates']
    assert d['secondary_enriched_union_blood_positive']==source['independent_private_artifact_verification']['explicit_blood_positive_images']
    methods={m['method']:m for m in d['primary_label_blind_method_comparison']}
    assert set(methods)=={'original_checkpoint','original_only_continued','expanded_continued','red_excess'}
    assert abs(methods['original_checkpoint']['roc_auc']-0.8594367381252617)<1e-12
    assert abs(methods['expanded_continued']['roc_auc']-0.8817150063051716)<1e-12
    assert abs(methods['expanded_continued']['average_precision']-0.6511411369051572)<1e-12
    assert methods['original_only_continued']['roc_auc']<methods['original_checkpoint']['roc_auc']
    assert all(m['frames']==512 and m['blood_positive']==122 for m in methods.values())
    budget=d['primary_review_budget_curve']
    assert sorted(map(int,budget))==[5,10,25,50,75,100]
    expected_methods=set(methods)|{'uniform'}
    for pct,entry in budget.items():
        k=512*int(pct)//100
        assert entry['selected_images']==k
        assert set(entry['hits_by_method'])==expected_methods
        assert all(0<=hits<=min(122,k) for hits in entry['hits_by_method'].values())
    assert budget['5']['hits_by_method']['original_checkpoint']==19
    assert budget['5']['hits_by_method']['expanded_continued']==16
    assert budget['10']['hits_by_method']=={
        'original_checkpoint':33,'original_only_continued':31,
        'expanded_continued':35,'red_excess':19,'uniform':10}
    assert budget['25']['hits_by_method']['original_checkpoint']==81
    assert budget['25']['hits_by_method']['expanded_continued']==78
    assert budget['50']['hits_by_method']['expanded_continued']==117
    assert all(v==122 for v in budget['100']['hits_by_method'].values())
    assert not d['individual_image_identities_committed'] and not d['clinical_validity']


def test_exact_replay_receipts_and_no_private_data_in_repo():
    rec=read(EXPERIMENT/'verification.json')
    fit=read(EXPERIMENT/'training-aggregate.json')
    score=read(EXPERIMENT/'exam29-comparison.json')
    assert rec['new_model_training_checkpoint_files_byte_identical_on_independent_rerun']
    assert rec['new_exam29_private_predictions_byte_identical_on_independent_rerun']
    assert rec['new_exam29_aggregate_byte_identical_on_independent_rerun']
    assert rec['independent_sklearn_metrics_match']
    assert not rec['patient_independent_clinical_validation']
    assert hashlib.sha256((EXPERIMENT/'training-aggregate.json').read_bytes()).hexdigest()==rec['training_aggregate_sha256']
    assert hashlib.sha256((EXPERIMENT/'exam29-comparison.json').read_bytes()).hexdigest()==rec['new_exam29_aggregate_sha256']
    assert score['fixed_training_checkpoints']['original_only_continued']==fit['new_model_results'][0]['weights_sha256']
    assert score['fixed_training_checkpoints']['expanded_continued']==fit['new_model_results'][1]['weights_sha256']
    assert not any(path.suffix.lower() in {'.png','.jpg','.jpeg','.zip','.7z','.pt','.csv'}
                   for path in EXPERIMENT.rglob('*') if path.is_file())
