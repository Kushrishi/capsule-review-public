"""Independent replay/metric verification for frozen CNN transfer on new Galar frames.

Uses the recorded source images and the unchanged original weights. Per-frame
identities and scores are private; public output contains aggregate checks only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

import torch
from torch import nn
from sklearn.metrics import average_precision_score, roc_auc_score

from capsule_review.baseline import AnatomyCNN,image_tensor
from blood_image_pilot import red_excess
from frozen_galar_transfer import EXAMS, EXPECTED, MODEL_SHA256, file_sha


def _load_checkpoint(weights):
    if file_sha(weights)!=MODEL_SHA256:
        raise ValueError('Original CNN weights differ from frozen source checkpoint.')
    torch.manual_seed(17)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    model=AnatomyCNN(2).cpu()
    state=torch.load(weights,weights_only=True,map_location='cpu')
    if set(state)!=set(model.state_dict()):raise ValueError('CNN architecture weights mismatch.')
    model.load_state_dict(state)
    model.eval()
    return model


def _score_batch(model,paths):
    with torch.inference_mode():
        tensor=torch.stack([image_tensor(p) for p in paths])
        return nn.functional.softmax(model(tensor),dim=1)[:,1].cpu().tolist()


def _original_development_replay(model, images_zip, pilot_zip):
    with ZipFile(pilot_zip) as pilot:
        old=list(csv.DictReader(io.StringIO(pilot.read('private-development-predictions/predictions.csv').decode('utf-8'))))
    if len(old)!=1024 or {int(x['exam']) for x in old}!={9,10}:
        raise ValueError('Original development score file or examination partition changed.')
    errs=[];red_errs=[];truth=[];model_scores=[]
    with ZipFile(images_zip) as images,tempfile.TemporaryDirectory() as d:
        if images.testzip() is not None:raise ValueError('Original development image ZIP CRC failed.')
        tmp=Path(d)
        for start in range(0,1024,32):
            group=old[start:start+32]
            paths=[]
            for x in group:
                exam=int(x['exam']);frame=int(x['frame'])
                filename=f'images/{exam:03d}/frame_{frame:06d}.PNG'
                raw=images.read(filename)
                if hashlib.sha256(raw).hexdigest()!=x['source_sha256']:
                    raise ValueError('Historical original-source PNG SHA mismatch.')
                local=tmp/f'{exam}_{frame}.PNG'
                local.write_bytes(raw)
                paths.append(local)
            values=_score_batch(model,paths)
            for row,score,path in zip(group,values,paths):
                err=abs(score-float(row['cnn_score']))
                red_err=abs(red_excess(path)-float(row['red_excess_score']))
                errs.append(err);red_errs.append(red_err)
                model_scores.append(score);truth.append(int(row['blood_label']))
                path.unlink()
    if max(errs)>1e-7 or max(red_errs)>1e-7:
        raise ValueError('Original historical 1024-frame replay failed; cannot trust new inference.')
    au=roc_auc_score(truth,model_scores)
    ap=average_precision_score(truth,model_scores)
    if abs(au-0.7261886154576442)>1e-10 or abs(ap-0.622537869374297)>1e-10:
        raise ValueError('Original historical AUC/AP not reproduced independently.')
    return {'historical_frames_replayed':1024,'historical_cnn_max_abs_score_error':max(errs),
            'historical_red_max_abs_score_error':max(red_errs),
            'historical_auc':float(au),'historical_ap':float(ap)}


def _new_exam_replay(model,scores_csv,images_dir,aggregate):
    with scores_csv.open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=3000 or {int(r['exam']) for r in rows}!=set(EXAMS):
        raise ValueError('Frozen new-fitting score rows or examination roster changed.')
    by_exam=defaultdict(list);err_cnn=[];err_red=[];seen=set()
    for start in range(0,len(rows),32):
        part=rows[start:start+32]
        paths=[]
        for r in part:
            exam,frame=int(r['exam']),int(r['frame'])
            if (exam,frame) in seen or exam not in EXAMS:raise ValueError('Source identity duplicated or reserved.')
            seen.add((exam,frame))
            p=images_dir/str(exam)/f'frame_{frame:06d}.PNG'
            if file_sha(p)!=r['source_image_sha256']:
                raise ValueError('Original source PNG changed after first inference.')
            paths.append(p)
        vals=_score_batch(model,paths)
        for r,p,v in zip(part,paths,vals):
            red=red_excess(p)
            err_cnn.append(abs(v-float(r['cnn_score'])))
            err_red.append(abs(red-float(r['red_excess_score'])))
            by_exam[int(r['exam'])].append({'frame':int(r['frame']),'blood':int(r['blood']),
                                             'reference':int(r['reference_uniform']),
                                             'cnn':v,'red':red})
    if max(err_cnn)>1e-7 or max(err_red)>1e-7:
        raise ValueError('Frozen new-exam score replay differed.')
    for exam in EXAMS:
        entries=sorted(by_exam[exam],key=lambda v:v['frame'])
        ref=[r for r in entries if r['reference']==1]
        if len(ref)!=512 or sum(x['blood'] for x in ref)!=EXPECTED[exam]['ref_positives']:
            raise ValueError('Reference selection changed or scores missing.')
        published=aggregate['per_examination'][str(exam)]
        for subset,metrics_label,metric_prefix in [(ref,'reference','reference'),(entries,'union','enriched_union')]:
            y=[x['blood'] for x in subset]
            for method in ('cnn','red'):
                s=[x[method] for x in subset]
                expected=published[f'{metric_prefix}_{"redness" if method=="red" else "cnn"}']
                if not math.isclose(roc_auc_score(y,s),expected['roc_auc'],abs_tol=1e-10):
                    raise ValueError('Independent AUC metrics disagree.')
                if not math.isclose(average_precision_score(y,s),expected['average_precision'],abs_tol=1e-10):
                    raise ValueError('Independent AP metrics disagree.')
                for pct in (5,10,25,50,75,100):
                    k=len(subset)*pct//100
                    ordered=sorted(range(len(subset)),key=lambda i:(-s[i],subset[i]['frame']))
                    hits=sum(y[i] for i in ordered[:k])
                    if hits!=expected['budgets'][str(pct)]['blood_positive_images']:
                        raise ValueError('Independent top-budget hits disagree.')
        for pct in (5,10,25,50,75,100):
            k=512*pct//100
            sampled=[ref[(2*j+1)*512//(2*k)] for j in range(k)]
            if sum(x['blood'] for x in sampled)!=published['reference_uniform']['budgets'][str(pct)]['blood_positive_images']:
                raise ValueError('Uniform budget comparator changed.')
    return {'new_fitting_images_replayed':3000,'reference_images_replayed':1536,
            'new_cnn_max_abs_score_error':max(err_cnn),'new_red_max_abs_score_error':max(err_red),
            'independent_metric_library':'scikit-learn (roc_auc_score, average_precision_score)',
            'per_examination_auc_ap_and_all_six_budgets_recomputed':True}


def verify(weights,private,results,images_zip,original_pilot,output):
    if output.exists():raise FileExistsError('Refusing overwrite of verification output.')
    aggregate=json.loads(results.read_text())
    model=_load_checkpoint(weights)
    historic=_original_development_replay(model,images_zip,original_pilot)
    new=_new_exam_replay(model,private/'source-scores.csv',private/'images',aggregate)
    report={'original_historical_replay':historic,'new_fitting_exam_replay':new,
            'aggregate_sha256':file_sha(results),
            'private_score_sha256':file_sha(private/'source-scores.csv'),
            'verified_model_sha256':MODEL_SHA256,'clinical_validation':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('weights','private','aggregate','original-images','original-pilot','output'):
        p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.weights,a.private,a.aggregate,a.original_images,a.original_pilot,a.output),indent=2),flush=True)

if __name__=='__main__':main()
