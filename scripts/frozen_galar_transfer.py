"""Frozen Galar original blood-CNN transfer, on *new fitting-candidate examinations*.

No training, model selection, future evaluation-cohort access, or clinical decisions.
Public aggregate output omits frame identities, per-image labels, and model scores;
private image/scores/provenance must be stored outside version control.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageOps
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from blood_image_pilot import red_excess, roc_ap

EXAMS = (21, 23, 30)
BUDGETS = (5, 10, 25, 50, 75, 100)
EXPECTED = {
  21: dict(inner='abc02cfa8e28020da2994b897c2e608db83d0d6c93131342afa8bca985fe5659',
           manifest='3a5a4640a792237a80bd868b57cb78fd672aa9a7540a574e60e13ec01b4f654d',
           outer='aa18ee3ba5ef98d0ac139fa2a76d033136f95e6686c7645389006c78e6d8c901',
           images=993, positives=13, ref_positives=1),
  23: dict(inner='4154c208752a095ecbbeea03380888834c312834989eab863589b9a38ef28b1b',
           manifest='fe3716c73bd19306d96127a611fa189e3c076a0274b7282092fd57bd8b5d7788',
           outer='44d2f6b6e91cb4f0df0243a8a0dc8560936e787f80b42c8cf1252a6d862be6f8',
           images=1001, positives=135, ref_positives=4),
  30: dict(inner='c20e9ded68735218529812718496ffe3924074a8574a3dc5b402dcecc5582048',
           manifest='142ec6e095489928fc91b1af42d9c0376fab10558c347f94338afb4e34ee9079',
           outer='8eaa78453566f57d06ccd094ca3a057db4ed23552d366d540341bb0a73041e45',
           images=1006, positives=366, ref_positives=120)
}
MODEL_SHA256 = 'f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3'
FROZEN_SOURCE_MANIFEST_SHA256 = '4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb'
FROZEN_HISTORICAL_MANIFEST_RAW_SHA256 = '0f1cec23f43023788428c0fa694f6f00f42b367fd2ed2f539b97a57443080f59'
FROZEN_SPEC_GIT_BLOB = '9a9aa2f0cc5a105e839af197de90088d9d6e37b6'


def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fp:
        for data in iter(lambda:fp.read(1024*1024),b''):
            h.update(data)
    return h.hexdigest()


def byte_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_historical_pixel_sha(manifest: Path) -> set[str]:
    if file_sha(manifest)!=FROZEN_HISTORICAL_MANIFEST_RAW_SHA256:
        raise ValueError('Historical fitting/development manifest source bytes changed.')
    j=json.loads(manifest.read_text(encoding='utf-8'))
    if j['sha256']!=FROZEN_SOURCE_MANIFEST_SHA256 or len(j['records'])!=5120 or (
            set(j['split']['train_exams'])!=set(range(1,9)) or
            set(j['split']['development_exams'])!={9,10}):
        raise ValueError('Historical pilot manifest identity/split mismatch.')
    return {r['pixel_sha256'] for r in j['records']}


def image_pixel_digest(raw: bytes) -> str:
    with Image.open(io.BytesIO(raw)) as im:
        if im.format != 'PNG' or getattr(im,'n_frames',1)!=1:
            raise ValueError('Unexpected source image encoding or animation.')
        if im.width * im.height > 24_000_000 or im.width<=0 or im.height<=0:
            raise ValueError('Unexpected image dimensions.')
        image=ImageOps.exif_transpose(im).convert('RGB')
        pixel_bytes=f'{image.width}x{image.height}:RGB:'.encode()+image.tobytes()
    return byte_sha(pixel_bytes)


def extract_source_archives(outer_paths: dict[int,Path], private: Path,
                            historical_pixel_shas: set[str]) -> tuple[list[dict],dict]:
    if set(outer_paths)!=set(EXAMS):
        raise ValueError('Exactly the three prespecified fitting examinations required.')
    images_dir=private/'images'
    if images_dir.exists():
        raise FileExistsError('Refusing to overwrite private source frames.')
    images_dir.mkdir(parents=True)
    rows=[];seen=set();seen_pixel={};within_old=0;cross_new=0
    provenance={}
    for exam in EXAMS:
        pkg=outer_paths[exam]
        exp=EXPECTED[exam]
        if file_sha(pkg)!=exp['outer']:
            raise ValueError(f'Exam {exam}: original outer archive SHA-256 mismatch.')
        with ZipFile(pkg) as outer:
            if outer.testzip() is not None:raise ValueError('Outer archive ZIP CRC failure.')
            names=outer.namelist()
            name=f'galar-exam{exam}-verified-source.zip'
            if name not in names or len(names)!=2:
                raise ValueError('Outer archive member inventory changed.')
            nested=private/f'private-exam{exam}.zip'
            if nested.exists():raise FileExistsError('Refuse overwrite of private image source zip.')
            with outer.open(name) as inp,nested.open('xb') as out:
                shutil.copyfileobj(inp,out,1024*1024)
        if file_sha(nested)!=exp['inner']:
            raise ValueError(f'Exam {exam}: nested source archive hash mismatch.')
        with ZipFile(nested) as z:
            if z.testzip() is not None:raise ValueError('Source ZIP CRC failed.')
            mj=z.read('verified-private-manifest.json')
            if byte_sha(mj)!=exp['manifest']:
                raise ValueError('Original image manifest hash mismatch.')
            manifest=json.loads(mj)
            expected_members={f'images/{exam:03d}/{x["filename"]}' for x in manifest}
            if len(manifest)!=exp['images'] or set(z.namelist()) != expected_members | {'verified-private-manifest.json'}:
                raise ValueError('Source image inventory/manifest count mismatch.')
            support=Counter();last=-1;image_bytes=0
            for record in manifest:
                if set(record)!=set(('exam','frame','filename','source_image_sha256','source_bytes','blood','fit_enriched','reference_uniform')):
                    raise ValueError('Unexpected private frame record shape.')
                frame=record['frame']
                if record['exam']!=exam or type(frame)!=int or frame<=last or frame<0 or (
                    record['filename']!=f'frame_{frame:06d}.PNG' or
                    type(record['blood'])!=int or record['blood'] not in (0,1) or
                    record['fit_enriched'] not in (0,1) or record['reference_uniform'] not in (0,1) or
                    record['fit_enriched']+record['reference_uniform'] < 1):
                    raise ValueError('Source frame identity, order, or original role mismatch.')
                last=frame
                source_key=(exam,frame)
                if source_key in seen:raise ValueError('Duplicate source examination/frame.')
                seen.add(source_key)
                rel=f'images/{exam:03d}/{record["filename"]}'
                raw=z.read(rel)
                if len(raw)!=record['source_bytes'] or byte_sha(raw)!=record['source_image_sha256']:
                    raise ValueError('Original source PNG SHA-256 or length mismatch.')
                pixel_hash=image_pixel_digest(raw)
                if pixel_hash in historical_pixel_shas:within_old+=1
                if pixel_hash in seen_pixel and seen_pixel[pixel_hash]!=exam:cross_new+=1
                seen_pixel.setdefault(pixel_hash,exam)
                dest=images_dir/str(exam)
                dest.mkdir(exist_ok=True)
                path=dest/record['filename']
                if path.exists():raise FileExistsError('Original frame already present.')
                path.write_bytes(raw)
                image_bytes+=len(raw)
                support['positives']+=record['blood']
                support['ref_count']+=record['reference_uniform']
                support['ref_positives']+=record['reference_uniform']*record['blood']
                support['fit_count']+=record['fit_enriched']
                rows.append({**record,'path':path,'pixel_sha256':pixel_hash})
        if support['positives']!=exp['positives'] or support['ref_count']!=512 or support['ref_positives']!=exp['ref_positives'] or support['fit_count']!=512:
            raise ValueError(f'Exam {exam} frozen plan counts not reproduced.')
        provenance[str(exam)]={'outer_sha256':exp['outer'],'inner_sha256':exp['inner'],
                               'private_manifest_sha256':exp['manifest'],
                               'unique_images':len(manifest),'blood_positive_images':support['positives'],
                               'reference_images':support['ref_count'],
                               'reference_blood_positive':support['ref_positives'],
                               'source_image_bytes':image_bytes}
        print('Validated source exam',exam,'images',len(manifest),'blood',support['positives'],'bytes',image_bytes,flush=True)
        nested.unlink()
    if len(rows)!=3000 or sum(r['blood'] for r in rows)!=514:
        raise ValueError('Combined image/label provenance mismatch.')
    provenance['pixel_identity_overlap_with_original_1_to_10']=within_old
    provenance['new_cross_examination_identical_pixels']=cross_new
    return rows,provenance


def rank_hits(rows: list[dict], scores: list[float]) -> dict:
    if len(rows)!=len(scores) or any(not math.isfinite(s) for s in scores):
        raise ValueError('Aligned, finite scores required.')
    n=len(rows); ordered=sorted(range(n),key=lambda i:(-scores[i],rows[i]['frame']))
    positive=sum(r['blood'] for r in rows)
    result={}
    for pct in BUDGETS:
        k=n*pct//100
        chosen=ordered[:k]
        result[str(pct)]={'selected_images':k,'blood_positive_images':sum(rows[i]['blood'] for i in chosen),
                          'positive_images_total':positive}
    return result


def uniform_rank_hits(rows: list[dict]) -> dict:
    n=len(rows)
    result={}
    for pct in BUDGETS:
        k=n*pct//100
        ix=[(2*j+1)*n//(2*k) for j in range(k)] if k else []
        result[str(pct)]={'selected_images':k,'blood_positive_images':sum(rows[i]['blood'] for i in ix),
                          'positive_images_total':sum(r['blood'] for r in rows)}
    return result


def metrics(rows: list[dict], field: str) -> dict:
    y=[r['blood'] for r in rows];sc=[r[field] for r in rows]
    return {'roc_auc':roc_ap(y,sc)['roc_auc'],'average_precision':roc_ap(y,sc)['average_precision'],
            'budgets':rank_hits(rows,sc)}


def summarize(rows: list[dict], provenance: dict) -> dict:
    out={'study':'Frozen original blood CNN descriptive transfer on new fitting Galar exams',
         'classification_target':'corrected binary visible blood annotation, not diagnosis',
         'model_training':'Original CNN trained only on 1-8, checkpoint fixed on historical inspected 9-10; no retraining',
         'review_budget_denominator':'Each examination\'s 512 label-blind reference source images, not real video length or clinical reading time',
         'reference_subset_mechanism':'Source-position uniform and fixed before inference, no label-based sample enrichment',
         'model_weights_sha256':MODEL_SHA256,
         'experimental_status':'post-acquisition nonblinded training-candidate transfer; no clinical validation',
         'per_examination':{},'label_blind_total':{},'enriched_union_secondary':{},
         'source_integrity':provenance,
         'limitations':['Exam 21 has 1 and exam 23 has 4 labelled positives among 512 uniformly sampled images; discrimination is highly unstable.',
            'Examinations are not confirmed unique patients. The acquired studies were selected for training based on already inspected labels.',
            'Annotation positives are not distinct lesions, temporal intervals, reader time or clinical diagnostic events.',
            'The union of pathology-enriched training and reference images is not a representative test distribution.',
            'Future reserved evaluation examinations 11-20 and authors\' 61-80 remain unopened.',
            'No architecture, checkpoint, hyperparameters, or thresholds were selected from these results.']}
    ref_all=[];union_all=[]
    for exam in EXAMS:
        exam_rows=sorted((r for r in rows if r['exam']==exam),key=lambda r:r['frame'])
        reference=[r for r in exam_rows if r['reference_uniform']==1]
        if len(reference)!=512 or sum(r['blood'] for r in reference)!=EXPECTED[exam]['ref_positives']:
            raise ValueError('Frozen reference frame sample mutated.')
        ref_all.extend(reference);union_all.extend(exam_rows)
        out['per_examination'][str(exam)]={
            'reference_support':{'images':512,'blood_positive':sum(r['blood'] for r in reference)},
            'reference_cnn':metrics(reference,'score_cnn'),
            'reference_redness':metrics(reference,'score_red'),
            'reference_uniform':{'budgets':uniform_rank_hits(reference)},
            'enriched_union_support':{'images':len(exam_rows),'blood_positive':sum(r['blood'] for r in exam_rows)},
            'enriched_union_cnn':metrics(exam_rows,'score_cnn'),
            'enriched_union_redness':metrics(exam_rows,'score_red')}
    # Pooled discrimination is highly confounded by between-exam prevalence and score shifts.
    out['label_blind_total']={'images':len(ref_all),'positive':sum(x['blood'] for x in ref_all),
                              'cnn_roc_auc':roc_ap([x['blood'] for x in ref_all],[x['score_cnn'] for x in ref_all])['roc_auc'],
                              'cnn_average_precision':roc_ap([x['blood'] for x in ref_all],[x['score_cnn'] for x in ref_all])['average_precision'],
                              'red_roc_auc':roc_ap([x['blood'] for x in ref_all],[x['score_red'] for x in ref_all])['roc_auc'],
                              'red_average_precision':roc_ap([x['blood'] for x in ref_all],[x['score_red'] for x in ref_all])['average_precision']}
    out['enriched_union_secondary']={'images':len(union_all),'positive':sum(x['blood'] for x in union_all),
             'cnn_roc_auc':roc_ap([x['blood'] for x in union_all],[x['score_cnn'] for x in union_all])['roc_auc'],
             'cnn_average_precision':roc_ap([x['blood'] for x in union_all],[x['score_cnn'] for x in union_all])['average_precision'],
             'red_roc_auc':roc_ap([x['blood'] for x in union_all],[x['score_red'] for x in union_all])['roc_auc'],
             'red_average_precision':roc_ap([x['blood'] for x in union_all],[x['score_red'] for x in union_all])['average_precision']}
    return out


def predict_scores(rows: list[dict], weights: Path) -> None:
    import torch
    from torch import nn
    from capsule_review.baseline import AnatomyCNN, image_tensor
    if file_sha(weights)!=MODEL_SHA256:
        raise ValueError('Original trained CNN weights differ from frozen original checkpoint.')
    torch.manual_seed(17)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    model=AnatomyCNN(2).cpu()
    state=torch.load(weights,map_location='cpu',weights_only=True)
    expected=model.state_dict()
    if not isinstance(state,dict) or set(state)!=set(expected) or any(
        state[k].shape!=expected[k].shape or not torch.isfinite(state[k]).all() for k in expected):
        raise ValueError('Malformed original fitted state dict.')
    model.load_state_dict(state)
    model.eval()
    # Preserve actual source-image preprocessing used in the historical experiment.
    with torch.inference_mode():
        for i in range(0,len(rows),32):
            block=rows[i:i+32]
            tensor=torch.stack([image_tensor(r['path']) for r in block])
            probs=nn.functional.softmax(model(tensor),dim=1)[:,1].cpu().tolist()
            for r,score in zip(block,probs):
                r['score_cnn']=float(score)
                r['score_red']=float(red_excess(r['path']))
            if (i//32)%20==0:print('CNN scored',min(i+len(block),len(rows)),'/',len(rows),flush=True)
    if any(not 0<=r['score_cnn']<=1 or not math.isfinite(r['score_red']) for r in rows):
        raise ValueError('Invalid image scores.')


def validate_frozen_spec(path: Path) -> dict:
    data=path.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if actual!=FROZEN_SPEC_GIT_BLOB:
        raise ValueError('Original pre-score frozen transfer spec Git blob changed.')
    spec=json.loads(data)
    if (spec['strict_separation']['allowed_evaluation_ids']!=list(EXAMS)
            or spec['historical_frozen_cnn']['weights_sha256']!=MODEL_SHA256
            or spec['comparators']['workload_budgets_percent']!=list(BUDGETS)
            or any(x['sha256']!=EXPECTED[x['exam']]['inner'] for x in spec['source_image_packages'])):
        raise ValueError('Frozen Galar evaluation identities/operating rules differ.')
    return spec


def execute(archives: dict[int,Path], weights:Path, prior_manifest:Path, private:Path, public:Path, spec:Path) -> dict:
    validate_frozen_spec(spec)
    repository=Path(__file__).resolve().parents[1]
    if private.resolve().is_relative_to(repository):
        raise ValueError('Never place original medical images or per-frame scores within repository tree.')
    if public.exists():raise FileExistsError('Refuse to replace frozen aggregate output.')
    if private.exists():raise FileExistsError('Private inference output already exists.')
    previous=load_historical_pixel_sha(prior_manifest)
    private.mkdir(parents=True)
    rows,prov=extract_source_archives(archives,private,previous)
    predict_scores(rows,weights)
    result=summarize(rows,prov)
    private_scores=private/'source-scores.csv'
    with private_scores.open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['exam','frame','source_image_sha256','pixel_sha256','blood','fit_enriched','reference_uniform','cnn_score','red_excess_score'])
        w.writeheader()
        for r in rows:
            w.writerow({k:r.get(v) for k,v in [
                ('exam','exam'),('frame','frame'),('source_image_sha256','source_image_sha256'),('pixel_sha256','pixel_sha256'),
                ('blood','blood'),('fit_enriched','fit_enriched'),('reference_uniform','reference_uniform'),
                ('cnn_score','score_cnn'),('red_excess_score','score_red')]})
    private_receipt=private/'provenance.json'
    private_receipt.write_text(json.dumps({'weights_sha256':MODEL_SHA256,'historical_manifest_identity':FROZEN_SOURCE_MANIFEST_SHA256,
        'source_score_sha256':file_sha(private_scores),'scores':len(rows),'research_only':True,
        'public_aggregate_sha256':byte_sha((json.dumps(result,sort_keys=True,indent=2)+'\n').encode()),
        'source_archive_digests':prov},sort_keys=True,indent=2)+'\n',encoding='utf-8')
    public.parent.mkdir(parents=True,exist_ok=True)
    public.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('Complete; private source predictions SHA-256:',file_sha(private_scores),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outer-21',type=Path,required=True)
    p.add_argument('--outer-23',type=Path,required=True)
    p.add_argument('--outer-30',type=Path,required=True)
    p.add_argument('--weights',type=Path,required=True)
    p.add_argument('--historical-manifest',type=Path,required=True)
    p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--private-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    execute({21:args.outer_21,23:args.outer_23,30:args.outer_30},args.weights,args.historical_manifest,args.private_dir,args.out,args.spec)

if __name__=='__main__':main()
