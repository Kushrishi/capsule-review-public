"""Private exact-range acquisition; frozen cohort only; no whole-file fallback."""
import concurrent.futures,hashlib,json,pathlib,sys,urllib.request,zipfile,shutil,datetime
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-dir',type=pathlib.Path,required=True)
parser.add_argument('--acquire',action='store_true',help='Explicitly authorize only the four frozen new blocks')
args=parser.parse_args()
if not args.acquire:parser.error('--acquire is required; no implicit source transfer')
repo=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'scripts'))
from probe_galar_archive import allowed_redirect,validate_official_catalog
from plan_galar31_40_development_blocks import validate_index
p=args.private_dir.resolve()
if p.is_relative_to(repo):raise ValueError('Private source outputs must stay outside public Git.')
preflight=json.loads((p/'technical-preflight.json').read_text())
if (preflight.get('lock_commit')!='bd59b4936770d8d782df0e29df5cf8a9df1af15d'
 or preflight.get('checkpoint_load_passed') is not True or preflight.get('synthetic_inference_passed') is not True
 or preflight.get('py7zr_synthetic_extract_passed') is not True or preflight.get('drive_available_GB_UI',0)<40
 or preflight.get('drive_folder_shared') is not False):raise ValueError('Frozen rights, technical and private capacity evidence required')
validate_official_catalog(json.loads((p/'catalog-live.json').read_text()),'fitting-31-40')
blocks,_=validate_index(json.loads((repo/'experiments/galar-31-40-index-20261105/aggregate.json').read_text()))
assert sum(blocks[i]['compressed_bytes'] for i in (0,1,4,7))==14065827988
parts=p/'new-source-parts';parts.mkdir(exist_ok=True)
N=50_000_000;work=[]
for bid in (0,1,4,7):
 b=blocks[bid]
 for j,start in enumerate(range(b['range_start'],b['range_end_inclusive']+1,N),1):
  end=min(start+N-1,b['range_end_inclusive']);work.append((bid,j,start,end))
def one(x):
 bid,j,start,end=x;dest=parts/f'galar313437-source-block{bid}.part{j:03}.zip';receipt=dest.with_suffix('.json')
 if dest.with_suffix('.remote.json').exists() and receipt.exists():
  r=json.loads(receipt.read_text())
  with (p/'source.sparse.7z').open('rb') as f:f.seek(start);raw=f.read(end-start+1)
  if hashlib.sha256(raw).hexdigest()!=r['raw_sha256']:raise ValueError('Retained working sparse range changed; restore from private remote receipt.')
  return r
 if dest.exists() and receipt.exists():
  r=json.loads(receipt.read_text());assert hashlib.sha256(dest.read_bytes()).hexdigest()==r['transport_sha256'];return r
 if shutil.disk_usage(p).free<7_000_000_000:raise ValueError('Storage reserve gate failed')
 req=urllib.request.Request('https://api.figshare.com/v2/file/download/44755700',headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
 with urllib.request.urlopen(req,timeout=120) as r:
  if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/69219317963' or not allowed_redirect(r.geturl()):raise ValueError('Pinned 206/range/redirect gate failed')
  if r.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Encoded source response')
  raw=r.read(end-start+2)
 if len(raw)!=end-start+1:raise ValueError('Truncated or excess source bytes')
 with (p/'source.sparse.7z').open('r+b') as f:f.seek(start);f.write(raw)
 zi=zipfile.ZipInfo(dest.stem+'.bin',date_time=(2026,11,6,0,0,0));zi.compress_type=zipfile.ZIP_STORED
 with zipfile.ZipFile(dest,'x') as z:z.writestr(zi,raw)
 item={'block':bid,'part':j,'range_start':start,'range_end_inclusive':end,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'transport_bytes':dest.stat().st_size,'transport_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'path':str(dest.resolve()),'http_status':206,'official_file_id':44755700,'retained_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 with receipt.open('x') as f:json.dump(item,f)
 return item
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for n,r in enumerate(pool.map(one,work),1):
  with (p/'new-source-progress.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
  if n%10==0:print(n,'/',len(work),'chunks verified',flush=True)
receipts=[]
with (p/'source.sparse.7z').open('rb') as f:
 for bid in (0,1,4,7):
  b=blocks[bid];h=hashlib.sha256();f.seek(b['range_start']);left=b['compressed_bytes']
  while left:
   raw=f.read(min(left,1024*1024));assert raw;h.update(raw);left-=len(raw)
  receipts.append({**b,'sha256':h.hexdigest()})
(p/'new-block-receipts.json').write_text(json.dumps(receipts,indent=2))
print('All four new source blocks complete',flush=True)
