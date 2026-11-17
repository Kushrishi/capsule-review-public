"""Control-path tests and generated canaries; no claim of real CUDA execution."""
import copy
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from capsule_review import cuda_qualification as qualification
from capsule_review import mps_diagnostic as diagnostic


def test_cuda_guard_and_environment_are_fail_closed(monkeypatch):
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK', '0')
    monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG', 'host-value')
    with pytest.raises(RuntimeError, match='before CUDA'):
        diagnostic.require_device(None, 'cuda')
    env = diagnostic.worker_environment()
    assert env['CUBLAS_WORKSPACE_CONFIG'] == ':4096:8'
    monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    fake = SimpleNamespace(version=SimpleNamespace(cuda=None), cuda=SimpleNamespace(is_available=lambda: False))
    with pytest.raises(RuntimeError, match='genuine'):
        diagnostic.require_device(fake, 'cuda')


def valid_reports():
    # Invented metadata exercises the verifier; it is not GPU measurement evidence.
    record = {'status': 'passed', 'device': 'cuda', 'cuda': {'build': 'invented'},
        'matched_encoder_tensors': True, 'effective_batch': 16, 'physical_microbatch': 1,
        'trained_state_sha256': 'invented', 'losses': [.1, .05], 'frame_scores': [[.2, .3]],
        'model_source_sha256': 'invented'}
    return {arm: [copy.deepcopy(record), copy.deepcopy(record)] for arm in ('classifier', 'detector')}


@pytest.mark.parametrize('field,value', [('trained_state_sha256', 'changed'),
    ('losses', [.1, .06]), ('frame_scores', [[.2, .31]]), ('model_source_sha256', 'changed'),
    ('cuda', {'build': 'changed'}), ('device', 'cpu'), ('status', 'failed'),
    ('effective_batch', 1), ('physical_microbatch', 16), ('matched_encoder_tensors', False)])
def test_determinism_or_cuda_evidence_mismatch_is_rejected(field, value):
    reports = valid_reports()
    qualification.verify_replicas(reports)
    reports['detector'][1][field] = value
    with pytest.raises(ValueError):
        qualification.verify_replicas(reports)


def test_missing_arm_or_replica_cannot_qualify():
    reports = valid_reports()
    reports['detector'].pop()
    with pytest.raises(ValueError, match='Two'):
        qualification.verify_replicas(reports)
    del reports['detector']
    with pytest.raises(ValueError, match='Both'):
        qualification.verify_replicas(reports)


def test_isolation_failure_is_retained_without_worker_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, 'nvidia_devices', lambda: [])
    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, ['bwrap'], stderr='invented namespace denied')
    monkeypatch.setattr(qualification, 'isolation_canary', fail)
    root = tmp_path / 'output'
    assert qualification.main(['--output', str(root)]) == 1
    report = json.loads((root / 'qualification.json').read_text())
    assert report['cuda_qualified'] is False and report['training_authorized'] is False
    assert report['stage'] == 'isolation_canary'
    assert 'namespace denied' in report['stderr']
    assert not list(root.glob('classifier-*'))


def test_canary_pass_without_nvidia_still_cannot_qualify(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, 'nvidia_devices', lambda: [])
    monkeypatch.setattr(qualification, 'isolation_canary', lambda *a, **k: {'paths': 'blocked'})
    root = tmp_path / 'output'
    assert qualification.main(['--output', str(root)]) == 1
    report = json.loads((root / 'qualification.json').read_text())
    assert not report['cuda_qualified']
    assert report['stage'] == 'cuda_device_preflight'
    assert 'No accessible NVIDIA' in report['error']


def test_mock_dispatch_uses_existing_device_isolation_and_fixed_work(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, 'nvidia_devices', lambda: [Path('/dev/nvidia0')])
    monkeypatch.setattr(qualification, 'isolation_canary', lambda *a, **k: {'paths': 'blocked'})
    monkeypatch.setattr(qualification.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='invented NVIDIA inventory'))
    calls = []
    reports = valid_reports()
    def execute(command, reads, output, forbidden, **kwargs):
        calls.append((command, reads, output, forbidden, kwargs))
        path = Path(command[command.index('--output') + 1])
        arm = command[command.index('--arm') + 1]
        diagnostic.atomic_json(path, reports[arm][0])
        return SimpleNamespace(stdout='', stderr='')
    monkeypatch.setattr(qualification, 'execute_isolated', execute)
    root = tmp_path / 'output'
    assert qualification.main(['--output', str(root)]) == 0
    assert len(calls) == 4
    for command, reads, output, forbidden, options in calls:
        assert command[command.index('--device') + 1] == 'cuda'
        assert command[command.index('--updates') + 1] == '1'
        assert command[command.index('--warmup') + 1] == '1'
        assert '--worker' in command
        assert options['devices'] == [Path('/dev/nvidia0')]
        assert 0 < options['timeout'] <= 1800
        assert forbidden
    with pytest.raises(FileExistsError):
        qualification.main(['--output', str(root)])


@pytest.mark.parametrize('limit', ['29', '1801'])
def test_total_work_is_bounded(tmp_path, limit):
    with pytest.raises(SystemExit, match='30..1800'):
        qualification.main(['--output', str(tmp_path / 'never'), '--timeout', limit])
    assert not (tmp_path / 'never').exists()


def test_state_hash_uses_tensor_identity_not_dictionary_order():
    torch = pytest.importorskip('torch')
    a, b = torch.tensor([1., 2.]), torch.tensor([3])
    assert diagnostic.state_digest(torch, {'a': a, 'b': b}) == diagnostic.state_digest(torch, {'b': b.clone(), 'a': a.clone()})
    assert diagnostic.state_digest(torch, {'a': a}) != diagnostic.state_digest(torch, {'a': a + 1})


def test_actual_generated_isolation_canary_without_gpu(tmp_path):
    # Namespace capability is required in GitHub CI; optional on remote sandboxes.
    root = tmp_path / 'output'
    root.mkdir()
    forbidden = tmp_path / 'forbidden'
    forbidden.mkdir()
    try:
        report = qualification.isolation_canary(root, forbidden, devices=[])
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        message = getattr(exc, 'stderr', None) or str(exc)
        if 'bwrap' not in message and 'bubblewrap' not in message:
            raise
        if os.environ.get('CAPSULE_REQUIRE_ISOLATION') == '1':
            raise
        pytest.skip(message)
    assert report == {'paths': 'blocked', 'network': 'blocked', 'stdin': 'EOF', 'cublas': ':4096:8'}


def test_device_inventory_failure_is_recorded(tmp_path, monkeypatch):
    def denied():
        raise PermissionError('generated device inventory denial')
    monkeypatch.setattr(qualification, 'nvidia_devices', denied)
    root = tmp_path / 'output'
    assert qualification.main(['--output', str(root)]) == 1
    report = json.loads((root / 'qualification.json').read_text())
    assert report['stage'] == 'device_inventory'
    assert report['error_type'] == 'PermissionError'
    assert report['cuda_qualified'] is False
