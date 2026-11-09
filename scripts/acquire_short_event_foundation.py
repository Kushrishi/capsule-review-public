"""Bounded, private, pinned solid-block recovery for short-event originals.

No source IDs, clinical membership or labels are selected by this executable.
They must be supplied in a separately retained acquisition contract.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
import urllib.request
import zipfile
import zlib
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def private(path):
    p=Path(path)
    if p.is_symlink() or p.resolve().is_relative_to(ROOT):
        raise ValueError('Private source data must stay outside Git.')
    return p.resolve()

def validate_range(status, content_range, start, length, total):
    if status!=206 or content_range!=f'bytes {start}-{start+length-1}/{total}':
        raise ValueError('Exact206 source range required; no full-file fallback.')

def run(contract_path, contract_sha, index_dir, decoder, output):
    contract_path=private(contract_path);index_dir=private(index_dir)
    decoder=private(decoder);output=private(output)
    if output.exists():raise FileExistsError('Never overwrite acquisition evidence.')
    c=json.loads(contract_path.read_text())
    if sha(contract_path)!=contract_sha or sha(__file__)!=c['acquisition_code_sha256'] or sha(decoder)!=c['decoder_sha256']:
        raise ValueError('Frozen contract/code/decoder mismatch.')
    if c['source_id']!=45258019 or c['source_bytes']!=31989399751:
        raise ValueError('Unqualified source.')
    if [b['block'] for b in c['blocks']]!=[1,3] or sum(b['bytes'] for b in c['blocks'])!=7014787752:
        raise ValueError('Frozen two-block design changed.')
    if c['charged_transfer_cap']!=7200000000 or len(c['new_originals'])!=159:
        raise ValueError('Frozen source resource gate changed.')
    if shutil.disk_usage(output.parent).free<c['minimum_free_bytes']:
        raise ValueError('Insufficient source/retention capacity.')
    output.mkdir();sparse=output/'source.sparse.7z'
    with sparse.open('xb') as f:f.truncate(c['source_bytes'])
    for p in c['index_parts']:
        source=index_dir/p['name']
        if source.stat().st_size!=p['length'] or sha(source)!=p['sha256']:
            raise ValueError('Retained index bytes changed.')
        with sparse.open('r+b') as f:f.seek(p['offset']);f.write(source.read_bytes())
    # Listing uses only retained metadata, before any new source block bytes.
    listed=subprocess.run([str(decoder),'l','-slt',str(sparse)],capture_output=True,text=True,check=True)
    (output/'decoder-index-listing.txt').write_text(listed.stdout)
    lock=threading.Lock();charged=0;receipts=[]
    ranges=[]
    for block in c['blocks']:
        for rel in range(0,block['bytes'],50000000):
            ranges.append((block['block'],block['start']+rel,min(50000000,block['bytes']-rel)))
    def one(item):
        nonlocal charged
        block,start,n=item;attempts=[]
        for attempt in range(2):
            with lock:
                if charged+n>c['charged_transfer_cap']:raise ValueError('Cumulative charged source cap reached.')
                charged+=n
            try:
                request=urllib.request.Request(f'https://api.figshare.com/v2/file/download/{c["source_id"]}',headers={'Range':f'bytes={start}-{start+n-1}','Accept-Encoding':'identity'})
                with urllib.request.urlopen(request,timeout=120) as r:
                    validate_range(r.status,r.headers.get('Content-Range'),start,n,c['source_bytes'])
                    if r.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Encoded response refused.')
                    raw=r.read(n+1)
                if len(raw)!=n:raise ValueError('Incomplete bounded source range.')
                with sparse.open('r+b') as f:f.seek(start);f.write(raw)
                record={'block':block,'start':start,'bytes':n,'sha256':hashlib.sha256(raw).hexdigest(),'prior_failures':attempts}
                with lock:receipts.append(record)
                return record
            except Exception as error:
                attempts.append({'attempt':attempt+1,'error':str(error)[:250]})
        raise RuntimeError('Pinned range failed; no alternate source or unbounded retry.')
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for i,_ in enumerate(pool.map(one,ranges),1):
                if i%10==0:print('verified source ranges',i,'/',len(ranges),flush=True)
    finally:
        (output/'range-receipts.json').write_text(json.dumps({'charged_bytes':charged,'receipts':receipts},indent=2))
    transports=[]
    for block in c['blocks']:
        h=hashlib.sha256()
        with sparse.open('rb') as f:
            f.seek(block['start']);remaining=block['bytes'];part=0
            while remaining:
                raw=f.read(min(350000000,remaining))
                if not raw:raise ValueError('Incomplete verified block.')
                h.update(raw);part+=1
                name=f'Galar_Fitting_45258019_Block{block["block"]}_Part{part:03d}.zip'
                member=name.removesuffix('.zip')+'.bin';dest=output/name
                with zipfile.ZipFile(dest,'x',zipfile.ZIP_STORED) as z:z.writestr(member,raw)
                transports.append({'file':name,'member':member,'source':c['source_id'],'block':block['block'],'start':block['start']+block['bytes']-remaining,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'wrapper_bytes':dest.stat().st_size,'wrapper_sha256':sha(dest)})
                remaining-=len(raw)
        if h.hexdigest()!=block['sha256']:raise ValueError('Pinned complete-block SHA256 mismatch.')
    (output/'compressed-retention-manifest-private.json').write_text(json.dumps(transports,indent=2))
    include=output/'selected-members-private.txt';include.write_text('\n'.join(r['path'] for r in c['new_originals'])+'\n')
    stage=output/'new-originals'
    result=subprocess.run([str(decoder),'x','-y','-mmt=2','-i@'+str(include),'-o'+str(stage),str(sparse)],capture_output=True,text=True)
    (output/'extraction.log').write_text(result.stdout+result.stderr)
    if result.returncode!=0:raise RuntimeError('Pinned source extraction failed.')
    if len(list(stage.rglob('*.PNG')))!=len(c['new_originals']):raise ValueError('Unexpected source extraction membership.')
    originals=[];package=output/'Short_Event_Foundation_New_Originals_20261109.zip'
    with zipfile.ZipFile(package,'x',zipfile.ZIP_STORED) as z:
        for row in c['new_originals']:
            raw=(stage/row['path']).read_bytes()
            if len(raw)!=row['bytes'] or zlib.crc32(raw)&0xffffffff!=row['crc32']:
                raise ValueError('Source member CRC/length mismatch.')
            with Image.open(io.BytesIO(raw)) as im:
                if im.format!='PNG':raise ValueError('Original PNG required.')
                im.load()
            originals.append({**row,'sha256':hashlib.sha256(raw).hexdigest()})
            z.writestr('images/'+row['path'],raw)
        z.writestr('source-manifest-private.json',json.dumps(originals,indent=2))
    proof={'contract_sha256':contract_sha,'verified_source_bytes':sum(b['bytes'] for b in c['blocks']),'charged_source_bytes':charged,'full_publisher_md5_verified':False,'originals':originals,'new_original_images':len(originals),'original_image_bytes':sum(r['bytes'] for r in originals),'package_sha256':sha(package),'package_bytes':package.stat().st_size,'complete_blocks_verified':c['blocks']}
    (output/'acquisition-proof-private.json').write_text(json.dumps(proof,indent=2))
    print('Source recovery complete:',len(originals),'new verified originals;',len(transports),'retention pieces',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('contract','index-dir','decoder','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--contract-sha',required=True);a=p.parse_args()
    run(a.contract,a.contract_sha,a.index_dir,a.decoder,a.output)
