"""Fixed ImageNet feature-transfer Galar blood-annotation research baseline.

Not a medical diagnostic model or an independent held-out test. This script
never downloads images or pretrained weights and never updates the frozen CNN.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from PIL import Image

from blood_image_pilot import evaluate, red_excess, validate_manifest
from capsule_review.baseline_data import safe_path

WEIGHTS_SHA256 = '047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'
MANIFEST_SHA256 = '4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb'
SPEC_SHA256 = '1bd8dedaca37e41709e84f993b422193d78797744e167e92ee08b30d567fb7cb'
LEGACY_METRICS_SHA256 = '781b855c0e14278fb20cb45f25f2481bcf379182aa4dd9d8e9b9c93a12928d7a'
DIMENSIONS = 576
SEED = 17
L2 = 0.01
MAX_ITER = 100
BUDGETS = (5, 10, 25, 50, 75, 100)


def hash_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_inputs(manifest: Path, images: Path, weights: Path, spec: Path) -> dict:
    if hash_file(weights) != WEIGHTS_SHA256:
        raise ValueError('Official torchvision pretrained weights have unexpected SHA-256.')
    if hash_file(spec) != SPEC_SHA256:
        raise ValueError('The frozen, pre-fit research specification changed.')
    data = validate_manifest(manifest, images, check_files=True)
    if data['sha256'] != MANIFEST_SHA256:
        raise ValueError('Different source images or examination split than frozen pilot.')
    if data['split']['train_exams'] != list(range(1,9)) or data['split']['development_exams'] != [9,10]:
        raise ValueError('Research split changed.')
    return data


def backbone_from_official_weights(weights_path: Path):
    """Only tensor weights from official torchvision; no internet requests."""
    import torch
    from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
    w = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    if w.url != 'https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth':
        raise ValueError('Torchvision weight identity changed unexpectedly.')
    net = mobilenet_v3_small(weights=None).cpu().eval()
    state = torch.load(weights_path, map_location='cpu', weights_only=True)
    reference = net.state_dict()
    if (not isinstance(state, dict) or state.keys()!=reference.keys() or any(
            not torch.is_tensor(state[k]) or state[k].shape!=reference[k].shape or
            not torch.isfinite(state[k]).all() for k in reference)):
        raise ValueError('Unexpected model architecture, weight shapes, or nonfinite values.')
    net.load_state_dict(state, strict=True)
    for param in net.parameters():
        param.requires_grad_(False)
    return net, w.transforms()


def extract_features(rows: list[dict], images: Path, weights: Path, *, batch_size: int=32):
    import torch
    from torch.utils.data import DataLoader, Dataset
    torch.set_num_threads(3)
    net, preprocess=backbone_from_official_weights(weights)
    class Frames(Dataset):
        def __len__(self):return len(rows)
        def __getitem__(self, i):
            with Image.open(safe_path(images, rows[i]['path'])) as im:
                return preprocess(im.convert('RGB'))
    loader=DataLoader(Frames(), batch_size=batch_size, shuffle=False, num_workers=0)
    outputs=[]
    with torch.inference_mode():
        for i, batch in enumerate(loader):
            features=net.avgpool(net.features(batch.cpu())).flatten(1)
            if features.shape[1]!=DIMENSIONS or not torch.isfinite(features).all():
                raise ValueError('Invalid MobileNet feature tensor.')
            outputs.append(features.detach().to(torch.float64))
            if (i+1)%40==0:
                print(f'features {min((i+1)*batch_size,len(rows))}/{len(rows)}',flush=True)
    return torch.cat(outputs,0)


def fit_linear_probe(features, labels, *, l2: float=L2):
    """Deterministic, train-only weighted regularized binary logistic probe."""
    import torch
    from torch.nn import functional as F
    if features.ndim != 2 or features.shape[1]!=DIMENSIONS or features.shape[0]!=len(labels):
        raise ValueError('Training feature/label shape mismatch.')
    if any(y not in (0,1) for y in labels) or len(set(labels))!=2:
        raise ValueError('Both explicit blood-label classes must occur in fitting data.')
    if not 0<l2<=1:
        raise ValueError('Invalid L2 coefficient.')
    y=torch.as_tensor(labels,dtype=torch.float64)
    if not torch.isfinite(features).all():
        raise ValueError('Nonfinite features cannot be fitted.')
    mean=features.mean(0)
    scale=features.std(0,unbiased=False).clamp_min(1e-6)
    x=(features-mean)/scale
    weight=torch.nn.Parameter(torch.zeros(DIMENSIONS,dtype=torch.float64))
    bias=torch.nn.Parameter(torch.zeros((),dtype=torch.float64))
    optimizer=torch.optim.LBFGS([weight,bias],lr=1,max_iter=MAX_ITER,
                                line_search_fn='strong_wolfe',tolerance_grad=1e-8)
    # Weight is fixed by train-only label prevalence, not development outcomes.
    pos_weight=torch.tensor(float((len(y)-sum(labels))/sum(labels)),dtype=torch.float64)
    def closure():
        optimizer.zero_grad()
        logits=x @ weight+bias
        loss=F.binary_cross_entropy_with_logits(logits,y,pos_weight=pos_weight)
        loss=loss + l2*(weight @ weight)/2
        loss.backward()
        return loss
    optimizer.step(closure)
    with torch.no_grad():
        fit_logits=x @ weight + bias
        loss=float(F.binary_cross_entropy_with_logits(fit_logits,y,pos_weight=pos_weight)
                   +l2*(weight @ weight)/2)
        return {'mean':mean.tolist(),'scale':scale.tolist(),'weight':weight.detach().tolist(),
                'bias':float(bias.detach()),'train_loss':loss,'train_positive':int(sum(labels)),
                'train_total':len(labels),'regularization':l2,
                'iterations_upper_bound':MAX_ITER}


def score_probe(features, probe: dict) -> list[float]:
    import torch
    if (features.ndim!=2 or features.shape[1]!=DIMENSIONS or
        len(probe['mean'])!=DIMENSIONS or len(probe['scale'])!=DIMENSIONS or
        len(probe['weight'])!=DIMENSIONS):
        raise ValueError('Unexpected pretrained feature/probe dimension.')
    m=torch.tensor(probe['mean'],dtype=torch.float64)
    s=torch.tensor(probe['scale'],dtype=torch.float64)
    w=torch.tensor(probe['weight'],dtype=torch.float64)
    b=float(probe['bias'])
    if (not (torch.isfinite(m).all() and torch.isfinite(s).all() and torch.isfinite(w).all()
          and math.isfinite(b)) or (s<=0).any()):
        raise ValueError('Invalid probe/scaling parameters.')
    with torch.inference_mode():
        return torch.sigmoid(((features-m)/s)@w+b).tolist()


def budgets(rows: list[dict], scores: list[float]) -> dict:
    import random
    if len(rows)!=len(scores) or any(not math.isfinite(v) or v<0 or v>1 for v in scores):
        raise ValueError('Scores and source rows must align and be finite probabilities.')
    result={}
    for pct in BUDGETS:
        by_exam={}
        for exam in (9,10):
            idx=[i for i,r in enumerate(rows) if r['exam']==exam]
            n=len(idx);k=n*pct//100
            if n!=512 or k<1:
                raise ValueError('Expected 512 frozen frames per development examination.')
            chosen=sorted(range(n),key=lambda j:(-scores[idx[j]],j))[:k]
            # Match the frozen original blood-image pilot's uniform selector.
            uniform={(2*j+1)*n//(2*k) for j in range(k)}
            y=[rows[i]['blood'] for i in idx]
            hit=sum(y[j] for j in chosen)
            uh=sum(y[j] for j in uniform)
            rng=random.Random(SEED+exam*1009+pct)
            rand=[sum(y[j] for j in rng.sample(range(n),k)) for _ in range(100)]
            pos=sum(y)
            by_exam[str(exam)]={'total':n,'selected':k,'blood_positive':pos,
                                'model_positive_hits':hit,
                                'uniform_positive_hits':uh,
                                'seeded_random_mean_hits':sum(rand)/len(rand),
                                'model_positive_recall':hit/pos if pos else None,
                                'uniform_positive_recall':uh/pos if pos else None,
                                'model_selected_blood_label_negative':k-hit}
        result[str(pct)]=by_exam
    return result


def cache_one_exam(manifest:Path, images:Path, weights:Path, spec:Path, output_dir:Path, exam:int) -> Path:
    """Resumable, integrity-checked feature extraction; never writes source pixels."""
    import numpy as np
    from capsule_review.baseline_data import image_identity
    if exam not in range(1,11):
        raise ValueError('Only the ten frozen Galar development examination IDs are allowed.')
    if hash_file(weights)!=WEIGHTS_SHA256 or hash_file(spec)!=SPEC_SHA256:
        raise ValueError('Pretrained weights or research protocol changed.')
    data=validate_manifest(manifest,images,check_files=False)
    if data['sha256']!=MANIFEST_SHA256:
        raise ValueError('Frozen manifest changed.')
    rows=[r for r in data['records'] if r['exam']==exam]
    if len(rows)!=512 or any(r['split']!=('train' if exam<=8 else 'development') for r in rows):
        raise ValueError('Unexpected examination split or source-frame count.')
    for row in rows:
        path=safe_path(images,row['path'])
        raw,pixel=image_identity(path)
        if (raw,pixel)!=(row['source_sha256'],row['pixel_sha256']):
            raise ValueError('Source PNG or decoded pixels changed from the frozen manifest.')
    dest=output_dir/f'features-exam-{exam:02}.npy'
    receipt=output_dir/f'features-exam-{exam:02}.json'
    if dest.exists() or receipt.exists():
        raise FileExistsError('Refusing to overwrite a verified feature shard.')
    output_dir.mkdir(parents=True,exist_ok=True)
    values=extract_features(rows,images,weights)
    if values.shape!=(512,DIMENSIONS):
        raise ValueError('Unexpected feature shape.')
    np.save(dest,values.numpy(),allow_pickle=False)
    meta={'manifest_sha256':data['sha256'],'official_weights_sha256':WEIGHTS_SHA256,
          'spec_sha256':SPEC_SHA256,'exam':exam,'count':512,'dimensions':DIMENSIONS,
          'features_sha256':hash_file(dest),'role':'train' if exam<=8 else 'development',
          'first_source_sha256':rows[0]['source_sha256'],
          'last_source_sha256':rows[-1]['source_sha256']}
    receipt.write_text(json.dumps(meta,indent=2))
    return dest


def load_feature_cache(cache_dir:Path,manifest_data:dict):
    import numpy as np
    import torch
    all_features=[]
    for exam in range(1,11):
        path=cache_dir/f'features-exam-{exam:02}.npy'
        receipt=cache_dir/f'features-exam-{exam:02}.json'
        meta=json.loads(receipt.read_text())
        rows=[x for x in manifest_data['records'] if x['exam']==exam]
        required={'manifest_sha256':MANIFEST_SHA256,'official_weights_sha256':WEIGHTS_SHA256,
                  'spec_sha256':SPEC_SHA256,'exam':exam,'count':512,
                  'dimensions':DIMENSIONS,'role':'train' if exam<=8 else 'development',
                  'first_source_sha256':rows[0]['source_sha256'],
                  'last_source_sha256':rows[-1]['source_sha256']}
        if any(meta.get(k)!=v for k,v in required.items()) or meta['features_sha256']!=hash_file(path):
            raise ValueError(f'Feature shard receipt mismatch for examination {exam}.')
        a=np.load(path,allow_pickle=False)
        if a.shape!=(512,DIMENSIONS) or a.dtype!=np.float64 or not np.isfinite(a).all():
            raise ValueError(f'Invalid feature matrix for examination {exam}.')
        all_features.append(torch.from_numpy(a.copy()))
    return torch.cat(all_features,dim=0)

def run(manifest: Path, images: Path, weights: Path, spec:Path, output:Path, existing_metrics: Path, cache_dir:Path|None=None):
    if output.exists():
        raise FileExistsError('Refusing to overwrite completed research results.')
    import torch
    if cache_dir is None:
        data=validate_inputs(manifest,images,weights,spec)
    else:
        if hash_file(weights)!=WEIGHTS_SHA256 or hash_file(spec)!=SPEC_SHA256:
            raise ValueError('Pretrained weights or fixed protocol changed.')
        data=validate_manifest(manifest,images,check_files=False)
        if data['sha256']!=MANIFEST_SHA256:
            raise ValueError('Frozen Galar manifest changed.')
    torch.manual_seed(SEED);torch.use_deterministic_algorithms(True)
    train=[r for r in data['records'] if r['split']=='train']
    dev=[r for r in data['records'] if r['split']=='development']
    if len(train)!=4096 or len(dev)!=1024:
        raise ValueError('Frozen train/development counts changed.')
    # All training and normalization use ONLY examinations 1-8.
    features=load_feature_cache(cache_dir,data) if cache_dir else None
    fit_features=features[:4096] if features is not None else extract_features(train,images,weights)
    head=fit_linear_probe(fit_features,[r['blood'] for r in train])
    del fit_features
    dev_features=features[4096:] if features is not None else extract_features(dev,images,weights)
    scores=score_probe(dev_features,head)
    if hash_file(existing_metrics)!=LEGACY_METRICS_SHA256:
        raise ValueError('Frozen original CNN comparator metrics changed.')
    original=json.loads(existing_metrics.read_text())
    if (original['dataset_manifest_sha256']!=data['sha256'] or
            original['development_examinations']!=[9,10] or
            original['fitting_examinations']!=list(range(1,9))):
        raise ValueError('Original comparator not aligned to frozen source/split.')
    metrics={'status':'historical exploratory development only, not independent pathology validation',
             'model':'torchvision ImageNet MobileNetV3-small frozen global-average-pool features + train-only weighted regularized logistic probe',
             'frozen_spec_sha256':SPEC_SHA256,
             'frozen_manifest_sha256':data['sha256'],
             'official_backbone_sha256':WEIGHTS_SHA256,
             'preprocessing':'torchvision IMAGENET1K_V1 deterministic validation transform',
             'label':'Galar v2 explicit blood; absent blood != all-pathology normal',
             'train_examinations':list(range(1,9)),'historical_development_examinations':[9,10],
             'training_support':{str(e):data['counts'][str(e)] for e in range(1,9)},
             'evaluation':evaluate(dev,scores),'budgets':budgets(dev,scores),
             'legacy_frozen_cnn':original['cnn'],
             'legacy_frozen_redness':original['fixed_red_excess_comparator'],
             'train_only_probe_loss':head['train_loss'],
             'limitations':['Exams 9/10 were examined during earlier work, no fresh held-out test.',
                            'Only exam 10 contains positive blood-labelled development frames.',
                            'Training positives are concentrated in exam 7 (208 of 239).',
                            'Frame scoring on 512 sparse images/examination; not full-sequence pathology interval coverage.',
                            'Uncalibrated ImageNet feature-transfer score, not a patient diagnosis or severity estimate.',
                            'Patient independence, site/device generalization, and clinical efficacy unverified.']}
    output.mkdir(parents=True,exist_ok=False)
    (output/'probe-head.json').write_text(json.dumps(head,indent=2,allow_nan=False))
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False))
    with (output/'predictions.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['exam','frame','source_sha256','blood_label','mobilenet_score'])
        for r,s in zip(dev,scores):
            writer.writerow([r['exam'],r['frame'],r['source_sha256'],r['blood'],format(s,'.17g')])
    (output/'provenance.json').write_text(json.dumps({
        'official_weight_bytes':weights.stat().st_size,'official_weight_sha256':WEIGHTS_SHA256,
        'frozen_spec_sha256':SPEC_SHA256,'frozen_manifest_sha256':data['sha256'],
        'head_sha256':hash_file(output/'probe-head.json'),'metrics_sha256':hash_file(output/'metrics.json'),
        'predictions_sha256':hash_file(output/'predictions.csv')},indent=2))
    return metrics


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('extract','fit'),default='fit')
    for key in ('manifest','images','weights','spec'):
        ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--cache-dir',type=Path)
    ap.add_argument('--exam',type=int)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--existing-metrics',type=Path)
    a=ap.parse_args()
    if a.mode=='extract':
        if a.exam is None or a.cache_dir is None:
            ap.error('Extraction needs --exam and --cache-dir.')
        print(cache_one_exam(a.manifest,a.images,a.weights,a.spec,a.cache_dir,a.exam))
    else:
        if a.output is None or a.existing_metrics is None:
            ap.error('Fit needs --output and --existing-metrics.')
        m=run(a.manifest,a.images,a.weights,a.spec,a.output,a.existing_metrics,a.cache_dir)
        print(json.dumps({'evaluation':m['evaluation']['aggregate'],
                          'exam10':m['evaluation']['by_examination']['10']},indent=2))

if __name__=='__main__':main()
