"""Mocked byte-range tests for Galar solid-archive index access. No network."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import struct
import sys
from threading import Thread
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import probe_galar_archive as m


def archive(next_header=b'\x01\x00', payload=b'\x02' * 24):
    start = m.SIGNATURE + b'\x00\x04'
    meta = struct.pack('<QQI', len(payload), len(next_header), zlib.crc32(next_header))
    return start + struct.pack('<I', zlib.crc32(meta)) + meta + payload + next_header


class MockRange(BaseHTTPRequestHandler):
    archive = b''
    mode = 'valid'
    requests = []
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.requests.append(self.headers.get('Range'))
        match = re.fullmatch(r'bytes=(\d+)-(\d+)', self.headers.get('Range', ''))
        if not match:
            self.send_error(400)
            return
        a,b = map(int, match.groups())
        if self.mode == 'no-range':
            self.send_response(200)
            self.send_header('Content-Length', str(len(self.archive)))
            self.end_headers()
            return
        self.send_response(206)
        self.send_header('Content-Range', f'bytes {a}-{b+1 if self.mode == "bad-range" else b}/{len(self.archive)}')
        self.send_header('Content-Length', str(b-a+1))
        self.end_headers()
        self.wfile.write(self.archive[a:b+1])


@pytest.fixture
def serve():
    servers = []
    def start(raw, mode='valid'):
        class Handler(MockRange):
            archive = raw
            requests = []
        Handler.mode = mode
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        servers.append((server, worker))
        return f'http://127.0.0.1:{server.server_port}/file', Handler
    yield start
    for server, worker in servers:
        server.shutdown(); worker.join(timeout=5); server.server_close()


def client(url, size):
    return m.RangeClient(url, size, cap=64*1024, allow_test_http=True)


def test_plain_archive_reads_only_signature_and_next_header(tmp_path, serve):
    raw = archive()
    url, handler = serve(raw)
    report = m.inspect(client(url, len(raw)), tmp_path/'out', sparse_path=tmp_path/'out'/'headers-only.7z')
    assert report['actual_index_only_bytes_transferred'] == 34
    assert handler.requests == ['bytes=0-31', f'bytes={len(raw)-2}-{len(raw)-1}']
    assert (tmp_path/'out'/'headers-only.7z').stat().st_size == len(raw)
    assert report['pixels_acquired'] == 0


def test_encoded_archive_reads_only_compressed_index_ranges(tmp_path, serve):
    # PackInfo offset 0, one stream of 5 bytes at byte 32.
    encoded = bytes([0x17, 0x06, 0x00, 0x01, 0x09, 0x05, 0x00])
    raw = archive(encoded, b'abcde')
    url, handler = serve(raw)
    report = m.inspect(client(url, len(raw)), tmp_path/'encoded')
    assert report['next_header_type'] == 'encoded'
    assert [p['length'] for p in report['parts']] == [32, 7, 5]
    assert handler.requests == ['bytes=0-31', 'bytes=37-43', 'bytes=32-36']


def test_official_identity_cannot_be_changed():
    with pytest.raises(ValueError, match='official'):
        m.RangeClient('https://example.org/data.7z', m.ARCHIVE_SIZE)
    with pytest.raises(ValueError, match='official'):
        m.RangeClient(m.SOURCE_URL, 123)


def test_no_range_200_fails_before_body(tmp_path, serve):
    raw=archive()
    url, handler=serve(raw, 'no-range')
    with pytest.raises(ValueError, match='HTTP 206'):
        m.inspect(client(url,len(raw)),tmp_path/'fail')
    assert len(handler.requests)==1


def test_bad_content_range_fails_closed(tmp_path, serve):
    raw=archive()
    url, handler=serve(raw,'bad-range')
    with pytest.raises(ValueError,match='Content-Range'):
        m.inspect(client(url,len(raw)),tmp_path/'fail')
    assert len(handler.requests)==1


def test_corrupt_start_crc_rejected(tmp_path,serve):
    raw=bytearray(archive());raw[8]^=1
    url,_=serve(bytes(raw))
    with pytest.raises(ValueError,match='start header CRC'):
        m.inspect(client(url,len(raw)),tmp_path/'fail')


def test_corrupt_next_crc_rejected(tmp_path,serve):
    raw=bytearray(archive());raw[-1]^=1
    url,_=serve(bytes(raw))
    with pytest.raises(ValueError,match='NextHeader CRC'):
        m.inspect(client(url,len(raw)),tmp_path/'fail')


def test_overlarge_metadata_rejected(tmp_path,serve):
    raw=archive(payload=b'X'*800)
    url,_=serve(raw)
    c=m.RangeClient(url,len(raw),cap=32,allow_test_http=True)
    with pytest.raises(ValueError,match='NextHeader too large'):
        m.inspect(c,tmp_path/'fail')


def test_existing_destination_rejected(tmp_path,serve):
    raw=archive();url,_=serve(raw)
    (tmp_path/'out').mkdir()
    with pytest.raises(FileExistsError,match='exists'):
        m.inspect(client(url,len(raw)),tmp_path/'out')


def test_sparse_must_be_private_directory(tmp_path,serve):
    raw=archive();url,_=serve(raw)
    with pytest.raises(ValueError,match='inside index'):
        m.inspect(client(url,len(raw)),tmp_path/'out',sparse_path=tmp_path/'outside.7z')


def test_varint_decode_and_fail_closed():
    assert m.unpack_int(b'\x04',0)==(4,1)
    assert m.unpack_int(b'\x80\x02',0)==(2,2)
    with pytest.raises(ValueError,match='Truncated'):
        m.unpack_int(b'\x80',0)
    with pytest.raises(ValueError,match='Unknown'):
        m.encoded_header_streams(b'\x42',100)
    with pytest.raises(ValueError,match='compressed-index'):
        m.encoded_header_streams(b'\x17\x06\x00\x00\x09',100)


def test_redirect_host_allowlist():
    assert m.allowed_redirect('https://ndownloader.figshare.com/files/45258019')
    assert m.allowed_redirect('https://foo.s3.amazonaws.com/abc')
    assert not m.allowed_redirect('http://example.com/not-safe')
    assert not m.allowed_redirect('https://example.com/')
    assert not m.allowed_redirect('https://figshare.com.evil.example/file')


def test_replay_receipt_matches_written_parts(tmp_path,serve):
    raw=archive()
    url,_=serve(raw)
    m.inspect(client(url,len(raw)),tmp_path/'out')
    rec=json.loads((tmp_path/'out'/'receipt.json').read_text())
    assert len(rec['parts'])==2
    assert rec['official_file_id'] is None
    assert rec['full_archive_downloaded'] is False
    assert rec['no_automatic_large_transfer'] is True


def unseen_catalog():
    source = m.APPROVED_SOURCES["unseen-11-20"]
    return {"id": 25304616, "version": 2, "files": [{
        "id": source["id"],
        "name": source["name"],
        "size": source["size"],
        "download_url": source["url"],
        "supplied_md5": source["md5"],
        "computed_md5": source["md5"],
        "is_link_only": False,
    }]}


def test_unseen_official_catalog_exact_identity_and_fail_closed_variations():
    actual = m.validate_official_catalog(unseen_catalog(), "unseen-11-20")
    assert actual["id"] == 44725302
    assert actual["size"] == 40_043_548_469
    assert actual["md5"] == "fdc88663514f5691a14c08dff13c667e"
    assert actual["name"] == "Galar_Frames_11_to_20.7z"
    for field, altered in [
        ("size", actual["size"] - 1),
        ("name", "Galar_Frames_21_to_29_2.7z"),
        ("computed_md5", "0" * 32),
        ("supplied_md5", "0" * 32),
        ("download_url", "https://example.org/malicious.7z"),
        ("is_link_only", True),
    ]:
        catalog = unseen_catalog()
        catalog["files"][0][field] = altered
        with pytest.raises(ValueError, match="publisher archive"):
            m.validate_official_catalog(catalog, "unseen-11-20")
    bad_version = unseen_catalog()
    bad_version["version"] = 3
    with pytest.raises(ValueError, match="Galar v2 catalog"):
        m.validate_official_catalog(bad_version, "unseen-11-20")
    bad_article = unseen_catalog()
    bad_article["id"] = 0
    with pytest.raises(ValueError, match="Galar v2 catalog"):
        m.validate_official_catalog(bad_article, "unseen-11-20")
    missing = unseen_catalog()
    missing["files"] = []
    with pytest.raises(ValueError, match="missing or duplicated"):
        m.validate_official_catalog(missing, "unseen-11-20")
    duplicate = unseen_catalog()
    duplicate["files"].append(dict(duplicate["files"][0]))
    with pytest.raises(ValueError, match="missing or duplicated"):
        m.validate_official_catalog(duplicate, "unseen-11-20")


def test_unseen_index_only_profile_uses_206_and_never_reads_image_payload(tmp_path, serve):
    raw = archive(next_header=b"\x01\x00", payload=b"synthetic compressed body NEVER OPEN")
    url, handler = serve(raw)
    client = m.RangeClient(
        url, len(raw), cap=64 * 1024,
        source="unseen-11-20", allow_test_http=True,
    )
    report = m.inspect(client, tmp_path / "unseen")
    assert report["record_type"] == "galar-11-20-7z-index-only-v1"
    assert report["official_file_id"] is None  # Synthetic local mock, not publisher.
    assert report["full_archive_downloaded"] is False
    assert report["pixels_acquired"] == 0
    assert report["actual_index_only_bytes_transferred"] == 34
    assert handler.requests == ["bytes=0-31", f"bytes={len(raw)-2}-{len(raw)-1}"]
    assert (tmp_path / "unseen" / "signature-header.bin").stat().st_size == 32
    assert len((tmp_path / "unseen" / "next-header.bin").read_bytes()) == 2
    assert not any(part["name"].startswith("image") for part in report["parts"])


def test_unseen_source_url_and_size_pinned_without_network():
    expected = m.APPROVED_SOURCES["unseen-11-20"]
    m.RangeClient(expected["url"], expected["size"], source="unseen-11-20")
    with pytest.raises(ValueError, match="official"):
        m.RangeClient(expected["url"], expected["size"] + 1, source="unseen-11-20")
    with pytest.raises(ValueError, match="official"):
        m.RangeClient("https://example.org/other.7z", expected["size"], source="unseen-11-20")
    with pytest.raises(ValueError, match="Unknown official"):
        m.RangeClient(expected["url"], expected["size"], source="unknown")
