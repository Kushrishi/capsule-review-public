"""Generated-only MPS/CPU/CUDA device diagnostic; never a real-data training executor.

The parent imports no torch and launches a fresh, bounded worker per arm with
CPU fallback disabled before torch initialization. No source-image input exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import threading
import time
import traceback


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def hardware():
    result = {'os': platform.system(), 'release': platform.release(),
              'macos': platform.mac_ver()[0], 'machine': platform.machine(),
              'python': sys.version, 'executable': sys.executable}
    if platform.system() == 'Darwin':
        for name, key in [('hw.model', 'model'), ('machdep.cpu.brand_string', 'chip'),
                          ('hw.memsize', 'physical_memory_bytes')]:
            probe = subprocess.run(['sysctl', '-n', name], capture_output=True,
                                   text=True, timeout=5, stdin=subprocess.DEVNULL)
            result[key] = probe.stdout.strip() if probe.returncode == 0 else None
    return result


def worker_environment():
    env = dict(os.environ)
    # Override hostile/inherited values, before importing torch in a new process.
    env.update(PYTORCH_ENABLE_MPS_FALLBACK='0', PYTORCH_MPS_FAST_MATH='0',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    # Do not inherit a disabled allocator limit from another experiment.
    env.pop('PYTORCH_MPS_HIGH_WATERMARK_RATIO', None)
    env.pop('PYTORCH_MPS_LOW_WATERMARK_RATIO', None)
    return env


def require_device(torch, device):
    if os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') != '0':
        raise RuntimeError('CPU fallback must be disabled before importing torch')
    if device == 'cuda':
        if os.environ.get('CUBLAS_WORKSPACE_CONFIG') != ':4096:8':
            raise RuntimeError('CUBLAS_WORKSPACE_CONFIG must be :4096:8 before CUDA initialization')
        if platform.system() != 'Linux' or not torch.version.cuda or not torch.cuda.is_available():
            raise RuntimeError('A genuine available Linux NVIDIA CUDA device/build is required')
    if device == 'mps':
        if platform.system() != 'Darwin' or platform.machine() != 'arm64':
            raise RuntimeError('MPS qualification requires native Apple Silicon macOS Python')
        if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():
            raise RuntimeError('MPS backend is not built/available')


def generated_batch(torch):
    """16 fixed full-field draws, including explicit empty and repeated/dual boxes."""
    rng = torch.Generator().manual_seed(19)
    images = torch.rand((16, 3, 576, 576), generator=rng)
    cases = [([[40., 50., 180., 210.]], [1]), ([], []),
             ([[30., 40., 140., 150.], [180., 190., 330., 370.],
               [360., 380., 500., 530.]], [1, 2, 2])]
    targets = []
    for n in range(16):
        boxes, labels = cases[n % 3]
        targets.append({'boxes': torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4),
                        'labels': torch.tensor(labels, dtype=torch.int64)})
    return images, targets


def cpu_tree(torch, value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {k: cpu_tree(torch, v) for k, v in value.items()}
    if isinstance(value, list):
        return [cpu_tree(torch, v) for v in value]
    if isinstance(value, tuple):
        return tuple(cpu_tree(torch, v) for v in value)
    return value


def operator_probes(torch, device):
    """Report detection kernels separately; never retry a failed op on CPU."""
    from torchvision.ops import nms, roi_align
    results = {}
    for name in ('nms', 'roi_align_backward'):
        try:
            if name == 'nms':
                boxes = torch.tensor([[0., 0., 8., 8.], [1., 1., 7., 7.]], device=device)
                value = nms(boxes, torch.tensor([.8, .7], device=device), .5)
                if value.device.type != device or value.tolist() != [0]:
                    raise RuntimeError('Unexpected NMS result/device')
            else:
                x = torch.ones(1, 2, 16, 16, device=device, requires_grad=True)
                boxes = [torch.tensor([[1., 2., 12., 14.]], device=device)]
                value = roi_align(x, boxes, (3, 3), aligned=False)
                value.sum().backward()
                if value.device.type != device or not torch.isfinite(x.grad).all() or not x.grad.count_nonzero():
                    raise RuntimeError('Invalid ROI gradient/device')
            results[name] = {'status': 'passed', 'device': str(value.device)}
        except Exception as exc:
            results[name] = {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}
    return results


def state_digest(torch, state):
    """Canonical tensor bytes, excluding pickle/storage IDs and temp filenames."""
    digest = hashlib.sha256()
    for name, value in sorted(state.items()):
        value = value.detach().cpu().contiguous()
        digest.update(json.dumps([name, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


class MemorySampler:
    """Sampled allocator peaks, NOT an exact transient Metal allocation peak."""
    def __init__(self, torch, device, report):
        self.report_target = report
        self.torch, self.device = torch, device
        self.stop = threading.Event()
        self.peak = {'tensor_bytes': 0, 'driver_bytes': 0}
        self.errors = []
        self.thread = threading.Thread(target=self._run, daemon=True)

    def sample(self):
        if self.device == 'mps':
            try:
                self.peak['tensor_bytes'] = max(self.peak['tensor_bytes'], self.torch.mps.current_allocated_memory())
                self.peak['driver_bytes'] = max(self.peak['driver_bytes'], self.torch.mps.driver_allocated_memory())
            except Exception as exc:
                self.errors.append(str(exc))

    def _run(self):
        while not self.stop.wait(.02):
            self.sample()

    def __enter__(self):
        self.sample()
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.sample()
        self.report_target["memory"] = self.report()

    def report(self):
        cuda_peak = None
        if self.device == 'cuda':
            cuda_peak = {'allocated_bytes': self.torch.cuda.max_memory_allocated(),
                         'reserved_bytes': self.torch.cuda.max_memory_reserved()}
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {'cuda_allocator_peak': cuda_peak,
                'sampled_mps_peak': self.peak if self.device == 'mps' else None,
                'sample_period_seconds': .02, 'sampler_errors': self.errors,
                'process_peak_rss_bytes': int(rss if platform.system() == 'Darwin' else rss * 1024),
                'note': ('CUDA peaks cover Torch allocator only; exclude driver and non-Torch allocations.'
                         if self.device == 'cuda' else
                         'RSS and Metal allocations overlap in unified memory; do not add them. Transient peaks may be missed.')}


def run_worker(args, report):
    import torch
    import torchvision
    from torchvision.models import resnet50
    from .spatial_comparison import build_pair, load_pair, make_optimizer, update, frame_scores

    report.update(torch=torch.__version__, torchvision=torchvision.__version__,
                  mps_built=torch.backends.mps.is_built(), mps_available=torch.backends.mps.is_available(),
                  cpu_fallback=os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK'),
                  device=args.device, precision='float32', seed=19,
                  physical_microbatch=1, effective_batch=16,
                  resolution=576, deterministic_algorithms=True,
                  data='generated only; no image loader or external evaluation',
                  encoder='authenticated ImageNet V2' if args.encoder else 'generated random encoder; not pretrained-weight qualification')
    from . import spatial_comparison
    report['model_source_sha256'] = hashlib.sha256(Path(spatial_comparison.__file__).read_bytes()).hexdigest()
    report['target_cases'] = ['one target1 box', 'explicit empty generated target', 'target1 and repeated target2 boxes']
    report['stage'] = 'device_preflight'
    require_device(torch, args.device)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(19)
    if args.device == 'mps':
        torch.mps.manual_seed(19)
        report['recommended_max_memory_bytes'] = torch.mps.recommended_max_memory()
    if args.device == 'cuda':
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
        properties = torch.cuda.get_device_properties(0)
        report['cuda'] = {'build': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(),
            'name': properties.name, 'capability': list(torch.cuda.get_device_capability(0)),
            'total_memory_bytes': properties.total_memory, 'visible_devices': torch.cuda.device_count(),
            'device': str(torch.cuda.current_device()), 'cublas_workspace_config': os.environ['CUBLAS_WORKSPACE_CONFIG'],
            'cudnn_benchmark': False, 'cudnn_deterministic': True, 'tf32': False}
        torch.cuda.reset_peak_memory_stats()
    sync = {'mps': torch.mps.synchronize, 'cuda': torch.cuda.synchronize}.get(args.device, lambda: None)
    report['stage'] = 'operator_probes'
    report['operator_probes'] = operator_probes(torch, args.device) if args.arm == 'detector' else {}
    report['stage'] = 'build_authentic_pair'

    def build():
        if args.encoder:
            return load_pair(Path(args.encoder))
        return build_pair(resnet50(weights=None).state_dict())

    pair = build()
    report['matched_encoder_tensors'] = all(torch.equal(value, pair[0].state_dict()[name])
                                              for name, value in pair[1].backbone.body.state_dict().items())
    if not report['matched_encoder_tensors']:
        raise RuntimeError('Encoder tensors differ')
    detector = args.arm == 'detector'
    model = pair[int(detector)]
    del pair
    model.to(args.device)
    report['parameters'] = sum(p.numel() for p in model.parameters())
    optimizer = make_optimizer(model, detector=detector)
    encoder = model.backbone.body if detector else model
    bn = {name: value.detach().clone() for name, value in encoder.named_buffers()
          if 'running_' in name or 'num_batches_tracked' in name}
    # Inspect every gradient before the production optimizer step. Retain one
    # representative tensor in each LR group to prove real parameter changes.
    representatives = [group['params'][0] for group in optimizer.param_groups]
    before = [p.detach().clone() for p in representatives]
    gradients = []

    def check_gradients(opt, *_):
        groups = []
        for group in opt.param_groups:
            active = 0
            for parameter in group['params']:
                if parameter.grad is not None:
                    if not torch.isfinite(parameter.grad).all():
                        raise RuntimeError('Nonfinite gradient')
                    active += bool(parameter.grad.count_nonzero())
            if not active:
                raise RuntimeError('No active gradient in optimizer group')
            groups.append(active)
        gradients.append(groups)

    handle = optimizer.register_step_pre_hook(check_gradients)
    cpu_images, cpu_targets = generated_batch(torch)
    images = cpu_images.to(args.device)
    targets = [{k: v.to(args.device) for k, v in t.items()} for t in cpu_targets]
    # Observe actual calls, rather than claiming effective-batch semantics from flags.
    forward_sizes = []
    def observe_forward(current, inputs):
        forward_sizes.append(len(inputs[0]))
        if len(forward_sizes) == 1:
            report['batchnorm_training_modes_during_update'] = {
                name: layer.training for name, layer in current.named_modules()
                if isinstance(layer, torch.nn.BatchNorm2d)}
        if any(layer.training for layer in encoder.modules() if isinstance(layer, torch.nn.BatchNorm2d)):
            raise RuntimeError('Encoder BatchNorm trained during update')
    hook = model.register_forward_pre_hook(observe_forward)
    times, losses = [], []
    with MemorySampler(torch, args.device, report) as memory:
        cycles = 1 if not args.benchmark else args.warmup + args.updates
        for cycle in range(cycles):
            report['stage'] = f'training_update_{cycle + 1}'
            sync()
            started = time.perf_counter()
            loss = update(model, optimizer, images, targets, detector=detector, microbatch_size=1)
            sync()
            times.append(time.perf_counter() - started)
            losses.append(float(loss))
        hook.remove()
        handle.remove()
        if forward_sizes != [1] * (16 * cycles) or len(gradients) != cycles:
            raise RuntimeError('Effective-batch accumulation differs')
        changed = [not torch.equal(old, new) for old, new in zip(before, representatives)]
        if not all(changed):
            raise RuntimeError('Encoder or head optimizer group did not update')
        for parameter in model.parameters():
            if not torch.isfinite(parameter).all():
                raise RuntimeError('Nonfinite model parameter')
        after_bn = dict(encoder.named_buffers())
        bn_equal = all(torch.equal(v, after_bn[k]) for k, v in bn.items())
        if not bn_equal:
            raise RuntimeError('Frozen encoder BatchNorm statistics changed')
        report.update(losses=losses, update_seconds=times, active_gradient_tensors_by_group=gradients,
                      representative_parameters_changed_by_group=changed,
                      actual_forward_microbatches=len(forward_sizes), encoder_bn_buffers_unchanged=bn_equal)
        report['stage'] = 'eval_frame_scores'

        def scores(current):
            return torch.cat([frame_scores(current, images[i:i+1], detector=detector).cpu()
                              for i in range(3)])

        sync()
        started = time.perf_counter()
        expected = scores(model)
        sync()
        report['cold_validation_three_frames_seconds'] = time.perf_counter() - started
        sync()
        started = time.perf_counter()
        repeated = scores(model)
        sync()
        report['warmed_validation_three_frames_seconds'] = time.perf_counter() - started
        if not torch.isfinite(expected).all() or expected.shape != (3, 2) or not ((expected >= 0) & (expected <= 1)).all():
            raise RuntimeError('Invalid frame scores')
        report['repeat_eval_max_abs_difference'] = float((expected - repeated).abs().max())
        torch.testing.assert_close(expected, repeated, rtol=1e-4, atol=1e-5)
        if any(layer.training for layer in model.modules() if isinstance(layer, torch.nn.BatchNorm2d)):
            raise RuntimeError('BatchNorm not in evaluation mode')
        report['trained_state_sha256'] = state_digest(torch, model.state_dict())
        report['stage'] = 'checkpoint_save'
        with tempfile.TemporaryDirectory(prefix='capsule-generated-') as folder:
            path = Path(folder) / 'generated.pt'
            sync()
            started = time.perf_counter()
            torch.save({'state_dict': cpu_tree(torch, model.state_dict()),
                        'optimizer': cpu_tree(torch, optimizer.state_dict())}, path)
            report['checkpoint_save_seconds'] = time.perf_counter() - started
            report['checkpoint_bytes'] = path.stat().st_size
            report['checkpoint_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            # Release the trained model and optimizer before a fresh construction.
            del optimizer, encoder, representatives, model
            if args.device in ('mps', 'cuda'):
                getattr(torch, args.device).empty_cache()
            report['stage'] = 'checkpoint_reload'
            started = time.perf_counter()
            pair = build()
            model = pair[int(detector)]
            del pair
            saved = torch.load(path, map_location='cpu', weights_only=True)
            model.load_state_dict(saved['state_dict'], strict=True)
            del saved
            model.to(args.device)
            sync()
            report['checkpoint_reload_seconds'] = time.perf_counter() - started
            actual = scores(model)
            report['checkpoint_score_max_abs_difference'] = float((expected - actual).abs().max())
            torch.testing.assert_close(expected, actual, rtol=1e-4, atol=1e-5)
            report['score_tolerance'] = {'rtol': 1e-4, 'atol': 1e-5}
            report['frame_scores'] = expected.tolist()
    if any(r['status'] != 'passed' for r in report['operator_probes'].values()):
        raise RuntimeError('Detection operator probe failed; see operator_probes')
    report['memory'] = memory.report()
    if memory.errors:
        raise RuntimeError('Memory sampling failed')
    if args.benchmark:
        measured = times[args.warmup:]
        report['warmed_training'] = {'updates': len(measured), 'seconds': sum(measured),
            'images_per_second': 16 * len(measured) / sum(measured),
            'warmup_updates_excluded': args.warmup,
            'includes': 'production update plus per-gradient finite checks and device synchronization; not a six-fit projection'}
    report.update(status='passed', stage='complete', training_authorized=False,
                  six_fit_duration_estimate=None)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', choices=['mps', 'cpu', 'cuda'], default='mps')
    p.add_argument('--arm', choices=['both', 'classifier', 'detector'], default='both')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--encoder', type=Path, help='Optional official SHA-pinned ImageNet V2 checkpoint; no download')
    p.add_argument('--benchmark', action='store_true')
    p.add_argument('--warmup', type=int, default=1)
    p.add_argument('--updates', type=int, default=2)
    p.add_argument('--timeout', type=int, default=900, help='Hard wall-time limit per fresh worker (seconds)')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.updates <= 4 or not 1 <= args.warmup <= 2 or not 10 <= args.timeout <= 1800:
        raise SystemExit('Bounds: updates1..4, warmup1..2, timeout10..1800')
    if args.worker:
        if args.arm == 'both':
            raise SystemExit('Worker needs one arm')
        report = {'hardware': hardware(), 'arm': args.arm,
                  'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'training_authorized': False}
        try:
            run_worker(args, report)
        except Exception as exc:
            report.update(status='failed', error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        atomic_json(args.output, report)
        return 0 if report['status'] == 'passed' else 1
    args.output.mkdir(parents=True, exist_ok=False)
    reports = {}
    for arm in (['classifier', 'detector'] if args.arm == 'both' else [args.arm]):
        path = args.output / f'{arm}.json'
        command = [sys.executable, '-m', 'capsule_review.mps_diagnostic', '--worker',
                   '--arm', arm, '--device', args.device, '--output', str(path),
                   '--updates', str(args.updates), '--warmup', str(args.warmup)]
        if args.benchmark:
            command.append('--benchmark')
        if args.encoder:
            command += ['--encoder', str(args.encoder.resolve())]
        with (args.output / f'{arm}.log').open('x') as log:
            try:
                completed = subprocess.run(command, env=worker_environment(), stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout, check=False)
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                exit_code = 'timeout'
        if path.exists():
            result = json.loads(path.read_text())
        else:
            result = {'status': 'failed', 'error': 'Worker did not complete', 'exit_code': exit_code}
        if exit_code != 0:
            result['status'] = 'failed'
            result['exit_code'] = exit_code
        reports[arm] = result
        print(arm, result['status'], result.get('stage'), flush=True)
    passed = all(r['status'] == 'passed' for r in reports.values())
    atomic_json(args.output / 'report.json', {'hardware': hardware(), 'device': args.device,
        'status': 'passed' if passed else 'failed', 'arms': reports,
        'scope': 'generated compatibility only; not clinical performance or training authorization',
        'training_authorized': False})
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
