"""Verify privately restored source pieces against complete frozen block hashes.

No network, source extraction, labels, clinical inference or whole-archive claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def verify(pieces,blocks,directory):
    results=[]
    for block in blocks:
        cursor=block['start'];total=0;digest=hashlib.sha256()
        selected=sorted((r for r in pieces if r['block']==block['block']),key=lambda r:r['start'])
        for row in selected:
            if row['start']!=cursor:raise ValueError('Source-piece gap or overlap.')
            p=Path(directory)/row['file'];wrapper=hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1048576),b''):wrapper.update(chunk)
            if p.stat().st_size!=row['wrapper_bytes'] or wrapper.hexdigest()!=row['wrapper_sha256']:
                raise ValueError('Retained source wrapper changed.')
            raw=hashlib.sha256();n=0
            with zipfile.ZipFile(p) as z:
                if z.namelist()!=[row['member']]:raise ValueError('Unexpected transport members.')
                with z.open(row['member']) as f:
                    for chunk in iter(lambda:f.read(1048576),b''):
                        digest.update(chunk);raw.update(chunk);n+=len(chunk)
            if n!=row['raw_bytes'] or raw.hexdigest()!=row['raw_sha256']:raise ValueError('Retained source payload changed.')
            cursor+=n;total+=n
        if total!=block['bytes'] or digest.hexdigest()!=block['sha256']:raise ValueError('Complete pinned source block mismatch.')
        results.append({'block':block['block'],'bytes':total,'sha256':digest.hexdigest(),'pieces':len(selected)})
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','contract','directory'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    if any(x.resolve().is_relative_to(root) for x in (a.manifest,a.contract,a.directory)):raise ValueError('Private source data must stay outside Git.')
    pieces=json.loads(a.manifest.read_text());contract=json.loads(a.contract.read_text())
    print(json.dumps({'verified_blocks':verify(pieces,contract['blocks'],a.directory),'all_match':True},indent=2))
