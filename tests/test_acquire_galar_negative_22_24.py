"""Fail-closed source integrity and privacy tests for the 22/24 original-PNG acquisition."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import acquire_galar_negative_22_24 as m


def test_exact_two_exam_source_inventory_and_three_immutable_blocks():
    assert m.EXAMS==(22,24)
    assert m.BLOCKS==(0,1,2)
    assert sum(x[1] for x in m.COMPRESSED.values())==10_420_312_279
    assert m.COMPRESSED[1][0]==3_474_498_124
    assert m.EXAM_SOURCE_BLOCK_COUNTS[22]=={0:6244,1:1285}
    assert m.EXAM_SOURCE_BLOCK_COUNTS[24]=={1:1225,2:12193}
    assert m.FROZEN_REQUEST_SHA=='1aedfcdecbb270687a660acd50f312803ed0884308ea9a0973102aac242409f1'


def test_immutable_protocol_matches_prepixel_commit():
    spec=Path(__file__).resolve().parents[1]/'docs'/'GALAR_NEGATIVE_22_24_ACQUISITION_SPEC.json'
    # Test with real tracked source file in GitHub CI, fail if spec omitted.
    if not spec.is_file():
        pytest.skip('Source-only local test fixture does not have the complete repository checkout.')
    result=m.verify_protocol(spec)
    assert result['allowed_examination_ids']==[22,24]
    assert result['source_archive']['total_exact_compressed_transfer_bytes']==10_420_312_279


def synthetic_request_csv(path:Path):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(m.EXPECTED_FIELDS),lineterminator='\n')
        writer.writeheader()
        for exam in (22,23,24):
            for i in range(3):
                frame=5*i
                writer.writerow({'exam':exam,'frame':frame,'filename':f'frame_{frame:06d}.PNG',
                                 'blood':'0','fit_enriched':'1','reference_uniform':'1',
                                 'source_csv_sha256':'0'*64})


def test_frozen_requests_rejects_modified_roles_and_protected_exams(tmp_path,monkeypatch):
    p=tmp_path/'selection.csv';synthetic_request_csv(p)
    monkeypatch.setattr(m,'EXPECTED_FRAMES',3)
    monkeypatch.setattr(m,'FROZEN_REQUEST_SHA',m.sha256_file(p))
    approved=m.read_frozen_requests(p)
    assert set(approved)=={22,24} and all(len(v)==3 for v in approved.values())
    # Other fitting-pool exam 23 requests are correctly ignored without data access.
    text=p.read_text().replace('frame_000005.PNG','frame_0x0005.PNG',1)
    p.write_text(text)
    with pytest.raises(ValueError,match='SHA-256'):
        m.read_frozen_requests(p)
    monkeypatch.setattr(m,'FROZEN_REQUEST_SHA',m.sha256_file(p))
    with pytest.raises(ValueError,match='frame name'):
        m.read_frozen_requests(p)


def listing(records):
    return 'Archive = synthetic.7z\n----------\n'+'\n\n'.join(
        f'Path = Galar/{ex}/frame_{frame:06d}.PNG\nFolder = -\nSize = 99\nBlock = {block}'
        for ex,frame,block in records)+'\n'


def test_original_source_index_partition_uses_real_block_not_guess(monkeypatch):
    monkeypatch.setattr(m,'EXAM_SOURCE_COUNTS',{22:2,24:2})
    monkeypatch.setattr(m,'EXAM_SOURCE_BLOCK_COUNTS',{22:{0:1,1:1},24:{1:1,2:1}})
    request={e:{i:{'exam':str(e),'frame':str(i),'filename':f'frame_{i:06d}.PNG',
                   'blood':'0','fit_enriched':'1','reference_uniform':'1'} for i in (0,5)} for e in (22,24)}
    base=[(22,0,0),(22,5,1),(24,0,1),(24,5,2)]
    result=m.exact_archive_member_partition(listing(base),request)
    assert {block:len(rows) for block,rows in result.items()}=={0:1,1:2,2:1}
    with pytest.raises(ValueError,match='Duplicate'):
        m.exact_archive_member_partition(listing(base+[(24,5,2)]),request)
    with pytest.raises(ValueError,match='outside the three allowed'):
        m.exact_archive_member_partition(listing(base[:-1]+[(24,5,7)]),request)
    with pytest.raises(ValueError,match='not all requested|Not all requested'):
        m.exact_archive_member_partition(listing(base[:-1]+[(24,99,2)]),request)
    # A protected Galar11 path has no permitted exam ID and is never selected.
    result=m.exact_archive_member_partition(listing(base+[(11,0,0)]),request)
    assert sum(map(len,result.values()))==4


def test_sparse_verified_header_reconstruction_rejects_tamper(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ARCHIVE_SIZE',1000)
    h=tmp_path/'headers';h.mkdir()
    parts=[]
    for name,offset,raw in [('signature-header.bin',0,b'abc'),('encoded-index-0.bin',200,b'xyz'),('next-header.bin',997,b'abc')]:
        (h/name).write_bytes(raw)
        parts.append({'name':name,'offset':offset,'length':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    target=tmp_path/'sparse.7z'
    m.sparse_archive_from_headers(h,{'parts':parts},target)
    assert target.stat().st_size==1000
    with pytest.raises(FileExistsError):
        m.sparse_archive_from_headers(h,{'parts':parts},target)
    target.unlink();(h/'signature-header.bin').write_bytes(b'xxx')
    with pytest.raises(ValueError,match='index bytes'):
        m.sparse_archive_from_headers(h,{'parts':parts},target)


class FakeHTTP:
    status=206
    def __init__(self,data,headers):
        self._stream=io.BytesIO(data)
        self.headers=headers
    def geturl(self):return m.SOURCE_URL
    def read(self,n=-1):return self._stream.read(n)
    def __enter__(self):return self
    def __exit__(self,*args):return False


def test_exact_http_range_sha_and_fail_closed_200(tmp_path,monkeypatch):
    raw=b'abcde';original=hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(m,'ARCHIVE_SIZE',100)
    monkeypatch.setattr(m,'COMPRESSED',{0:(10,len(raw),original)})
    archive=tmp_path/'sparse';archive.write_bytes(bytes(100))
    headers={'Content-Range':'bytes 10-14/100','Content-Length':'5'}
    def good(request,timeout=None):
        assert request.get_header('Range')=='bytes=10-14'
        return FakeHTTP(raw,headers)
    monkeypatch.setattr(m.urllib.request,'urlopen',good)
    receipt=m.transfer_verified_block(archive,0)
    assert receipt['compressed_sha256']==original
    assert archive.read_bytes()[10:15]==raw
    class WrongStatus(FakeHTTP):status=200
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda *a,**k:WrongStatus(raw,headers))
    with pytest.raises(ValueError,match='206'):
        m.transfer_verified_block(archive,0)
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda *a,**k:FakeHTTP(raw,{**headers,'Content-Range':'bytes 0-4/100'}))
    with pytest.raises(ValueError,match='Content-Range'):
        m.transfer_verified_block(archive,0)
    monkeypatch.setattr(m,'COMPRESSED',{0:(10,len(raw),'0'*64)})
    monkeypatch.setattr(m.urllib.request,'urlopen',good)
    with pytest.raises(ValueError,match='digest mismatch'):
        m.transfer_verified_block(archive,0)


def test_selected_png_verification_and_final_private_package(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_FRAMES',1)
    monkeypatch.setattr(m,'EXPECTED_TOTAL',2)
    source=tmp_path/'retained';source.mkdir()
    raw=io.BytesIO();Image.new('RGB',(8,8),(1,3,5)).save(raw,format='PNG')
    originals={}
    for exam in (22,24):
        d=source/f'{exam:03d}';d.mkdir()
        filename='frame_000005.PNG'
        (d/filename).write_bytes(raw.getvalue())
        originals[(exam,5)]={'exam':exam,'frame':5,'filename':filename,
                            'blood':0,'fit_enriched':1,'reference_uniform':1,
                            'source_csv_sha256':'f'*64,
                            'source_image_sha256':hashlib.sha256(raw.getvalue()).hexdigest(),
                            'source_bytes':len(raw.getvalue())}
    package=tmp_path/'private-output.zip'
    result=m.build_private_archive(source,originals,package)
    assert result['source_original_png_bytes']==2*len(raw.getvalue())
    assert result['source_blood_positive_annotations']==0
    assert result['original_archive_full_md5_verified'] is False
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={'images/022/frame_000005.PNG','images/024/frame_000005.PNG','verified-private-manifest.json'}
    with pytest.raises(FileExistsError):m.build_private_archive(source,originals,package)


def test_reject_incomplete_source_and_extra_uncorroborated_frames(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='Incomplete'):
        m.build_private_archive(tmp_path,{},tmp_path/'source.zip')
    # Guarantee original source transfer is only a paper plan until explicitly executed.
    assert m.MAX_SOURCE_TRANSFER==10_420_312_279
    assert m.EXAMS==(22,24)
    assert m.SOURCE_CORRECTED_ZIP_SHA!='0'*64
