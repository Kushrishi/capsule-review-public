"""Non-private public results regression; safe on CI with no medical images or ML wheels."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'experiments/galar-frozen-mobilenet-2026-11-02/aggregate.json'
SPEC=ROOT/'docs/GALAR_FROZEN_MOBILENET_CV_SPEC.json'
ORIGINAL=['1','2','3','4','5','6','7','8','21','23','25','27','29','30']
FOLDS={'A':[1,3,21,27,29],'B':[2,5,23,25,30],'C':[4,6,7,8]}


def read():return json.loads(RESULT.read_text())


def test_spec_precedes_results_and_protected_cohorts_are_protected():
    specbytes=SPEC.read_bytes()
    gitblob=hashlib.sha1(b'blob '+str(len(specbytes)).encode()+b'\0'+specbytes).hexdigest()
    assert gitblob=='2440eae552535e62e1824cff6fd6437d2641e565'
    spec=json.loads(specbytes)
    assert spec['partitions']==FOLDS
    assert spec['sources']['fitting_exams']==list(map(int,ORIGINAL))
    assert set(spec['sources']['blocked_exams']).isdisjoint(spec['sources']['fitting_exams'])
    assert spec['feature_extractor']['official_pretrained_weights_sha256']=='047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'


def test_source_identity_and_model_not_promoted():
    r=read()
    assert r['sources']['original_images_source_verified']==10123
    assert r['sources']['explicit_blood_positive_annotations']==1663
    assert r['sources']['label_blind_holdout_images']==7168
    assert r['sources']['prior_compact_cnn_aggregate_sha256']=='1c06c72f97bf67c5d51f24d32c93213743b1fec484a01441a5ba107c7653608f'
    assert r['sources']['prior_cv_source_meta_sha256']=='78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2'
    assert r['experiment_protocol_git_blob_sha1']=='2440eae552535e62e1824cff6fd6437d2641e565'
    assert r['representation']['frozen'] is True
    assert r['clinical_validity'] is False
    assert r['unopened_reserved_cohorts_preserved'] is True
    assert r['status'].startswith('complete exploratory')


def test_all_exams_and_fold_leakage_protected():
    r=read()
    assert set(r['per_exam'])==set(ORIGINAL)
    assert set(r['previous_frozen_compact_cnn']['per_exam'])==set(ORIGINAL)
    assert len(r['folds'])==3
    for fold in r['folds']:
        assert fold['heldout_exams']==FOLDS[fold['fold']]
        assert not set(fold['heldout_exams']).intersection(fold['train_exams'])
        assert fold['feature_dim']==576
        assert fold['scaler_fitted_on_training_only'] is True
        assert fold['convergence_warnings']==[]
        assert fold['actual_iterations']<=300
    assert {int(k) for k in r['per_exam']}==set.union(*[set(ids) for ids in FOLDS.values()])


def test_frozen_development_baselines_and_negative_exam_handling():
    r=read()
    a=r['summary'];b=r['previous_frozen_compact_cnn']['summary']
    assert a['high_support_positive_exams']==6
    assert a['blood_negative_exams']==3
    assert abs(a['macro_auc_positive_at_least_10']-0.6153647239785971)<1e-12
    assert abs(b['macro_auc_positive_at_least_10']-0.6865482670835646)<1e-12
    assert a['total_positive_image_hits_at_k']['51']==115
    assert b['total_positive_image_hits_at_k']['51']==151
    assert a['total_uniform_hits_at_k']['51']==50
    assert a['total_positive_image_hits_at_k']['512']==526
    assert b['total_positive_image_hits_at_k']['512']==526
    for exam in ('3','5','8'):
        assert r['per_exam'][exam]['blood_positive']==0
        assert r['per_exam'][exam]['roc_auc'] is None
        assert r['per_exam'][exam]['average_precision'] is None
    assert r['per_exam']['23']['roc_auc']>b['macro_auc_all_positive']
    assert r['per_exam']['25']['roc_auc']>r['previous_frozen_compact_cnn']['per_exam']['25']['roc_auc']
    assert r['per_exam']['27']['roc_auc']<r['previous_frozen_compact_cnn']['per_exam']['27']['roc_auc']


def test_each_prespecified_workload_and_no_individual_source_records():
    r=read()
    expected={'51','128','256','512'}
    for exam,vals in r['per_exam'].items():
        assert vals['n']==512
        assert vals['blood_positive']+vals['blood_negative_labelled']==512
        assert set(vals['top_k_blood_positive'])==expected
        assert set(vals['uniform_reference_blood_positive'])==expected
        assert vals['top_k_blood_positive']['512']==vals['blood_positive']
    content=RESULT.read_text()
    for key in ('"source_frame_ids"','"private-predictions"','"individual_annotations"','"source_image_sha256"','"pretrained_model_weights"'):
        assert key not in content
