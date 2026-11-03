"""Privacy, examination-separation and measured-result regression gates (no ML deps)."""
import ast
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / 'experiments' / 'galar-exam-cv-2026-11-02' / 'aggregate.json'
SPEC = ROOT / 'docs' / 'GALAR_EXAM_CV_SPEC.json'
CODE = ROOT / 'scripts' / 'galar_exam_cv.py'
EXAMS = {1,2,3,4,5,6,7,8,21,23,25,27,29,30}


def result():
    return json.loads(AGG.read_text())


def test_frozen_roles_folds_and_source_ids():
    spec = json.loads(SPEC.read_text())
    assert spec['source']['source_exams'] == sorted(EXAMS)
    assert sorted(int(e) for fold in spec['folds'].values() for e in fold['heldout']) == sorted(EXAMS)
    assert spec['model']['steps_per_fold_arm'] == 384
    assert spec['model']['batch_size'] == 32
    assert spec['model']['deterministic_seed'] == 37
    assert spec['model']['same_initial_weights_and_update_count'] is True
    assert len(spec['model']['arms']) == 2
    assert spec['reporting']['model_selection'].startswith('Retain both')
    tree = ast.parse(CODE.read_text())
    assigns = {n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
               if isinstance(n, ast.Assign) and len(n.targets)==1
               and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'EXAMS','FOLDS','ARMS'}}
    assert set(assigns['EXAMS']) == EXAMS
    assert set(assigns['ARMS']) == {'pooled_weighted','exam_balanced_jitter'}
    fold_values=list(assigns['FOLDS'].values())
    assert {x for f in fold_values for x in f} == EXAMS
    assert sum(len(x) for x in fold_values) == len(EXAMS)
    assert 'CAPSULE_CV_DATA_ROOT' in CODE.read_text()


def test_integrity_and_independent_replay():
    d=result()
    assert d['dataset']['original_images_verified']==10123
    assert d['dataset']['explicit_blood_positive_images']==1663
    assert d['dataset']['reference_images_per_exam']==512
    assert set(map(int,d['dataset']['reference_positive_per_exam']))==EXAMS
    assert {e for e,n in d['dataset']['reference_positive_per_exam'].items() if not n}=={'3','5','8'}
    assert d['private_reproducibility']['verified_predictions']==14336
    assert d['private_reproducibility']['independently_matched_topk_comparisons']==112
    assert d['private_reproducibility']['max_replay_score_difference']==0.0
    assert len(d['private_reproducibility']['trained_checkpoint_hashes'])==6
    assert d['private_reproducibility']['original_exact_execution_script_sha256']=='6b19c0c372fbf2b9cb9f792f44047616636d0fc95fa41e1d6ef328c398905adc'
    assert d['interpretation']['clinical_validity'] is False
    assert d['interpretation']['not_patient_independent'] is True


def test_every_examination_and_prespecified_review_workload():
    d=result()
    assert set(map(int,d['exam_results']))==EXAMS
    arm_names={'pooled_weighted','exam_balanced_jitter'}
    for ex, arms in d['exam_results'].items():
        assert set(arms)==arm_names
        for name, metric in arms.items():
            assert metric['n']==512
            assert metric['blood_positive'] + metric['blood_negative_labelled']==512
            assert metric['blood_positive']==d['dataset']['reference_positive_per_exam'][ex]
            assert set(metric['top_k_blood_positive'])=={'51','128','256','512'}
            assert set(metric['uniform_reference_blood_positive'])=={'51','128','256','512'}
            for k, n in metric['top_k_blood_positive'].items():
                assert 0 <= n <= min(int(k),metric['blood_positive'])
                assert metric['top_k_blood_positive']['512']==metric['blood_positive']
            if metric['blood_positive']==0:
                assert metric['roc_auc'] is None and metric['average_precision'] is None
            else:
                assert 0 <= metric['roc_auc'] <= 1 and 0 <= metric['average_precision'] <= 1


def test_preserve_weak_and_unfavorable_results():
    d=result()
    pooled=d['aggregates']['pooled_weighted']
    balanced=d['aggregates']['exam_balanced_jitter']
    assert abs(pooled['macro_auc_reference_positive_at_least_10']-0.6865482670835646)<1e-12
    assert abs(balanced['macro_auc_reference_positive_at_least_10']-0.4625667139927563)<1e-12
    assert pooled['total_positive_image_hits_by_k']['51']==151
    assert balanced['total_positive_image_hits_by_k']['51']==82
    assert pooled['total_uniform_positive_hits_by_k']['51']==50
    assert d['exam_results']['25']['pooled_weighted']['roc_auc'] < 0.2
    assert d['exam_results']['23']['pooled_weighted']['roc_auc'] < 0.5
    assert d['exam_results']['27']['pooled_weighted']['roc_auc'] > 0.9


def test_research_aggregate_has_no_private_frame_level_data():
    text=AGG.read_text()
    for key in ('"source_image_sha256"','"pixel_sha256"','"source_frame_id"',
                '"individual_scores"','"source_image_bytes"','"per_frame_labels"'):
        assert key not in text
    assert 'raw_images' not in text
