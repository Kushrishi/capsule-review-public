"""Independent sealed-score replay: no production selectors/evaluator imports."""
import csv,io,json,zipfile,math,pathlib,hashlib,bisect
import numpy as np
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-dir',type=pathlib.Path,required=True)
parser.add_argument('--labels-zip',type=pathlib.Path,required=True)
args=parser.parse_args()
p=args.private_dir.resolve()
if p.is_relative_to(pathlib.Path(__file__).resolve().parents[1]):raise ValueError('Private evidence must stay outside public Git.')
labels_path=args.labels_zip.resolve()
report=json.load(open(p/'aggregate.json'));draws=json.load(open(p/'repetitions-private.json'))
seal=json.load(open(p/'retention-seal.json'));checks=0;queues_checked=0

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def select(v,k,method):
 n=len(v);ranking=sorted(range(n),key=lambda i:(-v[i],i))
 if method=='uniform':return [((2*j+1)*n)//(2*k) for j in range(k)]
 if method=='score':return ranking[:k]
 if method=='score_bin':
  out=[max(range(j*n//k,(j+1)*n//k),key=lambda i:(v[i],-i)) for j in range(k)]
  return sorted(out,key=lambda i:(-v[i],i))
 radius=n//(2*k);blocked=set();chosen=[]
 for i in ranking:
  if i not in blocked:
   chosen.append(i);blocked.update(range(max(0,i-radius),min(n,i+radius+1)))
   if len(chosen)==k:return chosen
 seen=set(chosen)
 return chosen+[i for i in ranking if i not in seen][:k-len(chosen)]

assert digest(labels_path)=='2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
for exam,expected in ((31,24919),(34,10867),(37,18125)):
 s=json.load(open(p/f'galar{exam}-scores.json'));assert digest(p/f'galar{exam}-scores.json')==seal['examinations'][str(exam)]['scores']['remote_sha256']
 assert s['weights_sha256']=='f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3' and s['labels_accessed_during_scoring'] is False
 entries=s['complete_original_scores'];frames=[x['source_frame'] for x in entries];scores=[x['original_cnn_score'] for x in entries];n=len(frames);assert n==expected
 hashes=[x['original_png_sha256'] for x in entries]
 commitment=hashlib.sha256(json.dumps({'schema':1,'frames':frames,'source_sha256':hashes,'scores':scores},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
 assert commitment==s['input_commitment_sha256']
 assert all(b-a==5 for a,b in zip(frames,frames[1:]))
 # Independent original ZIP PNG membership/CRC/hash and separately retained source index.
 target=json.load(open(p/'target-members-private.json'));target={int(pathlib.PurePosixPath(x['path']).stem.split('_')[1]):x for x in target if x['exam']==exam}
 assert set(target)==set(frames)
 with zipfile.ZipFile(p/f'galar{exam}-originals.zip') as z:
  assert len(z.infolist())==n
  for frame,h in zip(frames,hashes):
   raw=z.read(f'images/{exam:03}/'+pathlib.PurePosixPath(target[frame]['path']).name);assert len(raw)==target[frame]['bytes'] and hashlib.sha256(raw).hexdigest()==h
 smooth=[max(scores[max(0,i-1):min(n,i+2)]) for i in range(n)]
 for row in s['frozen_queues']:
  percent=row['review_percent'];k=max(1,min(n,(n*percent+50)//100));assert row['k']==k
  for method,q in row['policies'].items():assert select(scores,k,method)==q;queues_checked+=1
  assert select(smooth,k,'score_bin')==row['temporal_window3_score_bin'];queues_checked+=1
 with zipfile.ZipFile(labels_path) as z:rows=list(csv.DictReader(io.StringIO(z.read(f'{exam}.csv').decode('utf-8-sig'))))
 assert [int(x['frame']) for x in rows]==frames
 assert all(x['blood'] in ('0','1') for x in rows)
 y=np.array([int(x['blood']) for x in rows]);runs=[]
 for i in np.flatnonzero(y):
  if i==0 or y[i-1]==0:runs.append([])
  runs[-1].append(int(i))
 rid=np.full(n,-1,dtype=int);strata=[]
 for i,r in enumerate(runs):rid[r]=i;strata.append(0 if len(r)<=5 else 1 if len(r)<=25 else 2)
 strata=np.array(strata,dtype=int)
 def counts(q):
  ids=np.unique(rid[q]);ids=ids[ids>=0]
  return [int(y[q].sum()),len(ids),*[int(np.count_nonzero(strata[ids]==j)) for j in range(3)]]
 for percent in (10,25):
  r=report['examinations'][str(exam)][str(percent)];k=(n*percent+50)//100;starts=np.array([j*n//k for j in range(k)]);lengths=np.array([(j+1)*n//k-j*n//k for j in range(k)])
  qs={m:select(scores,k,m) for m in ('uniform','score','score_diverse','score_bin')};qs['temporal_window3_score_bin']=select(smooth,k,'score_bin')
  for method,q in qs.items():
   c=counts(q);v=r['policies'][method];assert (c[0],c[1])==(v['positive_images'],v['runs_reached'])
   assert [v['strata'][key]['reached'] for key in ('short_1_5','medium_6_25','long_26_plus')]==c[2:]
  # Exact earliest-maximum order-statistic probabilities, including ties.
  cdfs=[];prob=np.zeros(n);multiplicity=[]
  for a,L in zip(starts,lengths):
   a,L=int(a),int(L);m=sum(x==max(scores[a:a+L]) for x in scores[a:a+L]);multiplicity.append(m)
   cdf=[1-(math.comb(L-j-1,m)/math.comb(L,m) if L-j-1>=m else 0) for j in range(L)];cdfs.append(cdf)
   prob[a:a+L]=np.diff([0]+cdf)
  expectation=[]
  for run in runs:
   mass={}
   for pos in run:
    b=bisect.bisect_right(starts,pos)-1;mass[b]=mass.get(b,0)+prob[pos]
   expectation.append(1-math.prod(1-min(1,v) for v in mass.values()))
  # Separate augmenting-path bipartite matching oracle (not production greedy).
  neighbours=[sorted({bisect.bisect_right(starts,pos)-1 for pos in run}) for run in runs]
  matching={}
  def augment(run_index,seen):
   for b in neighbours[run_index]:
    if b in seen:continue
    seen.add(b)
    if b not in matching or augment(matching[b],seen):matching[b]=run_index;return True
   return False
  for run_index in range(len(runs)):augment(run_index,set())
  oracle=r['ancillary_fixed_bin_oracle']
  assert oracle['maximum_distinct_runs']==len(matching)
  assert oracle['positive_bins']==len(set(b for ns in neighbours for b in ns))
  exact=r['controls']['within_bin_permuted_scores']['analytic_expected_counts']
  assert abs(sum(expectation)-exact['runs_reached'])<1e-9
  assert abs(float(np.dot(y,prob))-exact['positive_images'])<1e-8
  rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261106,exam,percent,1])))
  perm=[];geom=[];ties=[j for j,m in enumerate(multiplicity) if m>1]
  for _ in range(10000):
   u=rng.random(k);g=starts+(u*lengths).astype(int);selected=g.copy()
   for j in ties:selected[j]=starts[j]+bisect.bisect_right(cdfs[j],u[j])
   geom.append(counts(g));perm.append(counts(selected))
  np.testing.assert_array_equal(geom,draws[str(exam)][str(percent)]['geometry']);np.testing.assert_array_equal(perm,draws[str(exam)][str(percent)]['permutation'])
  phases=[counts([((200*i+2*j+1)*n)//(200*k) for i in range(k)]) for j in range(100)]
  np.testing.assert_array_equal(phases,draws[str(exam)][str(percent)]['phases'])
  cuts=[(j*n//16,(j+1)*n//16) for j in range(16)];rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261106,exam,percent,2])))
  shifted=[];v=np.array(scores)
  gather=starts[:,None]+np.arange(max(lengths))[None,:];valid=gather<(starts+lengths)[:,None];gather=np.minimum(gather,n-1)
  for _ in range(1000):
   v=np.array(scores)
   for a,b in cuts:v[a:b]=np.roll(np.asarray(scores[a:b]),-int(rng.integers(1,b-a)))
   winners=starts+np.argmax(np.where(valid,v[gather],-np.inf),axis=1);shifted.append(counts(winners))
  np.testing.assert_array_equal(shifted,draws[str(exam)][str(percent)]['coarse_shift'])
  checks+=1;print('Independent replay passed',exam,percent,flush=True)
result={'source_images_independently_hash_rechecked':53911,'all_policy_queues_reproduced':queues_checked,'exam_budget_records':checks,'randomization_controls_replayed':checks*11100,'production_code_imported':False,'script_sha256':digest(pathlib.Path(__file__))}
with (p/'independent-replay-check.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
