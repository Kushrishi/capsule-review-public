"""Exam-disjoint exploratory Galar blood CNN comparison; never opens reserved exam images.

Private original images, per-frame predictions and weights remain outside Git.
The full methodology is frozen in docs/GALAR_EXAM_CV_SPEC.json at commit cc93ec3.
"""
from __future__ import annotations
import hashlib, io, json, os, shutil, tempfile, zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from torch import nn
from PIL import Image, ImageOps, ImageChops, ImageStat
from sklearn.metrics import roc_auc_score, average_precision_score

BASE=Path(os.environ.get('CAPSULE_CV_DATA_ROOT', '/mnt/data/capsule_next'))
INPUT=BASE/'inputs'; PRIVATE=BASE/'private'; OUT=BASE/'private_outputs'
EXAMS=(1,2,3,4,5,6,7,8,21,23,25,27,29,30)
OLD_MANIFEST_SHA='0f1cec23f43023788428c0fa694f6f00f42b367fd2ed2f539b97a57443080f59'
OLD_IDENTIFIER='4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb'
OLD_ARCHIVES={
 '001_002':('galar-pilot-images-001-002.zip','303d6daed3593d6e31212be1c78ff7e780c032889cc6632780ea4764ab4ab2b2'),
 '003_004':('galar-pilot-images-003-004.zip','3fbb37e6154dc008e3c4f5e037b03d651cb0cdb64967418c9aa1b973ae383047'),
 '005_006':('galar-pilot-images-005-006.zip','17d7e68a10b33f436bc06f12c757472b396d09676107eb018c53e650d964b36b'),
 '007_008':('galar-pilot-images-007-008.zip','2f87e4a69ab1f30ae11510a1f4f08a0427133e7749c0419ef87bc3c36715c881')}
NEW_ARCHIVES={
 21:('galar-exam21-verified-frames-private.zip','aa18ee3ba5ef98d0ac139fa2a76d033136f95e6686c7645389006c78e6d8c901',993),
 23:('galar-exam23-verified-frames-private.zip','44d2f6b6e91cb4f0df0243a8a0dc8560936e787f80b42c8cf1252a6d862be6f8',1001),
 25:('galar-exam25-verified-frames-private.zip','6045abf1651bc6585cbc55ccaaf00d2462ba6a10900f4a11e4f064c62e51bb8b',1013),
 27:('galar-exam27-verified-frames-private.zip','b04e5e598357b50ccff29c77dfb5b88d2896a1ceaf45eabc2bd7719c363ae47a',1005),
 29:('galar-exam29-verified-frames-private.zip','9cf8736cb269fbb91bb2e1405425c7be0958be5914ab4321fa701e61f4b92d66',1009),
 30:('galar-exam30-verified-frames-private.zip','8eaa78453566f57d06ccd094ca3a057db4ed23552d366d540341bb0a73041e45',1006)}
FOLDS={'A':(1,3,21,27,29),'B':(2,5,23,25,30),'C':(4,6,7,8)}
ARMS=('pooled_weighted','exam_balanced_jitter')
BUDGETS=(51,128,256,512)
SEED=37;STEPS=384;BATCH=32;LR=0.0002;DECAY=0.0001

class AnatomyCNN(nn.Module):
 def __init__(self,classes=2):
  super().__init__(); blocks=[]
  for before,after in zip((3,16,32),(16,32,64)):
   blocks.extend([nn.Conv2d(before,after,3,stride=2,padding=1),nn.GroupNorm(4,after),nn.ReLU()])
  self.features=nn.Sequential(*blocks,nn.AdaptiveAvgPool2d(1))
  self.classifier=nn.Linear(64,classes)
 def forward(self,images):return self.classifier(self.features(images).flatten(1))

def hashfile(file):
 h=hashlib.sha256()
 with open(file,'rb') as f:
  for chunk in iter(lambda:f.read(1<<22),b''):h.update(chunk)
 return h.hexdigest()

def sha(data):return hashlib.sha256(data).hexdigest()

def get_pixels(raw):
 with Image.open(io.BytesIO(raw)) as im:
  if im.format!='PNG':raise ValueError('Original source image not valid PNG')
  im=ImageOps.exif_transpose(im).convert('RGB')
  padded=ImageOps.pad(im,(96,96),method=Image.Resampling.BILINEAR,color=(0,0,0))
  crop=ImageOps.fit(im,(96,96))
  r,g,b=crop.split();red=ImageChops.subtract(r,ImageChops.lighter(g,b))
  red_score=ImageStat.Stat(red).mean[0]/255.0
  return np.asarray(padded,dtype=np.uint8),red_score

def ingest():
 OUT.mkdir(exist_ok=True)
 oldpilot=PRIVATE/'capsule-blood-real-pilot.zip'
 with zipfile.ZipFile(oldpilot) as z:
  data=z.read('private-dataset-manifest/blood-manifest.json')
 if sha(data)!=OLD_MANIFEST_SHA:raise ValueError('Historical original blood-manifest digest mismatch')
 old=json.loads(data)
 if old['sha256']!=OLD_IDENTIFIER:raise ValueError('Original historical 512-image identity differs')
 oldrecords={r['path']:r for r in old['records'] if r['exam'] in range(1,9)}
 if len(oldrecords)!=4096:raise ValueError('Unexpected historical train records')
 allmeta=[];seen_ids=set();seen_sha=set()
 bank=OUT/'bank_96_rgb_uint8.dat'
 if bank.exists():raise FileExistsError('Private bank already exists, no overwrite')
 xx=np.memmap(bank,mode='w+',dtype=np.uint8,shape=(10123,96,96,3)); cursor=0
 def add(exam,frame,blood,reference,enriched,expected_sha,raw,original_bytes):
  nonlocal cursor
  if exam not in EXAMS or exam in (9,10) or (exam,frame) in seen_ids:raise ValueError('Forbidden or duplicate source exam/image')
  if blood not in (0,1) or reference not in (0,1) or enriched not in (0,1):raise ValueError('Invalid binary training label/role')
  if sha(raw)!=expected_sha or len(raw)!=original_bytes:raise ValueError('Original source image hash/bytes mismatch')
  if expected_sha in seen_sha:raise ValueError('Duplicate original source image bytes within/across examinations')
  seen_ids.add((exam,frame));seen_sha.add(expected_sha)
  pixel,red=get_pixels(raw)
  xx[cursor]=pixel
  allmeta.append({'exam':exam,'frame':frame,'blood':blood,'reference':reference,'enriched':enriched,'red_score':red})
  cursor+=1
 for key,(filename,expected) in OLD_ARCHIVES.items():
  zpath=INPUT/filename
  if hashfile(zpath)!=expected:raise ValueError('Original training PNG archive digest mismatch')
  with zipfile.ZipFile(zpath) as z:
   refs=[m for m in z.infolist() if m.filename.startswith('images/') and m.filename.upper().endswith('.PNG')]
   if len(refs)!=1024:raise ValueError('Unexpected original package image count')
   for m in refs:
    short=m.filename.removeprefix('images/')
    if short not in oldrecords:raise ValueError('Unmapped original historical image')
    r=oldrecords.pop(short);ex=int(r['exam']);frame=int(r['frame'])
    add(ex,frame,int(r['blood']),1,1,r['source_sha256'],z.read(m),m.file_size)
  print('verified original training archive',key,'images',cursor,flush=True)
 if oldrecords:raise ValueError('Some original 1-8 source images missing')
 for exam,(filename,expected,expected_count) in NEW_ARCHIVES.items():
  path=INPUT/filename
  if hashfile(path)!=expected:raise ValueError(f'Original Galar {exam} package digest mismatch')
  with zipfile.ZipFile(path) as outer, tempfile.TemporaryDirectory(dir=OUT) as temp:
   innername=next((n for n in outer.namelist() if n.endswith('.zip')),None)
   if not innername:raise ValueError('Missing verified nested source package')
   innertmp=Path(temp)/'source.zip'
   with outer.open(innername) as src,innertmp.open('wb') as dest:shutil.copyfileobj(src,dest,1<<20)
   with zipfile.ZipFile(innertmp) as inner:
    members=json.loads(inner.read('verified-private-manifest.json'))
    if len(members)!=expected_count:raise ValueError('Wrong verified source manifest length')
    counts=0;ref_count=0
    for r in members:
     ex=int(r['exam']);frame=int(r['frame']);filename=r['filename'];blood=int(r['blood'])
     if ex!=exam or filename!=f'frame_{frame:06d}.PNG':raise ValueError('Original source image ID and path disagree')
     ref=int(r['reference_uniform']);fit=int(r['fit_enriched'])
     if not(ref or fit):raise ValueError('Unknown image selection role')
     imgname=f'images/{exam:03d}/{filename}'
     add(ex,frame,blood,ref,fit,r['source_image_sha256'],inner.read(imgname),int(r['source_bytes']))
     counts+=1;ref_count+=ref
    if ref_count!=512:raise ValueError('Missing label-blind reference images')
   print('verified new fitting archive',exam,'images',counts,'total',cursor,flush=True)
 if cursor!=10123 or len(seen_ids)!=10123 or len(seen_sha)!=10123:raise ValueError('Cohort size/uniqueness mismatch')
 if sum(r['blood'] for r in allmeta)!=1663:raise ValueError('Fixed training-label support changed')
 for exam in EXAMS:
  rows=[r for r in allmeta if r['exam']==exam]
  if len(rows)!=(512 if exam<=8 else NEW_ARCHIVES[exam][2]):raise ValueError('Expected exam size differs')
  if sum(r['reference'] for r in rows)!=512:raise ValueError('Missing 512 label-blind per-examination validation reference')
  if exam in (3,5,8) and any(r['blood'] for r in rows):raise ValueError('Claimed negative examination contains positives')
 xx.flush();del xx
 # Highly private per-image metadata; do not move into Git.
 private=OUT/'private_source_metadata.json'
 if private.exists():raise FileExistsError('Refuse to overwrite prior metadata')
 private.write_text(json.dumps(allmeta,separators=(',',':')),encoding='utf-8')
 fingerprint=sha(private.read_bytes())
 print('COMPLETE SOURCE INTEGRITY',len(allmeta),'positive',sum(r['blood'] for r in allmeta),'private-metadata-sha',fingerprint,flush=True)
 return allmeta,fingerprint

def top_k(y, scores, frames, k):
 order=sorted(range(len(scores)),key=lambda i:(-scores[i],frames[i]))
 return int(sum(y[i] for i in order[:k]))

def uniform_k(y,k):
 n=len(y);return int(sum(y[((2*j+1)*n)//(2*k)] for j in range(k)))

def evaluate(exam, ids, scores, metas):
 ordered=sorted(range(len(ids)),key=lambda j:metas[ids[j]]['frame'])
 ids=[ids[j] for j in ordered];scores=[float(scores[j]) for j in ordered]
 y=[metas[i]['blood'] for i in ids];n=len(y)
 if n!=512:raise ValueError('Expected the 512 label-blind reference images')
 positive=sum(y);negative=n-positive
 value={'n':n,'blood_positive':positive,'blood_negative_labelled':negative,
       'roc_auc':float(roc_auc_score(y,scores)) if 0<positive<n else None,
       'average_precision':float(average_precision_score(y,scores)) if positive else None,
       'score_mean':float(np.mean(scores)),
       'score_min':float(np.min(scores)),'score_max':float(np.max(scores)),
       'top_k_blood_positive':{str(k):top_k(y,scores,[metas[i]['frame'] for i in ids],k) for k in BUDGETS},
       'uniform_reference_blood_positive':{str(k):uniform_k(y,k) for k in BUDGETS}}
 return value

def train(metas, fold, holdouts, arm, bank):
 held=set(holdouts); fit=np.array([i for i,r in enumerate(metas) if r['exam'] not in held],dtype=np.int64)
 fitexam=sorted(set(metas[i]['exam'] for i in fit))
 if set(fitexam)&held or len(fitexam)<8:raise ValueError('Examination leakage or insufficient fitting support')
 labels=np.array([r['blood'] for r in metas],dtype=np.int64)
 pos=int(labels[fit].sum());neg=int(len(fit)-pos)
 if pos<=0 or neg<=0:raise ValueError('Missing train classes')
 weights=torch.tensor([len(fit)/(2*neg),len(fit)/(2*pos)],dtype=torch.float32)
 torch.manual_seed(SEED)
 model=AnatomyCNN(2).float().cpu().train()
 opt=torch.optim.AdamW(model.parameters(),lr=LR,weight_decay=DECAY)
 rng=np.random.default_rng(SEED)
 jitter_rng=torch.Generator().manual_seed(SEED+1)
 by_exam={e:{c:np.array([i for i in fit if metas[int(i)]['exam']==e and labels[int(i)]==c],dtype=np.int64) for c in (0,1)} for e in fitexam}
 history=[]
 for step in range(1,STEPS+1):
  if arm=='pooled_weighted':
   batchids=rng.choice(fit,size=BATCH,replace=True)
  else:
   exams=rng.choice(fitexam,size=BATCH,replace=True)
   classes=rng.integers(0,2,size=BATCH)
   batchids=np.empty(BATCH,dtype=np.int64)
   for j,(exam,c) in enumerate(zip(exams,classes)):
    pool=by_exam[int(exam)][int(c)]
    if not len(pool):pool=by_exam[int(exam)][1-int(c)]
    batchids[j]=pool[int(rng.integers(len(pool)))]
  xb=torch.from_numpy(np.array(bank[batchids],copy=True)).permute(0,3,1,2).float().div_(255)
  yb=torch.from_numpy(labels[batchids].copy()).long()
  if arm=='exam_balanced_jitter':
   b=(0.75+0.5*torch.rand((BATCH,1,1,1),generator=jitter_rng))
   s=(0.75+0.5*torch.rand((BATCH,1,1,1),generator=jitter_rng))
   grey=(0.299*xb[:,0:1]+0.587*xb[:,1:2]+0.114*xb[:,2:3])
   xb=(grey+(xb-grey)*s)*b
   xb.clamp_(0,1)
  out=model(xb)
  loss=nn.functional.cross_entropy(out,yb,weight=weights if arm=='pooled_weighted' else None)
  if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
  opt.zero_grad(set_to_none=True);loss.backward();opt.step()
  if step in (1,96,192,288,384):
   history.append({'update':step,'loss':float(loss.detach().item())})
   if step in (1,192,384):print('TRAIN',fold,arm,'step',step,'loss',round(history[-1]['loss'],5),flush=True)
 model.eval()
 weightsfile=OUT/f'{fold}-{arm}.pt'
 if weightsfile.exists():raise FileExistsError('Refuse to overwrite prior model')
 torch.save({k:v.cpu() for k,v in model.state_dict().items()},weightsfile)
 checkpoint_sha=hashfile(weightsfile)
 results={}
 privatepred=[]
 with torch.no_grad():
  for ex in holdouts:
   select=np.array([i for i,r in enumerate(metas) if r['exam']==ex and r['reference']==1],dtype=np.int64)
   if len(select)!=512:raise ValueError('Held out source sample incorrect')
   scores=[]
   for batch in np.array_split(select,8):
    x=torch.from_numpy(np.array(bank[batch],copy=True)).permute(0,3,1,2).float().div_(255)
    scores.extend(nn.functional.softmax(model(x),dim=1)[:,1].tolist())
   results[str(ex)]=evaluate(ex,select,scores,metas)
   privatepred.extend({'exam':int(ex),'frame':metas[int(i)]['frame'],'blood':metas[int(i)]['blood'],'score':float(s)} for i,s in zip(select,scores))
 # Private per-frame predictions are stored in a separate sidecar, never Git.
 predfile=OUT/f'{fold}-{arm}-private-predictions.json'
 if predfile.exists():raise FileExistsError('Private predictions already exist')
 predfile.write_text(json.dumps(privatepred,separators=(',',':')),encoding='utf-8')
 return {'fold':fold,'arm':arm,'fit_exams':fitexam,'heldout_exams':list(holdouts),'fit_images':int(len(fit)),
         'fit_blood_positive':pos,'fit_blood_negative_labelled':neg,
         'optimizer_steps':STEPS,'batch_size':BATCH,'seed':SEED,
         'checkpoint_sha256':checkpoint_sha,'private_prediction_sha256':hashfile(predfile),
         'training_loss_snapshots':history,'exam_results':results}

def main():
 if (OUT/'aggregate.json').exists():raise FileExistsError('Do not overwrite aggregate')
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 np.random.seed(SEED);torch.manual_seed(SEED)
 from importlib.metadata import version
 meta,hashmeta=ingest()
 bank=np.memmap(OUT/'bank_96_rgb_uint8.dat',dtype=np.uint8,mode='r',shape=(len(meta),96,96,3))
 folds=[]
 for fold,held in FOLDS.items():
  for arm in ARMS:folds.append(train(meta,fold,held,arm,bank))
 exams=set();flat={}
 for row in folds:
  key=row['arm'];flat.setdefault(key,{})
  for ex,results in row['exam_results'].items():
   if ex in flat[key]:raise ValueError('Examination in more than one heldout fold')
   flat[key][ex]=results
 if any(set(group)!=set(map(str,EXAMS)) for group in flat.values()):raise ValueError('Heldout exam coverage incomplete')
 def score_summary(values):
  positive={int(e):v for e,v in values.items() if v['blood_positive']>0}
  stable={e:v for e,v in positive.items() if v['blood_positive']>=10}
  neg={int(e):v for e,v in values.items() if v['blood_positive']==0}
  return {'positive_exam_count':len(positive),'high_support_positive_exam_count':len(stable),'negative_exam_count':len(neg),
          'macro_auc_all_positive':float(np.mean([v['roc_auc'] for v in positive.values()])),
          'macro_auc_reference_positive_at_least_10':float(np.mean([v['roc_auc'] for v in stable.values()])),
          'macro_ap_all_positive':float(np.mean([v['average_precision'] for v in positive.values()])),
          'mean_score_negative_exams':float(np.mean([v['score_mean'] for v in neg.values()])),
          'total_positive_image_hits_by_k':{str(k):sum(v['top_k_blood_positive'][str(k)] for v in values.values()) for k in BUDGETS},
          'total_uniform_positive_hits_by_k':{str(k):sum(v['uniform_reference_blood_positive'][str(k)] for v in values.values()) for k in BUDGETS}}
 source={'candidate_data':'Galar fitting exams 1-8,21,23,25,27,29,30, original verified PNGs; no 9-10/11-20/61-80 access',
         'original_image_count':len(meta),'blood_positive_annotations':sum(r['blood'] for r in meta),
         'exam_reference_images':{str(e):sum(r['reference'] for r in meta if r['exam']==e) for e in EXAMS},
         'exam_reference_positive':{str(e):sum(r['blood']*r['reference'] for r in meta if r['exam']==e) for e in EXAMS},
         'private_metadata_sha256':hashmeta}
 report={'study':'Exam-separated blood-CNN pooled vs exam-balanced+jitter, 3 folds, 14 prior-inspected fitting examinations',
         'study_role':'Post-hoc exploratory training-only CV; exams are not verified unique patients; not clinically validated',
         'source':source,'training':{'steps_per_arm_fold':STEPS,'batch':BATCH,'seed':SEED,'lr':LR,'decay':DECAY,
         'torch_version':torch.__version__,'sklearn_version':version('scikit-learn'),'device':'CPU float32 two threads'},
         'prespecified_folds':FOLDS,'comparators':{k:{'per_exam':v,'summary':score_summary(v)} for k,v in flat.items()},
         'model_records':folds,'status':'both arms all three exam-disjoint folds completed',
         'source_image_label_positivity_not_lesions':True,'no_reserved_exams_accessed':True,'clinical_validity':False}
 output=OUT/'aggregate.json';output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print('RESULTS SUMMARY',json.dumps({key:value['summary'] for key,value in report['comparators'].items()},sort_keys=True),flush=True)
 print('OUTPUT_SHA256',hashfile(output),flush=True)

if __name__=='__main__':main()
