"""Independently replay and verify a frozen blood-visibility development run."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader,Dataset

from capsule_review.baseline import AnatomyCNN,image_tensor
from capsule_review.baseline_data import safe_path
from blood_image_pilot import evaluate, red_excess, validate_manifest


def compare(expected,actual,path='root'):
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or set(expected)!=set(actual):
            raise ValueError(f'Result structure changed: {path}')
        for k,v in expected.items():compare(v,actual[k],f'{path}.{k}')
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(expected)!=len(actual):
            raise ValueError(f'Length changed: {path}')
        for i,(x,y) in enumerate(zip(expected,actual)):compare(x,y,f'{path}[{i}]')
    elif isinstance(expected,float) or isinstance(actual,float):
        if not math.isclose(expected,actual,rel_tol=1e-8,abs_tol=1e-8):
            raise ValueError(f'Value changed: {path}')
    elif expected!=actual:
        raise ValueError(f'Value changed: {path}')


def verify(manifest:Path,images:Path,run:Path) -> dict:
    data=validate_manifest(manifest,images,check_files=True)
    metrics=json.loads((run/'metrics.json').read_text(encoding='utf-8'))
    if metrics['dataset_manifest_sha256']!=data['sha256']:
        raise ValueError('Run and manifest identities differ.')
    if metrics['weights_sha256']!=hashlib.sha256((run/'weights.pt').read_bytes()).hexdigest():
        raise ValueError('Trained model weights changed.')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model=AnatomyCNN(2).cpu()
    state=torch.load(run/'weights.pt',map_location='cpu',weights_only=True)
    reference=model.state_dict()
    if not isinstance(state,dict) or set(state)!=set(reference) or any(
            not torch.is_tensor(state[k]) or state[k].shape!=reference[k].shape or
            not torch.isfinite(state[k]).all() for k in reference):
        raise ValueError('Unexpected, invalid, or nonfinite weights.')
    model.load_state_dict(state);model.eval()
    dev=[r for r in data['records'] if r['split']=='development']
    class Frames(Dataset):
        def __len__(self):return len(dev)
        def __getitem__(self,i):return image_tensor(safe_path(images,dev[i]['path']))
    scores=[]
    with torch.inference_mode():
        for batch in DataLoader(Frames(),batch_size=32,num_workers=0):
            scores.extend(nn.functional.softmax(model(batch),dim=1)[:,1].tolist())
    with (run/'predictions.csv').open(newline='',encoding='utf-8') as fp:
        recorded=list(csv.DictReader(fp))
    if len(recorded)!=1024 or len(scores)!=1024:
        raise ValueError('Incorrect recorded or replayed frame count.')
    red_scores=[]
    for r,x,score in zip(dev,recorded,scores):
        if (int(x['exam']),int(x['frame']),x['source_sha256'],int(x['blood_label'])) != (
                r['exam'],r['frame'],r['source_sha256'],r['blood']):
            raise ValueError('Saved predictions do not correspond to the frozen source frames.')
        if abs(score-float(x['cnn_score']))>1e-7:
            raise ValueError('Independent replay of the CNN score differs.')
        red=red_excess(safe_path(images,r['path']))
        if abs(red-float(x['red_excess_score']))>1e-7:
            raise ValueError('Independent replay of fixed comparator score differs.')
        red_scores.append(red)
    compare(metrics['cnn'],evaluate(dev,scores),'CNN metrics')
    compare(metrics['fixed_red_excess_comparator'],evaluate(dev,red_scores),'fixed red-excess comparator')
    result={'status':'independent deterministic inference replay successful',
            'verified_real_development_frames':len(dev),
            'frozen_manifest_sha256':data['sha256'],
            'weights_sha256':metrics['weights_sha256'],
            'all_recorded_frame_identities_and_scores_match':True,
            'both_metric_tables_recomputed_and_matched':True,
            'clinical_validation':False}
    (run/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','images','run'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps(verify(a.manifest,a.images,a.run),indent=2))
if __name__=='__main__':main()
