"""Bounded block-transfer, source identity, and private export tests; no medical data."""
from __future__ import annotations
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import io
import json
import sys
from threading import Thread
from types import SimpleNamespace
import zipfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import acquire_galar_block1 as m


class Handler(BaseHTTPRequestHandler):
    data=b'A'*48
    no_range=False
    bad_range=False
    def log_message(self,*a):pass
    def do_GET(self):
        self.send_response(200 if self.no_range else 206)
        s,e=map(int,self.headers['Range'].split('=')[1].split('-'))
        if self.no_range:
            self.send_header('Content-Length',str(len(self.data)));self.end_headers();return
        self.send_header('Content-Length',str(e-s+1))
        self.send_header('Content-Range',f'bytes {s}-{e+int(self.bad_range)}/{m.ARCHIVE_SIZE}')
        self.end_headers();self.wfile.write(self.data[s:e+1])


@pytest.fixture
def serve():
    servers=[]
    def make(**kw):
        class Mock(Handler):pass
        for k,v in kw.items():setattr(Mock,k,v)
        server=ThreadingHTTPServer(('127.0.0.1',0),Mock)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        servers.append((server,thread))
        return f'http://127.0.0.1:{server.server_port}/data'
    yield make
    for server,thread in servers:
        server.shutdown();thread.join(timeout=4);server.server_close()


def test_stream_exact_range_into_sparse_file(tmp_path,serve):
    url=serve()
    sparse=tmp_path/'archive.7z'
    sparse.write_bytes(b'0'*64)
    result=m.download_exact_block(url,sparse,start=32,length=16,allow_mock_http=True)
    assert result['transferred_compressed_bytes']==16
    assert result['compressed_block_sha256']==hashlib.sha256(b'A'*16).hexdigest()
    assert sparse.read_bytes()[32:48]==b'A'*16
    assert result['full_source_md5_verified'] is False


def test_block_download_refuses_full_200_before_body(tmp_path,serve):
    url=serve(no_range=True)
    sparse=tmp_path/'archive.7z';sparse.write_bytes(b'0'*64)
    with pytest.raises(ValueError,match='HTTP 206'):
        m.download_exact_block(url,sparse,start=32,length=16,allow_mock_http=True)
    assert sparse.read_bytes()==b'0'*64


def test_block_download_rejects_content_range_mismatch(tmp_path,serve):
    url=serve(bad_range=True)
    sparse=tmp_path/'archive.7z';sparse.write_bytes(b'0'*64)
    with pytest.raises(ValueError,match='content-range'):
        m.download_exact_block(url,sparse,start=32,length=16,allow_mock_http=True)


def test_large_or_unofficial_source_rejected(tmp_path,serve):
    url=serve();sparse=tmp_path/'archive.7z';sparse.write_bytes(b'0'*64)
    with pytest.raises(ValueError,match='official'):
        m.download_exact_block(url,sparse,start=32,length=16)
    with pytest.raises(ValueError,match='bounded'):
        m.download_exact_block(url,sparse,start=32,length=m.MAX_BLOCK_BYTES+1,allow_mock_http=True)


def make_manifest(tmp_path):
    target=tmp_path/'private.csv'
    with target.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['exam','frame','filename','blood','fit_enriched','reference_uniform','source_csv_sha256'],lineterminator='\n')
        w.writeheader()
        for i in range(150):
            w.writerow({'exam':23,'frame':5*i,'filename':f'frame_{5*i:06d}.PNG','blood':str(int(i<5)),
                        'fit_enriched':'1','reference_uniform':str(int(i%2==0)),'source_csv_sha256':'a'*64})
        w.writerow({'exam':30,'frame':'10','filename':'frame_000010.PNG','blood':'1','fit_enriched':'1','reference_uniform':'1','source_csv_sha256':'b'*64})
    return target


def test_private_manifest_only_exam_23_and_unique(tmp_path):
    manifest=make_manifest(tmp_path)
    rows=m.requested_exam_rows(manifest)
    assert len(rows)==150 and all(int(r['exam'])==23 for r in rows)
    with pytest.raises(ValueError,match='exam 23'):
        m.requested_exam_rows(manifest,30)


def test_archive_member_mapping_exact_frame_ids(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_SOURCE_IMAGE_COUNT',3)
    names=[f'Galar/23/frame_{x:06d}.PNG' for x in (0,5,10)]
    listing='archive\n----------\n'+'\n\n'.join(f'Path = {path}\nSize = 120\nPacked Size = 200\nFolder = -\nBlock = 1' for path in names)
    rows=[{'frame':str(x),'filename':f'frame_{x:06d}.PNG','blood':'0'} for x in (0,5)]
    result=m.find_member_paths(listing,rows)
    assert len(result)==2
    assert all(path.startswith('Galar/23/') for _,path in result)
    bad=listing.replace('Block = 1','Block = 2')
    with pytest.raises(ValueError,match='outside'):
        m.find_member_paths(bad,rows)
    with pytest.raises(ValueError,match='missing'):
        m.find_member_paths(listing,rows+[{'frame':'500','filename':'frame_000500.PNG','blood':'1'}])


def test_index_layout_guard_rejects_wrong_metadata(tmp_path,monkeypatch):
    import zipfile
    base=Path(__file__).resolve().parents[1]/'experiments/galar-21-30-source-index'
    layout=json.loads((base/'layout.json').read_text())
    receipt=json.loads((base/'receipt.json').read_text())
    mfile=make_manifest(tmp_path)
    monkeypatch.setattr(m,'EXPECTED_PRIVATE_PLAN_SHA256',m.sha256_file(mfile))
    m.check_metadata(layout,receipt,mfile)
    broken={**layout,'image_members_by_exam':{'23':11784}}
    with pytest.raises(ValueError,match='mismatched'):
        m.check_metadata(broken,receipt,mfile)
    broken={**receipt,'pixels_acquired':1}
    with pytest.raises(ValueError,match='mismatched'):
        m.check_metadata(layout,broken,mfile)


def test_package_decoded_synthetic_pngs_with_frozen_private_identity(tmp_path,monkeypatch):
    from PIL import Image
    root=tmp_path/'job';root.mkdir()
    archive=tmp_path/'sparse.7z';archive.write_bytes(b'STUB')
    rows=[({'frame':str(x),'blood':str(int(x==5)),'fit_enriched':'1','reference_uniform':'0'}, f'root/23/frame_{x:06d}.PNG') for x in (0,5)]
    def fake7z(cmd,**kw):
        assert cmd[0]=='7z' and '-y' in cmd and any(v.startswith('-i@') for v in cmd)
        o=next(v[2:] for v in cmd if v.startswith('-o'))
        for _,p in rows:
            target=Path(o)/p;target.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(8,8),(250,0,0)).save(target)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,'run',fake7z)
    out=tmp_path/'output.zip'
    result=m.extract_and_package(archive,rows,root,out)
    assert result['verified_source_images']==2
    assert result['blood_positive_selected_images']==1
    assert result['image_source_archive_full_md5_verified'] is False
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert len([x for x in z.namelist() if x.endswith('.PNG')])==2
        manifest=json.loads(z.read('verified-private-manifest.json'))
        assert manifest[1]['blood']==1
    with pytest.raises(FileExistsError):
        m.extract_and_package(archive,rows,root,out)


def test_variable_zero_padding_preserves_exact_original_source_frame_id(monkeypatch):
    # Real publisher archive uses frame_<digits>.PNG, not a guaranteed six-digit width.
    monkeypatch.setattr(m,'EXPECTED_SOURCE_IMAGE_COUNT',2)
    listing=('archive\n----------\n'
             'Path = Galar/23/frame_0000000.PNG\nSize = 100\nFolder = -\nBlock = 1\n\n'
             'Path = Galar/23/frame_0000005.PNG\nSize = 100\nFolder = -\nBlock = 1\n')
    wanted=[{'frame':'0','blood':'0'},{'frame':'5','blood':'1'}]
    result=m.find_member_paths(listing,wanted)
    assert [int(x['frame']) for x,_ in result]==[0,5]
    assert result[0][1].endswith('frame_0000000.PNG')


def test_nonimage_member_in_study_folder_is_not_a_source_frame(monkeypatch):
    # Official block 0 has one extra non-PNG metadata member in its 7z listing.
    monkeypatch.setattr(m,'EXPECTED_SOURCE_IMAGE_COUNT',2)
    listing=('archive\n----------\n'
             'Path = Galar/23/frame_0000000.PNG\nSize = 100\nFolder = -\nBlock = 1\n\n'
             'Path = Galar/23/frame_0000005.PNG\nSize = 100\nFolder = -\nBlock = 1\n\n'
             'Path = Galar/23/archive_notes.txt\nSize = 40\nFolder = -\nBlock = 1\n')
    wanted=[{'frame':'0','blood':'0'},{'frame':'5','blood':'1'}]
    assert len(m.find_member_paths(listing,wanted)) == 2