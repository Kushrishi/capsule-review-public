"""Synthetic safety checks for exact, bounded two-block Galar source acquisition."""
from __future__ import annotations

import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
from threading import Thread
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import acquire_galar_multiblock as m


class Handler(BaseHTTPRequestHandler):
    data = b'0' * 32 + b'Q' * 64
    status_code = 206
    wrong_range = False
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(self.status_code)
        if self.status_code != 206:
            self.end_headers()
            return
        a, b = map(int, self.headers['Range'].split('=')[1].split('-'))
        self.send_header('Content-Range', f'bytes {a}-{b + int(self.wrong_range)}/{m.ARCHIVE_SIZE}')
        self.send_header('Content-Length', str(b-a+1))
        self.end_headers()
        self.wfile.write(self.data[a:b+1])


@pytest.fixture
def server():
    started = []
    def go(**changes):
        class Mock(Handler):
            pass
        for key, value in changes.items():
            setattr(Mock, key, value)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), Mock)
        t = Thread(target=srv.serve_forever, daemon=True)
        t.start(); started.append((srv, t))
        return f'http://127.0.0.1:{srv.server_port}/source'
    yield go
    for srv, t in started:
        srv.shutdown(); t.join(timeout=2); srv.server_close()


def test_exact_range_content_bytes_and_sha(tmp_path, server):
    source = tmp_path / 'source.7z'
    source.write_bytes(b'Z' * 128)
    output = m.download_verified_range(source, 8, 32, 16, url=server(), allow_mock_http=True)
    assert output['compressed_bytes'] == 16
    assert output['compressed_block_sha256'] == hashlib.sha256(b'Q'*16).hexdigest()
    assert source.read_bytes()[32:48] == b'Q' * 16
    assert output['source_archive_full_md5_verified'] is False


def test_refuses_200_wrong_range_and_unapproved_source(tmp_path, server):
    source = tmp_path / 'source.7z'; source.write_bytes(b'Z'*128)
    with pytest.raises(ValueError, match='206'):
        m.download_verified_range(source, 8, 32, 16, url=server(status_code=200), allow_mock_http=True)
    with pytest.raises(ValueError, match='Content-Range'):
        m.download_verified_range(source, 8, 32, 16, url=server(wrong_range=True), allow_mock_http=True)
    with pytest.raises(ValueError, match='Unapproved'):
        m.download_verified_range(source, 8, 32, 16, url=server())
    with pytest.raises(ValueError, match='Unapproved'):
        m.download_verified_range(source, 7, m.EXPECTED_BLOCK_START[8], m.EXPECTED_BLOCK_BYTES[8])
    assert source.read_bytes() == b'Z'*128


def sample_selection(tmp_path, *, forbidden=False):
    path = tmp_path / 'private-frames.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['exam','frame','filename','blood','fit_enriched','reference_uniform','source_csv_sha256'], lineterminator='\n')
        writer.writeheader()
        for i in range(1006):
            writer.writerow({'exam':30,'frame':5*i,'filename':f'frame_{5*i:06d}.PNG',
                             'blood':'1' if i<200 else '0','fit_enriched':'1',
                             'reference_uniform': '1' if i%2 else '0', 'source_csv_sha256':'a'*64})
        if forbidden:
            writer.writerow({'exam':11,'frame':5,'filename':'frame_000005.PNG','blood':'0',
                             'fit_enriched':'1','reference_uniform':'0','source_csv_sha256':'b'*64})
    return path


def test_source_receipt_exact_offsets_and_original_plan(tmp_path, monkeypatch):
    root=Path(__file__).resolve().parents[1]/'experiments/galar-21-30-source-index'
    layout=json.loads((root/'layout.json').read_text())
    receipt=json.loads((root/'receipt.json').read_text())
    selection=sample_selection(tmp_path)
    monkeypatch.setattr(m, 'EXPECTED_PRIVATE_PLAN_SHA256', m.sha256_file(selection))
    assert m.check_source(layout, receipt, selection) == [
        (8, 27_843_799_086, 3_514_256_456),
        (9, 31_358_055_542, 630_002_169),
    ]
    tampered=json.loads(json.dumps(layout))
    tampered['blocks'][8]['compressed_bytes']+=1
    with pytest.raises(ValueError, match='source size|mismatched'):
        m.check_source(tampered, receipt, selection)
    altered=json.loads(json.dumps(receipt))
    altered['parts'][0]['sha256']='0'*64
    with pytest.raises(ValueError, match='hashes'):
        m.check_source(layout, altered, selection)
    corrupted=tmp_path/'altered-selection.csv'
    corrupted.write_bytes(selection.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='manifest was changed'):
        m.check_source(layout, receipt, corrupted)


def test_forbidden_eval_examination_never_enters_fitting_request(tmp_path):
    with pytest.raises(ValueError, match='evaluation or unapproved'):
        m.requested_rows(sample_selection(tmp_path, forbidden=True))
    rows=m.requested_rows(sample_selection(tmp_path))
    assert len(rows)==1006 and all(int(x['exam'])==30 for x in rows)
    with pytest.raises(ValueError, match='Only the preregistered'):
        m.requested_rows(sample_selection(tmp_path), exam=11)


def test_source_member_mapping_all_blocks_and_variable_padding(monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_EXAM_BLOCK_IMAGES',{8:2,9:1})
    listing='archive\n----------\n'+'\n\n'.join([
        'Path = Galar/30/frame_0000005.PNG\nSize = 80\nFolder = -\nBlock = 8',
        'Path = Galar/30/frame_0000010.PNG\nSize = 80\nFolder = -\nBlock = 8',
        'Path = Galar/30/frame_0000015.PNG\nSize = 80\nFolder = -\nBlock = 9',
        'Path = Galar/30/readme.txt\nSize = 20\nFolder = -\nBlock = 9',
    ])
    wanted=[{'frame':'5','blood':'0'}, {'frame':'15','blood':'1'}]
    found=m.find_members(listing,wanted)
    assert [int(r['frame']) for r,_ in found]==[5,15]
    assert found[0][1].endswith('frame_0000005.PNG')
    with pytest.raises(ValueError, match='missing|does not exist'):
        m.find_members(listing,wanted+[{'frame':'50','blood':'1'}])
    with pytest.raises(ValueError, match='another solid block'):
        m.find_members(listing.replace('Block = 8','Block = 7'),wanted)
    with pytest.raises(ValueError, match='Ambiguous'):
        m.find_members(listing+'\n\nPath = Galar/30/frame_0000005.PNG\nFolder = -\nBlock = 8',wanted)


def test_source_image_package_checks_png_and_private_manifest(tmp_path,monkeypatch):
    from PIL import Image
    work=tmp_path/'stage';work.mkdir()
    sparse=tmp_path/'source.7z';sparse.write_bytes(b'FAKE')
    members=[({'frame':str(i),'blood':str(int(i==5)),'fit_enriched':'1','reference_uniform':'0'},
              f'Galar/30/frame_{i:06d}.PNG') for i in (0,5)]
    def fake_extract(cmd,**kwargs):
        assert cmd[0]=='7z' and any(s.startswith('-i@') for s in cmd)
        dest=Path(next(s[2:] for s in cmd if s.startswith('-o')))
        for _,path in members:
            f=dest/path;f.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(16,16),'red').save(f)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,'run',fake_extract)
    dest=tmp_path/'private.zip'
    result=m.extract_and_package(sparse,members,work,dest)
    assert result['verified_source_images']==2
    assert result['blood_positive_selected_images']==1
    assert not result['private_source_images_committed_to_github']
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        entries=json.loads(z.read('verified-private-manifest.json'))
        assert len(entries)==2 and {x['frame'] for x in entries}=={0,5}
        assert 'images/030/frame_000005.PNG' in z.namelist()
    with pytest.raises(FileExistsError):
        m.extract_and_package(sparse,members,work,dest)