import pathlib,sys,json,zipfile,csv,io,hashlib,heapq,itertools,collections
import argparse
a=argparse.ArgumentParser(description='Minimum whole-block private local-pair repair plan; no acquisition.')
a.add_argument('--private-dir',type=pathlib.Path,required=True);a.add_argument('--audit-zip',type=pathlib.Path,required=True);cfg=a.parse_args()
P=cfg.private_dir.resolve();assert not P.is_relative_to(pathlib.Path(__file__).resolve().parents[1])
from summarize_galar_archive_layout import records
allowed=set(range(1,9))|{21,23,25,27,29,30}
with zipfile.ZipFile(cfg.audit_zip) as z:
 meta=json.loads(z.read('PRIVATE_selected_source_metadata.json'));retained={(r['exam'],r['frame']):r for r in meta if r['exam'] in allowed}
 hashes={}
 for n in z.namelist():
  if n.startswith('PRIVATE_verified_'):
   for e,f,h,b in json.loads(z.read(n)):
    if e in allowed:hashes[e,f]={'sha256':h,'bytes':b}
sources={};members={};blocks=[]
for source,directory in [(44724816,'original-index-retry'),(45258019,'fitting-index')]:
 d=P/directory;receipt=json.load(open(d/'receipt.json'));sources[source]={'directory':directory,'receipt':receipt}
 entries=records((d/'listing.txt').read_text());sizes={int(x['Block']):int(x['Packed Size']) for x in entries if x.get('Block') and x.get('Packed Size')};offset=32
 for b,n in sorted(sizes.items()):blocks.append({'source':source,'block':b,'start':offset,'bytes':n});offset+=n
 for x in entries:
  path=pathlib.PurePosixPath(x['Path']);parts=path.parts
  if path.suffix.upper()!='.PNG' or len(parts)!=2 or not parts[0].isdigit():continue
  e=int(parts[0]);f=int(path.stem.split('_')[1])
  if e in allowed:
   key=(e,f);assert key not in members
   members[key]={'exam':e,'frame':f,'path':str(path),'source':source,'block':int(x['Block']),'bytes':int(x['Size']),'crc32':int(x['CRC'],16)}
candidates=[];summary={};labelsha={}
with zipfile.ZipFile(P/'recovered-inputs/historical/labels.zip') as z:
 for e in sorted(allowed):
  raw=z.read(f'{e}.csv');labelsha[str(e)]=hashlib.sha256(raw).hexdigest();rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));frames=[int(r['frame']) for r in rows];labels=[r['blood'] for r in rows];lookup=dict(zip(frames,labels));runs=[]
  assert len(frames)==len(set(frames)) and all(b>a for a,b in zip(frames,frames[1:]));assert all(y in ('0','1') for y in labels)
  assert set(frames)=={f for ex,f in members if ex==e}
  for i,y in enumerate(labels):
   if y=='1':
    if i==0 or labels[i-1]!='1' or frames[i]-frames[i-1]!=5:runs.append([])
    runs[-1].append(frames[i])
  for rid,run in enumerate(runs):
   if len(run)>5:continue
   for side,f,g in [('left',run[0],run[0]-5),('right',run[-1],run[-1]+5)]:
    if lookup.get(g)!='0':continue
    pair=[members[e,f],members[e,g]];needed=[x for x in pair if (e,x['frame']) not in retained]
    candidates.append({'exam':e,'run':rid,'run_length':len(run),'side':side,'positive':f,'negative':g,'members':pair,'missing':needed,'required_blocks':sorted(set((x['source'],x['block']) for x in needed))})
  summary[str(e)]={'retained_images':sum(ex==e for ex,f in retained),'label_rows':len(rows),'positive_runs':len(runs),'short_runs':sum(len(r)<=5 for r in runs),'label_grid_gaps':sum(b-a!=5 for a,b in zip(frames,frames[1:]))}
def choose(subset):
 options={}
 for x in candidates:
  if not set(map(tuple,x['required_blocks'])).issubset(subset):continue
  key=x['exam'],x['run'];cost=(sum(m['bytes'] for m in x['missing']),len(x['missing']),x['side'])
  if key not in options or cost<options[key][0]:options[key]=(cost,x)
 groups=collections.defaultdict(list)
 for cost,x in options.values():groups[x['exam']].append((cost,x))
 for e in groups:groups[e].sort(key=lambda v:(v[0],v[1]['run']))
 if len(groups)<4 or sum(min(16,len(v)) for v in groups.values())<32:return None
 best=None
 for anchors in itertools.combinations(sorted(groups),4):
  chosen=[groups[e][0][1] for e in anchors];keys={(x['exam'],x['run']) for x in chosen};count=collections.Counter(x['exam'] for x in chosen)
  pool=sorted(options.values(),key=lambda v:(v[0],v[1]['exam'],v[1]['run']))
  for cost,x in pool:
   key=x['exam'],x['run']
   if key not in keys and count[x['exam']]<16:
    chosen.append(x);keys.add(key);count[x['exam']]+=1
    if len(chosen)==32:break
  missing={(m['exam'],m['frame']):m for x in chosen for m in x['missing']}
  score=(sum(x['bytes'] for x in missing.values()),len(missing),tuple((x['exam'],x['run'],x['side']) for x in chosen))
  if best is None or score<best[0]:best=score,chosen
 return best
heap=[(0,(),-1)];tested=[];solution=None
while heap:
 cost,indices,last=heapq.heappop(heap);subset={(blocks[i]['source'],blocks[i]['block']) for i in indices};fit=choose(subset);tested.append({'bytes':cost,'blocks':sorted(subset),'feasible':fit is not None})
 if fit:solution=(cost,indices,fit[1]);break
 for i in range(last+1,len(blocks)):heapq.heappush(heap,(cost+blocks[i]['bytes'],indices+(i,),i))
assert solution
cost,bi,pairs=solution;needed={(x['exam'],x['frame']):x for p in pairs for x in p['missing']}
out={'eligibility':{'short_run_max_positions':5,'native_stride':5,'target_distinct_short_runs':32,'minimum_exams':4,'maximum_runs_per_exam':16,'adjacent_negative_only':True},'source_member_match_all_fitting_labels':True,'sources':sources,'summary':summary,'all_blocks':blocks,'tested_cheaper_subsets':tested,'chosen_blocks':[blocks[i] for i in bi],'compressed_bytes':cost,'pairs':pairs,'new_originals':list(needed.values()),'retained_hashes':[{**members[k],**v} for k,v in hashes.items()]}
(P/'local-pair-acquisition-plan-private.json').write_text(json.dumps(out,indent=2))
public={k:out[k] for k in ['eligibility','summary','chosen_blocks','compressed_bytes']};public.update({'selected_pairs_by_exam':dict(collections.Counter(x['exam'] for x in pairs)),'new_original_images':len(needed),'new_original_bytes':sum(x['bytes'] for x in needed.values()),'cheaper_subsets_checked':len(tested)-1,'existing_short_pairs':sum(not x['missing'] for x in candidates),'labels_sha256':labelsha})
(P/'local-pair-acquisition-aggregate.json').write_text(json.dumps(public,indent=2));print(json.dumps(public,indent=2))
