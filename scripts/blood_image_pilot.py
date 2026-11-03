"""Reproducible, sparse-frame Galar blood-annotation *development* pilot.

Only explicit 'blood' labels are used. A negative blood label is NOT an
assertion of normal anatomy or absence of all pathology. This is not a lesion
or interval detector; exams 9–10 were previously examined and are not a test.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter
from statistics import fmean
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

from capsule_review.baseline_data import canonical, digest, image_identity, safe_path
from capsule_review.importer import read_galar_labels

FORMAT = 'capsule-blood-sparse-v1'
TRAIN_EXAMS = tuple(range(1, 9))
DEV_EXAMS = (9, 10)
FUTURE_EXAMS = tuple(range(11, 21))  # assigned without viewing data/labels
BUDGETS = (5, 10, 25)


def prepare(selection: Path, labels_dir: Path, images: Path, receipt: Path, output: Path) -> dict:
    """Enforce frozen exam membership, official corrected-label hashes and image identity."""
    if output.exists():
        raise ValueError('Manifest exists; never overwrite a frozen selection.')
    src = json.loads(receipt.read_text(encoding='utf-8'))
    if (src.get('official_release_version') != 2
            or src.get('source_name') != '20251215_Labels_Updated.zip'
            or not src.get('source_sha256')
            or src.get('actual_md5') != src.get('expected_md5')):
        raise ValueError('Corrected-release provenance receipt is invalid.')
    official = {int(item['examination']): item for item in src['selected_csvs']}
    exam_labels: dict[int, dict] = {}
    for exam in (*TRAIN_EXAMS, *DEV_EXAMS):
        path = labels_dir / f'{exam}.csv'
        if (exam not in official or not official[exam].get('unmodified_source_bytes')
                or hashlib.sha256(path.read_bytes()).hexdigest() != official[exam]['sha256']):
            raise ValueError(f'Corrected Galar annotation bytes mismatch for exam {exam}.')
        exam_labels[exam] = read_galar_labels(path)
    rows, seen, pixel_split = [], set(), {}
    with selection.open(newline='', encoding='utf-8-sig') as fp:
        reader = csv.DictReader(fp)
        if set(reader.fieldnames or []) != {'examination', 'role', 'frame', 'filename'}:
            raise ValueError('Frozen source-frame selection columns changed.')
        for row in reader:
            exam = int(row['examination'])
            if exam not in (*TRAIN_EXAMS, *DEV_EXAMS):
                raise ValueError('Selection includes an unapproved examination.')
            split = 'train' if exam in TRAIN_EXAMS else 'development'
            if row['role'] != ('train' if split == 'train' else 'validation'):
                raise ValueError('Selection roles do not match the frozen anatomy split.')
            frame = int(row['frame'])
            filename = f'frame_{frame:06d}.PNG'
            if row['filename'] != filename:
                raise ValueError('Filename does not match original source frame.')
            key = (exam, frame)
            if key in seen:
                raise ValueError('Duplicate frame identity.')
            seen.add(key)
            ref = exam_labels[exam].get(frame)
            if ref is None or ref.get('blood') not in ('0', '1'):
                raise ValueError('Missing/unknown blood annotation; cannot coerce to negative.')
            rel = f'{exam:03d}/{filename}'
            raw_sha, pixel_sha = image_identity(safe_path(images, rel))
            other = pixel_split.setdefault(pixel_sha, split)
            if other != split:
                raise ValueError('Identical image pixels across fitting/development.')
            rows.append({'exam':exam,'frame':frame,'path':rel,'split':split,
                         'blood':int(ref['blood']),'source_sha256':raw_sha,
                         'pixel_sha256':pixel_sha})
    counts = Counter((r['exam'], r['split'], r['blood']) for r in rows)
    if len(rows) != 5120 or set(r['exam'] for r in rows) != set((*TRAIN_EXAMS, *DEV_EXAMS)):
        raise ValueError('Expected exactly 512 real images from each of ten examinations.')
    if any(sum(counts[(exam, s, b)] for b in (0,1))!=512 for exam in (*TRAIN_EXAMS, *DEV_EXAMS)
           for s in [('train' if exam in TRAIN_EXAMS else 'development')]):
        raise ValueError('Incorrect image count in an examination.')
    if len({r['path'] for r in rows}) != len(rows):
        raise ValueError('Duplicate image path.')
    result = {
        'format': FORMAT,
        'label': 'blood',
        'label_interpretation': 'explicit Galar frame-level blood annotation; zero != all-pathology-negative',
        'evaluation_role': 'historical exploratory development; NEVER independent test',
        'source': {'name': 'Galar v2; Le Floch et al.; CC BY 4.0',
                   'corrected_label_release_sha256': src['source_sha256'],
                   'source_receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
                   'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest()},
        'split': {'train_exams':list(TRAIN_EXAMS),'development_exams':list(DEV_EXAMS),
                  'future_unopened_evaluation_exams':list(FUTURE_EXAMS),
                  'authors_reserved_exams':'61–80, not opened',
                  'unit':'examination, not confirmed unique patient'},
        'sampling': 'the historical 512 uniformly selected source frames per examination; NOT dense sequences',
        'counts': {str(exam):{'positive':counts[(exam,'train' if exam in TRAIN_EXAMS else 'development',1)],
                               'negative':counts[(exam,'train' if exam in TRAIN_EXAMS else 'development',0)]}
                   for exam in (*TRAIN_EXAMS,*DEV_EXAMS)},
        'records': rows,
    }
    result['sha256'] = digest(canonical(result))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as fp:
        json.dump(result, fp, indent=2)
    return result


def validate_manifest(path: Path, images: Path, *, check_files: bool=True) -> dict:
    data=json.loads(path.read_text(encoding='utf-8'))
    claimed=data.pop('sha256',None)
    if data.get('format')!=FORMAT or claimed!=digest(canonical(data)):
        raise ValueError('Pilot manifest schema or SHA-256 mismatch.')
    data['sha256']=claimed
    rows=data['records']
    if len(rows)!=5120 or data['split']['train_exams']!=list(TRAIN_EXAMS) or data['split']['development_exams']!=list(DEV_EXAMS):
        raise ValueError('Pilot manifest split or size changed.')
    keys=set()
    for r in rows:
        exam,frame=r['exam'],r['frame']
        if type(exam)!=int or type(frame)!=int or type(r['blood'])!=int or r['blood'] not in (0,1):
            raise ValueError('Invalid frame identifier or binary blood label.')
        if exam not in (*TRAIN_EXAMS,*DEV_EXAMS) or r['split']!=('train' if exam in TRAIN_EXAMS else 'development'):
            raise ValueError('Split leakage or reserved examination present.')
        if (exam,frame) in keys:
            raise ValueError('Duplicated examination/source-frame pair.')
        keys.add((exam,frame))
        if check_files:
            image=safe_path(images,r['path'])
            raw,pix=image_identity(image)
            if (raw,pix)!=(r['source_sha256'],r['pixel_sha256']):
                raise ValueError('Source image changed since preparation.')
    return data


def red_excess(image_path: Path) -> float:
    """Fixed, untrained redness score; never fit on development data."""
    with Image.open(image_path) as im:
        image=ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(96,96))
        r,g,b=image.split()
        excess=ImageChops.subtract(r,ImageChops.lighter(g,b))
        return ImageStat.Stat(excess).mean[0]/255.0


def roc_ap(y: list[int], scores: list[float]) -> dict:
    """Exact tie-aware ROC-AUC and stepwise average precision, no sklearn required."""
    if not y or len(y)!=len(scores) or any(v not in (0,1) for v in y):
        raise ValueError('Aligned binary labels required.')
    if any(not math.isfinite(float(s)) for s in scores):
        raise ValueError('Finite scores required.')
    pos=sum(y); neg=len(y)-pos
    if not pos:
        return {'roc_auc': None,'average_precision': None, 'positive':0, 'negative':neg}
    order=sorted(range(len(y)),key=lambda i:(-scores[i],i))
    tp=fp=0; prev_r=0.0;prev_fpr=0.0; auc=ap=0.0
    j=0
    while j<len(order):
        k=j+1
        while k<len(order) and scores[order[k]]==scores[order[j]]:
            k+=1
        group=order[j:k]
        tp+=sum(y[i] for i in group)
        fp+=len(group)-sum(y[i] for i in group)
        recall=tp/pos
        ap+=(recall-prev_r)*(tp/(tp+fp))
        if neg:
            fpr=fp/neg
            auc+=(fpr-prev_fpr)*(prev_r+recall)/2
            prev_fpr=fpr
        prev_r=recall
        j=k
    return {'roc_auc':auc if neg else None,'average_precision':ap,'positive':pos,'negative':neg}


def budget_report(rows: list[dict], scores: list[float], *, seed: int=17) -> dict:
    if len(rows)!=len(scores) or not rows:
        raise ValueError('Scores and images must align.')
    exams=sorted({r['exam'] for r in rows})
    results={}
    for percentage in BUDGETS:
        per_exam={}; total_positive=total_found=0
        for exam in exams:
            idx=[i for i,r in enumerate(rows) if r['exam']==exam]
            n=len(idx); k=n*percentage//100
            order=sorted(range(n),key=lambda j:(-scores[idx[j]],j))[:k]
            chosen=set(order)
            pos=sum(rows[i]['blood'] for i in idx)
            found=sum(rows[idx[j]]['blood'] for j in chosen)
            uniform={(2*j+1)*n//(2*k) for j in range(k)} if k else set()
            uhit=sum(rows[idx[j]]['blood'] for j in uniform)
            rng=random.Random(seed+exam*1009+percentage)
            random_hits=[sum(rows[idx[j]]['blood'] for j in rng.sample(range(n),k)) for _ in range(100)]
            per_exam[str(exam)]={'frames':n,'selected':k,'blood_positive':pos,
                                 'model_positive_hits':found,'model_positive_recall':found/pos if pos else None,
                                 'uniform_positive_hits':uhit,'uniform_positive_recall':uhit/pos if pos else None,
                                 'random_mean_positive_hits':sum(random_hits)/len(random_hits),
                                 'random_mean_positive_recall':sum(random_hits)/(len(random_hits)*pos) if pos else None,
                                 'model_false_positive_selections':k-found}
            total_positive+=pos; total_found+=found
        results[str(percentage)]={'per_examination':per_exam,
                                  'pooled_positive_frame_recall':total_found/total_positive if total_positive else None,
                                  'examination_macro_positive_frame_recall':float(fmean(v['model_positive_recall'] for v in per_exam.values() if v['model_positive_recall'] is not None)) if total_positive else None}
    return results


def evaluate(rows: list[dict], scores: list[float]) -> dict:
    y=[r['blood'] for r in rows]
    return {'aggregate':roc_ap(y,scores),
            'by_examination':{str(e):roc_ap([y[i] for i,r in enumerate(rows) if r['exam']==e],
                                            [scores[i] for i,r in enumerate(rows) if r['exam']==e])
                              for e in sorted({r['exam'] for r in rows})},
            'budgets':budget_report(rows,scores)}


def train(manifest_path: Path, images: Path, output: Path) -> dict:
    """One fixed 10-epoch run. Selection uses known historical development loss."""
    if output.exists(): raise ValueError('Run directory already exists; do not overwrite evidence.')
    data=validate_manifest(manifest_path,images)
    # Heavy ML dependencies are optional for the app and all core-only tests.
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import DataLoader,Dataset
    from capsule_review.baseline import AnatomyCNN,image_tensor
    seed=17;torch.manual_seed(seed);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    np.random.seed(seed);random.seed(seed)
    train_rows=[r for r in data['records'] if r['split']=='train']
    dev_rows=[r for r in data['records'] if r['split']=='development']
    class Frames(Dataset):
        def __init__(self,rows):self.rows=rows
        def __len__(self):return len(self.rows)
        def __getitem__(self,i):
            r=self.rows[i];return image_tensor(safe_path(images,r['path'])),int(r['blood'])
    model=AnatomyCNN(2).cpu()
    loss_weight=torch.tensor([len(train_rows)/(2*sum(r['blood']==n for r in train_rows)) for n in (0,1)],dtype=torch.float32)
    if not torch.isfinite(loss_weight).all():raise ValueError('Both training classes required.')
    tr=DataLoader(Frames(train_rows),batch_size=32,shuffle=True,num_workers=0,generator=torch.Generator().manual_seed(seed))
    dv=DataLoader(Frames(dev_rows),batch_size=32,shuffle=False,num_workers=0)
    optimizer=torch.optim.AdamW(model.parameters(),lr=0.001,weight_decay=0.0001)
    output.mkdir(parents=True,exist_ok=False)
    history=[];best=float('inf');best_epoch=None
    for ep in range(1,11):
        model.train(); fitloss=0;count=0
        for x,y in tr:
            optimizer.zero_grad(set_to_none=True)
            logits=model(x)
            loss=nn.functional.cross_entropy(logits,y,weight=loss_weight)
            if not torch.isfinite(loss):raise ValueError('Nonfinite fitting loss.')
            loss.backward();optimizer.step()
            fitloss+=float(loss.detach().item())*len(y);count+=len(y)
        model.eval();devloss=0;dn=0
        with torch.inference_mode():
            for x,y in dv:
                logits=model(x)
                if not torch.isfinite(logits).all():raise ValueError('Nonfinite prediction.')
                devloss+=float(nn.functional.cross_entropy(logits,y,reduction='sum'));dn+=len(y)
        loss=devloss/dn
        history.append({'epoch':ep,'training_weighted_batch_loss':fitloss/count,'development_unweighted_cross_entropy':loss})
        print(f'epoch={ep} train={fitloss/count:.5f} development={loss:.5f}',flush=True)
        if loss<best:
            best=loss;best_epoch=ep
            torch.save({key:value.cpu() for key,value in model.state_dict().items()},output/'weights.pt')
    state=torch.load(output/'weights.pt',weights_only=True,map_location='cpu')
    model.load_state_dict(state);model.eval()
    prediction=[]
    with torch.inference_mode():
        for x,_ in dv:
            prob=nn.functional.softmax(model(x),dim=1)[:,1].cpu().tolist()
            prediction.extend(float(p) for p in prob)
    red=[red_excess(safe_path(images,r['path'])) for r in dev_rows]
    result={'status':'exploratory historical development, NOT independent held-out test',
            'dataset_manifest_sha256':data['sha256'],'fitting_examinations':list(TRAIN_EXAMS),
            'development_examinations':list(DEV_EXAMS),'future_unopened_evaluation_examinations':list(FUTURE_EXAMS),
            'architecture':'capsule-cnn-v1, 2-class blood vs blood-not-annotated',
            'training':{'epochs':10,'seed':seed,'batch_size':32,'learning_rate':0.001,
                        'loss':'train-only inverse-frequency weighted cross entropy',
                        'selection':'minimum historical development unweighted cross entropy',
                        'best_epoch':best_epoch,'best_development_cross_entropy':best},
            'per_examination_support':{str(e):{'positive':sum(r['blood'] for r in dev_rows if r['exam']==e),
                                               'total':sum(r['exam']==e for r in dev_rows)} for e in DEV_EXAMS},
            'cnn':evaluate(dev_rows,prediction), 'fixed_red_excess_comparator':evaluate(dev_rows,red),
            'limitations':['Sparse selection of 512 source frames per examination, not dense sequences.',
                           'Historical development exams were previously inspected and used for checkpoint selection.',
                           'Only one development examination has blood-positive frames.',
                           'Most fitting positive frames come from one examination.',
                           'Frame scores are not calibrated clinical probabilities.',
                           'Blood annotation is distinct from active bleeding, diagnosis or adjudicated lesions.',
                           'Patient identity is unavailable; examination split does not prove patient independence.']}
    with (output/'predictions.csv').open('w',newline='',encoding='utf-8') as fp:
        writer=csv.writer(fp);writer.writerow(['exam','frame','source_sha256','blood_label','cnn_score','red_excess_score'])
        for r,p,redness in zip(dev_rows,prediction,red):
            writer.writerow([r['exam'],r['frame'],r['source_sha256'],r['blood'],format(p,'.9g'),format(redness,'.9g')])
    (output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    (output/'history.json').write_text(json.dumps(history,indent=2,allow_nan=False),encoding='utf-8')
    result['weights_sha256']=hashlib.sha256((output/'weights.pt').read_bytes()).hexdigest()
    (output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    cmds=ap.add_subparsers(dest='command',required=True)
    pr=cmds.add_parser('prepare')
    for name in ('selection','labels','images','receipt','output'):
        pr.add_argument('--'+name,type=Path,required=True)
    tr=cmds.add_parser('train')
    for name in ('manifest','images','output'):
        tr.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args()
    if a.command=='prepare':
        result=prepare(a.selection,a.labels,a.images,a.receipt,a.output)
        print(json.dumps({'manifest_sha256':result['sha256'],'counts':result['counts']},indent=2))
    else:
        r=train(a.manifest,a.images,a.output)
        print(json.dumps({'best_epoch':r['training']['best_epoch'],
                          'cnn':r['cnn']['aggregate'],'red_excess':r['fixed_red_excess_comparator']['aggregate']},indent=2))
if __name__=='__main__':main()
