"""Adversarial canaries contain generated data only."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request

import pytest

from capsule_review import spatial_executor as executor


@pytest.mark.parametrize("kind", ["input", "output", "system"])
@pytest.mark.parametrize("direction", ["ancestor", "descendant", "equal"])
@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("forbidden_alias", [False, True])
def test_every_mount_overlap_is_rejected(tmp_path, monkeypatch, kind, direction, alias, forbidden_alias):
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()
    if direction == "ancestor":
        mount = tmp_path
    elif direction == "descendant":
        mount = forbidden / "generated.txt"
        mount.write_text("generated label canary")
    else:
        mount = forbidden
    if alias:
        link = tmp_path / "alias"
        link.symlink_to(mount)
        mount = link
    reads, output = [], tmp_path / "output"
    if kind == "input":
        reads = [mount]
    elif kind == "output":
        output = mount
    else:
        monkeypatch.setattr(executor.site, "getusersitepackages", lambda: str(mount))
    if forbidden_alias:
        link = tmp_path / "forbidden-alias"
        link.symlink_to(forbidden)
        forbidden = link
    with pytest.raises(ValueError, match="overlaps"):
        executor.isolation_command(["true"], reads, output, [forbidden])


def test_rejected_output_is_never_created(tmp_path):
    forbidden = tmp_path / "forbidden"
    output = forbidden / "output"
    with pytest.raises(ValueError, match="overlaps"):
        executor.execute_isolated(["true"], [], output, [forbidden])
    assert not output.exists()


def test_spawn_contract_and_environment_replacement(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", "HOST_VALUE_MUST_NOT_PROPAGATE")
    monkeypatch.setattr(executor.shutil, "which", lambda name: "/usr/bin/bwrap")
    def run(args, **kwargs):
        captured.update(args=args, **kwargs)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(executor.subprocess, "run", run)
    executor.execute_isolated(["true"], [], tmp_path/"output", [tmp_path/"labels"])
    assert "--unshare-net" in captured["args"]
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["close_fds"] is True
    assert captured["check"] is True
    assert captured["env"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"


def test_namespace_failure_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(executor.shutil, "which", lambda name: "/usr/bin/bwrap")
    calls = []
    def fail(args, **kwargs):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args, stderr="bwrap: namespace unavailable")
    monkeypatch.setattr(executor.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        executor.execute_isolated(["true"], [], tmp_path/"output", [tmp_path/"labels"])
    assert len(calls) == 1
    assert "--unshare-net" in calls[0]


def isolated_or_skip(command, reads, output, forbidden, *, timeout=60):
    try:
        return executor.execute_isolated(command, reads, output, forbidden, timeout=timeout)
    except RuntimeError as error:
        if "bubblewrap is required" not in str(error):
            raise
        if os.environ.get("CAPSULE_REQUIRE_ISOLATION") == "1":
            raise
        pytest.skip(str(error))
    except subprocess.CalledProcessError as error:
        if "bwrap:" not in error.stderr:
            raise
        if os.environ.get("CAPSULE_REQUIRE_ISOLATION") == "1":
            raise
        pytest.skip(error.stderr)


def test_network_stdin_paths_and_cuda_configuration_in_worker(tmp_path, monkeypatch):
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()
    secret = forbidden / "generated-labels.txt"
    secret.write_text("GENERATED SECRET")
    source = tmp_path / "source"
    source.mkdir()
    (source / "escape").symlink_to(secret)
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"GENERATED HTTP CANARY")
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    original_stdin = os.dup(0)
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", "INCORRECT_HOST_VALUE")
    code = """import json,os,pathlib,sys,urllib.request
assert os.environ['CUBLAS_WORKSPACE_CONFIG'] == ':4096:8'
assert sys.stdin.buffer.read() == b''
for name in sys.argv[2:]:
    try:
        pathlib.Path(name).read_bytes()
    except (PermissionError,FileNotFoundError):
        continue
    raise RuntimeError('External file was readable')
try:
    urllib.request.urlopen(sys.argv[1],timeout=2).read()
except OSError:
    pass
else:
    raise RuntimeError('Host HTTP endpoint was reachable')
print(json.dumps({'network':'blocked','stdin':'EOF','paths':'blocked','cublas':os.environ['CUBLAS_WORKSPACE_CONFIG']}))
"""
    try:
        assert urllib.request.urlopen(url, timeout=2).read() == b"GENERATED HTTP CANARY"
        with secret.open("rb") as stream:
            os.dup2(stream.fileno(), 0)
            result = isolated_or_skip([sys.executable, "-c", code, url,
                str(secret), str(source/"escape")], [source], tmp_path/"output", [forbidden])
        assert json.loads(result.stdout) == {
            "network":"blocked","stdin":"EOF","paths":"blocked","cublas":":4096:8"}
    finally:
        os.dup2(original_stdin, 0)
        os.close(original_stdin)
        server.shutdown()
        server.server_close()
        worker.join()


def test_forbidden_directory_descendant_never_launches(tmp_path, monkeypatch):
    forbidden = tmp_path/"external"
    forbidden.mkdir()
    secret = forbidden/"generated.txt"
    secret.write_text("GENERATED")
    def unexpected(*args, **kwargs):
        raise AssertionError("Worker launched with an external file mount")
    monkeypatch.setattr(executor.subprocess,"run",unexpected)
    with pytest.raises(ValueError,match="overlaps"):
        executor.execute_isolated(["true"],[secret],tmp_path/"output",[forbidden])


def test_generated_smoke_runs_inside_closed_executor(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    repo = Path(__file__).resolve().parents[1]
    code = ("import sys;sys.path.insert(0,sys.argv[1]);import pytest;"
            "raise SystemExit(pytest.main([sys.argv[2],'-q','-k','cpu_generated',"
            "'-p','no:cacheprovider']))")
    result = isolated_or_skip([sys.executable,"-c",code,str(repo/"src"),
        str(repo/"tests/test_spatial_data.py")], [repo],tmp_path/"output",
        [tmp_path/"external-labels"], timeout=240)
    assert "1 passed" in result.stdout
