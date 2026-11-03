"""Verify and summarize fixed Galar domain-adaptation experiments (aggregate only)."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

from blood_image_pilot import roc_ap
from train_domain_blood import (SPEC_SHA256,MANIFEST_SHA256,WEIGHTS_SHA256,
                                LEGACY_METRICS_SHA256,hash_file)


def read_run(run:Path, expected_mode:str, expected_holdout:int|None)->dict:
    metrics=json.loads((run/'metrics.json').read_text())
    receipt=json.loads((run/'source-provenance.json').read_text())
    expected={'mode':expected_mode,'heldout_exam':expected_holdout,
              'frozen_spec_sha256':SPEC_SHA256,
              'frozen_manifest_sha256':MANIFEST_SHA256,
              'official_imagenet_weights_sha256':WEIGHTS_SHA256}
    if any(metrics.get(k)!=v for k,v in expected.items()):
        raise ValueError(f'Unexpected role or source for {run}')
    if (receipt['result_sha256']!=hash_file(run/'metrics.json') or
            receipt['prediction_sha256']!=hash_file(run/'predictions.csv') or
            receipt['fine_tuned_checkpoint_sha256']!=hash_file(run/'candidate-weights.pt') or
            metrics['predictions_sha256']!=receipt['prediction_sha256'] or
            metrics['fine_tuned_checkpoint_sha256']!=receipt['fine_tuned_checkpoint_sha256'] or
            receipt['manifest']!=MANIFEST_SHA256 or receipt['spec']!=SPEC_SHA256):
        raise ValueError('Frozen run artifact or receipt mismatch')
    scores=[];labels=[];exams=[]
    with (run/'predictions.csv').open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['exam','frame','source_sha256','blood_label','domain_adapted_score']:
            raise ValueError('Unexpected model-score schema')
        seen=set()
        for r in reader:
            k=(int(r['exam']),int(r['frame']))
            if k in seen:raise ValueError('Duplicate individual medical image record')
            seen.add(k)
            exams.append(k[0]);labels.append(int(r['blood_label']));scores.append(float(r['domain_adapted_score']))
    if (len(scores)!=(512 if expected_mode=='fold' else 1024) or
        sorted(set(exams)) != ([expected_holdout] if expected_mode=='fold' else [9,10]) or
        sum(labels)!=(22 if expected_holdout==1 else 208 if expected_holdout==7 else 213)):
        raise ValueError('Unexpected saved examination labels or counts')
    aggregate=roc_ap(labels,scores)
    for exam in sorted(set(exams)):
        y=[labels[i] for i,x in enumerate(exams) if x==exam]
        a=[scores[i] for i,x in enumerate(exams) if x==exam]
        exact=roc_ap(y,a)
        record=metrics['fine_tuned'][str(exam)]['rank_metrics']
        for k in ('roc_auc','average_precision','positive','negative'):
            if (exact[k] is None)!=(record[k] is None) or exact[k] is not None and abs(exact[k]-record[k])>1e-9:
                raise ValueError('Saved per-examination metric fails replay')
    return {'metrics':metrics,'aggregate':aggregate,'checkpoint_sha256':receipt['fine_tuned_checkpoint_sha256'],
            'metrics_sha256':receipt['result_sha256'],'predictions_sha256':receipt['prediction_sha256']}


def summarize(fold1:Path,fold7:Path,final:Path,original:Path,prior_probe:Path)->dict:
    folds={1:read_run(fold1,'fold',1),7:read_run(fold7,'fold',7)}
    developed=read_run(final,'final',None)
    if hash_file(original)!=LEGACY_METRICS_SHA256:
        raise ValueError('Original CNN comparator changed')
    baseline=json.loads(original.read_text())
    prior=json.loads(prior_probe.read_text())
    if (baseline['dataset_manifest_sha256']!=MANIFEST_SHA256 or
        prior['frozen_manifest_sha256']!=MANIFEST_SHA256):
        raise ValueError('Baselines not aligned to Galar source')
    comparisons={}
    for exam,record in folds.items():
        info=record['metrics']
        comparisons[str(exam)]={
            'fold_training_exams':info['fit_exams'],
            'heldout_positive_images':info['fine_tuned'][str(exam)]['rank_metrics']['positive'],
            'fine_tuned':{
                'roc_auc':info['fine_tuned'][str(exam)]['rank_metrics']['roc_auc'],
                'average_precision':info['fine_tuned'][str(exam)]['rank_metrics']['average_precision'],
                'top_10pct_positive':info['fine_tuned'][str(exam)]['budgets']['10']['positive_frames_found']},
            'previous_frozen_feature_baseline':{
                'roc_auc':info['frozen_image_features'][str(exam)]['rank_metrics']['roc_auc'],
                'average_precision':info['frozen_image_features'][str(exam)]['rank_metrics']['average_precision'],
                'top_10pct_positive':info['frozen_image_features'][str(exam)]['budgets']['10']['positive_frames_found']},
            'untrained_redness':{
                'roc_auc':info['red_excess'][str(exam)]['rank_metrics']['roc_auc'],
                'average_precision':info['red_excess'][str(exam)]['rank_metrics']['average_precision'],
                'top_10pct_positive':info['red_excess'][str(exam)]['budgets']['10']['positive_frames_found']},
            'uniform_top_10pct':info['fine_tuned'][str(exam)]['budgets']['10']['uniform_positive_frames_found'],
            'candidate_model_checkpoint_sha256':record['checkpoint_sha256']}
    final_metrics=developed['metrics']
    output={
        'study':'Capsule Review fixed train-only domain adaptation on Galar sparse images',
        'frozen_spec_sha256':SPEC_SHA256,
        'frozen_manifest_sha256':MANIFEST_SHA256,
        'train_examinations':list(range(1,9)),
        'heldout_training_folds':[1,7],
        'folds':comparisons,
        'historical_development':{
            'exams':[9,10],
            'combined':developed['aggregate'],
            'exam_10':final_metrics['fine_tuned']['10']['rank_metrics'],
            'review_10pct_exam10':{
                'fine_tuned':final_metrics['fine_tuned']['10']['budgets']['10']['positive_frames_found'],
                'original_CNN':baseline['cnn']['budgets']['10']['per_examination']['10']['model_positive_hits'],
                'uniform':final_metrics['fine_tuned']['10']['budgets']['10']['uniform_positive_frames_found']},
            'original_CNN_combined':baseline['cnn']['aggregate'],
            'original_CNN_exam10':baseline['cnn']['by_examination']['10'],
            'prior_frozen_feature_model_combined':prior['evaluation']['aggregate'],
            'new_model_checkpoint_sha256':developed['checkpoint_sha256'],
            'no_independent_validation':True},
        'comparability_note':'Domain-adapted model also changes preprocessing to whole-field resize; this is not a controlled ablation of fine-tuning alone.',
        'zero_lesion_sensitivity_claim':True,
        'zero_reader_time_claim':True,
        'unopened_reserved_Galar_holdout':'61-80',
        'source_images_committed_to_git':False,
        'decision_rule':'Do not replace the previous original CNN based on these historical development cases; use newly acquired examination-level data for external model selection.'
    }
    return output


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['fold1','fold7','final','original','prior_probe','output']:
        p.add_argument('--'+name.replace('_','-'),required=True,type=Path)
    args=p.parse_args(argv)
    if args.output.exists():raise FileExistsError('Research record exists')
    out=summarize(args.fold1,args.fold7,args.final,args.original,args.prior_probe)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
