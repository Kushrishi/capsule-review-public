"""Synthetic only: verify Galar 35 PRIVATE source contract without medical data/network."""
from __future__ import annotations

import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace
import zipfile

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acquire_galar35_private as m


def public_aggregate():
    return json.loads(
        (Path(__file__).resolve().parents[1] /
         "experiments/galar-31-40-index-20261105/aggregate.json").read_text()
    )


def test_exact_frozen_source_block_and_public_aggregate():
    a = public_aggregate()
    assert m.validate_public_index(a) == {
        "exam": 35, "byte_start": 17_802_009_149,
        "byte_end_inclusive": 21_255_343_164,
        "compressed_bytes": 3_453_334_016,
        "expected_source_images": 9643,
    }
    assert sum(b["compressed_bytes"] for b in a["blocks"]) + 3_629_193 == m.ARCHIVE_SIZE
    assert m.MAX_SOURCE_REQUEST_BYTES == 3_453_334_016
    assert m.SOURCE_URL == "https://ndownloader.figshare.com/files/44755700"


@pytest.mark.parametrize("mutation", [
    lambda a: a["official_source"].update(file_id=44725302),
    lambda a: a["official_source"].update(expected_publisher_md5_unverified="0"*32),
    lambda a: a["verification"].update(full_archive_md5_verified=True),
    lambda a: a["verification"].update(original_image_pixels_acquired=1),
    lambda a: a["blocks"][5].update(compressed_bytes=1),
    lambda a: a["blocks"][5].update(image_members_by_exam={"35":9643}),
    lambda a: a["studies"]["35"].update(required_block_ids_for_complete_export=[4,5]),
])
def test_rejects_mutated_or_misleading_source_aggregate(mutation):
    aggregate = public_aggregate()
    mutation(aggregate)
    with pytest.raises(ValueError, match="contract"):
        m.validate_public_index(aggregate)


def synthetic_labels(tmp_path, monkeypatch):
    p=tmp_path/"synthetic-only.zip"
    records = [
        {"frame":"100", "blood":"0"},
        {"frame":"105", "blood":"1"},
        {"frame":"110", "blood":"0"},
    ]
    s=BytesIO()
    writer=csv.DictWriter(s if False else [], fieldnames=["frame","blood"]) if False else None
    text="frame,blood\n"+"\n".join(f"{x['frame']},{x['blood']}" for x in records)+"\n"
    with zipfile.ZipFile(p, "x", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("35.csv",text)
        # Forbidden cohort members must never be read.
        z.writestr("61.csv","frame,blood\n999,1\n")
        z.writestr("11.csv","frame,blood\n888,0\n")
    monkeypatch.setattr(m,"LABEL_ARCHIVE_BYTES",p.stat().st_size)
    monkeypatch.setattr(m,"LABEL_ARCHIVE_SHA256",m.sha256_file(p))
    monkeypatch.setattr(m,"EXPECTED_IMAGES",3)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_IMAGES",1)
    monkeypatch.setattr(m,"EXPECTED_ANNOTATION_RUNS",1)
    return p


def test_only_exam35_labels_read_and_exact_native_grid(tmp_path,monkeypatch):
    source = synthetic_labels(tmp_path,monkeypatch)
    # Any code attempting a full-ZIP CRC would access 11.csv and 61.csv.
    original=zipfile.ZipFile.open
    def forbid(self, name, *args, **kwargs):
        if name in ("11.csv","61.csv") or getattr(name,"filename",None) in ("11.csv","61.csv"):
            raise AssertionError("Protected outcome file read")
        return original(self,name,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,"open",forbid)
    assert m.verified_label_rows(source) == {100:"0",105:"1",110:"0"}


def test_label_sha_and_row_count_are_enforced(tmp_path,monkeypatch):
    source = synthetic_labels(tmp_path,monkeypatch)
    assert m.verified_label_rows(source)[105]=="1"
    monkeypatch.setattr(m,"LABEL_ARCHIVE_SHA256","0"*64)
    with pytest.raises(ValueError,match="SHA"):
        m.verified_label_rows(source)


@pytest.mark.parametrize("bad_rows,expected", [
    ("frame,blood\n100,0\n105,\n110,0\n","Unknown"),
    ("frame,blood\n100,0\n106,1\n110,0\n","grid"),
    ("frame,blood\n100,0\n105,1\n105,0\n","grid"),
])
def test_unknown_duplicate_or_off_stride_source_labels_rejected(tmp_path,monkeypatch,bad_rows,expected):
    source = synthetic_labels(tmp_path,monkeypatch)
    with zipfile.ZipFile(source,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("35.csv",bad_rows)
    monkeypatch.setattr(m,"LABEL_ARCHIVE_BYTES",source.stat().st_size)
    monkeypatch.setattr(m,"LABEL_ARCHIVE_SHA256",m.sha256_file(source))
    with pytest.raises(ValueError,match=expected):
        m.verified_label_rows(source)


def synthetic_member_list():
    def member(e,idx):
        return f"Path = archive/{e}/frame_{idx:07d}.PNG\nSize = 123\nFolder = -\nBlock = 5"
    return "7z metadata only\n----------\n" + "\n\n".join([
        member(34,10),member(35,100),member(35,105),member(35,110),member(36,10)
    ])


def test_index_joins_original_source_filenames_to_original_labels(monkeypatch):
    monkeypatch.setattr(m,"EXPECTED_BLOCK_IMAGE_MEMBERS",{34:1,35:3,36:1})
    labels={100:"0",105:"1",110:"0"}
    selected=m.index_members(synthetic_member_list(),labels)
    assert [i for i,_ in selected]==[100,105,110]
    assert all("/35/" in name for _,name in selected)
    assert not any("/34/" in name or "/36/" in name for _,name in selected)
    with pytest.raises(ValueError,match="incomplete"):
        m.index_members(synthetic_member_list(),{100:"0",105:"1",110:"0",115:"0"})


def test_unapproved_heldout_index_is_never_accepted(monkeypatch):
    monkeypatch.setattr(m,"EXPECTED_BLOCK_IMAGE_MEMBERS",{34:1,35:3,36:1})
    bad=synthetic_member_list()+"\n\nPath = archive/61/frame_0000061.PNG\nSize = 1\nFolder = -\nBlock = 5\n"
    with pytest.raises(ValueError,match="Unexpected source examination"):
        m.index_members(bad,{100:"0",105:"1",110:"0"})


def test_expected_header_part_hashes_pinned():
    a=public_aggregate()
    assert m.verified_index_receipt({
        "official_file_id":44755700,
        "official_full_archive_bytes":m.ARCHIVE_SIZE,
        "actual_index_only_bytes_transferred":3_629_193,
        "record_type":m.PROFILE["receipt_type"],
        "full_archive_downloaded":False,"pixels_acquired":0,
        "parts":[{"name":name,"sha256":digest}
                 for name,digest in m.SOURCE_INDEX_PART_HASHES.items()],
    }) is None
    with pytest.raises(ValueError,match="receipt"):
        m.verified_index_receipt({
            "official_file_id":44755700,
            "official_full_archive_bytes":m.ARCHIVE_SIZE,
            "actual_index_only_bytes_transferred":3_629_193,
            "record_type":m.PROFILE["receipt_type"],
            "full_archive_downloaded":False,"pixels_acquired":0,
            "parts":[{"name":"signature-header.bin","sha256":"0"*64}],
        })


class MockRange(BaseHTTPRequestHandler):
    data=b"abcdefghijklmnopqrstuvwx"
    mode="good"
    seen=[]
    def log_message(self,*args): pass
    def do_GET(self):
        self.seen.append(self.headers.get("Range"))
        if self.mode=="bad-200":
            self.send_response(200)
            self.send_header("Content-Length",str(len(self.data)))
            self.end_headers()
            return
        left,right=map(int,self.headers.get("Range","").split("=")[1].split("-"))
        self.send_response(206)
        suffix=(right+1) if self.mode=="bad-range" else right
        self.send_header("Content-Range",f"bytes {left}-{suffix}/{m.ARCHIVE_SIZE}")
        self.send_header("Content-Length",str(right-left+1))
        self.end_headers()
        self.wfile.write(self.data[left:right+1])


@pytest.fixture
def mock_http():
    servers=[]
    def create(mode="good"):
        class Handler(MockRange): pass
        Handler.seen=[]
        Handler.mode=mode
        srv=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        servers.append((srv,thread))
        return f"http://127.0.0.1:{srv.server_port}/mock",Handler
    yield create
    for srv,thread in servers:
        srv.shutdown();thread.join(timeout=3);srv.server_close()


def test_exact_206_bounded_source_block_stream_and_sha(tmp_path,mock_http):
    url,handler=mock_http()
    p=tmp_path/"private-sparse.7z";p.write_bytes(b"\0"*40)
    receipt=m.download_one_block(p,url=url,test_range=(3,7))
    assert handler.seen==["bytes=3-9"]
    assert p.read_bytes()[3:10] == b"defghij"
    assert receipt["source_block_sha256"] == hashlib.sha256(b"defghij").hexdigest()
    assert receipt["full_source_md5_verified"] is False


@pytest.mark.parametrize("mode,expected", [
    ("bad-200","206"),("bad-range","Content-Range")
])
def test_range_server_cannot_force_full_source_download(tmp_path,mock_http,mode,expected):
    url,handler=mock_http(mode)
    p=tmp_path/"private-sparse.7z";p.write_bytes(b"\0"*40)
    with pytest.raises(ValueError,match=expected):
        m.download_one_block(p,url=url,test_range=(3,7))
    assert p.read_bytes()==b"\0"*40


def test_original_png_private_package_verified_without_public_artifacts(tmp_path,monkeypatch):
    members=[(100,"Galar/35/frame_0000100.PNG"),
             (105,"Galar/35/frame_0000105.PNG"),
             (110,"Galar/35/frame_0000110.PNG")]
    labels={100:"0",105:"1",110:"0"}
    monkeypatch.setattr(m,"EXPECTED_IMAGES",3)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_IMAGES",1)
    def fake_subprocess(cmd,**kwargs):
        root=Path(next(x[2:] for x in cmd if x.startswith("-o")))
        for frame,name in members:
            target=root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            Image.new("RGB",(12,12),(frame%255,20,30)).save(target,format="PNG")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,"run",fake_subprocess)
    original=tmp_path/"private-sparse.7z";original.write_bytes(b"0")
    package=tmp_path/"original-images-private.zip"
    report=m.package_original_images(
        original,tmp_path/"stage",package,members,labels,
        {"block":5,"source_block_sha256":"a"*64})
    assert report["verified_original_source_images"]==3
    assert report["positive_annotation_images"]==1
    assert report["all_source_images_and_frame_labels_private"] is True
    assert report["archive_complete_full_publisher_md5_verified"] is False
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read("source-frame-private-manifest.json"))
        assert len(manifest)==3
        assert sum(x["blood_label"] for x in manifest)==1
        assert all(x["original_png_sha256"] for x in manifest)
        assert z.read("images/035/frame_0000105.PNG")[:8]==b"\x89PNG\r\n\x1a\n"
    with pytest.raises(FileExistsError):
        m.package_original_images(original,tmp_path/"stage",package,members,labels,{})
