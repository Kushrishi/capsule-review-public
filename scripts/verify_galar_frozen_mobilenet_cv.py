"""Independent replay of saved MobileNet feature-bank/logistic model predictions.

Recompute models and per-exam metrics without importing their original evaluator;
spot-check fresh PNG->feature inference across each of 14 verified exams.
Private medical source frame identifiers must not be committed to Git.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
import zipfile

import numpy as np
from PIL import Image,ImageOps
import torch
from torchvision.models import mobilenet_v3_small
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,average_precision_score

from galar_exam_cv import OLD_ARCHIVES,NEW_ARCHIVES,FOLDS,EXAMS,BUDGETS

PRIOR_META_SHA='78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2'
WEIGHT_SHA='047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'
N=10123
D=576


def digest(f):
 h=hashlib.sha256()
 with open(f,'rb') as fp:
  for b in iter(lambda:fp.read(1048576),b''):h.update(b)
 return h.hexdigest()


def source_feature_validation(root,meta,bank,weights):
    if digest(weights)!=WEIGHT_SHA:raise ValueError('Original pretrained weights mismatch')
    model=mobilenet_v3_small(weights=None).cpu().eval()
    model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    net=model.features
    mean=torch.tensor((.485,.456,.406)).reshape(1,3,1,1)
    std=torch.tensor((.229,.224,.225)).reshape(1,3,1,1)
    positions={}
    for ex in EXAMS:
        indices=[i for i,r in enumerate(meta) if r['exam']==ex]
        positions[ex]=[indices[0],indices[len(indices)//2],indices[-1]]
    sha_list=[]
    errors=[]
    def check(i,raw,expected_sha):
        if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('Selected original source pixel SHA mismatch')
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='PNG':raise ValueError('Not original PNG')
            image=ImageOps.exif_transpose(image).convert('RGB')
            # Independent construction of the 160x160 normalized RGB tensor.
            image=image.resize((160,160),Image.Resampling.BICUBIC)
            rgb=np.asarray(image,dtype=np.uint8).copy()
        data=torch.tensor(rgb.copy(),dtype=torch.float32).permute(2,0,1).unsqueeze(0)/255.
        data=(data-mean)/std
        with torch.no_grad():feature=net(data).mean(dim=(2,3)).numpy().ravel()
        difference=float(np.max(np.abs(feature-np.asarray(bank[i]))))
        if difference>1e-5:raise ValueError('Fresh original-PNG MobileNet features disagree with saved feature cache.')
        errors.append(difference)
        sha_list.append(expected_sha)
    with zipfile.ZipFile(root/'private'/'capsule-blood-real-pilot.zip') as z:
        hist=json.loads(z.read('private-dataset-manifest/blood-manifest.json'))
    old_records={int(r['exam']):{} for r in hist['records'] if int(r['exam'])<=8}
    for rec in hist['records']:
        ex=int(rec['exam'])
        if ex<=8:old_records[ex][int(rec['frame'])]=rec['source_sha256']
    for pair,(name,sha) in OLD_ARCHIVES.items():
        with zipfile.ZipFile(root/'inputs'/name) as z:
            for ex in range(1,9):
                if f'{ex:03d}' not in pair.split('_'):continue
                for i in positions[ex]:
                    f=int(meta[i]['frame']);member=f'images/{ex:03d}/frame_{f:06d}.PNG'
                    check(i,z.read(member),old_records[ex][f])
    for ex,(name,outer_sha,n) in NEW_ARCHIVES.items():
        with zipfile.ZipFile(root/'inputs'/name) as z:
            inner_name=next(name for name in z.namelist() if name.endswith('.zip'))
            with tempfile.TemporaryDirectory() as td:
                inner=Path(td)/'original.zip'
                with z.open(inner_name) as src,inner.open('wb') as dst:shutil.copyfileobj(src,dst)
                with zipfile.ZipFile(inner) as inn:
                    manifest=json.loads(inn.read('verified-private-manifest.json'))
                    source={int(x['frame']):x for x in manifest}
                    for i in positions[ex]:
                        f=int(meta[i]['frame']);r=source[f]
                        check(i,inn.read(f'images/{ex:03d}/{r["filename"]}'),r['source_image_sha256'])
    if len(errors)!=42:raise ValueError('Expected three independently reconstructed examples per examination.')
    return {'fresh_png_feature_checks':len(errors),'max_abs_feature_error':max(errors),
            'fresh_png_source_identity_digest_sha256':hashlib.sha256(('\n'.join(sha_list)+'\n').encode()).hexdigest()}


def verify(data_root:Path,workdir:Path,weights:Path,private_out:Path):
    meta_file=data_root/'private_outputs/private_source_metadata.json'
    if digest(meta_file)!=PRIOR_META_SHA:raise ValueError('Prior source-image role metadata has changed.')
    meta=json.loads(meta_file.read_text())
    if len(meta)!=N:raise ValueError('Changed source cohort length')
    fbank=workdir/'extracted/features-10123-float32.bin'
    feature_meta=json.loads((workdir/'extracted/feature-source-verification.json').read_text())
    if digest(fbank)!=feature_meta['feature_bank_sha256']:raise ValueError('Feature bank no longer matches completed real source verification')
    bank=np.memmap(fbank,mode='r',dtype=np.float32,shape=(N,D))
    pubpath=workdir/'results/aggregate.json';record=json.loads(pubpath.read_text())
    priv=json.loads((workdir/'results/private-predictions.json').read_text())
    if len(priv)!=7168:raise ValueError('Exactly 7168 predictions required')
    predicted={(int(r['exam']),int(r['frame'])):float(r['score']) for r in priv}
    pred_label={(int(r['exam']),int(r['frame'])):int(r['blood']) for r in priv}
    if len(predicted)!=len(priv):raise ValueError('Duplicate private prediction key')
    labels=np.array([r['blood'] for r in meta],dtype=np.int64)
    exams=np.array([r['exam'] for r in meta],dtype=np.int64)
    reference=np.array([r['reference'] for r in meta],dtype=np.int64)
    max_diff=0
    metric_checks=0
    for fold,heldout in FOLDS.items():
        fitting=np.flatnonzero(~np.isin(exams,heldout))
        eval_ids=np.flatnonzero(np.isin(exams,heldout)&(reference==1))
        if set(exams[fitting]).intersection(heldout) or len(eval_ids)!=512*len(heldout):
            raise ValueError('Training/heldout examination leakage')
        checkpoint=np.load(workdir/f'results/{fold}-frozen-probe.npz',allow_pickle=False)
        assert checkpoint['coef'].shape==(1,576)
        assert set(checkpoint['heldout_exams'])==set(heldout)
        scal=StandardScaler().fit(np.asarray(bank[fitting],dtype=np.float64))
        if not np.allclose(scal.mean_,checkpoint['mean'],rtol=0,atol=1e-12):raise ValueError('Train-only mean mismatch')
        if not np.allclose(scal.scale_,checkpoint['scale'],rtol=0,atol=1e-12):raise ValueError('Train-only std mismatch')
        model=LogisticRegression(solver='lbfgs',penalty='l2',C=0.1,class_weight='balanced',fit_intercept=True,
                                 max_iter=300,tol=1e-6,random_state=37)
        model.fit(scal.transform(np.asarray(bank[fitting],dtype=np.float64)),labels[fitting])
        if not np.allclose(model.coef_,checkpoint['coef'],rtol=0,atol=1e-11):raise ValueError('Independent fold refit weights mismatch')
        if not np.allclose(model.intercept_,checkpoint['intercept'],rtol=0,atol=1e-11):raise ValueError('Independent fold refit intercept mismatch')
        x=np.asarray(bank[eval_ids],dtype=np.float64)
        # Independently apply the saved linear probe in raw NumPy.
        linear=((x-checkpoint['mean'])/checkpoint['scale'])@checkpoint['coef'].T+checkpoint['intercept']
        vals=1/(1+np.exp(-linear.ravel()))
        for i,score in zip(eval_ids,vals):
            key=(int(exams[i]),int(meta[i]['frame']))
            if key not in predicted or pred_label[key]!=int(labels[i]):
                raise ValueError('Saved prediction identity or label changed')
            max_diff=max(max_diff,abs(float(score)-predicted[key]))
        for ex in heldout:
            ids=sorted((int(i) for i in eval_ids if exams[i]==ex),key=lambda i:meta[i]['frame'])
            y=np.asarray([labels[i] for i in ids],dtype=np.int64)
            score=np.asarray([predicted[(ex,int(meta[i]['frame']))] for i in ids])
            result=record['per_exam'][str(ex)]
            if len(y)!=512 or int(y.sum())!=result['blood_positive']:
                raise ValueError('Per-exam heldout label count mismatch')
            auc=roc_auc_score(y,score) if 0<sum(y)<len(y) else None
            ap=average_precision_score(y,score) if sum(y)>0 else None
            if (auc is None)!=(result['roc_auc'] is None) or (ap is None)!=(result['average_precision'] is None):
                raise ValueError('Undefined AUC/AP handled incorrectly')
            if auc is not None and abs(auc-result['roc_auc'])>1e-12:raise ValueError('Heldout AUC replay mismatch')
            if ap is not None and abs(ap-result['average_precision'])>1e-12:raise ValueError('Heldout AP replay mismatch')
            for k in BUDGETS:
                ranked=sorted(range(512),key=lambda j:(-score[j],meta[ids[j]]['frame']))
                got=sum(y[j] for j in ranked[:k]);expected=result['top_k_blood_positive'][str(k)]
                if got!=expected:raise ValueError('Heldout top-K replay mismatch')
                metric_checks+=1
    if max_diff>1e-10:raise ValueError('Original heldout predictions not matched by separate numpy implementation')
    visual=source_feature_validation(data_root,meta,bank,weights)
    receipt={'source_images_verified_by_original_extractor':10123,'independently_reextracted_original_png_features':visual,
             'folds_retrained_exactly':3,'heldout_prediction_rows_replayed':7168,
             'max_abs_saved_prediction_error':max_diff,'examination_budget_outcomes_replayed':metric_checks,
             'all_14_examinations_present':True,'no_evaluation_exam_used_during_its_fold_training':True,
             'underlying_label_provenance_private':True,'clinical_validity':False,
             'source_features_sha256':feature_meta['feature_bank_sha256'],
             'public_aggregate_sha256':digest(pubpath)}
    if private_out.exists():raise FileExistsError('Verification receipt exists, refusing overwrite')
    private_out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('INDEPENDENT_REPLAY',json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--weights',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    verify(a.data_root,a.workdir,a.weights,a.output)

if __name__=='__main__':main()
