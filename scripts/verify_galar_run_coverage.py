"""Independent replay of Galar annotation-run coverage using original saved sources.

This verification implementation does not import galar_reference_run_coverage.py.
It checks exact preexisting private score CSV hashes, reference memberships, and
all six budgets for original CNN, red excess, and uniform source sampling.
It emits only aggregate verification facts, never original frame IDs or labels.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path

EXAMS=(9,10,21,23,25,27,29,30)
DATA={
'pilot':('private-development-predictions/predictions.csv','f921194639a99e206c9b24e3e896f25ff1a409669024f87c4b8b42767c70b36b'),
'new':('private/source-scores.csv','caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812'),
'exam25':('private-per-image-scores.csv','285d3b14ab0f9e2cf45f4a7ca51205623e5694a17db0d55b9ba421e3023029c7'),
'exam27':('private-source-scores.csv','4bd6bb1f605c10c1e1749f3c9d69238951de866c0b72009326923644ca927fe8'),
'exam29':('private-predictions.csv','f27a410a75cdf51bc726b181083fee3f89e9f71f0bed567c04223c1aebf51e79')
}


def hash_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as file:
  for part in iter(lambda:file.read(1<<20),b''):h.update(part)
 return h.hexdigest()


def read_csv_zip(path,internal,expected):
 with zipfile.ZipFile(path) as z:
  if z.testzip() is not None:raise ValueError('ZIP CRC mismatch')
  raw=z.read(internal)
 if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Private saved score digest mismatch')
 return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def verify(labels_zip, paths, aggregate_path):
 expected=json.load(open(aggregate_path))
 assert hash_file(labels_zip)==expected['source_corrected_release_sha256']
 source={}
 with zipfile.ZipFile(labels_zip) as z:
  for exam in EXAMS: # explicit allowed names; never load the reserved cohorts
   records=list(csv.DictReader(io.StringIO(z.read(f'{exam}.csv').decode('utf-8-sig'))))
   run_index={}
   runs=[]
   last_frame=None
   last_positive=False
   for row in records:
    f=int(row['frame']);positive=row['blood']=='1'
    if positive:
     if not last_positive or last_frame is None or f-last_frame!=5:runs.append([])
     runs[-1].append(f)
     run_index[f]=len(runs)-1
    last_frame=f;last_positive=positive
   source[exam]=(runs,run_index)

 score_rows={exam:[] for exam in EXAMS}
 for k,(internal,sha) in DATA.items():
  for row in read_csv_zip(paths[k],internal,sha):
   if k=='pilot':
    e=int(row['exam']);f=int(row['frame']);label=int(row['blood_label']);role=1
    score=float(row['cnn_score']);red=float(row['red_excess_score'])
   elif k=='new':
    e=int(row['exam']);f=int(row['frame']);label=int(row['blood']);role=int(row['reference_uniform'])
    score=float(row['cnn_score']);red=float(row['red_excess_score'])
   elif k=='exam25':
    e=int(row['examination']);f=int(row['source_frame']);label=int(row['blood_label']);role=int(row['reference_uniform'])
    score=float(row['original_checkpoint']);red=float(row['red_excess'])
   else:
    e=int(row['exam']);f=int(row['frame']);label=int(row['blood']);role=int(row['reference_uniform'])
    score=float(row['original_checkpoint']);red=float(row['red_excess'])
   if e not in EXAMS:raise ValueError('Unexpected source examination')
   if role:score_rows[e].append((f,label,score,red))

 comparisons=0
 for exam,rows in score_rows.items():
  rows.sort(key=lambda x:x[0]);n=len(rows)
  assert n==512
  runs,run_id=source[exam]
  agg=expected['examinations'][str(exam)]
  assert len(runs)==agg['source_blood_annotation_runs']
  assert sum(v[1] for v in rows)==agg['reference_blood_positive']
  ceiling={run_id[v[0]] for v in rows if v[1]}
  assert len(ceiling)==agg['reference_run_ceiling_hits']
  for pct in (5,10,25,50,75,100):
   k=n*pct//100
   selections={
    'original_checkpoint':sorted(range(n),key=lambda i:(-rows[i][2],i))[:k],
    'red_excess':sorted(range(n),key=lambda i:(-rows[i][3],i))[:k],
    'uniform':[(2*j+1)*n//(2*k) for j in range(k)]
   }
   for method,ix in selections.items():
    found=sum(rows[j][1] for j in ix)
    run_hits=len({run_id[rows[j][0]] for j in ix if rows[j][1]})
    measured=agg['budgets'][str(pct)]['methods'][method]
    assert (found,run_hits)==(measured['blood_positive_reference_images_found'],measured['source_annotation_runs_hit'])
    comparisons+=1
 return {'verification':'independent real-data run segmentation and all-budget replay passed',
         'examinations_checked':len(EXAMS),'source_reference_images_checked':8*512,
         'method_budget_comparisons_recomputed':comparisons,
         'source_original_sha256':expected['source_corrected_release_sha256'],
         'private_source_csv_digests':{k:v[1] for k,v in DATA.items()},
         'original_source_positive_runs_checked':sum(len(x[0]) for x in source.values()),
         'unreachable_source_runs_under_complete_512_reference':sum(len(source[e][0])-expected['examinations'][str(e)]['reference_run_ceiling_hits'] for e in EXAMS),
         'source_aggregate_sha256':hash_file(aggregate_path),
         'reserved_exams_11_20_and_61_80_opened':False,
         'individual_source_frame_identity_exported':False,
         'clinical_validation':False}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('labels-zip','pilot','new','exam25','exam27','exam29','aggregate','output'):
  p.add_argument('--'+name,required=True,type=Path)
 args=p.parse_args()
 if args.output.exists():raise FileExistsError('Refusing to overwrite independent verification')
 result=verify(args.labels_zip,{k:getattr(args,k) for k in DATA},args.aggregate)
 args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
