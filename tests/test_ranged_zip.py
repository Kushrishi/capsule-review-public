"""HTTP Range support and fail-closed data extraction with *only generated fixtures*."""
import contextlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import stat
import sys
import threading
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ranged_zip import AcquisitionError, HTTPRangeReader, extract, inspect, main


def zip_bytes(entries, compression=ZIP_STORED):
    data = io.BytesIO()
    with ZipFile(data, "w", compression=compression, allowZip64=True) as z:
        for name, content in entries:
            if isinstance(name, ZipInfo):
                z.writestr(name, content)
            else:
                z.writestr(name, content)
    return data.getvalue()


@contextlib.contextmanager
def server(payload: bytes, *, behavior="range"):
    class Handler(BaseHTTPRequestHandler):
        requests = []
        bytes_sent = 0

        def log_message(self, *_):
            pass

        def do_GET(self):
            self.__class__.requests.append(self.headers.get("Range"))
            if behavior == "no-range":
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                # Don't deliver body; the client must refuse status 200 on headers.
                return
            header = self.headers.get("Range", "")
            assert header.startswith("bytes=")
            start, end = (int(x) for x in header[6:].split("-"))
            assert 0 <= start <= end < len(payload)
            body = payload[start:end+1]
            self.send_response(206)
            cr_start = start + 1 if behavior == "bad-start" else start
            total = len(payload) + 1 if behavior == "bad-total" and start else len(payload)
            self.send_header("Content-Range", f"bytes {cr_start}-{end}/{total}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.__class__.bytes_sent += len(body)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    worker = threading.Thread(target=srv.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/archive.zip", Handler
    finally:
        srv.shutdown()
        srv.server_close()
        worker.join(timeout=3)


def test_lists_remote_index_without_full_download():
    payload = zip_bytes([(f"videos/video-{i:02}.avi", bytes([i]) * 150_000) for i in range(12)])
    with server(payload) as (url, handler):
        output = inspect(url, max_transfer_bytes=250_000, match="video-0",
                         allow_http_for_tests=True)
    assert output["matched_members"] == 10
    assert len(handler.requests) >= 2
    assert all(h and h.startswith("bytes=") for h in handler.requests)
    assert output["transferred_bytes"] < 250_000 < len(payload)
    assert output["archive_bytes"] == len(payload)
    assert output["source_identity"].startswith("size only")


def test_extracts_one_member_with_crc_and_sha256(tmp_path):
    content = b"video example " * 16000
    payload = zip_bytes([("subdir/clip_a.avi", content),
                         ("subdir/clip_b.avi", b"other" * 100_000),
                         ("subdir/clip_c.avi", b"next" * 200_000)])
    with server(payload) as (url, handler):
        output = extract(url, ["subdir/clip_a.avi"], tmp_path,
                         max_transfer_bytes=900_000, allow_http_for_tests=True)
    assert (tmp_path / "clip_a.avi").read_bytes() == content
    assert [x.name for x in tmp_path.iterdir()] == ["clip_a.avi"]
    assert output["extracted"][0]["bytes"] == len(content)
    assert len(output["extracted"][0]["sha256"]) == 64
    assert output["transferred_bytes"] < len(payload)
    assert all(x.startswith("bytes=") for x in handler.requests)


def test_rejects_http_200_without_reading_archive_body():
    with server(zip_bytes([("a", b"data")]), behavior="no-range") as (url, handler):
        with pytest.raises(AcquisitionError, match="not 206"):
            inspect(url, allow_http_for_tests=True)
    assert handler.bytes_sent == 0


def test_rejects_false_content_range():
    with server(zip_bytes([("a", b"data")]), behavior="bad-start") as (url, _):
        with pytest.raises(AcquisitionError, match="unexpected byte range"):
            inspect(url, allow_http_for_tests=True)


def test_rejects_changing_remote_archive_size():
    with server(zip_bytes([("a", b"data")]), behavior="bad-total") as (url, _):
        with pytest.raises(AcquisitionError, match="archive length changed"):
            inspect(url, allow_http_for_tests=True)


def test_transfer_budget_blocks_member_read(tmp_path):
    payload = zip_bytes([("target.avi", b"x" * 150_000)])
    with server(payload) as (url, _):
        with pytest.raises(AcquisitionError, match="exceed the byte budget"):
            extract(url, ["target.avi"], tmp_path, max_transfer_bytes=80_000,
                    allow_http_for_tests=True)
    assert not (tmp_path / "target.avi").exists()


@pytest.mark.parametrize("unsafe", ["../other.avi", "/absolute.avi", "a/../../evil.avi",
                                     "subdir\\windows.avi", "C:/drive.avi", "x//y.avi"])
def test_rejects_unsafe_zip_paths(unsafe, tmp_path):
    payload = zip_bytes([(unsafe, b"data")])
    with server(payload) as (url, _):
        with pytest.raises(AcquisitionError, match="Unsafe archive member"):
            extract(url, [unsafe], tmp_path, allow_http_for_tests=True)
    assert not list(tmp_path.rglob("*.avi"))


def test_rejects_zip_symlink(tmp_path):
    info = ZipInfo("pseudo.avi")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    payload = zip_bytes([(info, b"/tmp/other")])
    with server(payload) as (url, _):
        with pytest.raises(AcquisitionError, match="Unsafe archive member"):
            extract(url, ["pseudo.avi"], tmp_path, allow_http_for_tests=True)


def test_rejects_existing_destination(tmp_path):
    (tmp_path / "target.avi").write_bytes(b"untouched")
    with server(zip_bytes([("folder/target.avi", b"new")])) as (url, _):
        with pytest.raises(AcquisitionError, match="Destination exists"):
            extract(url, ["folder/target.avi"], tmp_path, allow_http_for_tests=True)
    assert (tmp_path / "target.avi").read_bytes() == b"untouched"


def test_rejects_duplicate_output_basenames(tmp_path):
    with server(zip_bytes([("a/clip.avi", b"a"), ("b/clip.avi", b"b")])) as (url, _):
        with pytest.raises(AcquisitionError, match="Duplicate output filename"):
            extract(url, ["a/clip.avi", "b/clip.avi"], tmp_path,
                    allow_http_for_tests=True)


def test_corrupted_zip_member_not_committed(tmp_path):
    sentinel = b"ORIGINAL_SENTINEL"
    payload = zip_bytes([("clip.avi", sentinel + b"_data")])
    assert sentinel in payload
    payload = payload.replace(sentinel, b"CORRUPT!_SENTINEL")  # same byte count
    with server(payload) as (url, _):
        with pytest.raises(BadZipFile, match="Bad CRC"):
            extract(url, ["clip.avi"], tmp_path, allow_http_for_tests=True)
    assert not (tmp_path / "clip.avi").exists()
    assert not list(tmp_path.glob(".partial-*"))


def test_refuses_decompression_bombs(tmp_path):
    payload = zip_bytes([("big.txt", b"a" * 1_000_000)], compression=ZIP_DEFLATED)
    with server(payload) as (url, _):
        with pytest.raises(AcquisitionError, match="decompression bomb"):
            extract(url, ["big.txt"], tmp_path, allow_http_for_tests=True)


def test_rejects_http_and_too_large_budget_from_cli(capsys):
    assert main(["http://example.org/data.zip", "list"]) == 2
    assert "HTTPS" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main(["https://example.org/data.zip", "--max-transfer-mib", "513", "list"])
    assert e.value.code == 2


def test_reader_does_not_allow_read_all_or_out_of_bounds_seek():
    with server(zip_bytes([("a", b"A" * 2_000_000)])) as (url, _):
        with HTTPRangeReader(url, max_transfer_bytes=2_000_000,
                             allow_http_for_tests=True) as f:
            with pytest.raises(AcquisitionError, match="Unbounded remote read refused"):
                f.read()
            with pytest.raises(AcquisitionError, match="Seek beyond"):
                f.seek(-1)


def test_failure_of_later_member_does_not_leave_earlier_file(tmp_path):
    payload = zip_bytes([("good.avi", b"good"), ("bad.avi", b"CORRUPT_ME")])
    payload = payload.replace(b"CORRUPT_ME", b"CORRUPT_NO")  # CRC must fail on second member
    with server(payload) as (url, _):
        with pytest.raises(BadZipFile, match="Bad CRC"):
            extract(url, ["good.avi", "bad.avi"], tmp_path,
                    allow_http_for_tests=True)
    assert not list(tmp_path.iterdir())


def test_duplicate_archive_paths_are_not_ambiguous(tmp_path):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        payload = zip_bytes([("dup.avi", b"one"), ("dup.avi", b"two")])
    with server(payload) as (url, _):
        with pytest.raises(AcquisitionError, match="duplicate member paths"):
            extract(url, ["dup.avi"], tmp_path, allow_http_for_tests=True)
