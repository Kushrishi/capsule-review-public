#!/usr/bin/env python3
"""Independent, source-safe replay for the frozen MobileNet short-event study.

This implementation DOES NOT import the fitting script or its evaluator.
Private individual logits and image membership are read only from provided
private folders and never emitted in report output. It compares the full
frozen representation (classification/ranking) against PR72's published
compact-CNN aggregate cells on the same 69 held-out runs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
import torch

EXAMS=(23,25,29,30)
SEEDS=(17,29,43)
ARMS=('classification','ranking')


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


def published_controls(path:Path):
    d=json.loads(path.read_text())
    if d['cohort']!='expanded_balanced69': raise ValueError('Wrong historical comparator cohort')
    rows={}
    for exam,seed,arm,n,ordered,singletons,singleton_ordered in d['cells']:
        k=(exam,seed,arm)
        if k in rows or exam not in EXAMS or seed not in SEEDS or arm not in ARMS:
            raise ValueError('Unexpected historical comparator key')
        if n not in (23,20,11,15) or not(0<=ordered<=n) or not (0<=singleton_ordered<=singletons):
            raise ValueError('Invalid historical aggregate')
        rows[k]={'pairs':n,'ordered':ordered,'singletons':singletons,
                 'singleton_ordered':singleton_ordered,'pair_accuracy':ordered/n,
                 'singleton_accuracy':singleton_ordered/singletons}
    if len(rows)!=24: raise ValueError('Missing PR72 historical comparator cells')
    return rows


def replay_one(held_pairs, endpoint_indices, logits):
    """Use only numerical logits and the held-out source manifest, with no fitting imports."""
    lookup={int(i):np.asarray(x,dtype=np.float64) for i,x in zip(endpoint_indices,logits)}
    if len(lookup)!=len(endpoint_indices) or len(lookup)!=len(logits):
        raise ValueError('Duplicate endpoint indices or mismatched predictions')
    margins=[];singleton=[]
    for p in held_pairs:
        a=lookup[p['positive_index']];b=lookup[p['negative_index']]
        if a.shape!=(2,) or b.shape!=(2,) or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError('Invalid frozen logit record')
        margin=float((a[1]-a[0])-(b[1]-b[0]))
        margins.append(margin)
        if p['run_length']==1:singleton.append(margin)
    if len(margins)==0 or len(singleton)==0:raise ValueError('Empty held-out run or singleton denominator')
    correct=sum(float(m>0)+.5*float(m==0) for m in margins)
    scorrect=sum(float(m>0)+.5*float(m==0) for m in singleton)
    return {'pairs':len(margins),'ordered':correct,'singletons':len(singleton),
            'singleton_ordered':scorrect,'pair_accuracy':correct/len(margins),
            'singleton_accuracy':scorrect/len(singleton),
            'ties':sum(m==0 for m in margins)}


def effects(rows, controls):
    """Prespecified, explicitly conditional advancement diagnostics."""
    if set(rows)!=set(controls):raise ValueError('Non-matched representations or incomplete cells')
    def summary(data, arm, metric):
        return float(np.mean([data[(e,s,arm)][metric] for e in EXAMS for s in SEEDS]))
    def contrast(data, arm1, data2, arm2, metric):
        per_seed={str(s):100*float(np.mean([data[(e,s,arm1)][metric]-data2[(e,s,arm2)][metric] for e in EXAMS])) for s in SEEDS}
        per_exam={str(e):100*float(np.mean([data[(e,s,arm1)][metric]-data2[(e,s,arm2)][metric] for s in SEEDS])) for e in EXAMS}
        macro=100*float(np.mean([data[(e,s,arm1)][metric]-data2[(e,s,arm2)][metric] for e in EXAMS for s in SEEDS]))
        return {'macro_pp':macro,'by_seed_pp':per_seed,'by_exam_pp':per_exam}
    comparisons={
       'mobilenet_ranking_minus_mobilenet_classification':contrast(rows,'ranking',rows,'classification','pair_accuracy'),
       'mobilenet_classification_minus_pr72_cnn_classification':contrast(rows,'classification',controls,'classification','pair_accuracy'),
       'mobilenet_ranking_minus_pr72_cnn_ranking':contrast(rows,'ranking',controls,'ranking','pair_accuracy'),
    }
    singleton={
       'mobilenet_ranking_minus_mobilenet_classification':contrast(rows,'ranking',rows,'classification','singleton_accuracy'),
       'mobilenet_classification_minus_pr72_cnn_classification':contrast(rows,'classification',controls,'classification','singleton_accuracy'),
       'mobilenet_ranking_minus_pr72_cnn_ranking':contrast(rows,'ranking',controls,'ranking','singleton_accuracy'),
    }
    def passes(c,s):
        return bool(c['macro_pp']>0 and all(v>0 for v in c['by_seed_pp'].values()) and
                    all(v>=0 for v in c['by_exam_pp'].values()) and s['macro_pp']>=0)
    gate={k:passes(v,singleton[k]) for k,v in comparisons.items()}
    # A frozen encoder should outperform the appropriate prior CNN control before a
    # full-source benchmark is even considered. The within-encoder objective check
    # is separately required if advancing ranking rather than classification.
    gate['classification_eligible_for_further_benchmark']=gate['mobilenet_classification_minus_pr72_cnn_classification']
    gate['ranking_eligible_for_further_benchmark']=bool(
        gate['mobilenet_ranking_minus_pr72_cnn_ranking'] and
        gate['mobilenet_ranking_minus_mobilenet_classification'])
    return {
      'macro_pair_ordering_pct':{label:{arm:100*summary(table,arm,'pair_accuracy') for arm in ARMS}
                                 for label,table in [('published_cnn',controls),('frozen_mobilenet',rows)]},
      'macro_singleton_ordering_pct':{label:{arm:100*summary(table,arm,'singleton_accuracy') for arm in ARMS}
                                 for label,table in [('published_cnn',controls),('frozen_mobilenet',rows)]},
      'paired_comparisons':comparisons,'singleton_comparisons':singleton,'consistency_checks':gate,
      'not_independent_patient_validation':True,'clinical_model_promoted':False,
    }


def verify_predictions(private_root:Path,score_root:Path,receipt_hash:str,controls:Path,feature_file:Path|None=None):
    # Import only the source-audit helper; the production fitting/evaluation script
    # is intentionally not imported for metric calculation.
    from recover_frozen_mobilenet import build
    if sha(score_root/'prediction-receipt.json')!=receipt_hash:
        raise ValueError('Pre-outcome seal mismatch')
    images,pairs,features,mapping,found=build(private_root)
    receipt=json.loads((score_root/'prediction-receipt.json').read_text())
    if len(receipt['records'])!=24:raise ValueError('Incomplete fit collection')
    feature_array=None
    if feature_file is not None:
        if sha(feature_file)!=receipt['feature_sha256']:
            raise ValueError('Fitted feature bank does not match the pre-outcome seal')
        feature_array=np.load(feature_file,allow_pickle=False)
        if feature_array.shape!=(4412,576) or feature_array.dtype!=np.float32 or not np.isfinite(feature_array).all():
            raise ValueError('Invalid frozen feature bank for independent model reconstruction')
    # Independently verify the frozen source/feature mapping; earlier feature rows
    # must not be silently overwritten by newly extracted representations.
    if feature_array is not None:
        for i,j in enumerate(mapping):
            if j is not None and not np.array_equal(feature_array[i],features[j]):
                raise ValueError('Previously verified cached feature row was modified')
    baseline=published_controls(controls)
    rows={}; model_checks=[]
    for r in receipt['records']:
        k=(r['exam'],r['seed'],r['arm'])
        if k not in baseline or k in rows:raise ValueError('Unprescribed fit')
        f=score_root/r['score_file'];ck=score_root/r['head_file']
        if sha(f)!=r['score_sha256'] or sha(ck)!=r['head_sha256']:
            raise ValueError('Frozen checkpoint or score digest changed')
        scores=json.loads(f.read_text())
        for name,expected in (('held_out_exam',r['exam']),('seed',r['seed']),('arm',r['arm']),
                              ('head_checkpoint_sha256',r['head_sha256'])):
            if scores.get(name)!=expected:
                raise ValueError('Score record/receipt mismatch: '+name)
        held=[p for p in pairs if p['exam']==r['exam']]
        if scores.get('heldout_runs')!=len(held):
            raise ValueError('Record does not match prespecified held-out run count')
        val=replay_one(held,scores['endpoint_indices'],scores['logits'])
        if val['pairs']!=baseline[k]['pairs'] or val['singletons']!=baseline[k]['singletons']:
            raise ValueError('Different held-out source support than PR72')
        rows[k]=val
        # Independently reconstruct the linear head and normalization from the
        # saved frozen checkpoint. Do not import fitting or evaluation code.
        if feature_array is not None:
            state=torch.load(ck,map_location='cpu',weights_only=True)
            w=state['state_dict']['weight'].detach().numpy().astype(np.float32)
            b=state['state_dict']['bias'].detach().numpy().astype(np.float32)
            mu=state['scaler_mean'].detach().numpy().astype(np.float32)
            sd=state['scaler_std'].detach().numpy().astype(np.float32)
            if w.shape!=(2,576) or b.shape!=(2,) or mu.shape!=(576,) or sd.shape!=(576,) or np.any(sd<=0):
                raise ValueError('Incorrect saved head or scaler shape')
            ix=scores['endpoint_indices']
            independent=((feature_array[ix]-mu)/sd)@w.T+b
            observed=np.asarray(scores['logits'],dtype=np.float32)
            if independent.shape!=observed.shape or not np.allclose(independent,observed,rtol=1e-5,atol=2e-5):
                raise ValueError('Independent checkpoint logits do not reproduce sealed records')
        model_checks.append({'fold':r['exam'],'seed':r['seed'],'arm':r['arm'],
                             'checkpoint_sha256':r['head_sha256'],
                             'scores_sha256':r['score_sha256']})
    if len(rows)!=24:raise ValueError('Missing paired experiment cells')
    return effects(rows,baseline),model_checks


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--private-root',type=Path,required=True)
    ap.add_argument('--scores',type=Path,required=True)
    ap.add_argument('--receipt-sha',required=True)
    ap.add_argument('--historical-controls',type=Path,default=Path(__file__).with_name('pr72_published_controls.json'))
    ap.add_argument('--features',type=Path,help='Complete frozen 4412x576 feature bank; required for independent checkpoint-logit replay')
    ap.add_argument('--output',type=Path,required=True)
    x=ap.parse_args()
    if x.features is None:ap.error('Independent checkpoint-logit replay requires --features')
    results,checks=verify_predictions(x.private_root,x.scores,x.receipt_sha,x.historical_controls,x.features)
    if x.output.exists():raise FileExistsError('Refuse to overwrite independent research audit')
    x.output.parent.mkdir(parents=True,exist_ok=True)
    results['independent_replay_count']=len(checks)
    results['baseline_contract_sha256']=sha(x.historical_controls)
    # Do not export image IDs, endpoint logits or private model checkpoint paths.
    x.output.write_text(json.dumps(results,indent=2,allow_nan=False))
    print(json.dumps({'independent_replay_count':len(checks),
                      'consistency_checks':results['consistency_checks']},indent=2))

if __name__=='__main__':main()
