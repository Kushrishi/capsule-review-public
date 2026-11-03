"""Fixed original-vs-expanded blood-CNN transfer comparison on fitting exam 25.

All model checkpoints and the 512-image reference role were fixed before the
source images were downloaded. Results are development evidence, not a clinical
or independent-patient evaluation. Do not tune these checkpoints to the result.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import zipfile

from PIL import Image
from blood_image_pilot import roc_ap, red_excess

EXAM = 25
UNION_COUNT = 1013
REFERENCE_COUNT = 512
REFERENCE_POSITIVES = 14
ENRICHED_COUNT = 512
ENRICHED_POSITIVES = 256
OVERLAP = 11
BUDGETS = (5, 10, 25, 50, 75, 100)
MODEL_HASHES = {
    'original_checkpoint':'f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3',
    'original_only_continued':'ae88ccfedc53d8f419b3da8c0c01ca6b61361ef29858b6a536e25408ba99eefb',
    'expanded_continued':'2534d3b7982ee8c557cadc5ad3fcc4c7c4c557f899fa013e881d8655eab97111',
}


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for raw in iter(lambda:f.read(1<<20),b''):
            h.update(raw)
    return h.hexdigest()


def extract_verified(source_zip:Path, expected_sha:str, expected_manifest_sha:str, dest:Path)->list[dict]:
    if digest(source_zip)!=expected_sha:
        raise ValueError('Verified original Galar25 source ZIP differs from acquired receipt.')
    if dest.exists():
        raise FileExistsError('Private image destination must not exist.')
    dest.mkdir()
    with zipfile.ZipFile(source_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError('Original source ZIP CRC mismatch.')
        raw_manifest=archive.read('verified-private-manifest.json')
        if hashlib.sha256(raw_manifest).hexdigest()!=expected_manifest_sha:
            raise ValueError('Original per-image manifest digest mismatch.')
        rows=json.loads(raw_manifest)
        if type(rows) is not list or len(rows)!=UNION_COUNT:
            raise ValueError('Wrong image count in original sample.')
        keys=set()
        for r in rows:
            frame=r['frame']
            name=f'frame_{frame:06d}.PNG' if type(frame) is int and frame>=0 else ''
            if (r.get('exam')!=EXAM or not name or r['filename']!=name or frame in keys or
                    type(r['blood']) is not int or r['blood'] not in (0,1) or
                    r['reference_uniform'] not in (0,1) or r['fit_enriched'] not in (0,1) or
                    not (r['reference_uniform'] or r['fit_enriched'])):
                raise ValueError('Non-fitting image ID, label, or duplicate in original source manifest.')
            keys.add(frame)
            blob=archive.read(f'images/{EXAM:03d}/{name}')
            if len(blob)!=r['source_bytes'] or hashlib.sha256(blob).hexdigest()!=r['source_image_sha256']:
                raise ValueError('Original source image size or SHA-256 mismatch.')
            target=dest/name
            with target.open('xb') as f:
                f.write(blob)
            with Image.open(target) as im:
                if im.format!='PNG':
                    raise ValueError('Non-PNG in private original source sample.')
                im.verify()
            r['private_path']=target
        expected={f'images/{EXAM:03d}/frame_{n:06d}.PNG' for n in keys}|{'verified-private-manifest.json'}
        if len(archive.namelist())!=UNION_COUNT+1 or set(archive.namelist())!=expected:
            raise ValueError('Unexpected source members not included in verified manifest.')
    rows.sort(key=lambda x:x['frame'])
    if (sum(r['reference_uniform'] for r in rows)!=REFERENCE_COUNT or
            sum(r['blood']*r['reference_uniform'] for r in rows)!=REFERENCE_POSITIVES or
            sum(r['fit_enriched'] for r in rows)!=ENRICHED_COUNT or
            sum(r['blood']*r['fit_enriched'] for r in rows)!=ENRICHED_POSITIVES or
            sum(r['reference_uniform']*r['fit_enriched'] for r in rows)!=OVERLAP):
        raise ValueError('Frozen sample reference roles/annotation totals do not match.')
    return rows


def score_cnn(weights:Path, sha:str, rows:list[dict])->list[float]:
    import torch
    from torch import nn
    from capsule_review.baseline import AnatomyCNN, image_tensor
    if digest(weights)!=sha:
        raise ValueError('Frozen historical model checkpoint changed.')
    model=AnatomyCNN(2).cpu()
    state=torch.load(weights,map_location='cpu',weights_only=True)
    reference=model.state_dict()
    if not isinstance(state,dict) or set(state)!=set(reference):
        raise ValueError('Unexpected model state format.')
    if any(not torch.is_tensor(state[k]) or state[k].shape!=reference[k].shape or
           not torch.isfinite(state[k]).all() for k in state):
        raise ValueError('Nonfinite or changed model architecture.')
    model.load_state_dict(state,strict=True)
    model.eval()
    scores=[]
    with torch.inference_mode():
        for start in range(0,len(rows),32):
            x=torch.stack([image_tensor(r['private_path']) for r in rows[start:start+32]])
            scores.extend(float(v) for v in nn.functional.softmax(model(x),dim=1)[:,1].tolist())
    if len(scores)!=len(rows) or not all(math.isfinite(s) for s in scores):
        raise ValueError('Frozen inference scores corrupted.')
    return scores


def compute_metrics(rows:list[dict],scores:dict[str,list[float]])->dict:
    if not rows or any(len(x)!=len(rows) for x in scores.values()):
        raise ValueError('Scores and source image identities differ.')
    ys=[r['blood'] for r in rows]
    auc={name:roc_ap(ys,x) for name,x in scores.items()}
    budget={}
    for pct in BUDGETS:
        k=len(rows)*pct//100
        selections={name:sorted(range(len(rows)),key=lambda j:(-x[j],j))[:k]
                    for name,x in scores.items()}
        selections['uniform']=[(2*j+1)*len(rows)//(2*k) for j in range(k)]
        budget[str(pct)]={'selected':k,'blood_positive_images_found':{
            name:sum(ys[j] for j in selection) for name,selection in selections.items()}}
    return {'n':len(rows),'blood_positive':sum(ys),'rank_metrics':auc,'review_budgets':budget}


def evaluate(source:Path,model_paths:dict[str,Path],source_sha:str,manifest_sha:str,
             output_dir:Path)->dict:
    import torch
    if output_dir.exists():
        raise FileExistsError('Refusing to overwrite evaluation results.')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    with TemporaryDirectory(prefix=f'.galar{EXAM}-frozen-inputs-',dir=output_dir.parent) as td:
        rows=extract_verified(source,source_sha,manifest_sha,Path(td)/'source-images')
        scores={k:score_cnn(model_paths[k],sha,rows) for k,sha in MODEL_HASHES.items()}
        scores['red_excess']=[red_excess(row['private_path']) for row in rows]
        ref=[i for i,r in enumerate(rows) if r['reference_uniform']]
        primary=compute_metrics([rows[i] for i in ref],{k:[v[i] for i in ref] for k,v in scores.items()})
        secondary=compute_metrics(rows,scores)
        payload={
            'study':f'Galar{EXAM} fixed original/continued/expanded blood-CNN transfer to a previously selected fitting examination',
            'role':'Exploratory fitting-pool transfer, NOT blinded independent clinical validation',
            'examination':EXAM,
            'reference_cohort':primary,
            'enriched_union_descriptive_only':secondary,
            'model_checkpoints_sha256':MODEL_HASHES,
            'verified_source_package_sha256':source_sha,
            'verified_source_manifest_sha256':manifest_sha,
            'training_changed':False,
            'model_selection_from_evaluation':False,
            'patient_independence_confirmed':False,
            'clinical_validity':False,
            'limits':[
                'Only one examination, selected with known fitting-pool label counts.',
                ('Fourteen blood-positive uniformly sampled frames produce unstable image-level AUC/AP.'
                 if EXAM == 25 else f'{REFERENCE_POSITIVES} blood-positive uniformly sampled frames produce unstable image-level AUC/AP.'),
                'Enriched union deliberately overrepresents blood-positive frames.',
                'Sparse image labels and runs are not independent lesions or consecutive video sensitivity.',
                'No model tuning or default-model promotion from this comparison.',
                'Examinations 11-20 and the author holdout 61-80 are not accessed.'
            ],
        }
        stage=output_dir.parent / ('.'+output_dir.name+'.stage')
        if stage.exists():
            raise FileExistsError('Staging output exists; refuse overwrite.')
        stage.mkdir()
        with (stage/'private-source-scores.csv').open('x',newline='',encoding='utf8') as f:
            columns=['examination','source_frame','reference_uniform','fit_enriched','blood_label','original_image_sha256',*scores]
            writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n')
            writer.writeheader()
            for j,row in enumerate(rows):
                writer.writerow({'examination':EXAM,'source_frame':row['frame'],'reference_uniform':row['reference_uniform'],
                                 'fit_enriched':row['fit_enriched'],'blood_label':row['blood'],
                                 'original_image_sha256':row['source_image_sha256'],
                                 **{k:format(v[j],'.17g') for k,v in scores.items()}})
        (stage/'aggregate.json').write_text(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')
        (stage/'receipt.json').write_text(json.dumps({'source_sha256':source_sha,'manifest_sha256':manifest_sha,
              'private_predictions_sha256':digest(stage/'private-source-scores.csv'),
              'aggregate_sha256':digest(stage/'aggregate.json'),
              'checkpoint_sha256':MODEL_HASHES,'clinical_validity':False},indent=2)+'\n',encoding='utf8')
        os.replace(stage,output_dir)
    return payload


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('source-zip','source-sha256','manifest-sha256','original-weights','original-only-weights',
                'expanded-weights','output'):
        p.add_argument('--'+arg,required=True,type=Path if arg.endswith('weights') or arg in ('source-zip','output') else str)
    a=p.parse_args(argv)
    if not a.output.parent.is_dir():
        p.error('Output parent directory must exist.')
    model_paths={'original_checkpoint':a.original_weights,'original_only_continued':a.original_only_weights,
                 'expanded_continued':a.expanded_weights}
    report=evaluate(a.source_zip,model_paths,a.source_sha256,a.manifest_sha256,a.output)
    print(json.dumps({'reference_metrics':report['reference_cohort']['rank_metrics'],
                      'ten_percent':report['reference_cohort']['review_budgets']['10']},indent=2))


if __name__=='__main__':
    main()
