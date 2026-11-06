"""Verified retained-index target extraction, original bytes only; no labels."""
from pathlib import Path
import py7zr,json,hashlib,zipfile,sys,shutil,zlib,io,re
from PIL import Image
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-dir',type=Path,required=True)
parser.add_argument('--exam',type=int,choices=(31,34,37),required=True)
args=parser.parse_args()
p=args.private_dir.resolve();exam=args.exam
if p.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Private extraction must stay outside public Git.')
expected={31:24919,34:10867,37:18125};assert exam in expected
required={31:[0,1],34:[4,5],37:[6,7]}[exam]
# Require source acquisition receipts for complete needed blocks, not partial grids.
for bid in required:
 if bid in (5,6):
  if bid==6:assert (p/'block6-reused.json').exists()
  else:assert (p/'block5-reused.json').exists()
 else:
  rows=[json.loads(x.read_text()) for x in (p/'new-source-parts').glob(f'*block{bid}.part*.json') if re.search(r'\.part[0-9]+\.json$',x.name)]
  target={0:(32,7094259392-3605831609),1:(3488427783,7094259392),4:(14292057434,17802009149),7:(24686214119,28147831032)}[bid]
  rows.sort(key=lambda x:x['range_start']);assert rows and rows[0]['range_start']==target[0] and rows[-1]['range_end_inclusive']+1==target[1]
  assert all(a['range_end_inclusive']+1==b['range_start'] for a,b in zip(rows,rows[1:]))
rows=[x for x in json.loads((p/'target-members-private.json').read_text()) if x['exam']==exam]
assert len(rows)==expected[exam]
# One extracted exam + its ZIP; reserve 3GB, account for concurrently queued ranges.
need=sum(x['bytes'] for x in rows)*2+3_000_000_000
assert shutil.disk_usage(p).free>need,('extraction storage gate',need,shutil.disk_usage(p).free)
stage=p/f'extract-{exam}';assert not stage.exists();stage.mkdir()
print('Extracting approved examination',exam,flush=True)
with py7zr.SevenZipFile(p/'source.sparse.7z') as z:z.extract(path=stage,targets=[x['path'] for x in rows])
manifest=[];dest=p/f'galar{exam}-originals.zip';assert not dest.exists()
with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
 for i,row in enumerate(sorted(rows,key=lambda x:int(Path(x['path']).stem.split('_')[1])),1):
  src=stage/row['path'];raw=src.read_bytes()
  assert len(raw)==row['bytes'] and (zlib.crc32(raw)&0xffffffff)==row['crc32']
  with Image.open(io.BytesIO(raw)) as im:assert im.format=='PNG';im.verify()
  with Image.open(io.BytesIO(raw)) as im:im.load();shape=im.size
  frame=int(src.stem.split('_')[1]);name=f'images/{exam:03}/{src.name}'
  zi=zipfile.ZipInfo(name,date_time=(2026,11,6,0,0,0));zi.compress_type=zipfile.ZIP_STORED
  z.writestr(zi,raw)
  manifest.append({'exam':exam,'source_frame':frame,'source_path':row['path'],'bytes':len(raw),'source_crc32':row['crc32'],'sha256':hashlib.sha256(raw).hexdigest(),'width':shape[0],'height':shape[1]})
  if i%5000==0:print(exam,i,'original PNGs decoded, CRC/SHA checked and packaged',flush=True)
assert len(manifest)==expected[exam] and all(b['source_frame']-a['source_frame']==5 for a,b in zip(manifest,manifest[1:]))
assert len({x['sha256'] for x in manifest})<=expected[exam]
with (p/f'galar{exam}-image-hashes-private.json').open('x') as f:json.dump(manifest,f)
h=hashlib.sha256()
with dest.open('rb') as f:
 for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
receipt={'exam':exam,'images':len(manifest),'png_bytes':sum(x['bytes'] for x in manifest),'package_bytes':dest.stat().st_size,'package_sha256':h.hexdigest(),'unique_png_sha256':len({x['sha256'] for x in manifest}),'source_blocks':required,'all_png_decode_and_archive_crc_verified':True}
with (p/f'galar{exam}-originals-receipt.json').open('x') as f:json.dump(receipt,f,indent=2)
shutil.rmtree(stage)
print(json.dumps(receipt),flush=True)
