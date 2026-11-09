import hashlib
import sys
from pathlib import Path
import zipfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_foundation_retained_blocks import verify

def test_reconstructed_block_requires_exact_payload_and_contiguity(tmp_path):
    rows=[];start=50
    for j,raw in enumerate((b'first',b'second')):
        file=tmp_path/f'piece{j}.zip';member=f'piece{j}.bin'
        with zipfile.ZipFile(file,'w') as z:z.writestr(member,raw)
        rows.append({'file':file.name,'member':member,'block':1,'start':start,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'wrapper_bytes':file.stat().st_size,'wrapper_sha256':hashlib.sha256(file.read_bytes()).hexdigest()});start+=len(raw)
    blocks=[{'block':1,'start':50,'bytes':11,'sha256':hashlib.sha256(b'firstsecond').hexdigest()}]
    assert verify(rows,blocks,tmp_path)[0]['bytes']==11
    rows[1]['start']+=1
    with pytest.raises(ValueError,match='gap or overlap'):verify(rows,blocks,tmp_path)

def test_corrupt_wrapper_is_rejected(tmp_path):
    p=tmp_path/'bad.zip';p.write_bytes(b'not original')
    row={'file':p.name,'block':1,'start':0,'wrapper_bytes':1,'wrapper_sha256':'0'*64}
    with pytest.raises(ValueError,match='wrapper changed'):verify([row],[{'block':1,'start':0}],tmp_path)
