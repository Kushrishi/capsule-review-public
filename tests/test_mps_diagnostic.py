"""No medical inputs, network requests, hardware substitutions or model downloads."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from capsule_review import mps_diagnostic as diagnostic


def test_fallback_and_allocator_override_before_fresh_worker(monkeypatch):
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    monkeypatch.setenv('PYTORCH_MPS_FAST_MATH', '1')
    monkeypatch.setenv('PYTORCH_MPS_HIGH_WATERMARK_RATIO', '0')
    env = diagnostic.worker_environment()
    assert env['PYTORCH_ENABLE_MPS_FALLBACK'] == '0'
    assert env['PYTORCH_MPS_FAST_MATH'] == '0'
    assert 'PYTORCH_MPS_HIGH_WATERMARK_RATIO' not in env
    assert os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] == '1'


def test_device_guard_rejects_cpu_fallback_and_non_mac(monkeypatch):
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    with pytest.raises(RuntimeError, match='fallback'):
        diagnostic.require_device(None, 'cpu')
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK', '0')
    monkeypatch.setattr(diagnostic.platform, 'system', lambda: 'Linux')
    with pytest.raises(RuntimeError, match='Apple Silicon'):
        diagnostic.require_device(None, 'mps')


def test_parent_preserves_failure_and_runs_both_arms(tmp_path, monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        path = Path(command[command.index('--output') + 1])
        arm = command[command.index('--arm') + 1]
        diagnostic.atomic_json(path, {'status': 'failed' if arm == 'detector' else 'passed',
            'stage': 'training_update_1', 'error': 'invented unsupported operator'})
        return SimpleNamespace(returncode=int(arm == 'detector'))
    monkeypatch.setattr(diagnostic.subprocess, 'run', run)
    monkeypatch.setattr(diagnostic, 'hardware', lambda: {'machine': 'generated fixture'})
    out = tmp_path / 'result'
    assert diagnostic.main(['--output', str(out)]) == 1
    report = json.loads((out / 'report.json').read_text())
    assert report['arms']['classifier']['status'] == 'passed'
    assert report['arms']['detector']['status'] == 'failed'
    assert report['training_authorized'] is False
    assert len(calls) == 2
    for command, kwargs in calls:
        assert kwargs['stdin'] == diagnostic.subprocess.DEVNULL
        assert kwargs['env']['PYTORCH_ENABLE_MPS_FALLBACK'] == '0'
        assert kwargs['timeout'] == 900
        assert '--worker' in command and '--device' in command
    with pytest.raises(FileExistsError):
        diagnostic.main(['--output', str(out)])


def test_timeout_is_a_failure_not_compatibility(tmp_path, monkeypatch):
    def timeout(*a, **k):
        raise diagnostic.subprocess.TimeoutExpired(a[0], k['timeout'])
    monkeypatch.setattr(diagnostic.subprocess, 'run', timeout)
    monkeypatch.setattr(diagnostic, 'hardware', lambda: {})
    out = tmp_path / 'timeout'
    assert diagnostic.main(['--arm', 'classifier', '--output', str(out)]) == 1
    assert json.loads((out / 'report.json').read_text())['arms']['classifier']['exit_code'] == 'timeout'


@pytest.mark.parametrize('option,value', [('--updates', '0'), ('--updates', '5'),
    ('--warmup', '0'), ('--warmup', '3'), ('--timeout', '9'), ('--timeout', '1801')])
def test_work_is_bounded(tmp_path, option, value):
    with pytest.raises(SystemExit, match='Bounds'):
        diagnostic.main(['--output', str(tmp_path / 'never'), option, value])
    assert not (tmp_path / 'never').exists()


def test_generated_draws_targets_and_detection_operators(monkeypatch):
    torch = pytest.importorskip('torch')
    pytest.importorskip('torchvision')
    a, targets = diagnostic.generated_batch(torch)
    b, again = diagnostic.generated_batch(torch)
    assert torch.equal(a, b) and a.shape == (16, 3, 576, 576)
    assert torch.equal(targets[0]['labels'], torch.tensor([1]))
    assert targets[1]['boxes'].shape == (0, 4)
    assert targets[2]['labels'].tolist() == [1, 2, 2]
    assert all(r['status'] == 'passed' for r in diagnostic.operator_probes(torch, 'cpu').values())
    from torchvision import ops
    monkeypatch.setattr(ops, 'nms', lambda *a, **k: (_ for _ in ()).throw(NotImplementedError('invented nms MPS failure')))
    failures = diagnostic.operator_probes(torch, 'cpu')
    assert failures['nms']['status'] == 'failed'
    assert failures['nms']['error_type'] == 'NotImplementedError'
    assert failures['roi_align_backward']['status'] == 'passed'
