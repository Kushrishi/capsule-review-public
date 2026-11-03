"""Fixed, training-examination-held-out Galar blood domain-adaptation experiment.

Run on permitted locally retained research images only. No downloads, no clinical
use, no unseen Galar holdout. Protocol was frozen before any model fitting.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import tempfile

from PIL import Image
from blood_image_pilot import red_excess, roc_ap, validate_manifest
from capsule_review.baseline_data import safe_path
from pretrained_blood_probe import (backbone_from_official_weights,
                                     fit_linear_probe, load_feature_cache,
                                     score_probe, WEIGHTS_SHA256, MANIFEST_SHA256)

SPEC_SHA256 = 'cbbf7f2724d5ca0ab03a676775fcb74556bd0a889af35124d9068b93e32d7f65'
LEGACY_METRICS_SHA256 = '781b855c0e14278fb20cb45f25f2481bcf379182aa4dd9d8e9b9c93a12928d7a'
TRAIN_EXAMS = tuple(range(1, 9))
HISTORICAL_DEV_EXAMS = (9, 10)
FOLD_EXAMS = (1, 7)
BUDGETS = (5, 10, 25, 50, 75, 100)
SEED = 29
EPOCHS = 3
BATCH_SIZE = 32
RESOLUTION = 160


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_spec(path: Path) -> dict:
    if hash_file(path) != SPEC_SHA256:
        raise ValueError('Pre-fit frozen domain adaptation specification changed.')
    s = json.loads(path.read_text())
    if (s.get('training_examinations') != list(TRAIN_EXAMS) or
        s.get('held_out_training_fold_examinations') != list(FOLD_EXAMS) or
        s.get('historical_development_examinations') != list(HISTORICAL_DEV_EXAMS) or
        s.get('manifest_sha256') != MANIFEST_SHA256 or
        s.get('pretrained_weights_sha256') != WEIGHTS_SHA256 or
        s.get('training', {}).get('epochs') != EPOCHS or
        s.get('training', {}).get('batch_size') != BATCH_SIZE):
        raise ValueError('Invalid frozen experiment design.')
    return s


def ensure_exam_partition(rows: list[dict], mode: str, heldout: int|None) -> tuple[list[dict],list[dict]]:
    if mode == 'fold' and heldout in FOLD_EXAMS:
        train_exams = set(TRAIN_EXAMS) - {heldout}
        eval_exams = {heldout}
    elif mode == 'final' and heldout is None:
        train_exams = set(TRAIN_EXAMS)
        eval_exams = set(HISTORICAL_DEV_EXAMS)
    else:
        raise ValueError('Only internal folds 1/7 and fixed final historical-development run are allowed.')
    training = [r for r in rows if r['exam'] in train_exams and r['split']=='train']
    evaluation = [r for r in rows if r['exam'] in eval_exams and
                  r['split']==('development' if mode=='final' else 'train')]
    if (len(training) != 512*len(train_exams) or
        len(evaluation) != 512*len(eval_exams) or
        any(r['blood'] not in (0,1) for r in training + evaluation) or
        {r['exam'] for r in training} & {r['exam'] for r in evaluation} or
        set(r['exam'] for r in training) != train_exams or
        set(r['exam'] for r in evaluation) != eval_exams or
        len({(r['exam'],r['frame']) for r in training+evaluation}) != len(training)+len(evaluation)):
        raise ValueError('Cross-examination leakage, inconsistent labels or incomplete split.')
    if sum(r['blood'] for r in training)<1:
        raise ValueError('Training partition has no positive labels.')
    return training, evaluation


def make_transform():
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    return transforms.Compose([
        transforms.Resize((RESOLUTION, RESOLUTION),interpolation=InterpolationMode.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize(mean=[.485,.456,.406], std=[.229,.224,.225])
    ])


def make_model(official_weights: Path):
    import torch
    from torch import nn
    net, _ = backbone_from_official_weights(official_weights)
    for p in net.parameters(): p.requires_grad_(False)
    for p in net.features[11:].parameters(): p.requires_grad_(True)
    # Official head is replaced; its ImageNet class probabilities are not used.
    class Candidate(nn.Module):
        def __init__(self):
            super().__init__()
            self.early = net.features[:11]
            self.tail = net.features[11:]
            self.head = nn.Linear(576, 1)
        def train(self, mode: bool=True):
            super().train(mode)
            self.early.eval()  # freeze early BatchNorm statistics as well
            return self
        def forward(self, x):
            with torch.no_grad():
                x = self.early(x)
            x = self.tail(x).mean((2,3))
            return self.head(x).flatten()
    return Candidate()


def load_rows(dataset_rows: list[dict], images: Path, *, shuffle: bool=False):
    from torch.utils.data import Dataset, DataLoader
    transform = make_transform()
    class Frames(Dataset):
        def __len__(self):return len(dataset_rows)
        def __getitem__(self,i):
            r=dataset_rows[i]
            with Image.open(safe_path(images,r['path'])) as im:
                return transform(im.convert('RGB')), int(r['blood'])
    return DataLoader(Frames(),batch_size=BATCH_SIZE,shuffle=shuffle,
                      generator=__import__('torch').Generator().manual_seed(SEED),num_workers=0)


def train_fixed(training:list[dict], images:Path, official_weights:Path):
    import torch
    from torch import nn
    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    random.seed(SEED)
    torch.use_deterministic_algorithms(True)
    model=make_model(official_weights)
    pos=sum(int(r['blood']) for r in training)
    neg=len(training)-pos
    posweight=min(10.0, neg/pos)
    loss_fn=nn.BCEWithLogitsLoss(pos_weight=torch.tensor(posweight,dtype=torch.float32))
    opt=torch.optim.AdamW([
        {'params':model.tail.parameters(),'lr':0.00015},
        {'params':model.head.parameters(),'lr':0.001}
    ],weight_decay=0.01)
    loader=load_rows(training,images,shuffle=True)
    logs=[]
    for epoch in range(EPOCHS):
        model.train()
        total=0.;seen=0
        for batch,labels in loader:
            opt.zero_grad(set_to_none=True)
            logits=model(batch)
            loss=loss_fn(logits,labels.float())
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite fine-tuning loss')
            loss.backward()
            opt.step()
            total += float(loss.detach())*len(labels);seen+=len(labels)
        logs.append({'epoch':epoch+1,'train_weighted_loss':total/seen,'train_frames':seen})
        print(f'fixed train epoch {epoch+1}/{EPOCHS}: loss={total/seen:.5f}',flush=True)
    return model, {'positives':pos,'negatives':neg,'positive_loss_weight':posweight,'training_history':logs}


def predict(model, rows:list[dict], images:Path) -> list[float]:
    import torch
    model.eval()
    scores=[]
    with torch.no_grad():
        for x,labels in load_rows(rows,images,shuffle=False):
            scores.extend(torch.sigmoid(model(x)).tolist())
    if len(scores)!=len(rows) or not all(math.isfinite(s) and 0<=s<=1 for s in scores):
        raise ValueError('Invalid inference result')
    return scores


def budget_metrics(rows:list[dict], scores:list[float]) -> dict:
    if len(rows)!=len(scores) or any(not math.isfinite(s) for s in scores):
        raise ValueError('Scores misaligned or nonfinite.')
    results={}
    for exam in sorted(set(r['exam'] for r in rows)):
        ix=[i for i,r in enumerate(rows) if r['exam']==exam]
        if len(ix)!=512:raise ValueError('Expected 512 sampled positions per examination.')
        y=[rows[i]['blood'] for i in ix]
        s=[scores[i] for i in ix]
        ranked=sorted(range(512),key=lambda j:(-s[j],j))
        values={}
        for pct in BUDGETS:
            k=512*pct//100
            uniform={(2*j+1)*512//(2*k) for j in range(k)}
            values[str(pct)]={'reviewed':k,
                              'positive_frames_found':sum(y[j] for j in ranked[:k]),
                              'uniform_positive_frames_found':sum(y[j] for j in uniform),
                              'positive_total':sum(y)}
        results[str(exam)]={'support':{'positive':sum(y),'negative':len(y)-sum(y)},
                            'rank_metrics':roc_ap(y,s), 'budgets':values}
    return results


def compare_fold_features(manifest:dict,cache_dir:Path,train:list[dict],val:list[dict]):
    import torch
    rows=manifest['records']; features=load_feature_cache(cache_dir,manifest)
    lookup={(r['exam'],r['frame']):i for i,r in enumerate(rows)}
    ti=[lookup[(r['exam'],r['frame'])] for r in train]
    vi=[lookup[(r['exam'],r['frame'])] for r in val]
    head=fit_linear_probe(features[ti], [r['blood'] for r in train])
    return score_probe(features[vi],head)


def atomic_run(manifest:Path,images:Path,weights:Path,spec:Path,
               output:Path,mode:str,heldout:int|None=None,cache_dir:Path|None=None,
               original_metrics:Path|None=None):
    if output.exists():
        raise FileExistsError('Refusing to overwrite any research output.')
    validate_spec(spec)
    if hash_file(weights)!=WEIGHTS_SHA256:
        raise ValueError('Official pretrained weights changed.')
    data=validate_manifest(manifest,images,check_files=True)
    if data['sha256']!=MANIFEST_SHA256:
        raise ValueError('Original Galar source manifest changed.')
    fit,ev=ensure_exam_partition(data['records'],mode,heldout)
    if mode=='fold' and cache_dir is None:
        raise ValueError('Fold requires verified private pretrained feature cache.')
    if mode=='final' and (original_metrics is None or hash_file(original_metrics)!=LEGACY_METRICS_SHA256):
        raise ValueError('Original frozen CNN comparator changed or missing.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.domain-validate-',dir=output.parent) as stage:
        stage=Path(stage)
        model,train_info=train_fixed(fit,images,weights)
        scores=predict(model,ev,images)
        red_scores=[red_excess(safe_path(images,r['path'])) for r in ev]
        result={
            'analysis':'train-only examination holdout' if mode=='fold' else 'previously inspected historical development',
            'mode':mode,'heldout_exam':heldout,'fit_exams':sorted({r['exam'] for r in fit}),
            'evaluated_exams':sorted({r['exam'] for r in ev}),
            'frozen_spec_sha256':SPEC_SHA256,'frozen_manifest_sha256':MANIFEST_SHA256,
            'official_imagenet_weights_sha256':WEIGHTS_SHA256,
            'training':train_info,
            'fine_tuned':budget_metrics(ev,scores),
            'red_excess':budget_metrics(ev,red_scores),
            'examination_unit':'not confirmed unique patients',
            'clinical_validity':False,
            'image_sampling':'512 sparse images/exam; no dense pathology-interval ground truth',
        }
        if mode=='fold':
            linear=compare_fold_features(data,cache_dir,fit,ev)
            result['frozen_image_features']=budget_metrics(ev,linear)
        ckpt=stage/'candidate-weights.pt'
        import torch
        torch.save({'tail':model.tail.state_dict(),'head':model.head.state_dict()},ckpt)
        result['fine_tuned_checkpoint_sha256']=hash_file(ckpt)
        result['evaluated_prediction_file']='predictions.csv'
        with (stage/'predictions.csv').open('w',newline='',encoding='utf8') as f:
            writer=csv.writer(f)
            writer.writerow(['exam','frame','source_sha256','blood_label','domain_adapted_score'])
            for r,score in zip(ev,scores):
                writer.writerow([r['exam'],r['frame'],r['source_sha256'],r['blood'],format(score,'.17g')])
        result['predictions_sha256']=hash_file(stage/'predictions.csv')
        (stage/'metrics.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        (stage/'source-provenance.json').write_text(json.dumps({
            'manifest':MANIFEST_SHA256,'spec':SPEC_SHA256,'source_image_count':len(fit)+len(ev),
            'original_cnn_metrics':LEGACY_METRICS_SHA256 if mode=='final' else None,
            'prediction_sha256':result['predictions_sha256'],
            'result_sha256':hash_file(stage/'metrics.json'),
            'fine_tuned_checkpoint_sha256':result['fine_tuned_checkpoint_sha256']
        },indent=2,sort_keys=True)+'\n')
        os.replace(stage,output)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('fold','final'),required=True)
    p.add_argument('--heldout',type=int,choices=FOLD_EXAMS)
    for opt in ('manifest','images','weights','spec','output'):
        p.add_argument('--'+opt.replace('_','-'),type=Path,required=True)
    p.add_argument('--feature-cache',type=Path)
    p.add_argument('--original-metrics',type=Path)
    a=p.parse_args(argv)
    r=atomic_run(a.manifest,a.images,a.weights,a.spec,a.output,a.mode,a.heldout,a.feature_cache,a.original_metrics)
    print(json.dumps({k:v for k,v in r.items() if k not in ('fine_tuned','red_excess','frozen_image_features')},indent=2))

if __name__=='__main__':main()
