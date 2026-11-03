"""Reconcile committed aggregate Galar25 scientific evidence; no medical frames."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/galar25-2026-11-02'


def read(name):
    return json.loads((BASE/name).read_text(encoding='utf8'))


def test_preacquisition_frozen_spec_integrity_and_role():
    path=ROOT/'docs/GALAR_25_TRANSFER_SPEC.json'
    raw=path.read_bytes()
    git_blob=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    assert git_blob=='1e30c6bd31feb7e7dd4c7a41cca9513b8947bb7e'
    spec=json.loads(raw)
    assert spec['acquisition']['allowed_exam']==25
    assert [v['id'] for v in spec['acquisition']['blocks']]==[2,3,4]
    assert spec['fixed_model_evaluation']['no_training_or_adaptation_on_exam25'] is True
    assert spec['fixed_model_evaluation']['no_checkpoint_selection'] is True
    assert spec['preselected_images']['uniform_positive']==14
    assert all(x not in [25] for x in spec['isolation']['never_read'])
    assert spec['fixed_model_evaluation']['reference_cohort'].startswith('512 locked label-blind')


def test_original_image_acquisition_provenance_is_consistent():
    a=read('acquisition-aggregate.json')
    assert a['source_examination']==25
    assert a['source_images_verified']==1013
    assert a['positive_blood_annotations']==265
    assert a['source_original_png_bytes']==307936304
    assert a['fit_frames']==a['uniform_reference_frames']==512
    assert a['overlap']==11
    assert a['uniform_reference_positive']==14
    assert a['enriched_fitting_positive']==256
    assert a['unique_pixel_decodes']==1013
    assert not a['complete_31gb_original_archive_md5_verified']
    assert [r['block_id'] for r in a['verified_compressed_block_receipts']]==[2,3,4]
    assert [r['selected_images_verified'] for r in a['verified_compressed_block_receipts']]==[98,657,258]
    assert sum(r['compressed_bytes'] for r in a['verified_compressed_block_receipts'])==10447872590
    assert sum(r['selected_images_verified'] for r in a['verified_compressed_block_receipts'])==1013
    for field in ('original_source_zip_sha256','private_manifest_sha256','outer_artifact_sha256'):
        assert len(a[field])==64 and all(c in '0123456789abcdef' for c in a[field])


def test_primary_model_results_preserve_negative_transfer_and_all_budgets():
    m=read('model-comparison.json')
    v=read('verification.json')
    primary=m['reference_cohort']
    assert m['examination']==25 and not m['clinical_validity']
    assert not m['training_changed'] and not m['model_selection_from_evaluation']
    assert primary['n']==512 and primary['blood_positive']==14
    assert m['enriched_union_descriptive_only']['n']==1013
    assert m['enriched_union_descriptive_only']['blood_positive']==265
    assert m['verified_source_package_sha256']==v['original_source_zip_sha256']
    assert m['verified_source_manifest_sha256']==v['private_source_manifest_sha256']
    assert v['all_1013_prediction_rows_second_pass_byte_identical']
    assert v['all_512_reference_sk_learn_auc_ap_and_budget_hits_matched']
    assert v['same_source_file_sha256_vs_prior_9129']==0
    assert v['within_new_exam_exact_decoded_pixel_duplicates']==0
    metrics=primary['rank_metrics']
    assert set(metrics)=={'original_checkpoint','original_only_continued','expanded_continued','red_excess'}
    for name,actual in metrics.items():
        assert actual['positive']==14 and actual['negative']==498
        assert 0<=actual['roc_auc']<0.5, (name,actual)
    assert abs(metrics['original_checkpoint']['roc_auc']-0.30450372920252433)<1e-12
    assert abs(metrics['original_only_continued']['roc_auc']-0.23006310958118287)<1e-12
    assert abs(metrics['expanded_continued']['roc_auc']-0.4291451520367183)<1e-12
    budgets=primary['review_budgets']
    assert set(budgets)=={'5','10','25','50','75','100'}
    assert [budgets[k]['selected'] for k in ('5','10','25','50','75','100')]==[25,51,128,256,384,512]
    expected_10={'expanded_continued':0,'original_checkpoint':0,
                 'original_only_continued':2,'red_excess':0,'uniform':1}
    assert budgets['10']['blood_positive_images_found']==expected_10
    assert budgets['100']['blood_positive_images_found']=={k:14 for k in expected_10}
    assert budgets['25']['blood_positive_images_found']['expanded_continued']==2
    assert budgets['25']['blood_positive_images_found']['original_checkpoint']==3
    assert budgets['25']['blood_positive_images_found']['uniform']==4
    assert budgets['75']['blood_positive_images_found']['expanded_continued']==14


def test_no_individual_medical_data_or_fitted_weights_enter_research_repo():
    assert not any(p.suffix.lower() in {'.csv','.png','.jpg','.jpeg','.pt','.zip','.7z','.sqlite','.db'}
                   for p in BASE.rglob('*') if p.is_file())
    comparison=read('model-comparison.json')
    assert not any(k in comparison for k in ('frame','source_frame','images','pixels','patient_id'))
    assert comparison['clinical_validity'] is False
    assert 'source_examination' not in comparison or comparison['source_examination']==25
