# Generated-only Linux/CUDA qualification

No provider is CUDA-qualified by this change. The remotely accessible development
host has no NVIDIA devices, a CPU-only Torch build, and denies bubblewrap's network
namespace initialization. These are recorded failures, not CUDA measurements.
No owner-computer commands or paid resources are required for the included tests.

## What the code reuses

`cuda_qualification` uses the unchanged production `spatial_executor`, model builders,
optimizer groups, microbatch update and uncensored frame-score extraction. It adds
CUDA handling to the existing generated device diagnostic, not another model or
medical-data loader. The authenticated loader and `run_six` remain unchanged:
source hashes/membership, explicit normal policy, protected source boundaries,
exact runtime, encoder digest, CUDA availability, compute budgets and owner fitting
authorization still apply. Diagnostic success cannot set any fitting gate.

The qualification wrapper first checks generated forbidden-file descendants,
output overlap, direct/symlink reads, parent stdin and a live host-local HTTP
canary **with the same NVIDIA device bindings** used by the model workers. An
isolation failure stops execution; there is no unisolated fallback. Existing CI
requires the actual no-GPU canary and existing executor adversarial regressions.
That proves only CPU-host isolation/control paths, never CUDA device behavior.

Each authentic arm runs in two fresh isolated processes with diagnostic seed19,
576² float32 images, physical microbatch1, effective batch16. Each replica performs
one warm-up and one timed effective update:8 total generated optimizer updates
across4 workers. Targets include positive, empty, dual and repeated categories.
Encoder BatchNorm is frozen by the production update. All gradients/parameters
must be finite; both optimizer groups must change. Evaluation and fresh checkpoint
reload are checked, then canonical tensor hashes, losses and scores must agree
**exactly across replicas**. Numerical, deterministic, missing-GPU and timeout
failures remain failures. The scientific seeds19/37/73 and six-fit protocol do not
change; this does not run the scientific experiment.

CUDA workers require `CUBLAS_WORKSPACE_CONFIG=:4096:8` before initialization,
strict deterministic algorithms, cuDNN benchmarking off, and TF32 off. They record
GPU name, capability, visible count, total/free starting VRAM, driver inventory, Torch/CUDA/cuDNN/
Torchvision versions, model-source hash, losses, timings and allocator peak
allocated/reserved bytes. CUDA synchronization bounds timing. Reported memory
excludes allocations outside Torch's allocator; driver inventory and process RSS
provide context. MPS memory remains sampled and is not substituted for CUDA data.

## Remote operator procedure — only after compute approval

Use one dedicated Linux VM/GPU, public code and generated fixtures only. No private
research archive, cloud drive or external-test directory is mounted or downloaded.
Require NVIDIA character devices and functioning driver libraries, bubblewrap,
unprivileged namespaces and read-only source mounts. Test those before the model
work. A managed container that denies namespaces fails this qualification even if
its GPU works. Do not remove namespace flags or run a privileged fallback.

Candidate reproducible **diagnostic** runtime (not a replacement fitting commitment):
Ubuntu24.04 x86_64, native Python3.12, official Torch2.14.1/Torchvision0.29.1 CUDA12.6
wheels, one full A40/A6000. Host driver compatibility must be demonstrated by the
actual run. Resolve and retain the exact checkout, package freeze and driver output.
The following are remote-VM operator commands; the owner runs nothing locally:

```sh
sudo apt-get update
sudo apt-get install -y bubblewrap python3.12-venv git
python3.12 -m venv /opt/capsule-venv
. /opt/capsule-venv/bin/activate
python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
git clone --branch work/cloud-cuda-qualification https://github.com/Kushrishi/capsule-review-public.git /opt/capsule-review
cd /opt/capsule-review
python -m pip install -e '.[dev,spatial]'
python -m pip freeze > /tmp/capsule-cuda-environment.txt
CAPSULE_REQUIRE_ISOLATION=1 python -m pytest -q tests/test_spatial_executor_security.py tests/test_cuda_qualification.py
python -m capsule_review.cuda_qualification --output /tmp/capsule-cuda-qualification --timeout 1800
```

The wrapper can optionally receive the preserved public `--encoder` checkpoint;
production `load_pair` authenticates its complete SHA. The default random matched
encoder qualifies architecture/operators only, **not ImageNet initialization**.
Do not claim the latter without a run using that checkpoint. No weights are
downloaded automatically. Generated checkpoints are temporary; interrupted workers
may leave temporary generated artifacts. Export the JSON/logs/package freeze and
verify their hashes remotely before destroying the instance.

The wrapper has a total1800-second ceiling and no automatic retries or sweeps.
Provider billing includes installation/boot/cleanup outside that limit. Establish
a separate provider-control-plane termination watchdog before starting. Shell
shutdown alone is not a billing stop. A subsequent six-fit runtime commitment and
explicit owner authorization are required even after qualification passes. No
six-fit time or memory estimate is inferred from CPU results or short generated runs.

## Narrow provider decision (public pages checked November16,2026)

| Option | Verified public information | Outstanding prerequisite |
| --- | --- | --- |
| Runpod A40,48GB | A40 model page lists Community$0.35/h and Secure$0.59/h; storage is additional. | No specific slot or namespace capability verified. Lowest advertised rate here is not a qualified execution offer. |
| Runpod RTX A6000,48GB | Current pricing page lists$0.69/h. | Same namespace/device-mount gate; no live availability confirmation. |
| Vast A40/A6000 VM | Full Linux VM templates support nested containers; host-specific compute, storage and bandwidth prices. | An actual VM-capable48GB offer, access and all-in quote are required. No static minimum is asserted. |
| Lambda A6000,48GB | Published single-GPU price$1.09/h; GPU instances support SSH and optional persistent filesystems. | Slot/account access and actual bubblewrap/CUDA canaries remain unverified. Preferred predictable-price VM candidate. |

Provider security claims are not permission to move medical data. For this
qualification use per-run SSH credentials, owner-only access, no unauthenticated
Jupyter/public model endpoint, no provider API key inside workers, and generated
outputs only. Use instance scratch for this small run; persistent volumes are
unnecessary. Export evidence before termination. Retained volumes can keep billing.

No free GPU endpoint is connected to this session. Colab offers contingent free
GPUs but no guaranteed device/quota or verified matching namespace environment.
ZeroGPU offers free quota (currently48GB large slices), but its Gradio/shared
allocation model is not a verified replacement for this Linux executor, and no
eligible authenticated account is connected. The inspected Torchvision0.29.2 ROIAlign
path uses lazy `torch.compile` for deterministic CUDA, while ZeroGPU documents
no `torch.compile` support: an additional unexecuted compatibility concern, not
a reason to disable determinism. GitHub GPU larger runners are paid,
not free for public repositories, and require eligible organization plans. No
free-service deployment, new account, paid runner or credit purchase was initiated.

**Bounded proposal, not authorization:** one Lambda A6000 VM for at most60 billed
minutes, quoted GPU rate no higher than$1.25/h; current advertised compute component
is$1.09 for that ceiling. Request a US$3 total usage cap including incidental
charges/tax, no persistent filesystem, no automatic top-up/retry, and provider API
termination at the deadline (including setup time). Any deposit/card hold is
separate and must be disclosed before approval. If unavailable, obtain one Vast
VM quote within the same cap; do not silently substitute a managed container.
Runpod's lower catalog rate is worth considering only after namespace support is
confirmed; its advertised$10 starting funding exceeds the proposed usage budget.
Nothing has been purchased, and no cheapest **execution-qualified** option exists
yet. Account/control-plane access and paid-resource approval are the remaining
external dependencies; stop before provisioning.

Sources: [Runpod pricing](https://www.runpod.io/pricing),
[A40 tiers](https://www.runpod.io/gpu-models/a40),
[Runpod storage](https://docs.runpod.io/pods/storage/types),
[Runpod funding](https://www.runpod.io/blog/manage-runpod-account-funding),
[Vast VM capabilities](https://docs.vast.ai/guides/instances/virtual-machines),
[Vast billing](https://docs.vast.ai/guides/instances/pricing),
[Lambda pricing](https://lambda.com/pricing),
[Lambda instances](https://docs.lambda.com/public-cloud/on-demand/),
[Lambda billing](https://docs.lambda.com/public-cloud/billing/),
[Colab limits](https://research.google.com/colaboratory/faq.html),
[ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu),
[GitHub runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing),
[PyTorch wheel pairs](https://pytorch.org/get-started/previous-versions/).
