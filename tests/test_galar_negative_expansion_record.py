"""Non-private regression checks for frozen Galar22/24 training-only expansion."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'experiments/galar-negative-expansion-cv-2026-11-02'
sys.path.insert(0,str(ROOT/'scripts'))
import compare_galar_negative_expansion as comp


def source(path:Path):return json.loads(path.read_text(encoding='utf-8'))


def test_immutable_prefit_protocol_and_original_reserved_split():
    s=ROOT/'docs/GALAR_NEGATIVE_EXPANSION_CV_SPEC.json'
    raw=s.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert blob=='aa15f1ffaba381bb663a2ef3f0e1c578b4fd56c9'
    spec=json.loads(raw)
    assert spec['source']['new_training_only_examinations']==[22,24]
    assert spec['source']['expected_source_png_count']==11147
    assert spec['source']['expected_blood_positive_source_images']==1663
    assert spec['comparison']['frozen_folds']=={'A':[1,3,21,27,29],'B':[2,5,23,25,30],'C':[4,6,7,8]}
    assert spec['comparison']['treatment'].startswith('Same code/architecture')


def test_full_source_and_fold_integrity_without_new_exam_evaluation():
    value=source(RESULTS/'aggregate.json')
    assert value['source']['original_image_count']==11147
    assert value['source']['blood_positive_annotations']==1663
    assert set(map(int,value['source']['exam_reference_images']))==set(range(1,9))|{21,22,23,24,25,27,29,30}
    assert all(value['source']['exam_reference_images'][str(ex)]==512 for ex in (22,24))
    assert all(value['source']['exam_reference_positive'][str(ex)]==0 for ex in (22,24))
    assert value['no_reserved_exams_accessed'] is True
    assert value['clinical_validity'] is False
    assert len(value['model_records'])==3
    expected=value['prespecified_folds']
    assert set(expected)=={'A','B','C'}
    seen=[]
    for fold in value['model_records']:
        assert fold['arm']=='pooled_weighted'
        assert fold['heldout_exams']==expected[fold['fold']]
        assert not set(fold['fit_exams'])&set(fold['heldout_exams'])
        assert {22,24}<=set(fold['fit_exams'])
        assert fold['optimizer_steps']==384
        assert fold['batch_size']==32
        assert fold['seed']==37
        seen+=fold['heldout_exams']
        assert len(fold['checkpoint_sha256'])==64
        assert len(fold['private_prediction_sha256'])==64
    assert set(seen)==set(comp.ORIGINAL_EXAMS)
    assert len(seen)==len(set(seen))==14
    assert sum(value['source']['exam_reference_images'][str(ex)] for ex in seen)==7168


def test_old_new_metrics_match_published_original_baseline_exactly():
    prev=source(ROOT/'experiments/galar-exam-cv-2026-11-02/aggregate.json')
    new=source(RESULTS/'aggregate.json')
    paired=source(RESULTS/'paired_comparison.json')
    prior=prev['aggregates']['pooled_weighted']
    current=new['comparators']['pooled_weighted']['summary']
    assert paired['macro_roc_auc_high_support_6']['old']==prior['macro_auc_reference_positive_at_least_10']
    assert paired['macro_roc_auc_high_support_6']['new']==current['macro_auc_reference_positive_at_least_10']
    assert paired['macro_roc_auc_all_11_positive']['old']==prior['macro_auc_all_positive']
    assert paired['macro_roc_auc_all_11_positive']['new']==current['macro_auc_all_positive']
    assert set(paired['per_exam'])==set(prev['exam_results'])==set(new['comparators']['pooled_weighted']['per_exam'])
    for ex,entry in paired['per_exam'].items():
        old=prev['exam_results'][ex]['pooled_weighted']
        now=new['comparators']['pooled_weighted']['per_exam'][ex]
        assert entry['n']==old['n']==now['n']==512
        assert entry['blood_positive_reference_images']==old['blood_positive']==now['blood_positive']
        assert entry['baseline_roc_auc']==old['roc_auc']
        assert entry['expanded_training_roc_auc']==now['roc_auc']
        assert entry['baseline_topk_positive']==old['top_k_blood_positive']
        assert entry['expanded_topk_positive']==now['top_k_blood_positive']
    for k in ('51','128','256','512'):
        assert paired['all_14_exam_positive_image_hits_by_k'][k]=={
           'old':prior['total_positive_image_hits_by_k'][k],
           'new':current['total_positive_image_hits_by_k'][k],
           'uniform':current['total_uniform_positive_hits_by_k'][k],
        }
    assert paired['macro_roc_auc_high_support_6']['new']>paired['macro_roc_auc_high_support_6']['old']
    assert paired['all_14_exam_positive_image_hits_by_k']['51']=={'old':151,'new':153,'uniform':50}
    assert paired['per_exam']['23']['expanded_topk_positive']['51']==0
    assert paired['per_exam']['25']['expanded_topk_positive']['51']==0
    assert paired['per_exam']['29']['expanded_topk_positive']['51']<paired['per_exam']['29']['baseline_topk_positive']['51']


def test_negative_exams_and_independent_reproduction_receipts():
    new=source(RESULTS/'aggregate.json')['comparators']['pooled_weighted']['per_exam']
    for exam in ('3','5','8'):
        assert new[exam]['blood_positive']==0
        assert new[exam]['roc_auc'] is None and new[exam]['average_precision'] is None
        assert new[exam]['top_k_blood_positive']['51']==0
    verify=source(RESULTS/'verification.json')
    spotcheck=source(RESULTS/'source_pixel_spotcheck.json')
    identities=source(RESULTS/'heldout_identity_replay.json')
    assert verify['source_original_images']==11147
    assert verify['checkpoint_count']==3
    assert verify['independently_replayed_scores']==7168
    assert verify['independently_matched_topk_examination_budgets']==56
    assert verify['largest_absolute_inference_difference']==0
    assert spotcheck['independently_reloaded_original_pngs']==32
    assert spotcheck['examination_count']==16
    assert spotcheck['max_absolute_pixel_difference']==0
    assert identities['exact_original_frame_and_blood_annotation_identity_match'] is True
    assert identities['original_exam_heldout_identity_records']==identities['expanded_exam_heldout_identity_records']==7168
    assert identities['canonical_private_reference_identity_sha256']=='5ec4c132525b2ae7ceeeda4ad7a83b8142846a511d718a94fee5b40906ce6814'


def test_comparator_rejects_corrupt_source_or_fold(tmp_path,monkeypatch):
    # Build the connector-private comparator schema from the public prior aggregate:
    # this tests source exclusion guards without publishing any original frame IDs.
    old_public=source(ROOT/'experiments/galar-exam-cv-2026-11-02/aggregate.json')
    data={'source':{'original_image_count':10123},'comparators':{
       'pooled_weighted':{'per_exam':{k:row['pooled_weighted'] for k,row in old_public['exam_results'].items()},
                          'summary':old_public['aggregates']['pooled_weighted']}}}
    raw=json.dumps(data,sort_keys=True).encode('utf8')
    archive=tmp_path/'old.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('private_results/aggregate.json',raw)
    monkeypatch.setattr(comp,'EXPECTED_OLD',hashlib.sha256(raw).hexdigest())
    fresh=RESULTS/'aggregate.json'
    compared=comp.compare(archive,fresh)
    assert compared['old_fitting_images']==10123 and compared['new_fitting_images']==11147
    assert compared['macro_roc_auc_high_support_6']['new']>compared['macro_roc_auc_high_support_6']['old']
    altered=source(fresh)
    altered['model_records'][0]['heldout_exams'].append(22)
    temp=tmp_path/'changed.json';temp.write_text(json.dumps(altered))
    with pytest.raises(ValueError,match='heldout leakage|unequal optimizer'):
        comp.compare(archive,temp)
    altered=source(fresh);altered['source']['exam_reference_positive']['22']=1
    temp.write_text(json.dumps(altered))
    with pytest.raises(ValueError,match='not explicitly blood-negative'):
        comp.compare(archive,temp)


def test_public_outputs_exclude_individual_frame_data():
    for fname in ('aggregate.json','paired_comparison.json','verification.json','source_pixel_spotcheck.json','heldout_identity_replay.json'):
        raw=(RESULTS/fname).read_text()
        assert '"source_image_sha256"' not in raw
        assert '"frame"' not in raw
        assert '"source_frame_ids"' not in raw
        assert '"raw_images"' not in raw
    assert source(RESULTS/'aggregate.json')['clinical_validity'] is False
