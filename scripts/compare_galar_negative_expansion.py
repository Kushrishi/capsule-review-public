"""Paired descriptive comparison: frozen 14-exam pooled CNN vs pooled CNN + 22/24 fitting-only.

Reads nonindividual published research aggregates, validates SHA/source support,
reports every previously examined held-out exam, including negative outcomes.
Never tunes models or reads reserved Galar examinations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_OLD='1c06c72f97bf67c5d51f24d32c93213743b1fec484a01441a5ba107c7653608f'
ORIGINAL_EXAMS=(1,2,3,4,5,6,7,8,21,23,25,27,29,30)
NEW_FIT_EXAMS=set(ORIGINAL_EXAMS)|{22,24}
FOLDS={'A':[1,3,21,27,29],'B':[2,5,23,25,30],'C':[4,6,7,8]}
BUDGETS=('51','128','256','512')

def sha(raw):return hashlib.sha256(raw).hexdigest()

def compare(old_zip:Path,new_aggregate:Path)->dict:
    with zipfile.ZipFile(old_zip) as z:
        raw=z.read('private_results/aggregate.json')
    if sha(raw)!=EXPECTED_OLD:
        raise ValueError('Immutable original pooled CNN research comparator altered.')
    previous=json.loads(raw)
    if previous['source']['original_image_count']!=10123:
        raise ValueError('Original fitting source count differs.')
    new_bytes=new_aggregate.read_bytes();new=json.loads(new_bytes)
    if (new['source']['original_image_count']!=11147
        or new['source']['blood_positive_annotations']!=1663
        or new['training']['steps_per_arm_fold']!=384 or new['training']['batch']!=32
        or new['training']['seed']!=37
        or new['no_reserved_exams_accessed'] is not True):
        raise ValueError('Prespecified new fitting/data/optimization roles changed.')
    assert set(map(int,new['source']['exam_reference_images']))==NEW_FIT_EXAMS
    if any(new['source']['exam_reference_images'][str(e)]!=512 for e in NEW_FIT_EXAMS):
        raise ValueError('Unexpected per-study source sample support.')
    if any(new['source']['exam_reference_positive'][str(e)]!=0 for e in (22,24)):
        raise ValueError('New fitting-only examinations were not explicitly blood-negative-labelled.')
    records=new['model_records']
    if len(records)!=3 or {r['fold'] for r in records}!=set(FOLDS) or {r['arm'] for r in records}!={'pooled_weighted'}:
        raise ValueError('New run changed locked fold or number of models.')
    for r in records:
        if (r['heldout_exams']!=FOLDS[r['fold']]
            or not {22,24}.issubset(set(r['fit_exams']))
            or len(set(r['fit_exams'])&set(r['heldout_exams']))>0
            or r['optimizer_steps']!=384 or r['batch_size']!=32):
            raise ValueError('Whole-examination heldout leakage or unequal optimizer updates.')
    previous_cases=previous['comparators']['pooled_weighted']['per_exam']
    current_cases=new['comparators']['pooled_weighted']['per_exam']
    if set(map(int,previous_cases))!=set(ORIGINAL_EXAMS) or set(map(int,current_cases))!=set(ORIGINAL_EXAMS):
        raise ValueError('Paired heldout examination coverage changed.')
    rows={}
    for exam in ORIGINAL_EXAMS:
        k=str(exam);a=previous_cases[k];b=current_cases[k]
        if a['n']!=512 or b['n']!=512 or a['blood_positive']!=b['blood_positive']:
            raise ValueError('Cannot compare models on changed reference source frames/labels.')
        if a['uniform_reference_blood_positive']!=b['uniform_reference_blood_positive']:
            raise ValueError('Locked label-blind uniform workload baseline changed.')
        rows[k]={
            'n':512,'blood_positive_reference_images':a['blood_positive'],
            'baseline_roc_auc':a['roc_auc'],'expanded_training_roc_auc':b['roc_auc'],
            'auc_difference':b['roc_auc']-a['roc_auc'] if a['roc_auc'] is not None else None,
            'baseline_average_precision':a['average_precision'],
            'expanded_average_precision':b['average_precision'],
            'baseline_topk_positive':a['top_k_blood_positive'],
            'expanded_topk_positive':b['top_k_blood_positive'],
            'uniform_topk_positive':a['uniform_reference_blood_positive'],
            'baseline_score_mean':a['score_mean'],
            'expanded_score_mean':b['score_mean'],
        }
    old_summary=previous['comparators']['pooled_weighted']['summary']
    new_summary=new['comparators']['pooled_weighted']['summary']
    return {
       'study':'Frozen negative-fitting source addition to matched three-fold pooled CNN',
       'study_role':'Exploratory, prior heldout results known; no independent clinical validation',
       'immutable_original_14_exam_pooled_cnn_aggregate_sha256':EXPECTED_OLD,
       'new_16_fitting_exam_pooled_cnn_aggregate_sha256':sha(new_bytes),
       'old_fitting_images':10123,'new_fitting_images':11147,
       'additional_training_only_examinations':[22,24],
       'heldout_examinations_exactly_the_original_14':list(ORIGINAL_EXAMS),
       'matched_training_optimizer_updates_per_fold':384,
       'macro_roc_auc_high_support_6':{
         'old':old_summary['macro_auc_reference_positive_at_least_10'],
         'new':new_summary['macro_auc_reference_positive_at_least_10'],
         'delta':new_summary['macro_auc_reference_positive_at_least_10']-old_summary['macro_auc_reference_positive_at_least_10']},
       'macro_roc_auc_all_11_positive':{
         'old':old_summary['macro_auc_all_positive'],'new':new_summary['macro_auc_all_positive'],
         'delta':new_summary['macro_auc_all_positive']-old_summary['macro_auc_all_positive']},
       'all_14_exam_positive_image_hits_by_k':{
          str(budget):{'old':old_summary['total_positive_image_hits_by_k'][str(budget)],
              'new':new_summary['total_positive_image_hits_by_k'][str(budget)],
              'uniform':new_summary['total_uniform_positive_hits_by_k'][str(budget)]}
          for budget in (51,128,256,512)},
       'per_exam':rows,
       'new_training_source_examination_positive_support':new['source']['exam_reference_positive'],
       'number_of_new_models_fitted':3,
       'all_new_images_have_private_verifiable_original_sha':True,
       'no_reserved_exams_accessed':True,'clinical_validity':False,
       'model_promotion_authorized':False,
    }


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--prior-private-zip',type=Path,required=True)
 p.add_argument('--new-aggregate',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True)
 a=p.parse_args()
 if a.out.exists():p.error('Refusing to overwrite frozen research comparison')
 result=compare(a.prior_private_zip,a.new_aggregate)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print('Exact data-only negative-training comparison results')
 print(json.dumps({k:result[k] for k in ('macro_roc_auc_high_support_6','macro_roc_auc_all_11_positive','all_14_exam_positive_image_hits_by_k')},sort_keys=True))

if __name__=='__main__':main()
