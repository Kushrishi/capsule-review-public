"""Reproduce the fixed equal-update Galar blood-CNN fitting comparison.

Research only: original 1–8 versus original 1–8 + new 21,23,30.
Never reads examination 29 or reserved evaluation examinations. Outputs private
weight checkpoints and provenance. See docs/GALAR_EXPANDED_FIT_SPEC.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from capsule_review.baseline import AnatomyCNN, image_tensor

OLD_MANIFEST_SHA='0f1cec23f43023788428c0fa694f6f00f42b367fd2ed2f539b97a57443080f59'
NEW_SCORES_SHA='caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812'
ORIGINAL_WEIGHTS_SHA='f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3'
HISTORICAL_MANIFEST_ID='4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb'
OLD_EXAMS=frozenset(range(1,9))
NEW_EXAMS=frozenset((21,23,30))
FIT_EXAMS=OLD_EXAMS|NEW_EXAMS
FORBIDDEN=frozenset((9,10,29))|frozenset(range(11,21))|frozenset(range(61,81))
SEED=37
STEPS=666
BATCH=32
LR=0.0001
WEIGHT_DECAY=0.0001


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


def read_rows(old_manifest:Path, old_images:Path, new_scores:Path, new_images:Path)->list[tuple]:
    if digest(old_manifest)!=OLD_MANIFEST_SHA or digest(new_scores)!=NEW_SCORES_SHA:
        raise ValueError('Frozen source manifest or new fitting image record has changed.')
    old=json.loads(old_manifest.read_text(encoding='utf-8'))
    if old.get('sha256')!=HISTORICAL_MANIFEST_ID or len(old.get('records',[]))!=5120:
        raise ValueError('Wrong original blood pilot source identity.')
    rows=[];seen=set()
    for record in old['records']:
        if record['split']!='train':continue
        ex,frame,label=(int(record['exam']),int(record['frame']),int(record['blood']))
        if (ex not in OLD_EXAMS or label not in (0,1) or
                record['path']!=f'{ex:03d}/frame_{frame:06d}.PNG'):
            raise ValueError('Original fitting record is not approved.')
        if (ex,frame) in seen:raise ValueError('Duplicate source examination/frame.')
        seen.add((ex,frame))
        rows.append((ex,frame,label,old_images/record['path'],record['source_sha256']))
    if len(rows)!=4096 or sum(r[2] for r in rows)!=239:
        raise ValueError('Original fitting cohort does not match frozen counts.')
    with new_scores.open(encoding='utf-8',newline='') as f:
        newer=list(csv.DictReader(f))
    if len(newer)!=3000:raise ValueError('Expected all verified new fitting images.')
    for record in newer:
        ex,frame,label=(int(record['exam']),int(record['frame']),int(record['blood']))
        if (ex not in NEW_EXAMS or label not in (0,1) or frame<0 or
                record['fit_enriched'] not in ('0','1') or
                record['reference_uniform'] not in ('0','1') or
                not (record['fit_enriched']=='1' or record['reference_uniform']=='1')):
            raise ValueError('Unapproved fitting source, label or selection role.')
        if (ex,frame) in seen:raise ValueError('Cross-examination/source identity duplicate.')
        seen.add((ex,frame))
        rows.append((ex,frame,label,new_images/str(ex)/f'frame_{frame:06d}.PNG',record['source_image_sha256']))
    if (len(rows)!=7096 or sum(row[2] for row in rows)!=753 or
            {r[0] for r in rows}!=FIT_EXAMS or FORBIDDEN.intersection(r[0] for r in rows)):
        raise ValueError('Expanded fitting cohort violates original frozen data roles.')
    return rows


def prepare_images(rows:list[tuple]):
    x=torch.empty((len(rows),3,96,96),dtype=torch.float32)
    y=torch.tensor([r[2] for r in rows],dtype=torch.long)
    seen_raw=set()
    for i,(_,_,_,path,expected) in enumerate(rows):
        if not path.is_file() or digest(path)!=expected or expected in seen_raw:
            raise ValueError('Image SHA-256, presence or cross-exam identity mismatch.')
        seen_raw.add(expected)
        frame=image_tensor(path)
        if frame.shape!=(3,96,96) or not torch.isfinite(frame).all():
            raise ValueError('Invalid original image transform result.')
        x[i]=frame
    return x,y


def train_one(name:str,old_only:bool, rows:list[tuple],x:torch.Tensor,y:torch.Tensor,
              initial:dict[str,torch.Tensor], output:Path)->dict:
    selected=torch.tensor([i for i,r in enumerate(rows) if r[0] in (OLD_EXAMS if old_only else FIT_EXAMS)],dtype=torch.long)
    labels=y[selected]
    pos=int(labels.sum());neg=len(selected)-pos
    if (len(selected),pos)!=((4096,239) if old_only else (7096,753)):
        raise ValueError('Arm source cohort changed.')
    weights=torch.tensor([len(selected)/(2*neg),len(selected)/(2*pos)],dtype=torch.float32)
    torch.manual_seed(SEED)
    model=AnatomyCNN(2).cpu()
    model.load_state_dict(initial,strict=True)
    model.train()
    optim=torch.optim.AdamW(model.parameters(),lr=LR,weight_decay=WEIGHT_DECAY)
    sampler=torch.Generator().manual_seed(SEED)
    losses=[]
    for step in range(1,STEPS+1):
        positions=torch.randint(len(selected),(BATCH,),generator=sampler)
        batch=selected[positions]
        output_logits=model(x[batch])
        loss=nn.functional.cross_entropy(output_logits,y[batch],weight=weights)
        if not torch.isfinite(loss):raise ValueError('Nonfinite fitting loss.')
        optim.zero_grad(set_to_none=True)
        loss.backward()
        optim.step()
        if step%111==0:
            losses.append({'step':step,'weighted_batch_loss':float(loss.detach().item())})
            print(f'arm={name} step={step}/{STEPS} loss={losses[-1]["weighted_batch_loss"]:.5f}',flush=True)
    model.eval()
    if output.exists():raise FileExistsError('Refusing to overwrite model weights.')
    torch.save({k:v.cpu() for k,v in model.state_dict().items()},output)
    return {'arm':name,'fitting_examinations':sorted({rows[int(i)][0] for i in selected}),
            'training_images':len(selected),'blood_positive':pos,'blood_negative':neg,
            'optimizer_updates':STEPS,'batch_size':BATCH,'class_weights':weights.tolist(),
            'sampled_instances_with_replacement':True,'seed':SEED,
            'training_loss_checkpoints':losses,'weights_sha256':digest(output)}


def run(args)->dict:
    if args.output.exists():raise FileExistsError('Refusing to overwrite private fitting results.')
    if digest(args.original_weights)!=ORIGINAL_WEIGHTS_SHA:
        raise ValueError('Original CNN checkpoint SHA-256 changed.')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    np.random.seed(SEED)
    rows=read_rows(args.historical_manifest,args.historical_images,args.new_fitting_scores,args.new_fitting_images)
    start=torch.load(args.original_weights,map_location='cpu',weights_only=True)
    expected=AnatomyCNN(2).state_dict()
    if not isinstance(start,dict) or set(start)!=set(expected) or any(
            start[k].shape!=expected[k].shape or not torch.isfinite(start[k]).all() for k in start):
        raise ValueError('Original CNN checkpoint structure changed.')
    x,y=prepare_images(rows)
    args.output.mkdir(parents=True)
    outcomes=[]
    for name,old_only in [('original_only_continued',True),('expanded_continued',False)]:
        outcomes.append(train_one(name,old_only,rows,x,y,start,args.output/f'{name}.pt'))
    report={'status':'two frozen training-only arms complete; exam29 NOT read or evaluated',
            'source_checkpoint_sha256':ORIGINAL_WEIGHTS_SHA,
            'training_source_hashes':{'historical_manifest':OLD_MANIFEST_SHA,'new_private_scores':NEW_SCORES_SHA},
            'optimization':{'updates':STEPS,'batch_size':BATCH,'lr':LR,'weight_decay':WEIGHT_DECAY,'seed':SEED},
            'new_model_results':outcomes,'clinical_validity':False}
    (args.output/'training.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('historical-manifest','historical-images','new-fitting-scores',
                'new-fitting-images','original-weights','output'):
        p.add_argument('--'+key,dest=key.replace('-','_'),type=Path,required=True)
    args=p.parse_args(argv)
    result=run(args)
    print(json.dumps({'status':result['status'],
                      'model_checkpoint_hashes':[row['weights_sha256'] for row in result['new_model_results']]},indent=2))

if __name__=='__main__':main()
