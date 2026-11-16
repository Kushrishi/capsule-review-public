# CR-SP-01 generated Apple Silicon diagnostic

This checks the existing ResNet-50 two-output classifier and Faster R-CNN
ResNet-50-FPN-v2 three-class detector. It is not a medical-data executor or fitting
authorization. The Linux/CUDA executor, fixed study seeds (19,37,73), data and
selection protocol are unchanged. Diagnostic seed19 is generated-only.

## Run later on the Mac

Use native arm64 Python3.12, outside Rosetta, and a new virtual environment.
The following PyTorch/Torchvision pair has an official macOS installation command;
its MPS behavior on this M3 Max is still untested. Do not mix incompatible wheels.

```sh
git clone https://github.com/Kushrishi/capsule-review-public.git
cd capsule-review-public
# Check out the reviewed diagnostic PR branch until it is merged:
git switch work/mps-generated-diagnostic
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.14.1 torchvision==0.29.1
python -m pip install -e '.[spatial]'
python -m pip freeze > /tmp/capsule-mps-environment.txt
python -m capsule_review.mps_diagnostic --output /tmp/capsule-mps-check
```

Choose a new output directory for each invocation. A nonzero exit means failed or
incomplete, even if the other arm passed. Inspect `report.json`, both arm JSONs and
logs. Report hardware includes actual chip/model, unified physical memory, OS,
Python, Torch and Torchvision. No result is attributed to a different Mac.

The default is a **single effective update per arm**,16 generated full-field576²
images, physical microbatch1, float32, strict deterministic algorithms. Targets
include positive, explicit empty, dual-class and repeated same-class boxes. It
uses production `build_pair`, `make_optimizer`, `update` and uncensored
`frame_scores`. Encoder BatchNorm remains frozen; detector-specific BatchNorm
retains production behavior. Both optimizer groups must have finite active
gradients and changed representative weights. It checks all parameter finiteness,
repeated evaluation and a fresh checkpoint reload (rtol1e-4, atol1e-5). This is a
compatibility smoke, not a learnability or accuracy experiment.

No weights are downloaded. Default encoder tensors are generated with matched
random initialization; this does not authenticate ImageNet initialization. To
check that too, append `--encoder /absolute/path/resnet50-11ad3fa6.pth` using the
already preserved official checkpoint. Production `load_pair` rejects every SHA
except `11ad3fa62ca79e40addfd354a8ec4b7c75143b3038b8d2a807fbc68deab379ca`.
No COCO weights, architecture substitutes, altered proposal caps or fallback arm
are used. Temporary generated checkpoints/optimizer states are deleted; only JSON
and logs remain. This utility has no image/label/dataset input argument.

## Bounded warmed benchmark

After compatibility passes, on AC power, close unrelated memory-heavy programs:

```sh
python -m capsule_review.mps_diagnostic --benchmark --warmup 1 --updates 2 --timeout 900 --output /tmp/capsule-mps-benchmark
```

This performs3 effective updates per arm:1 warm-up excluded from measured training
throughput, then2 measured updates (32 images). Each arm has a hard900-second
process limit; timeout is retained as a failure. Bounds prevent more than2 warm-up
and4 measured updates or a timeout over1800 seconds. No automatic retries.
Per-update device synchronization prevents asynchronous timing errors. Timings
include diagnostic finite-gradient checks, which can add synchronization overhead;
they are not an overhead-free production throughput estimate. Cold and warmed
three-frame score extraction, checkpoint+optimizer save/reload overhead, checkpoint
size and numerical differences are reported separately. Synthetic tensors are
prebuilt: image decoding, full validation populations and source I/O are excluded.
No six-fit duration is calculated from this short run.

Metal tensor/driver memory is sampled every20ms, with process peak RSS from the
OS. These are **sampled allocator peaks**, not guaranteed transient peaks. Unified
memory counters overlap: do not add RSS and driver bytes. The recommended Metal
working set is also recorded. An allocation failure remains a failure; never
disable allocator limits to turn it into a pass.

The launcher forces `PYTORCH_ENABLE_MPS_FALLBACK=0` and fast math off before Torch
imports, overriding inherited fallback settings. Independent NMS and ROIAlign
backward probes retain unsupported-operation messages; the authentic detector is
also attempted without replacement kernels. Strict deterministic failures remain
failures. This prevents PyTorch's optional unsupported-op CPU fallback, but is not
a claim that every framework bookkeeping operation or vendor kernel runs on GPU.
The optional ImageNet loader uses CPU only for loading/authentication.

## Remote verification and execution boundary

`--device cpu` exercises the same harness on Linux; it is explicitly labeled CPU
and cannot establish MPS compatibility. The focused regressions cover hostile
fallback settings, platform rejection, failure/timeout retention, work bounds,
generated targets and unsupported detection kernels. Existing CI also runs the
full CPU architecture smoke and retains the generated report. No Mac runner was
available in this work session; M3 Max memory, throughput and operator support
remain unmeasured.

A future macOS executor needs an independently qualified filesystem/network
isolation mechanism with Metal access, read-only authenticated training/dev mounts,
private writable outputs, inaccessible external-test labels (including aliases,
parent mounts, stdin, IPC and network channels), deterministic RNG handling and
resource/watchdog enforcement. Python path checks, a subprocess or macOS privacy
prompts do not replace Linux bubblewrap isolation. This diagnostic grants none of
those capabilities. Real fitting still requires the existing scientific gates,
authorized compute/protocol commitments and explicit owner approval.

References: [PyTorch macOS wheel pairs](https://pytorch.org/get-started/previous-versions/),
[MPS environment controls](https://docs.pytorch.org/docs/2.15/mps_environment_variables.html),
[MPS timing and memory APIs](https://docs.pytorch.org/docs/2.15/mps.html).
