"""Synthetic privacy, integrity and exact-range tests for Galar36 source reuse."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace
import zipfile

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acquire_galar36_private_incremental as m


def index():
    return json.loads((Path(__file__).resolve().parents[1] /
        "experiments/galar-31-40-index-20261105/aggregate.json").read_text())


def test_live_verified_source_36_contract_and_reused_block_ranges():
    result=m.verify_source_plan(index())
    assert result == {"complete_source_examination":36,"source_file_id":44755700,
                      "reused_block":5,"new_block":6,
                      "new_exact_range":[21_255_343_165,24_686_214_118],
                      "new_compressed_bytes":3_430_870_954}


@pytest.mark.parametrize("tamper",[
    lambda x:x["official_source"].update(file_id=44725302),
    lambda x:x["verification"].update(original_image_pixels_acquired=1),
    lambda x:x["blocks"][6].update(compressed_bytes=1),
    lambda x:x["blocks"][5]["image_members_by_exam"].update({"36":3097}),
    lambda x:x["studies"]["36"].update(required_block_ids_for_complete_export=[6]),
    lambda x:x["studies"]["36"].update(previous_label_positive_rows=999),
])
def test_tampered_publisher_index_refuses_original_source_reuse(tamper):
    i=index()
    tamper(i)
    with pytest.raises((ValueError,m.InvalidSourcePlan)):
        m.verify_source_plan(i)


def test_official_original_block_5_sha_is_fixed():
    assert m.OLD_BYTES==3_453_334_016
    assert m.OLD_SHA256=="0b24a245d8f7e72b69ad1e1295d757ce43a03ccaa87e73795423804c5e70d225"
    assert m.NEW_START==m.OLD_START+m.OLD_BYTES
    assert m.END_EXCLUSIVE==m.NEW_START+m.NEW_BYTES


def fake_labels_zip(tmp_path, monkeypatch, bad=None):
    p=tmp_path/"synthetic-corrected-labels.zip"
    rows="frame,blood\n100,0\n105,1\n110,1\n115,0\n120,1\n125,0\n130,0\n"
    if bad=="gap":
        rows=rows.replace("105,1","106,1")
    if bad=="unknown":
        rows=rows.replace("105,1","105,")
    with zipfile.ZipFile(p,"x") as z:
        z.writestr("36.csv",rows)
        z.writestr("61.csv","frame,blood\n100,1\n")
        z.writestr("11.csv","frame,blood\n100,0\n")
    monkeypatch.setattr(m,"LABEL_ARCHIVE_BYTES",p.stat().st_size)
    monkeypatch.setattr(m,"LABEL_ARCHIVE_SHA256",m.sha256_file(p))
    monkeypatch.setattr(m,"EXPECTED_SOURCE_IMAGES",7)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_IMAGES",3)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_RUNS",2)
    return p


def test_official36_only_label_member_opened(tmp_path,monkeypatch):
    labels=fake_labels_zip(tmp_path,monkeypatch)
    orig=zipfile.ZipFile.open
    def guard(self,name,*args,**kwargs):
        n=name if isinstance(name,str) else name.filename
        if n in ("11.csv","61.csv"):
            raise AssertionError("Protected outcome file was read.")
        return orig(self,name,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,"open",guard)
    assert m.verified_labels36(labels)=={
        100:"0",105:"1",110:"1",115:"0",120:"1",125:"0",130:"0"
    }


@pytest.mark.parametrize("bad,match",[("gap","grid"),("unknown","Unknown")])
def test_incomplete_or_unknown_outcomes_fail_closed(tmp_path,monkeypatch,bad,match):
    p=fake_labels_zip(tmp_path,monkeypatch,bad)
    with pytest.raises(ValueError,match=match):
        m.verified_labels36(p)


def test_original_label_zip_checksum_required(tmp_path,monkeypatch):
    p=fake_labels_zip(tmp_path,monkeypatch)
    monkeypatch.setattr(m,"LABEL_ARCHIVE_SHA256","0"*64)
    with pytest.raises(ValueError,match="SHA256"):
        m.verified_labels36(p)


def fake_index_receipts(tmp_path,monkeypatch):
    p=tmp_path/"synthetic-retained-source-index.zip"
    parts = {
        "signature-header.bin":(0,b"abc"),
        "encoded-index-0.bin":(10,b"defg"),
        "next-header.bin":(97,b"xyz"),
    }
    descriptions={}
    for name,(offset,raw) in parts.items():
        descriptions[name]=(hashlib.sha256(raw).hexdigest(),offset,len(raw))
    monkeypatch.setattr(m,"SOURCE_INDEX_NAMES",descriptions)
    with zipfile.ZipFile(p,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name,(_,raw) in parts.items():
            z.writestr(m.PRIVATE_RECEIPT_ROOT+name,raw)
        z.writestr(m.PRIVATE_RECEIPT_ROOT+"receipt.json",json.dumps({
            "official_file_id":m.FILE_ID,
            "official_full_archive_bytes":m.ARCHIVE_SIZE,
            "actual_index_only_bytes_transferred":3_629_193,
            "full_archive_downloaded":False,"pixels_acquired":0,
            "record_type":"galar-31-40-7z-index-only-v1",
            "parts":[{"name":name,"offset":offset,"length":len(raw),
                      "sha256":hashlib.sha256(raw).hexdigest()}
                     for name,(offset,raw) in parts.items()]
        }))
        z.writestr("20251215_Labels_Updated.zip","synthetic forbidden private data")
    return p,parts


def test_reuses_pinned_private_index_header_parts_without_other_data(tmp_path,monkeypatch):
    p,parts=fake_index_receipts(tmp_path,monkeypatch)
    original=zipfile.ZipFile.read
    def guard(self,name,*args,**kwargs):
        n=name if isinstance(name,str) else name.filename
        if n=="20251215_Labels_Updated.zip":
            raise AssertionError("Index preflight attempted to open protected label archive.")
        return original(self,name,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,"read",guard)
    assert sorted(m.retained_index_parts(p))==sorted([
        (offset,raw) for offset,raw in parts.values()
    ])


def test_corrupt_retained_header_part_fail_closed(tmp_path,monkeypatch):
    p,parts=fake_index_receipts(tmp_path,monkeypatch)
    with zipfile.ZipFile(p,"a") as z:
        # Use a new unique invalid name; never allow an external unexpected part.
        z.writestr(m.PRIVATE_RECEIPT_ROOT+"receipt.json","{}")
    with pytest.raises((ValueError,KeyError)):
        m.retained_index_parts(p)


def test_reuse_block5_requires_exact_byte_hash(tmp_path,monkeypatch):
    p=tmp_path/"block5-synthetic.bin"
    p.write_bytes(b"block5data")
    monkeypatch.setattr(m,"OLD_BYTES",10)
    monkeypatch.setattr(m,"OLD_SHA256",hashlib.sha256(b"block5data").hexdigest())
    m.verify_retained_block(p)
    p.write_bytes(b"badblock55")
    with pytest.raises(ValueError,match="block5"):
        m.verify_retained_block(p)


def test_sparse_original_archive_reconstruction_is_bounded(tmp_path,monkeypatch):
    p=tmp_path/"old-block5.bin"
    p.write_bytes(b"original")
    monkeypatch.setattr(m,"OLD_BYTES",8)
    monkeypatch.setattr(m,"OLD_START",3)
    monkeypatch.setattr(m,"ARCHIVE_SIZE",30)
    monkeypatch.setattr(m,"OLD_SHA256",hashlib.sha256(b"original").hexdigest())
    sparse=tmp_path/"private-sparse.7z"
    m.assemble_private_sparse(p,[(0,b"abc"),(27,b"xyz")],sparse)
    assert sparse.stat().st_size==30
    assert sparse.read_bytes()[:11]==b"abcoriginal"
    assert sparse.read_bytes()[27:]==b"xyz"
    with pytest.raises(FileExistsError):
        m.assemble_private_sparse(p,[],sparse)


class MockPartial(BaseHTTPRequestHandler):
    DATA=b"abcdefghijklmnopqrstuvwxyz"
    MODE="good"
    seen=[]
    def log_message(self,*args): pass
    def do_GET(self):
        self.seen.append(self.headers.get("Range"))
        if self.MODE=="full":
            self.send_response(200)
            self.send_header("Content-Length",str(len(self.DATA)))
            self.end_headers()
            self.wfile.write(self.DATA)
            return
        a,b=map(int,self.headers["Range"].split("=")[1].split("-"))
        self.send_response(206)
        expected_b=b+1 if self.MODE=="wrong-range" else b
        self.send_header("Content-Range",f"bytes {a}-{expected_b}/{m.ARCHIVE_SIZE}")
        self.send_header("Content-Length",str(b-a+1))
        self.end_headers()
        self.wfile.write(self.DATA[a:b+1])


@pytest.fixture
def mock_http():
    servers=[]
    def create(mode="good"):
        class Handler(MockPartial):pass
        Handler.MODE=mode
        Handler.seen=[]
        srv=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        servers.append((srv,thread))
        return f"http://127.0.0.1:{srv.server_port}/test",Handler
    yield create
    for srv,thread in servers:
        srv.shutdown();thread.join(timeout=3);srv.server_close()


def test_exact_range_http206_with_local_mock_and_private_sparse(tmp_path,mock_http):
    url,handler=mock_http()
    sparse=tmp_path/"private-sparse.7z";sparse.write_bytes(b"\0"*30)
    report=m.download_block6(sparse,url=url,test_range=(4,8))
    assert handler.seen==["bytes=4-11"]
    assert sparse.read_bytes()[4:12]==b"efghijkl"
    assert report["compressed_bytes_received"]==8
    assert report["source_block_sha256"]==hashlib.sha256(b"efghijkl").hexdigest()
    assert report["full_source_md5_verified"] is False


@pytest.mark.parametrize("mode,error",[("full","206"),("wrong-range","Content-Range")])
def test_reject_full_archive_http200_or_wrong_content_range(tmp_path,mock_http,mode,error):
    url,handler=mock_http(mode)
    sparse=tmp_path/"private-sparse.7z";sparse.write_bytes(b"\0"*30)
    with pytest.raises(ValueError,match=error):
        m.download_block6(sparse,url=url,test_range=(4,8))
    assert sparse.read_bytes()==b"\0"*30


def synthetic_listing(rows):
    return "Path = source.7z\nType = 7z\n\n----------\n" + "\n\n".join(
        f"Path = Galar/{exam}/frame_{frame:07d}.PNG\nFolder = -\nBlock = {block}\nSize = 123"
        for exam,frame,block in rows
    )


def test_source_listing_selects_full36_not_partial34_or37(monkeypatch):
    rows=[(34,100,5),(35,100,5),(36,100,5),(36,105,5),
          (36,110,6),(36,115,6),(37,200,6)]
    listing=synthetic_listing(rows)
    monkeypatch.setattr(m,"EXPECTED_SOURCE_IMAGES",4)
    monkeypatch.setattr(m,"EXPECTED_BLOCK_MEMBERS",{
        5:{34:1,35:1,36:2},6:{36:2,37:1}
    })
    fake=SimpleNamespace(returncode=0,stdout=listing.encode(),stderr=b"")
    monkeypatch.setattr(m.subprocess,"run",lambda *a,**k:fake)
    # The expected per block counts are protected and must be validated.
    with pytest.raises(ValueError,match="Complete Galar36"):
        m.list_complete_exam36(Path("synthetic.7z"),{
            100:"0",105:"1",110:"1",115:"0"
        })


def test_private_png_packaging_original_names_crc_and_no_overwrite(tmp_path,monkeypatch):
    labels={100:"0",105:"1",110:"1"}
    entries=[(100,"Galar/36/frame_0000100.PNG"),
             (105,"Galar/36/frame_0000105.PNG"),
             (110,"Galar/36/frame_0000110.PNG")]
    monkeypatch.setattr(m,"EXPECTED_SOURCE_IMAGES",3)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_IMAGES",2)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_RUNS",1)
    def simulated_7z(cmd,**kwargs):
        directory=Path(next(x[2:] for x in cmd if x.startswith("-o")))
        for frame,name in entries:
            p=directory/name
            p.parent.mkdir(parents=True,exist_ok=True)
            Image.new("RGB",(20,20),(frame%255,30,40)).save(p,format="PNG")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,"run",simulated_7z)
    pkg=tmp_path/"private-original-study36.zip"
    report=m.private_package36(
        tmp_path/"sparse.7z",entries,labels,tmp_path/"temp",pkg,
        {"source_block6":{"source_block_sha256":"a"*64}})
    assert report["verified_original_source_images"]==3
    assert report["positive_annotated_images"]==2
    assert report["all_individual_original_images_and_labels_private"] is True
    with zipfile.ZipFile(pkg) as z:
        assert z.testzip() is None
        raw=json.loads(z.read("source-frame-private-manifest.json"))
        assert sum(x["blood_label"] for x in raw)==2
        assert z.read("images/036/frame_0000100.PNG")[:8]==b"\x89PNG\r\n\x1a\n"
    with pytest.raises(FileExistsError):
        m.private_package36(tmp_path/"sparse.7z",entries,labels,
                            tmp_path/"temp",pkg,{})
