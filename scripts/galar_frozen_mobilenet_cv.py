"""Frozen pretrained MobileNetV3 full-field feature + logistic probe on Galar fit-only exams.

Method precommitted in docs/GALAR_FROZEN_MOBILENET_CV_SPEC.json before extraction.
Never read reserved exams. Private images, per-frame features, IDs and predictions
must remain outside the source repository. Exam IDs are not verified unique patients.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import warnings
import zipfile

import numpy as np
from PIL import Image, ImageOps
import torch
from torch import nn
from torchvision.models import mobilenet_v3_small
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.exceptions import ConvergenceWarning

# A literal import of previously merged, source-verified roles and source receipts.
# No training/checkpoints/metric values are imported from the prior experiment.
from galar_exam_cv import OLD_ARCHIVES, NEW_ARCHIVES, EXAMS, FOLDS, BUDGETS, OLD_MANIFEST_SHA, OLD_IDENTIFIER

SPEC_BLOB_SHA = '2440eae552535e62e1824cff6fd6437d2641e565'
WEIGHTS_SHA = '047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'
PRIOR_META_SHA = '78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2'
PRIOR_CV_AGG_SHA = '1c06c72f97bf67c5d51f24d32c93213743b1fec484a01441a5ba107c7653608f'
N = 10123
FEAT = 576
SIZE = 160
SEED = 37
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
C = 0.1
ITER = 300
TOL = 1e-6
DEFAULT_SOURCE = Path(os.environ.get('CAPSULE_CV_DATA_ROOT', '/private/capsule-review'))


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def validate_spec(path: Path) -> dict:
    raw = path.read_bytes()
    if git_blob(raw) != SPEC_BLOB_SHA:
        raise ValueError('Frozen methodology changed; refusing unregistered analysis.')
    spec = json.loads(raw)
    if (spec['sources']['fitting_exams'] != list(EXAMS)
            or spec['sources']['prior_verified_private_metadata_sha256'] != PRIOR_META_SHA
            or spec['feature_extractor']['official_pretrained_weights_sha256'] != WEIGHTS_SHA
            or spec['partitions'] != {k:list(v) for k,v in FOLDS.items()}
            or spec['linear_probe']['algorithm'] != "sklearn LogisticRegression with solver lbfgs and L2 penalty, C=0.1, class_weight='balanced', fit_intercept=true, max_iter=300, tol=1e-6, random_state=37"):
        raise ValueError('Frozen source/method/folds changed.')
    return spec


def check_metadata(private_metadata: Path) -> list[dict]:
    if hash_file(private_metadata) != PRIOR_META_SHA:
        raise ValueError('Previous full-source verification manifest changed.')
    rows = json.loads(private_metadata.read_text(encoding='utf-8'))
    if len(rows) != N or any(set(row) != {'exam','frame','blood','reference','enriched','red_score'} for row in rows):
        raise ValueError('Prior Galar source metadata structure changed.')
    if [sum(row['reference'] for row in rows if row['exam']==exam) for exam in EXAMS] != [512] * len(EXAMS):
        raise ValueError('Expected 512 chronological label-blind source reference rows for each study.')
    if len({(r['exam'], r['frame']) for r in rows}) != N or sum(r['blood'] for r in rows) != 1663:
        raise ValueError('Prior source IDs or label support changed.')
    if any(r['exam'] not in EXAMS or r['blood'] not in (0,1) or r['reference'] not in (0,1) for r in rows):
        raise ValueError('Forbidden source examination or invalid label/ref role in metadata.')
    return rows


def make_backbone(weights: Path) -> nn.Module:
    if hash_file(weights) != WEIGHTS_SHA:
        raise ValueError('Official ImageNet MobileNet backbone weight SHA mismatch.')
    model = mobilenet_v3_small(weights=None).cpu()
    checkpoint = torch.load(weights, map_location='cpu',weights_only=True)
    model.load_state_dict(checkpoint, strict=True)
    model.eval()
    if model.classifier[0].in_features != FEAT:
        raise ValueError('Unexpected official backbone feature dimension.')
    for p in model.parameters():p.requires_grad_(False)
    return model.features


def decode(raw: bytes) -> torch.Tensor:
    with Image.open(io.BytesIO(raw)) as original:
        if original.format != 'PNG':
            raise ValueError('Original Galar research-source PNG expected.')
        original.verify()
    with Image.open(io.BytesIO(raw)) as original:
        rgb = ImageOps.exif_transpose(original).convert('RGB')
        # Full original image, no central crop or label-informed focus.
        resized = rgb.resize((SIZE,SIZE),resample=Image.Resampling.BICUBIC)
        pixels = np.array(resized,dtype=np.uint8,copy=True)
    return torch.from_numpy(pixels).permute(2,0,1).contiguous()


class FeatureWriter:
    def __init__(self, bank: np.memmap, metas: list[dict], net: nn.Module,
                 batch_size: int=24, resume_verified_prefix: int=0):
        self.bank=bank;self.metas=metas;self.net=net;self.batch_size=batch_size
        self.resume_verified_prefix=resume_verified_prefix
        self.counter=0;self.images=[];self.keys=[];self.seen_raw=set()
        self.m = torch.tensor(MEAN).reshape(1,3,1,1)
        self.s = torch.tensor(STD).reshape(1,3,1,1)

    def add(self, ex:int,frame:int,blood:int,ref:int,fit:int,expected_sha:str,
            raw:bytes, expected_size:int):
        if self.counter>=N or (ex,frame,blood,ref,fit)!=tuple(self.metas[self.counter][k] for k in ('exam','frame','blood','reference','enriched')):
            raise ValueError('Decoded original PNG does not match prior verified exam/frame/label/reference role order.')
        if ex not in EXAMS or ex in (9,10) or not (ref or fit):
            raise ValueError('Non-approved fitting source or invalid role.')
        if hash_bytes(raw)!=expected_sha or len(raw)!=expected_size:
            raise ValueError('Original publisher image bytes/hash mismatch.')
        if expected_sha in self.seen_raw:
            raise ValueError('Duplicate original image source bytes across examinations.')
        self.seen_raw.add(expected_sha)
        if self.counter>=self.resume_verified_prefix:
            self.images.append(decode(raw))
            self.keys.append(self.counter)
        self.counter+=1
        if len(self.images)>=self.batch_size:
            self.flush()

    @torch.inference_mode()
    def flush(self):
        if not self.images:return
        image_batch=torch.stack(self.images).float().div_(255)
        image_batch=(image_batch-self.m)/self.s
        out=self.net(image_batch).mean((2,3)).cpu().numpy()
        if out.shape!=(len(self.images),FEAT) or not np.isfinite(out).all():
            raise ValueError('Invalid pretrained feature extractor result.')
        self.bank[self.keys]=out
        self.images.clear();self.keys.clear()


def extract_all(root:Path, out:Path, source_meta:list[dict], weights:Path,
                *,threads:int=4, batch_size:int=24, resume_verified_prefix:int=0) -> dict:
    if resume_verified_prefix not in (0,1024,2048,3072,4096,5089,6090,7103,8108,9117):
        raise ValueError('Only completed, source-verified archive boundaries permit resume.')
    if out.exists() != (resume_verified_prefix>0):
        raise ValueError('Resume requires existing cache; initial run requires no cache.')
    out.mkdir(parents=True,exist_ok=resume_verified_prefix>0)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    backbone=make_backbone(weights)
    featurefile=out/'features-10123-float32.bin'
    bank=np.memmap(featurefile,dtype='float32',mode='r+' if resume_verified_prefix else 'w+',shape=(N,FEAT))
    if resume_verified_prefix:
        prefix=np.asarray(bank[:resume_verified_prefix])
        if not np.isfinite(prefix).all() or np.any(np.abs(prefix).sum(axis=1)==0):
            raise ValueError('Previously completed source features are corrupt or missing.')
        print('REUSING earlier hashed + decoded feature rows',resume_verified_prefix,flush=True)
    write=FeatureWriter(bank,source_meta,backbone,batch_size=batch_size,resume_verified_prefix=resume_verified_prefix)
    input_root=root/'inputs';private=root/'private'
    with zipfile.ZipFile(private/'capsule-blood-real-pilot.zip') as z:
        oldbytes=z.read('private-dataset-manifest/blood-manifest.json')
    if hash_bytes(oldbytes)!=OLD_MANIFEST_SHA:
        raise ValueError('Historical original blood pilot source manifest SHA differs.')
    original=json.loads(oldbytes)
    if original.get('sha256')!=OLD_IDENTIFIER:
        raise ValueError('Historical source identity identifier invalid.')
    oldrecords={r['path']:r for r in original['records'] if r['exam'] in range(1,9)}
    if len(oldrecords)!=4096:raise ValueError('Old training frame count changed.')
    for group,(archive_name,archive_hash) in OLD_ARCHIVES.items():
        zpath=input_root/archive_name
        if hash_file(zpath)!=archive_hash:raise ValueError('Original source package checksum failed '+group)
        with zipfile.ZipFile(zpath) as z:
            imgs=[x for x in z.infolist() if x.filename.startswith('images/') and x.filename.upper().endswith('.PNG')]
            if len(imgs)!=1024:raise ValueError('Original archive group image count changed.')
            for member in imgs:
                rel=member.filename.removeprefix('images/')
                if rel not in oldrecords:raise ValueError('Unexpected historical image identity.')
                record=oldrecords.pop(rel)
                write.add(int(record['exam']),int(record['frame']),int(record['blood']),1,1,
                          record['source_sha256'],z.read(member),member.file_size)
        print('Verified original image group',group,'images ingested',write.counter,flush=True)
    if oldrecords:raise ValueError('Original image manifest contains missing source files.')
    for exam,(archive_name,archive_hash,expected_count) in NEW_ARCHIVES.items():
        zpath=input_root/archive_name
        if hash_file(zpath)!=archive_hash:raise ValueError('Galar archive outer checksum failed '+str(exam))
        with zipfile.ZipFile(zpath) as outer, tempfile.TemporaryDirectory(dir=out) as stage:
            inside=[n for n in outer.namelist() if n.endswith('.zip')]
            if len(inside)!=1:raise ValueError('Unexpected original nested archive structure.')
            nested=Path(stage)/'source-original.zip'
            with outer.open(inside[0]) as src,nested.open('wb') as dst:
                shutil.copyfileobj(src,dst,1024*1024)
            with zipfile.ZipFile(nested) as imgs:
                records=json.loads(imgs.read('verified-private-manifest.json'))
                if len(records)!=expected_count:raise ValueError('Original nested manifest count differs.')
                reference=0
                for row in records:
                    e=int(row['exam']);f=int(row['frame']);label=int(row['blood']);ref=int(row['reference_uniform']);fit=int(row['fit_enriched'])
                    if e!=exam or row['filename']!=f'frame_{f:06d}.PNG':
                        raise ValueError('Incorrect original research source path identity.')
                    rel=f'images/{exam:03d}/{row["filename"]}'
                    raw=imgs.read(rel)
                    write.add(e,f,label,ref,fit,row['source_image_sha256'],raw,int(row['source_bytes']))
                    reference+=ref
                if reference!=512:raise ValueError('Expected all 512 label-blind source reference positions.')
        print('Verified additional source',exam,'images ingested',write.counter,flush=True)
    write.flush()
    bank.flush();del bank
    if write.counter!=N or len(write.seen_raw)!=N:
        raise ValueError('Not all original 10,123 images verified.')
    source_fingerprints={
        'source_count':N,
        'features_dim':FEAT,
        'source_manifest_sha256':PRIOR_META_SHA,
        'official_backbone_weight_sha256':WEIGHTS_SHA,
        'feature_bank_sha256':hash_file(featurefile),
        'data_privacy':'feature bank contains original-image-derived per-image embeddings; keep private',
        'all_original_images_sha256_reverified':True,
    }
    (out/'feature-source-verification.json').write_text(json.dumps(source_fingerprints,sort_keys=True,indent=2)+'\n')
    return source_fingerprints


def fixed_topk(labels:np.ndarray, scores:np.ndarray,frame_ids:list[int],k:int) -> int:
    if labels.size!=scores.size or labels.size!=len(frame_ids) or k<1 or k>len(labels) or not np.isfinite(scores).all():
        raise ValueError('Invalid held-out source score candidate selection.')
    order=sorted(range(len(scores)),key=lambda i:(-float(scores[i]),int(frame_ids[i])))
    return int(labels[order[:k]].sum())


def uniform_count(labels:np.ndarray,k:int) -> int:
    n=len(labels)
    return int(sum(labels[((2*j+1)*n)//(2*k)] for j in range(k)))


def evaluate_exam(exam:int,indices:list[int],scores:np.ndarray,metas:list[dict]) -> dict:
    ids=sorted(indices,key=lambda i:metas[i]['frame'])
    if len(ids)!=512 or len(ids)!=len(set(ids)):
        raise ValueError('Heldout examination must contain exactly 512 source reference images.')
    labels=np.array([metas[i]['blood'] for i in ids],dtype=np.int64)
    row_scores=np.array([scores[i] for i in ids],dtype=np.float64)
    if not np.isfinite(row_scores).all() or np.any((row_scores<0)|(row_scores>1)):
        raise ValueError('Invalid held-out uncalibrated classifier probabilities.')
    positives=int(labels.sum()); negatives=int(len(labels)-positives)
    return {'n':len(labels),'blood_positive':positives,'blood_negative_labelled':negatives,
            'roc_auc':float(roc_auc_score(labels,row_scores)) if positives and negatives else None,
            'average_precision':float(average_precision_score(labels,row_scores)) if positives else None,
            'score_mean':float(row_scores.mean()), 'score_min':float(row_scores.min()),'score_max':float(row_scores.max()),
            'score_95th_percentile':float(np.percentile(row_scores,95)),
            'top_k_blood_positive':{str(k):fixed_topk(labels,row_scores,[metas[i]['frame'] for i in ids],k) for k in BUDGETS},
            'uniform_reference_blood_positive':{str(k):uniform_count(labels,k) for k in BUDGETS}}


def evaluate_folds(features:Path, metas:list[dict], output:Path, compare:Path, verify:dict) -> dict:
    if output.exists():raise FileExistsError('Result directory exists; no overwrite.')
    if hash_file(compare)!=PRIOR_CV_AGG_SHA:raise ValueError('Prior comparable CNN aggregate is not immutable.')
    prior=json.loads(compare.read_text())
    prior_results=prior['comparators']['pooled_weighted']['per_exam']
    if set(prior_results)!=set(map(str,EXAMS)):
        raise ValueError('Prior comparable model does not contain all expected exams.')
    if hash_file(features)!=verify['feature_bank_sha256']:
        raise ValueError('Feature cache did not match original feature extraction receipt.')
    feat=np.memmap(features,mode='r',dtype=np.float32,shape=(N,FEAT))
    labels=np.array([r['blood'] for r in metas],dtype=np.int64)
    exams=np.array([r['exam'] for r in metas],dtype=np.int64)
    reference=np.array([r['reference'] for r in metas],dtype=np.int64)
    scores=np.full(N,np.nan,dtype=np.float64)
    output.mkdir(parents=True)
    models=[];per_exam={}
    fitted={}
    for fold,heldout in FOLDS.items():
        excluded=np.isin(exams,heldout)
        fitting=np.flatnonzero(~excluded)
        evaluated=np.flatnonzero(excluded & (reference==1))
        if (len(evaluated)!=len(heldout)*512 or
                set(exams[fitting]).intersection(heldout) or
                set(exams[evaluated])!=set(heldout) or
                int(labels[fitting].sum())==0):
            raise ValueError('Exam holdout separation or positive training support invalid.')
        x=np.asarray(feat[fitting],dtype=np.float64)
        scaler=StandardScaler(with_mean=True,with_std=True).fit(x)
        X=scaler.transform(x)
        if not np.isfinite(X).all():raise ValueError('Bad train-fold feature scaling.')
        model=LogisticRegression(solver='lbfgs',penalty='l2',C=C,class_weight='balanced',fit_intercept=True,
                                 max_iter=ITER,tol=TOL,random_state=SEED)
        with warnings.catch_warnings(record=True) as warned:
            warnings.simplefilter('always', ConvergenceWarning)
            model.fit(X,labels[fitting]);convergence=[str(w.message) for w in warned if issubclass(w.category,ConvergenceWarning)]
        if model.coef_.shape!=(1,FEAT):raise ValueError('Unexpected logistic probe coefficient dimensions.')
        X_eval=scaler.transform(np.asarray(feat[evaluated],dtype=np.float64))
        scores[evaluated]=model.predict_proba(X_eval)[:,1]
        model_file=output/f'{fold}-frozen-probe.npz'
        np.savez(model_file,mean=scaler.mean_,scale=scaler.scale_,coef=model.coef_,intercept=model.intercept_,
                 train_exams=np.array(sorted(set(exams[fitting])),dtype=np.int64),heldout_exams=np.array(heldout,dtype=np.int64))
        for exam in heldout:
            ids=[int(i) for i in evaluated if exams[i]==exam]
            per_exam[str(exam)]=evaluate_exam(exam,ids,scores,metas)
            earlier=prior_results[str(exam)]
            if (per_exam[str(exam)]['n'],per_exam[str(exam)]['blood_positive'],
                per_exam[str(exam)]['uniform_reference_blood_positive']) != (
                earlier['n'],earlier['blood_positive'],earlier['uniform_reference_blood_positive']):
                raise ValueError('Prior CNN held-out reference population/labels do not match.')
        models.append({'fold':fold,'heldout_exams':list(heldout),'train_exams':sorted(set(map(int,exams[fitting]))),
                       'train_image_count':int(len(fitting)),'train_blood_positive':int(labels[fitting].sum()),
                       'scaler_fitted_on_training_only':True,'model_weights_sha256':hash_file(model_file),
                       'max_iter':ITER,'actual_iterations':int(model.n_iter_[0]),
                       'convergence_warnings':convergence,'feature_dim':FEAT})
        print('FOLD',fold,'train',len(fitting),'eval',len(evaluated),'iterations',int(model.n_iter_[0]),
              'convergence_warnings',len(convergence),flush=True)
    expected=set(np.flatnonzero(reference==1));actual=set(np.flatnonzero(np.isfinite(scores)))
    if expected!=actual or len(actual)!=14*512:
        raise ValueError('Heldout predictions not exactly all allowed 7,168 references.')
    # private predictions are aligned to prior verified source frame identity, not in Git.
    private_predictions=[{'exam':int(metas[i]['exam']),'frame':int(metas[i]['frame']),
                          'blood':int(metas[i]['blood']),'score':float(scores[i])}
                         for i in sorted(expected,key=lambda i:(metas[i]['exam'],metas[i]['frame']))]
    private=output/'private-predictions.json'
    private.write_text(json.dumps(private_predictions,separators=(',',':')))
    positive=[d for d in per_exam.values() if d['blood_positive']>0]
    high=[d for d in positive if d['blood_positive']>=10]
    def summary(per):
        pos=[d for d in per.values() if d['blood_positive']>0]
        high_support=[d for d in pos if d['blood_positive']>=10]
        negative=[d for d in per.values() if d['blood_positive']==0]
        return {'positive_exams':len(pos),'high_support_positive_exams':len(high_support),'blood_negative_exams':len(negative),
                'macro_auc_positive_at_least_10':float(np.mean([d['roc_auc'] for d in high_support])),
                'macro_auc_all_positive':float(np.mean([d['roc_auc'] for d in pos])),
                'macro_ap_all_positive':float(np.mean([d['average_precision'] for d in pos])),
                'mean_score_negative_exams':float(np.mean([d['score_mean'] for d in negative])),
                'total_positive_image_hits_at_k':{str(k):sum(int(d['top_k_blood_positive'][str(k)]) for d in per.values()) for k in BUDGETS},
                'total_uniform_hits_at_k':{str(k):sum(int(d['uniform_reference_blood_positive'][str(k)]) for d in per.values()) for k in BUDGETS}}
    prior_summary=summary(prior_results)
    result={'study':'Frozen full-field ImageNet MobileNetV3 576-D features + train-only logistic vs previous compact CNN',
            'role':'Previously examined Galar fitting studies, three exam-disjoint folds; not blinded or clinically validated',
            'experiment_protocol_git_blob_sha1':SPEC_BLOB_SHA,
            'sources':{'prior_cv_source_meta_sha256':PRIOR_META_SHA,'backbone_imageNet_v1_weights_sha256':WEIGHTS_SHA,
                       'original_images_source_verified':N,'explicit_blood_positive_annotations':int(labels.sum()),
                       'label_blind_holdout_images':len(expected),'feature_bank_sha256':verify['feature_bank_sha256'],
                       'prior_compact_cnn_aggregate_sha256':PRIOR_CV_AGG_SHA},
            'representation':{'name':'MobileNetV3_small_ImageNet_V1_fullfield_160_576D','frozen':True,'all_original_png_hashes_verified':True},
            'linear_probe':{'train_fold_only_standardization':True,'solver':'lbfgs','C':C,'max_iter':ITER,'tol':TOL,'class_weight':'balanced'},
            'folds':models,'per_exam':per_exam,'summary':summary(per_exam),
            'prior_pooled_weighted_cnn':{'per_exam':prior_results,'summary':prior_summary},
            'status':'complete exploratory, no model promotion','clinical_validity':False,'independent_patient_ids_verified':False,
            'unopened_reserved_cohorts_preserved':True,
            'private_prediction_sha256':hash_file(private)}
    (output/'aggregate-private.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    # Nonidentifying aggregate for git -- omit weights/individual score refs, detailed private source metadata.
    public={k:v for k,v in result.items() if k not in ('prior_pooled_weighted_cnn','private_prediction_sha256')}
    public['previous_frozen_compact_cnn']={'summary':prior_summary,'per_exam':prior_results}
    # Internal private scaler and checkpoint checksums are not useful publicly.
    public['folds']=[{k:v for k,v in row.items() if k!='model_weights_sha256'} for row in models]
    (output/'aggregate.json').write_text(json.dumps(public,sort_keys=True,indent=2)+'\n')
    print('RESULT_SUMMARY',json.dumps({'pretrained':result['summary'],'pooled_cnn':prior_summary},sort_keys=True),flush=True)
    print('PUBLIC_AGGREGATE_SHA256',hash_file(output/'aggregate.json'),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--weight-path',type=Path,required=True)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--prior-aggregate',type=Path,required=True)
    p.add_argument('--mode',choices=('all','extract','fit'),default='all')
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--resume-verified-prefix',type=int,default=0)
    a=p.parse_args()
    if not 1<=a.threads<=8:raise ValueError('Limit feature extraction to approved threads 1..8.')
    validate_spec(a.spec)
    if not a.workdir.exists():a.workdir.mkdir(parents=True)
    features=a.workdir/'extracted'
    metadata=check_metadata(a.data_root/'private_outputs'/'private_source_metadata.json')
    if a.mode in ('all','extract'):
        extract_all(a.data_root,features,metadata,a.weight_path,threads=a.threads,resume_verified_prefix=a.resume_verified_prefix)
    if a.mode in ('all','fit'):
        verification=json.loads((features/'feature-source-verification.json').read_text())
        evaluate_folds(features/'features-10123-float32.bin',metadata,a.workdir/'results',a.prior_aggregate,verification)


if __name__=='__main__':main()
