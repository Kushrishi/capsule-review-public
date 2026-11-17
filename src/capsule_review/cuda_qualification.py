"""Generated-only, fail-closed Linux/CUDA qualification; never provisions compute.

Reuse the production isolation boundary and device diagnostic. Two fixed fresh
replicas per arm test actual training-state repeatability. No medical-data input,
external evaluator, fitting commitment override or unisolated fallback exists.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from .mps_diagnostic import atomic_json, hardware
from .spatial_executor import execute_isolated, isolation_command


def nvidia_devices():
    return sorted([p for p in Path('/dev').glob('nvidia*') if p.is_char_device()] +
                  [p for p in Path('/dev/nvidia-caps').glob('*') if p.is_char_device()])


def isolation_canary(root, forbidden, *, devices, timeout=30):
    """The actual device mounts must not reopen paths, stdin or host networking."""
    source = root / 'generated-input'
    source.mkdir()
    secret = forbidden / 'generated-only.txt'
    secret.write_text('GENERATED LABEL CANARY')
    (source / 'alias').symlink_to(secret)
    for reads, output in [([secret], root / 'rejected'), ([], forbidden / 'rejected')]:
        try:
            isolation_command(['true'], reads, output, [forbidden], devices=devices)
        except ValueError:
            pass
        else:
            raise RuntimeError('Forbidden descendant mount accepted')

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'GENERATED HTTP CANARY')
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    code = """import json,os,pathlib,sys,urllib.request
if os.environ['CUBLAS_WORKSPACE_CONFIG'] != ':4096:8': raise RuntimeError('CUBLAS environment differs')
if sys.stdin.buffer.read() != b'': raise RuntimeError('Parent stdin exposed')
for name in sys.argv[2:]:
    try: pathlib.Path(name).read_bytes()
    except (PermissionError,FileNotFoundError): continue
    raise RuntimeError('Forbidden generated file readable')
try: urllib.request.urlopen(sys.argv[1],timeout=2).read()
except OSError: pass
else: raise RuntimeError('Host network accessible')
print(json.dumps({'paths':'blocked','network':'blocked','stdin':'EOF','cublas':os.environ['CUBLAS_WORKSPACE_CONFIG']}))
"""
    stdin = os.dup(0)
    try:
        url = f'http://127.0.0.1:{server.server_port}/'
        # Establish that the positive canary is listening before its negative test.
        import urllib.request
        if urllib.request.urlopen(url, timeout=2).read() != b'GENERATED HTTP CANARY':
            raise RuntimeError('Host positive network canary failed')
        with secret.open('rb') as stream:
            os.dup2(stream.fileno(), 0)
            result = execute_isolated([sys.executable, '-c', code, url, str(secret), str(source / 'alias')],
                [source], root / 'canary-output', [forbidden], timeout=timeout, devices=devices)
        value = json.loads(result.stdout)
        expected = {'paths': 'blocked', 'network': 'blocked', 'stdin': 'EOF', 'cublas': ':4096:8'}
        if value != expected:
            raise RuntimeError('Isolation canary evidence differs')
        return value
    finally:
        os.dup2(stdin, 0)
        os.close(stdin)
        server.shutdown()
        server.server_close()
        thread.join()


def verify_replicas(reports):
    if set(reports) != {'classifier', 'detector'}:
        raise ValueError('Both authentic arms required')
    for arm, replicas in reports.items():
        if len(replicas) != 2:
            raise ValueError('Two independent fresh replicas required')
        for report in replicas:
            if (report.get('status') != 'passed' or report.get('device') != 'cuda'
                    or not report.get('cuda', {}).get('build')
                    or not report.get('matched_encoder_tensors')
                    or report.get('effective_batch') != 16 or report.get('physical_microbatch') != 1):
                raise ValueError('Actual CUDA execution evidence incomplete')
        for field in ('trained_state_sha256', 'losses', 'frame_scores', 'model_source_sha256', 'cuda'):
            if field not in replicas[0] or field not in replicas[1] or replicas[0][field] != replicas[1][field]:
                raise ValueError(f'{arm}: deterministic replica mismatch for {field}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--encoder', type=Path, help='Optional preserved public SHA-pinned ImageNet encoder')
    parser.add_argument('--timeout', type=int, default=1800, help='Total qualification seconds, maximum1800')
    args = parser.parse_args(argv)
    if not 30 <= args.timeout <= 1800:
        raise SystemExit('Total qualification time must be30..1800 seconds')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    devices = nvidia_devices()
    summary = {'hardware': hardware(), 'status': 'failed', 'cuda_qualified': False,
               'training_authorized': False, 'device_nodes': [str(p) for p in devices],
               'scope': 'generated only; no provisioning, medical data or external test',
               'maximum_seconds': args.timeout, 'stage': 'isolation_canary'}
    # A separate, generated forbidden tree must never overlap writable output.
    try:
        with tempfile.TemporaryDirectory(prefix='capsule-forbidden-') as tmp:
            forbidden = Path(tmp)
            summary['isolation'] = isolation_canary(root, forbidden, devices=devices,
                timeout=min(30, args.timeout))
            summary['stage'] = 'cuda_device_preflight'
            if not devices:
                raise RuntimeError('No accessible NVIDIA character devices; no CUDA qualification performed')
            smi = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv'],
                                 capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                 timeout=10, check=True)
            summary['nvidia_smi'] = smi.stdout
            source = Path(__file__).resolve().parents[1]
            read_paths = [source]
            if args.encoder:
                read_paths.append(args.encoder.resolve())
            reports = {'classifier': [], 'detector': []}
            for arm in reports:
                for replica in (1, 2):
                    summary['stage'] = f'{arm}_replica_{replica}'
                    remaining = args.timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise RuntimeError('Total qualification compute limit exceeded')
                    path = root / f'{arm}-{replica}.json'
                    worker_args = ['--worker', '--arm', arm, '--device', 'cuda', '--output', str(path),
                                   '--benchmark', '--warmup', '1', '--updates', '1']
                    if args.encoder:
                        worker_args += ['--encoder', str(args.encoder.resolve())]
                    code = ('import os,sys; sys.path.insert(0,sys.argv[1]); '
                            'os.environ["PYTORCH_ENABLE_MPS_FALLBACK"]="0"; '
                            'from capsule_review.mps_diagnostic import main; '
                            'raise SystemExit(main(sys.argv[2:]))')
                    try:
                        result = execute_isolated([sys.executable, '-c', code, str(source), *worker_args],
                            read_paths, root, [forbidden], timeout=remaining, devices=devices)
                    except subprocess.CalledProcessError as error:
                        (root / f'{arm}-{replica}.log').write_text((error.stdout or '') + (error.stderr or ''))
                        raise
                    (root / f'{arm}-{replica}.log').write_text(result.stdout + result.stderr)
                    reports[arm].append(json.loads(path.read_text()))
            summary['stage'] = 'deterministic_replay_verification'
            verify_replicas(reports)
            if time.monotonic() - started > args.timeout:
                raise RuntimeError('Total qualification compute limit exceeded')
            summary.update(status='passed', stage='complete', cuda_qualified=True,
                encoder_initialization='authenticated ImageNet' if args.encoder else 'random matched; ImageNet unqualified',
                artifact_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in root.glob('*.json')}, replicas=reports)
    except Exception as error:
        summary.update(error_type=type(error).__name__, error=str(error))
        if isinstance(error, subprocess.CalledProcessError):
            summary['stderr'] = error.stderr
    summary['seconds'] = time.monotonic() - started
    atomic_json(root / 'qualification.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'stage', 'cuda_qualified', 'training_authorized')}))
    return 0 if summary['cuda_qualified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
