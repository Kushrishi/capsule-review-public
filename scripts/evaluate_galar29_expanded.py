"""Reproduce fixed Galar-29 blood-CNN comparison on label-blind frames.

Requires only the privately preserved exam-29 verified source package and the
three exact model checkpoints. Fitting and evaluation exams never overlap.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZipFile

import torch
from torch import nn
from capsule_review.baseline import AnatomyCNN, image_tensor
from blood_image_pilot import red_excess, roc_ap

SPEC_GIT_BLOB='ac042de43b22d33a2860df06fbac03e80a1cb331'
EXPECTED_SOURCE_ZIP='124f48bf18dc14a63241c8e2c03918eefecb89ddc465c2cacaa2151d97045be5'
EXPECTED_SOURCE_MANIFEST='d047d1eb7cc6f1f2cc740624bbd61199589abc2ae7ccddadc0876f8b0a4e7cae'
MODEL_HASHES={
    'original_checkpoint':'f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3',
    'original_only_continued':'ae88ccfedc53d8f419b3da8c0c01ca6b61361ef29858b6a536e25408ba99eefb',
    'expanded_continued':'2534d3b7982ee8c557cadc5ad3fcc4c7c4c557f899fa013e881d8655eab97111',
}
BUDGETS=(5,10,25,50,75,100)


def sha(path: Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for v in iter(lambda:f.read(1<<20),b''):
            h.update(v)
    return h.hexdigest()


def records_from_verified_source(source:Path,images:Path)->list[dict]:
    if sha(source)!=EXPECTED_SOURCE_ZIP:
        raise ValueError('Original exam29 source ZIP SHA-256 mismatch.')
    with ZipFile(source) as z:
        if z.testzip() is not None:raise ValueError('Source ZIP CRC error.')
        manifest=z.read('verified-private-manifest.json')
        if hashlib.sha256(manifest).hexdigest()!=EXPECTED_SOURCE_MANIFEST:
            raise ValueError('Frozen source frame identities or annotations changed.')
    records=json.loads(manifest)
    if len(records)!=1009:raise ValueError('Missing source frames.')
    seen=set();valid=[]
    for row in records:
        frame=int(row['frame'])
        if (row['exam']!=29 or frame in seen or frame<0 or
                row['filename']!=f'frame_{frame:06d}.PNG' or
                row['blood'] not in (0,1) or row['reference_uniform'] not in (0,1) or
                row['fit_enriched'] not in (0,1) or not (row['reference_uniform'] or row['fit_enriched'])):
            raise ValueError('Wrong evaluation examination, source ID or annotation.')
        seen.add(frame)
        p=images/row['filename']
        if not p.is_file() or p.stat().st_size!=row['source_bytes'] or sha(p)!=row['source_image_sha256']:
            raise ValueError('Original image bytes changed.')
        valid.append({**row,'image_path':p})
    valid.sort(key=lambda row:row['frame'])
    if len(valid)!=1009 or sum(r['reference_uniform'] for r in valid)!=512 or sum(
            r['blood']*r['reference_uniform'] for r in valid)!=122 or sum(r['fit_enriched'] for r in valid)!=512:
        raise ValueError('Original reference role or blood support does not match frozen study.')
    return valid


def predict(model_file:Path, expected_sha:str, records:list[dict])->list[float]:
    if sha(model_file)!=expected_sha:raise ValueError('Model checkpoint identity changed.')
    model=AnatomyCNN(2).cpu()
    data=torch.load(model_file,map_location='cpu',weights_only=True)
    original=model.state_dict()
    if not isinstance(data,dict) or set(data)!=set(original) or any(
            data[key].shape!=original[key].shape or not torch.isfinite(data[key]).all() for key in data):
        raise ValueError('Malformed, modified or nonfinite checkpoint.')
    model.load_state_dict(data,strict=True)
    model.eval()
    scores=[]
    with torch.inference_mode():
        for start in range(0,len(records),32):
            batch=torch.stack([image_tensor(r['image_path']) for r in records[start:start+32]])
            scores.extend(float(q) for q in nn.functional.softmax(model(batch),dim=1)[:,1].tolist())
    if len(scores)!=len(records) or any(not math.isfinite(q) for q in scores):
        raise ValueError('Invalid score count or nonfinite predictions.')
    return scores


def rank_metrics(rows:list[dict],scores:list[float],name:str)->dict:
    y=[r['blood'] for r in rows]
    result=roc_ap(y,scores)
    # Independent optional check, not required by the application at runtime.
    try:
        from sklearn.metrics import roc_auc_score,average_precision_score
    except ImportError:
        pass
    else:
        if (abs(result['roc_auc']-roc_auc_score(y,scores))>1e-9 or
                abs(result['average_precision']-average_precision_score(y,scores))>1e-9):
            raise ValueError('Independent ROC-AUC/AP cross-check failed.')
    return {'method':name,'frames':len(y),'blood_positive':sum(y),
            'roc_auc':float(result['roc_auc']), 'average_precision':float(result['average_precision'])}


def review_budget(rows:list[dict],values:dict[str,list[float]])->dict:
    n=len(rows)
    y=[r['blood'] for r in rows]
    ranked={name:sorted(range(n),key=lambda j:(-scores[j],j)) for name,scores in values.items()}
    table={}
    for pct in BUDGETS:
        k=n*pct//100
        counts={name:sum(y[j] for j in idx[:k]) for name,idx in ranked.items()}
        uniform=[(2*j+1)*n//(2*k) for j in range(k)]
        counts['uniform']=sum(y[j] for j in uniform)
        table[str(pct)]={'selected_images':k,'hits_by_method':counts}
    return table


def evaluate(args)->dict:
    if args.output.exists():raise FileExistsError('Refusing overwrite of existing experiment.')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    all_rows=records_from_verified_source(args.source_zip,args.images)
    models={
        'original_checkpoint':args.original_weights,
        'original_only_continued':args.original_only_weights,
        'expanded_continued':args.expanded_weights,
    }
    scores={name:predict(model,MODEL_HASHES[name],all_rows) for name,model in models.items()}
    scores['red_excess']=[red_excess(row['image_path']) for row in all_rows]
    ref_ix=[i for i,r in enumerate(all_rows) if r['reference_uniform']]
    reference=[all_rows[j] for j in ref_ix]
    ref_scores={key:[p[j] for j in ref_ix] for key,p in scores.items()}
    primary=[rank_metrics(reference,sc,key) for key,sc in ref_scores.items()]
    secondary=[rank_metrics(all_rows,sc,key) for key,sc in scores.items()]
    budget=review_budget(reference,ref_scores)
    args.output.mkdir(parents=True)
    with (args.output/'private-source-scores.csv').open('x',encoding='utf-8',newline='') as f:
        fieldnames=['exam','frame','blood','reference_uniform','source_image_sha256',*models.keys(),'red_excess']
        w=csv.DictWriter(f,fieldnames=fieldnames,lineterminator='\n')
        w.writeheader()
        for j,row in enumerate(all_rows):
            w.writerow({'exam':29,'frame':row['frame'],'blood':row['blood'],
                        'reference_uniform':row['reference_uniform'],'source_image_sha256':row['source_image_sha256'],
                        **{key:format(s[j],'.17g') for key,s in scores.items()}})
    result={
        'analysis':'Galar exam29 fixed, prospective-to-training, fitting-cohort evaluation; not blinded clinical validation',
        'evaluation_examination':29,'patient_independence_confirmed':False,
        'primary_reference_images':512,'primary_reference_blood_positive':122,
        'primary_label_blind_method_comparison':primary,
        'primary_review_budget_curve':budget,
        'secondary_enriched_union_images':1009,'secondary_enriched_union_blood_positive':372,
        'secondary_enriched_union_comparison_not_representative':secondary,
        'frozen_training_spec_git_blob':SPEC_GIT_BLOB,
        'fixed_training_checkpoints':dict(MODEL_HASHES),
        'source_private_zip_sha256':sha(args.source_zip),
        'private_image_identity_sha256':EXPECTED_SOURCE_MANIFEST,
        'individual_image_identities_committed':False,'clinical_validity':False,
        'limitations':['Exam29 source labels were previously available and its acquisition was informed by positive-run counts, so this is not a truly blinded independent test.',
                       'One evaluation examination cannot establish generalization across patients/devices.',
                       'Blood annotation is not lesion identity or diagnosis.',
                       'Sparse 512-frame reference is not entire video or reader-time measure.',
                       'Each model and workload decision is fixed; no post-evaluation model selection.']
    }
    (args.output/'aggregate.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (args.output/'private-model-hashes.json').write_text(json.dumps(MODEL_HASHES,indent=2)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for option in ('source-zip','images','original-weights','original-only-weights','expanded-weights','output'):
        p.add_argument('--'+option,dest=option.replace('-','_'),type=Path,required=True)
    args=p.parse_args(argv)
    data=evaluate(args)
    print(json.dumps({'primary':data['primary_label_blind_method_comparison'],
                      'ten_percent':data['primary_review_budget_curve']['10'],
                      'aggregate_sha256':sha(args.output/'aggregate.json')},indent=2))

if __name__=='__main__':main()
