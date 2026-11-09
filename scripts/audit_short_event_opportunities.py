"""Exhaustive permitted-source boundary/context inventory, no publisher payload."""
import pathlib,json,hashlib,zipfile,csv,io,sys,collections,itertools
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-dir',type=pathlib.Path,required=True);args=p.parse_args()
R=pathlib.Path(__file__).resolve().parents[1];P=args.private_dir.resolve();BASE=P.parent
if P.is_relative_to(R):raise ValueError('Private source metadata must stay outside Git.')
sys.path.insert(0,str(R/'scripts'))
from summarize_galar_archive_layout import records
old=BASE/'unpacked/Local_Short_Event_Preoutcome_Evidence_20261109/private-short';contract=BASE/'unpacked/Local_Short_Event_Private_Acquisition_Contract_20261109';plan=json.load(open(old/'local-pair-acquisition-plan-private.json'))
allowed=set(range(1,9))|{21,23,25,27,29,30}
retained={(r['exam'],r['frame']):r for r in plan['retained_hashes']}
newproof=json.load(open(old/'new-originals-proof-private.json'))
for r in newproof['originals']:retained[r['exam'],r['frame']]=r
assert len(retained)==10144
member={};blocks={}
for src,sub in ((44724816,'original-index-retry'),(45258019,'fitting-index')):
 rec=records((contract/sub/'listing.txt').read_text())
 for r in rec:
  pp=pathlib.PurePosixPath(r['Path'])
  if pp.suffix.upper()!='.PNG' or len(pp.parts)!=2 or not pp.parts[0].isdigit():continue
  e=int(pp.parts[0]);f=int(pp.stem.split('_')[1])
  if e not in allowed:continue
  member[e,f]={'exam':e,'frame':f,'source':src,'block':int(r['Block']),'bytes':int(r['Size']),'crc32':int(r['CRC'],16),'path':str(pp)}
for r in plan['all_blocks']:blocks[r['source'],r['block']]=r
blocklist=sorted(blocks);bit={b:1<<i for i,b in enumerate(blocklist)}
def mask(keys):
 v=0
 for k in keys:
  if k not in retained:v|=bit[member[k]['source'],member[k]['block']]
 return v
labels=BASE/'69expanded/Matched_Diversity_PreOutcome_Evidence_20261107/historical/labels.zip';assert hashlib.sha256(labels.read_bytes()).hexdigest()=='2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
rows=[];summary={};labmap={}
with zipfile.ZipFile(labels) as z:
 for e in sorted(allowed):
  raw=z.read(f'{e}.csv');assert hashlib.sha256(raw).hexdigest()==json.load(open(old/'objective-manifest-private.json'))['label_csv_sha256'][str(e)]
  rr=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));lab={int(r['frame']):r['blood'] for r in rr};labmap[e]=lab
  assert set(lab)=={f for ex,f in member if ex==e};runs=[];prev=None
  for f,y in sorted(lab.items()):
   if y=='1':
    if prev is None or f-prev!=5:runs.append([])
    runs[-1].append(f);prev=f
   else:prev=None
  for rid,g in enumerate(runs):
   if len(g)>5:continue
   edges=[]
   for side,p,n in (('left',g[0],g[0]-5),('right',g[-1],g[-1]+5)):
    if lab.get(n)!='0':continue
    keys=[(e,p),(e,n)];edges.append({'side':side,'positive':p,'negative':n,'required_mask':mask(keys),'required_blocks':[[member[k]['source'],member[k]['block']] for k in keys if k not in retained]})
   if not edges:continue
   both=lab.get(g[0]-5)=='0' and lab.get(g[-1]+5)=='0'
   context=[(e,f) for f in range(g[0]-10,g[-1]+11,5) if f in lab]
   full_context=(len(context)==len(g)+4 and all(lab.get(f)=='0' for f in (g[0]-10,g[0]-5,g[-1]+5,g[-1]+10)))
   core=[(e,f) for f in g]+([(e,g[0]-5),(e,g[-1]+5)] if both else [])
   rows.append({'exam':e,'run_id':rid,'run_length':len(g),'positive_frames':g,'singleton':len(g)==1,'edges':edges,'both_sides_label_supported':both,'positive_and_two_sided_keys':core if both else None,'positive_and_two_sided_mask':mask(core) if both else None,'wider_context_keys':context,'wider_context_complete_label_supported':full_context,'wider_context_mask':mask(context) if full_context else None})
  er=[r for r in rows if r['exam']==e]
  summary[e]={'all_short_runs_with_boundary':len(er),'retained_short_runs':sum(any(x['required_mask']==0 for x in r['edges']) for r in er),'retained_boundary_edges':sum(x['required_mask']==0 for r in er for x in r['edges']),'retained_singleton_runs':sum(r['singleton'] and any(x['required_mask']==0 for x in r['edges']) for r in er),'retained_complete_two_sided_runs':sum(r['both_sides_label_supported'] and r['positive_and_two_sided_mask']==0 for r in er),'retained_wider_context_runs':sum(r['wider_context_complete_label_supported'] and r['wider_context_mask']==0 for r in er),'source_singletons':sum(r['singleton'] for r in er),'source_both_sides_runs':sum(r['both_sides_label_supported'] for r in er)}
oldm=json.load(open(old/'objective-manifest-private.json'));oldkeys={(p['exam'],p['run_id']) for p in oldm['pairs']}
for p in oldm['pairs']:
 r=next(x for x in rows if (x['exam'],x['run_id'])==(p['exam'],p['run_id']));a,b=[oldm['images'][p[k]]['frame'] for k in ('positive_index','negative_index')];assert any(e['positive']==a and e['negative']==b and e['required_mask']==0 for e in r['edges'])
extra=[(r['exam'],r['run_id']) for r in rows if any(e['required_mask']==0 for e in r['edges']) and (r['exam'],r['run_id']) not in oldkeys]

def support(sel):
 counts=collections.Counter();two=collections.Counter();wide=collections.Counter();single=collections.Counter();edge=0;keys=set()
 for r in rows:
  good=[e for e in r['edges'] if e['required_mask']&sel==e['required_mask']]
  if not good:continue
  e=r['exam'];counts[e]+=1;single[e]+=int(r['singleton']);edge+=len(good)
  for ed in good:keys|={(e,ed['positive']),(e,ed['negative'])}
  if r['both_sides_label_supported'] and r['positive_and_two_sided_mask']&sel==r['positive_and_two_sided_mask']:two[e]+=1;keys|=set(map(tuple,r['positive_and_two_sided_keys']))
  if r['wider_context_complete_label_supported'] and r['wider_context_mask']&sel==r['wider_context_mask']:wide[e]+=1;keys|=set(map(tuple,r['wider_context_keys']))
 return {'runs':dict(counts),'singletons':dict(single),'boundary_edges':edge,'two_sided_complete':dict(two),'wider_context_complete':dict(wide),'unique_useful_images':len(keys),'new_useful_images':len(keys-set(retained)),'new_useful_image_bytes':sum(member[k]['bytes'] for k in keys-set(retained))}
scenarios=[]
# Exact source cost versus information gain for all one/two-block choices, plus prior50 plan.
for n in (0,1,2):
 for bb in itertools.combinations(blocklist,n):
  sel=sum(bit[b] for b in bb);s=support(sel);scenarios.append({'blocks':[list(b) for b in bb],'source_bytes':sum(blocks[b]['bytes'] for b in bb),'meaningful_5_run_exams':sum(v>=5 for v in s['runs'].values()),'meaningful_10_run_exams':sum(v>=10 for v in s['runs'].values()),**s})
prior=[(44724816,5),(44724816,6),(44724816,7),(45258019,1),(45258019,4)];prior_support=support(sum(bit[b] for b in prior));assert sum(blocks[b]['bytes'] for b in prior)==18006872916
out={'permitted_exams':sorted(allowed),'retained_originals':len(retained),'old32_reconciled':True,'summary':summary,'additional_retained_runs_vs32':extra,'runs':rows,'members':list(member.values()),'blocks':[blocks[b] for b in blocklist],'scenarios':scenarios,'prior50_blocks_all_eligible_yield':prior_support}
(P/'opportunities-private.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'summary':summary,'additional_retained_runs_vs32':extra,'prior50_blocks_all_eligible_yield':prior_support},indent=2))
print('BEST one/two-block plans:')
for n in (1,2):
 plans=[s for s in scenarios if len(s['blocks'])==n]
 for s in sorted(plans,key=lambda s:(-s['meaningful_10_run_exams'],-s['meaningful_5_run_exams'],-sum(s['runs'].values()),s['source_bytes']))[:5]:print(s)
