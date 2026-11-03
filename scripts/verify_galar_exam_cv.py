"""Independent checkpoint-to-reference-scores replay of examination-disjoint experiment.

Private source metadata, per-image scores and model weights never enter Git.
"""
import hashlib,json,os
from pathlib import Path
import numpy as np
import torch
from torch import nn
from sklearn.metrics import roc_auc_score, average_precision_score

ROOT=Path(os.environ.get('CAPSULE_CV_OUTPUT_DIR', '/mnt/data/capsule_next/private_outputs'))
EXAMS=(1,2,3,4,5,6,7,8,21,23,25,27,29,30)
EXPECTED_SOURCE_META_SHA='78fc3b0d9711b675f3ffe802554d28232a58f01abb36acda60849c96c32fa4c2'

class IndependentReplayCNN(nn.Module):
 def __init__(self):
  super().__init__()
  self.features=nn.Sequential(nn.Conv2d(3,16,3,stride=2,padding=1),nn.GroupNorm(4,16),nn.ReLU(),
     nn.Conv2d(16,32,3,stride=2,padding=1),nn.GroupNorm(4,32),nn.ReLU(),
     nn.Conv2d(32,64,3,stride=2,padding=1),nn.GroupNorm(4,64),nn.ReLU(),nn.AdaptiveAvgPool2d(1))
  self.classifier=nn.Linear(64,2)
 def forward(self,x):return self.classifier(self.features(x).flatten(1))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
 report=json.loads((ROOT/'aggregate.json').read_text())
 metadatafile=ROOT/'private_source_metadata.json'
 assert sha(metadatafile)==EXPECTED_SOURCE_META_SHA
 meta=json.loads(metadatafile.read_text())
 assert len(meta)==10123 and sum(m['blood'] for m in meta)==1663
 bank=np.memmap(ROOT/'bank_96_rgb_uint8.dat',dtype=np.uint8,mode='r',shape=(len(meta),96,96,3))
 assert set(m['exam'] for m in meta)==set(EXAMS)
 torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 maxabs=0.0;recordcount=0;metriccount=0
 for record in report['model_records']:
  fold,arm=record['fold'],record['arm']
  weights=ROOT/f'{fold}-{arm}.pt'
  saved=ROOT/f'{fold}-{arm}-private-predictions.json'
  assert sha(weights)==record['checkpoint_sha256']
  assert sha(saved)==record['private_prediction_sha256']
  predictions=json.loads(saved.read_text())
  expected_by_exam={}
  for p in predictions:expected_by_exam.setdefault(p['exam'],[]).append(p)
  assert set(expected_by_exam)==set(record['heldout_exams'])
  model=IndependentReplayCNN().eval()
  model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
  with torch.no_grad():
   for ex in record['heldout_exams']:
    ids=np.array([i for i,r in enumerate(meta) if r['exam']==ex and r['reference']==1],dtype=np.int64)
    assert len(ids)==512 and len(expected_by_exam[ex])==512
    for i,p in zip(ids,expected_by_exam[ex]):
     assert meta[int(i)]['frame']==p['frame'] and meta[int(i)]['blood']==p['blood']
    replay=[]
    for group in np.array_split(ids,8):
     batch=torch.tensor(np.array(bank[group],copy=True)).permute(0,3,1,2).float().div_(255)
     replay.extend(torch.softmax(model(batch),dim=1)[:,1].tolist())
    saved_scores=[p['score'] for p in expected_by_exam[ex]]
    diff=max(abs(a-b) for a,b in zip(replay,saved_scores))
    maxabs=max(maxabs,diff)
    if diff>1e-7:raise AssertionError(f'Checkpoint replay mismatch: fold={fold}, arm={arm}, exam={ex}, diff={diff}')
    labels=[p['blood'] for p in expected_by_exam[ex]]
    res=report['comparators'][arm]['per_exam'][str(ex)]
    assert sum(labels)==res['blood_positive']
    auc=roc_auc_score(labels,replay) if 0<sum(labels)<512 else None
    ap=average_precision_score(labels,replay) if sum(labels)>0 else None
    if auc is None:assert res['roc_auc'] is None
    else:assert abs(auc-res['roc_auc'])<1e-12
    if ap is None:assert res['average_precision'] is None
    else:assert abs(ap-res['average_precision'])<1e-12
    frames=[p['frame'] for p in expected_by_exam[ex]]
    sortedidx=sorted(range(512),key=lambda i:(-replay[i],frames[i]))
    for k in (51,128,256,512):
     count=sum(labels[i] for i in sortedidx[:k])
     assert count==res['top_k_blood_positive'][str(k)]
     metriccount+=1
    recordcount+=512
  print('Independent replay succeeded',fold,arm,flush=True)
 verify={'source_manifest_sha256':EXPECTED_SOURCE_META_SHA,'aggregate_sha256':sha(ROOT/'aggregate.json'),
         'source_original_images':10123,'checkpoint_count':len(report['model_records']),
         'independently_replayed_scores':recordcount,'independently_matched_topk_examination_budgets':metriccount,
         'largest_absolute_inference_difference':maxabs,'heldout_exam_count_per_arm':len(EXAMS),
         'no_reserved_exams_used':True,'clinical_validity':False}
 output=ROOT/'verification.json'
 if output.exists():raise FileExistsError('Do not overwrite private verification receipt')
 output.write_text(json.dumps(verify,sort_keys=True,indent=2)+'\n')
 print('VERIFICATION',json.dumps(verify),flush=True)

if __name__=='__main__':main()
