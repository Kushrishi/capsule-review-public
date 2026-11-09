#!/usr/bin/env python3
"""Exploratory four-examination frozen-encoder transfer experiment (private outputs only).

Run only after a private data/code/weight lock and complete source-hashed 4412x576
feature extraction. Each held-out examination is excluded from the fit AND scaling.
The score records must be sealed before invoking 'evaluate'. Never use selected
outcomes or a favorable seed to change the frozen configuration.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
import random
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

EXAMS=(23,25,29,30)
SEEDS=(17,29,43)
UPDATES=1024
LR=.001
WD=.0001
RANK_WEIGHT=.5


def sha_file(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):
            h.update(b)
    return h.hexdigest()


def cycles(n,count,seed):
    if n<1 or count<1:raise ValueError('Empty schedule population')
    g=torch.Generator().manual_seed(seed)
    return torch.cat([torch.randperm(n,generator=g) for _ in range(math.ceil(count/n))])[:count]


def balanced_pair_schedule(pairs,held_out,seed,count=8192):
    groups={e:[i for i,p in enumerate(pairs) if p['exam']==e] for e in EXAMS if e!=held_out}
    if len(groups)!=3 or any(len(x)<10 for x in groups.values()):
        raise ValueError('Four supported source examinations required')
    exams=sorted(groups)
    slots=cycles(3,count,seed+100003)
    out=torch.empty(count,dtype=torch.long)
    for j,e in enumerate(exams):
        loc=torch.nonzero(slots==j).flatten()
        ix=cycles(len(groups[e]),len(loc),seed+200003+e)
        out[loc]=torch.tensor(groups[e],dtype=torch.long)[ix]
    return out


def fit_snapshot(feat,manifest,held_out,seed,arm):
    """Fit *only*; return frozen tensors and held-out endpoint logits, never outcomes."""
    if held_out not in EXAMS or seed not in SEEDS or arm not in ('classification','ranking'):
        raise ValueError('Unfrozen fold, seed or objective')
    images=manifest['images']; pairs=manifest['pairs']
    core=torch.tensor([i for i in manifest['core_indices'] if images[i]['exam']!=held_out],dtype=torch.long)
    training=[p for p in pairs if p['exam']!=held_out]
    held=[p for p in pairs if p['exam']==held_out]
    if len(training)<30 or len(held)<10:raise ValueError('Insufficient heldout source support')
    x=torch.from_numpy(np.asarray(feat,dtype=np.float32).copy());y=torch.tensor([p['blood'] for p in images],dtype=torch.long)
    # Standardization is determined exclusively by *unique training images*.
    train_indices=sorted(set(core.tolist())|{p[k] for p in training for k in ('positive_index','negative_index')})
    held_indices=sorted({p[k] for p in held for k in ('positive_index','negative_index')})
    if set(train_indices)&set(held_indices) or any(images[i]['exam']==held_out for i in train_indices):
        raise ValueError('Exam-heldout feature or source leakage')
    if {images[i]['sha256'] for i in train_indices}&{images[i]['sha256'] for i in held_indices}:
        raise ValueError('Original image SHA leakage')
    mean=x[train_indices].mean(dim=0)
    std=x[train_indices].std(dim=0,unbiased=False).clamp(min=1e-6)
    x=(x-mean)/std
    pos=torch.tensor([p['positive_index'] for p in pairs],dtype=torch.long)
    neg=torch.tensor([p['negative_index'] for p in pairs],dtype=torch.long)
    co=cycles(len(core),16384,seed).reshape(UPDATES,16)
    po=balanced_pair_schedule(pairs,held_out,seed).reshape(UPDATES,8)
    positives=8192+int(y[core[co]].sum())
    counts=(32768-positives,positives)
    weights=torch.tensor([32768/(2*n) for n in counts],dtype=torch.float32)
    torch.manual_seed(seed);random.seed(seed);np.random.seed(seed)
    linear=torch.nn.Linear(576,2)
    init_sha=hashlib.sha256(b''.join(t.detach().numpy().tobytes() for t in linear.state_dict().values())).hexdigest()
    optimizer=torch.optim.AdamW(linear.parameters(),lr=LR,weight_decay=WD)
    for step in range(UPDATES):
        indices=torch.cat([core[co[step]],pos[po[step]],neg[po[step]]])
        logits=linear(x[indices]);optimizer.zero_grad(set_to_none=True)
        ce=F.cross_entropy(logits,y[indices],weight=weights)
        z=logits[:,1]-logits[:,0]
        loss=ce if arm=='classification' else ce+RANK_WEIGHT*F.softplus(z[24:32]-z[16:24]).mean()
        if not torch.isfinite(loss):raise ValueError('Nonfinite objective')
        loss.backward();optimizer.step()
    endpoint=sorted({p[k] for p in pairs for k in ('positive_index','negative_index')})
    with torch.inference_mode():outputs=linear(x[endpoint]).tolist()
    return {'held_out_exam':held_out,'seed':seed,'arm':arm,'logits':outputs,
            'endpoint_indices':endpoint,'initial_linear_sha256':init_sha,
            'schedule_sha256':hashlib.sha256(co.numpy().tobytes()+po.numpy().tobytes()).hexdigest(),
            'class_exposures':counts,'updates':UPDATES,
            'train_core':len(core),'training_runs':len(training),'heldout_runs':len(held),
            'head_state_dict':{k:v.detach().cpu().clone() for k,v in linear.state_dict().items()},
            'scaler_mean':mean,'scaler_std':std}


def input_check(root:Path, private_root:Path,feature_file:Path,expected_sha:str):
    from recover_frozen_mobilenet import build
    if sha_file(feature_file)!=expected_sha:raise ValueError('Frozen feature input mismatch')
    images,pairs,bank,mapping,gaps=build(private_root)
    with __import__('zipfile').ZipFile(private_root/'Short_Event_Foundation_Private_Final_Evidence_20261109.zip') as z:
        m=json.loads(z.read('foundation/support-manifest-private.json'))
    feats=np.load(feature_file,allow_pickle=False)
    if feats.shape!=(4412,576) or feats.dtype!=np.float32 or not np.isfinite(feats).all():
        raise ValueError('Wrong frozen feature array')
    if len(m['pairs'])!=69 or Counter(p['exam'] for p in m['pairs'])!=Counter({23:23,25:20,29:11,30:15}):
        raise ValueError('Frozen supported runs changed')
    for i,j in enumerate(mapping):
        if j is not None and not np.array_equal(feats[i],bank[j]):
            raise ValueError('Existing 4,232 cached features have changed')
    return feats,m



def validate_prefit_lock(lock_path:Path,private_root:Path,feature_file:Path,feature_sha:str):
    """Mandatory private, externally retained pre-outcome commitment.

    Create this immutable lock *after* extracting and hashing 180 new features,
    but before fitting any head or reading any new held-out scores. The lock
    binds all scientific implementation bytes, manifest and model identities.
    """
    import zipfile
    if not lock_path.is_file() or not feature_file.is_file():
        raise ValueError('Prefit lock and feature bank required')
    lock=json.loads(lock_path.read_text())
    expected={
      'status':'PREFIT_LOCKED',
      'feature_sha256':feature_sha,
      'training_code_sha256':sha_file(Path(__file__)),
      'recovery_code_sha256':sha_file(Path(__file__).with_name('recover_frozen_mobilenet.py')),
      'published_controls_sha256':sha_file(Path(__file__).with_name('pr72_published_controls.json')),
      'official_backbone_weights_sha256':'047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f',
      'cached_old_feature_bank_sha256':'611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae',
      'exams':list(EXAMS),'seeds':list(SEEDS),'updates':UPDATES,
      'head':'single 576->2 affine layer','ranking_weight':RANK_WEIGHT,
      'runs':69,'singleton_runs':21,
      'training':'1024 AdamW updates; 16 fitting references, 8 positive and 8 negative pair endpoints per batch; last checkpoint',
      'scaling':'unique fitting images only, excluding whole held-out examination',
      'read_heldout_outcomes_after_seal':True,
    }
    with zipfile.ZipFile(private_root/'Short_Event_Foundation_Private_Final_Evidence_20261109.zip') as z:
        source_manifest_sha=hashlib.sha256(z.read('foundation/support-manifest-private.json')).hexdigest()
    expected['source_manifest_sha256']=source_manifest_sha
    for name,value in expected.items():
        if lock.get(name)!=value:
            raise ValueError('Prefit lock mismatch: '+name)
    for required in ('canary_archive_sha256','feature_extraction_receipt_sha256','canary_max_abs_difference'):
        if required not in lock or lock[required] is None:
            raise ValueError('Prefit lock missing private provenance: '+required)
    if not (isinstance(lock['canary_archive_sha256'],str) and len(lock['canary_archive_sha256'])==64 and
            isinstance(lock['feature_extraction_receipt_sha256'],str) and len(lock['feature_extraction_receipt_sha256'])==64 and
            isinstance(lock['canary_max_abs_difference'],(int,float)) and
            math.isfinite(lock['canary_max_abs_difference']) and lock['canary_max_abs_difference']>=0):
        raise ValueError('Invalid prefit extraction/canary provenance types')
    if sha_file(feature_file)!=feature_sha:raise ValueError('Feature file changed after locking')
    return sha_file(lock_path)


def execute(private_root:Path,feature_file:Path,out:Path,feature_sha:str,lock_path:Path):
    if out.exists():raise FileExistsError('Do not overwrite any existing predictions')
    lock_sha=validate_prefit_lock(lock_path,private_root,feature_file,feature_sha)
    feats,manifest=input_check(out,private_root,feature_file,feature_sha)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    out.mkdir(parents=True)
    records=[]
    # Seeding and exposure schedule fixed. All scores are recorded; no evaluation here.
    for held_out in EXAMS:
        for seed in SEEDS:
            for arm in ('classification','ranking'):
                entry=fit_snapshot(feats,manifest,held_out,seed,arm)
                model_file=out/f'fold{held_out}-seed{seed}-{arm}-head.pt'
                torch.save({'state_dict':entry.pop('head_state_dict'),
                            'scaler_mean':entry.pop('scaler_mean'),
                            'scaler_std':entry.pop('scaler_std')},model_file)
                entry['head_checkpoint_sha256']=sha_file(model_file)
                score_file=out/f'fold{held_out}-seed{seed}-{arm}-scores.json'
                score_file.write_text(json.dumps(entry,allow_nan=False,separators=(',',':')))
                records.append({'exam':held_out,'seed':seed,'arm':arm,
                                'head_file':model_file.name,'head_sha256':sha_file(model_file),
                                'score_file':score_file.name,'score_sha256':sha_file(score_file)})
    (out/'prediction-receipt.json').write_text(json.dumps({'feature_sha256':feature_sha,'prefit_lock_sha256':lock_sha,'records':records},indent=2))
    return {'fits':len(records),'folds':len(EXAMS),'seeds':len(SEEDS),'evaluation_executed':False}


def evaluate(private_root:Path,scores_dir:Path,out:Path,receipt_sha:str,lock_path:Path):
    """Evaluate only after the complete, immutable 24-fit prediction-receipt seal."""
    from recover_frozen_mobilenet import build
    if sha_file(scores_dir/'prediction-receipt.json')!=receipt_sha:
        raise ValueError('Prediction seal mismatch')
    _,m,_,_,_=build(private_root)
    rec_data=json.loads((scores_dir/'prediction-receipt.json').read_text())
    if sha_file(lock_path)!=rec_data.get('prefit_lock_sha256'):
        raise ValueError('Outcome evaluation lacks the original frozen prefit lock')
    records=rec_data['records']
    if len(records)!=24 or len({(r['exam'],r['seed'],r['arm']) for r in records})!=24:
        raise ValueError('Incomplete prescribed model set')
    rows=[]
    for rec in records:
        path=scores_dir/rec['score_file']
        if sha_file(path)!=rec['score_sha256']:raise ValueError('Sealed score digest changed')
        pred=json.loads(path.read_text())
        logits=dict(zip(pred['endpoint_indices'],pred['logits']))
        held=[p for p in m['pairs'] if p['exam']==rec['exam']]
        correct=0;ties=0;singleton_correct=0;singletons=0
        for p in held:
            zpos=logits[p['positive_index']][1]-logits[p['positive_index']][0]
            zneg=logits[p['negative_index']][1]-logits[p['negative_index']][0]
            margin=zpos-zneg
            correct+=float(margin>0)+.5*float(margin==0)
            ties+=int(margin==0)
            if p['run_length']==1:
                singletons+=1;singleton_correct+=float(margin>0)+.5*float(margin==0)
        rows.append({'exam':rec['exam'],'seed':rec['seed'],'arm':rec['arm'],'runs':len(held),
                     'ordered':correct,'pair_accuracy':correct/len(held),
                     'singletons':singletons,'singleton_ordered':singleton_correct,
                     'ties':ties})
    paired=[]
    for e in EXAMS:
        for s in SEEDS:
            c=next(r for r in rows if r['exam']==e and r['seed']==s and r['arm']=='classification')
            p=next(r for r in rows if r['exam']==e and r['seed']==s and r['arm']=='ranking')
            paired.append({'exam':e,'seed':s,'ranking_minus_classification_pp':100*(p['pair_accuracy']-c['pair_accuracy'])})
    macro={a:float(np.mean([r['pair_accuracy'] for r in rows if r['arm']==a])) for a in ('classification','ranking')}
    singleton_macro={a:float(np.mean([r['singleton_ordered']/r['singletons'] for r in rows if r['arm']==a and r['singletons']>0])) for a in ('classification','ranking')}
    seed_effects={s:float(np.mean([x['ranking_minus_classification_pp'] for x in paired if x['seed']==s])) for s in SEEDS}
    exam_effects={e:float(np.mean([x['ranking_minus_classification_pp'] for x in paired if x['exam']==e])) for e in EXAMS}
    out_json={'development_only':True,'patient_independence_verified':False,
            'model_promoted':False,'frozen_encoder_pair_accuracy':macro,
            'frozen_encoder_singleton_ordering':singleton_macro,
            'paired_ranking_effect_pp':100*(macro['ranking']-macro['classification']),
            'effect_by_seed_pp':seed_effects,'effect_by_exam_pp':exam_effects,
            'prespecified_consistency_pass':bool(all(v>0 for v in seed_effects.values()) and
                     all(v>=0 for v in exam_effects.values()) and
                     singleton_macro['ranking']>=singleton_macro['classification']),
            'records':rows,'paired':paired}
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError('Refusing to overwrite outcomes')
    out.write_text(json.dumps(out_json,indent=2,allow_nan=False))
    return {'macro_pair_accuracy':macro,'prespecified_consistency_pass':out_json['prespecified_consistency_pass']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('fit','evaluate'))
    ap.add_argument('--private-root',type=Path,required=True)
    ap.add_argument('--features',type=Path)
    ap.add_argument('--feature-sha',type=str)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--scores',type=Path)
    ap.add_argument('--receipt-sha',type=str)
    ap.add_argument('--lock',type=Path,help='privately sealed prefit comparison contract; required for both actions')
    x=ap.parse_args()
    if x.action=='fit':
        if not x.features or not x.feature_sha or not x.lock:
            ap.error('fit requires --features, --feature-sha and --lock')
        result=execute(x.private_root,x.features,x.output,x.feature_sha,x.lock)
    else:
        if not x.scores or not x.receipt_sha or not x.lock:
            ap.error('evaluate requires --scores, --receipt-sha and --lock')
        result=evaluate(x.private_root,x.scores,x.output,x.receipt_sha,x.lock)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
