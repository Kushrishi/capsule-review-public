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