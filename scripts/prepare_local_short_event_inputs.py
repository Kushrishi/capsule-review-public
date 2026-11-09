import pathlib,json,hashlib,zipfile,csv,io,sys,collections
import numpy as np
from PIL import Image,ImageOps
import argparse
args=argparse.ArgumentParser(description='Verify private fitting sources and build the frozen matched-objective bank.')
args.add_argument('--private-dir',type=pathlib.Path,required=True);args.add_argument('--source-dir',type=pathlib.Path,required=True);args.add_argument('--audit-zip',type=pathlib.Path,required=True);cfg=args.parse_args()
P=cfg.private_dir.resolve();BASE=cfg.source_dir.resolve()
assert not P.is_relative_to(pathlib.Path(__file__).resolve().parents[1])
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(P/'local-pair-acquisition-plan-private.json')=='2df3b7633d5a2f44ac087b467e8327c5cb4d9994c7933b32f8221a368de010cf'
plan=json.load(open(P/'local-pair-acquisition-plan-private.json'));oldcore=json.load(open(P/'recovered-inputs/new-private/selected-arms-private.json'))['diverse_population']
pair_keys={(x['exam'],f) for x in plan['pairs'] for f in (x['positive'],x['negative'])};wanted=pair_keys|{(r['exam'],r['frame']) for r in oldcore}
audit=cfg.audit_zip.resolve()
assert sha(audit)=='5cf828dd0288364bfe0bb2a5e3a6615b9e5ddaac91dec51b1a7765923fd04709'
with zipfile.ZipFile(audit) as z:
 deps=json.loads(z.read('PRIVATE_source_archive_dependencies.json'));meta=json.loads(z.read('PRIVATE_selected_source_metadata.json'))
 expected={}
 for n in z.namelist():
  if n.startswith('PRIVATE_verified_'):
   for e,f,h,b in json.loads(z.read(n)):
    if e in set(range(1,9))|{21,23,25,27,29,30}:expected[e,f]=(h,b)
labelmap={};csvsha={}
labels=P/'recovered-inputs/historical/labels.zip';assert sha(labels)=='2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
with zipfile.ZipFile(labels) as z:
 for e in set(range(1,9))|{21,23,25,27,29,30}:
  raw=z.read(f'{e}.csv');csvsha[str(e)]=hashlib.sha256(raw).hexdigest()
  for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
   assert r['blood'] in ('0','1');labelmap[e,int(r['frame'])]=int(r['blood'])
for r in meta:
 key=r['exam'],r['frame']
 if key in expected:assert r['blood']==labelmap[key]
rows=[];tensors=[];seen=set();all_hashes=set();proof=[]
benchmark_hashes={r['sha256'] for e in (31,34,37) for r in json.load(open(P/f'recovered-inputs/historical/galar{e}-image-hashes-private.json'))}
def add(key,raw,source_hash,size):
 assert key not in seen and len(raw)==size and hashlib.sha256(raw).hexdigest()==source_hash
 assert source_hash not in all_hashes and source_hash not in benchmark_hashes
 seen.add(key);all_hashes.add(source_hash)
 if key not in wanted:return
 with Image.open(io.BytesIO(raw)) as im:
  assert im.format=='PNG';im=ImageOps.pad(ImageOps.exif_transpose(im).convert('RGB'),(96,96),method=Image.Resampling.BILINEAR,color=(0,0,0));a=np.array(im,dtype=np.uint8).transpose(2,0,1).copy()
 rows.append({'exam':key[0],'frame':key[1],'blood':labelmap[key],'sha256':source_hash,'bytes':size});tensors.append(a)
for d in deps:
 if 'negative-22-24' in d['archive']:continue
 paths=list(BASE.rglob(d['archive']));assert len(paths)==1,d['archive'];f=paths[0];assert f.stat().st_size==d['size_bytes'] and sha(f)==d['sha256'];n=0
 with zipfile.ZipFile(f) as outer:
  z=outer if 'pilot-images' in d['archive'] else zipfile.ZipFile(io.BytesIO(outer.read(next(x for x in outer.namelist() if x.endswith('.zip')))))
  for name in z.namelist():
   pp=pathlib.PurePosixPath(name)
   if pp.suffix.upper()!='.PNG' or len(pp.parts)!=3 or pp.parts[0]!='images':continue
   key=int(pp.parts[1]),int(pp.stem.split('_')[1]);assert key in expected
   h,b=expected[key];add(key,z.read(name),h,b);n+=1
  if z is not outer:z.close()
 proof.append({'file':d['archive'],'sha256':d['sha256'],'verified_pngs':n});print(d['archive'],n,'originals hash-verified',flush=True)
assert len(seen)==10123
newproof=json.load(open(P/'new-originals-proof-private.json'))
assert sha(P/'Local_Short_Event_New_Originals_20261109.zip')==newproof['package_sha256']
with zipfile.ZipFile(P/'Local_Short_Event_New_Originals_20261109.zip') as z:
 for r in newproof['originals']:add((r['exam'],r['frame']),z.read('images/'+r['path']),r['sha256'],r['bytes'])
assert seen.issuperset(wanted) and len(rows)==len(wanted)
index={(r['exam'],r['frame']):i for i,r in enumerate(rows)};core=[index[r['exam'],r['frame']] for r in oldcore]
pairs=[{'exam':r['exam'],'run_id':r['run'],'run_length':r['run_length'],'positive_index':index[r['exam'],r['positive']],'negative_index':index[r['exam'],r['negative']]} for r in sorted(plan['pairs'],key=lambda r:(r['exam'],r['run']))]
dest=P/'objective-bank.npy';assert not dest.exists();np.save(dest,np.stack(tensors))
manifest={'images':rows,'core_indices':core,'pairs':pairs,'labels_zip_sha256':sha(labels),'label_csv_sha256':csvsha,'new_originals_package_sha256':newproof['package_sha256'],'source_archive_proofs':proof,'verified_retained_pngs':10123,'verified_new_pngs':21,'raw_png_benchmark_overlap':0,'core_membership_source':'PR69 fixed diverse arm, unchanged4096 references','reference_counts':{'positive':239,'other':3857}}
(P/'objective-manifest-private.json').write_text(json.dumps(manifest,indent=2));print('Objective input bank ready',len(rows),'distinct images;32 genuine short-event pairs',flush=True)
