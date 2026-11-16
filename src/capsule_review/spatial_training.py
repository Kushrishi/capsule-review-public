"""Private-data CR-SP-01 orchestration. External test inputs have no entry point."""
import hashlib
import json
import math
from pathlib import Path
import time

SEEDS = (19, 37, 73)
EPOCHS = (4, 8, 12, 16, 20)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def seal(folder, paths):
    manifest = {str(p.relative_to(folder)): digest(p) for p in paths}
    write_new(folder / "SELECTION_SEAL.json", manifest)
    return digest(folder / "SELECTION_SEAL.json")


def verify_selection(folder, expected_digest):
    if digest(folder / "SELECTION_SEAL.json") != expected_digest:
        raise ValueError("Selection seal changed")
    for name, expected in json.loads((folder / "SELECTION_SEAL.json").read_text()).items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or digest(path) != expected:
            raise ValueError("Selected artifact changed")


def verify_six(folder, expected_digest):
    verify_selection(folder, expected_digest)
    selections = json.loads((folder / "six-selections.json").read_text())
    expected_names = {f"{seed}-{arm}" for seed in SEEDS for arm in ("classifier", "detector")}
    if set(selections) != expected_names:
        raise ValueError("Incomplete six-fit selection")
    for name, commitment in selections.items():
        verify_selection(folder / name, commitment)


def learning_rate_factor(update, updates):
    if updates <= 500:
        raise ValueError("Training horizon must exceed the frozen warm-up")
    if update < 500:
        return (update + 1) / 500
    return .5 * (1 + math.cos(math.pi * (update - 500) / (updates - 500)))


def development_metrics(scores, records):
    from .spatial_comparison import development_threshold
    if len(scores) != len(records):
        raise ValueError("Development record alignment differs")
    if any(len(s) != 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in s) for s in scores):
        raise ValueError("Invalid development scores")
    thresholds, recalls = [], []
    for target in (0, 1):
        normal = {}
        for score, record in zip(scores, records):
            if record["label"] == "Normal":
                normal.setdefault(record["video"], []).append(score[target])
        threshold = development_threshold(normal)
        labels = ("Angiectasia",) if target == 0 else ("Erosion", "Ulcer")
        videos = {}
        for score, record in zip(scores, records):
            if record["label"] in labels:
                videos.setdefault(record["video"], []).append(score[target] > threshold)
        if not videos:
            raise ValueError("Missing target support")
        thresholds.append(threshold)
        recalls.append(sum(sum(v) / len(v) for v in videos.values()) / len(videos))
    return {"thresholds": thresholds, "recalls": recalls}


def run_arm(model, *, detector, seed, pools, population_size, load_batch,
            evaluate_development, output, device="cuda", maximum_seconds=28800):
    """Run one arm with authenticated loader callbacks and no external evaluator.

    load_batch receives the shared (ID, augmentation) plan and returns CPU
    tensors and target dictionaries. evaluate_development returns exactly
    {scores, records}, in committed order. Neither callback may expose test data.
    A physical microbatch of one accumulates 16 images per optimizer update.
    """
    import torch
    from .spatial_comparison import make_optimizer, matched_draws, update
    if seed not in SEEDS or population_size <= 0 or len(pools) != 3 or any(not p for p in pools):
        raise ValueError("Invalid fixed seed or vascular/mucosal/normal pools")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    updates_per_epoch = math.ceil(population_size / 16)
    updates = 20 * updates_per_epoch
    plan = iter(matched_draws(pools, seed, updates * 16))
    measurements = []
    try:
        model.to(device)
        optimizer = make_optimizer(model, detector=detector)
        torch.use_deterministic_algorithms(True)
        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
            torch.manual_seed(seed)
            with (output / "trace.jsonl").open("x") as trace:
                for step in range(updates):
                    if time.monotonic() - started > maximum_seconds:
                        raise RuntimeError("Arm compute limit exceeded")
                    batch_plan = [next(plan) for _ in range(16)]
                    images, targets = load_batch(batch_plan)
                    factor = learning_rate_factor(step, updates)
                    for group, base in zip(optimizer.param_groups, (1e-4, 1e-3)):
                        group["lr"] = base * factor
                    loss = update(model, optimizer, images.to(device),
                                  [{k: v.to(device) for k, v in t.items()} for t in targets],
                                  detector=detector, microbatch_size=1)
                    trace.write(json.dumps({"step": step + 1, "loss": float(loss),
                        "batch_sha256": hashlib.sha256(json.dumps(batch_plan).encode()).hexdigest()}) + "\n")
                    trace.flush()
                    epoch = (step + 1) // updates_per_epoch
                    if (step + 1) % updates_per_epoch == 0 and epoch in EPOCHS:
                        # Validation must not consume the next training RNG state.
                        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
                            evidence = evaluate_development(model, detector)
                        result = development_metrics(evidence["scores"], evidence["records"])
                        if time.monotonic() - started > maximum_seconds:
                            raise RuntimeError("Arm compute limit exceeded during validation")
                        checkpoint = output / f"epoch-{epoch}.pt"
                        with checkpoint.open("xb") as handle:
                            torch.save(model.state_dict(), handle)
                        write_new(output / f"development-{epoch}.json", evidence)
                        measurements.append({"epoch": epoch, **result,
                                             "checkpoint": checkpoint.name,
                                             "checkpoint_sha256": digest(checkpoint)})
            selected = min(measurements, key=lambda r: (-sum(r["recalls"]), r["epoch"]))
            write_new(output / "selection.json", {"seed": seed, "detector": detector,
                "selected": selected, "measurements": measurements,
                "updates": updates, "exposures": updates * 16,
                "epoch_definition": "ceil(population_size/16) complete effective batches",
                "seconds": time.monotonic() - started})
            return seal(output, sorted(output.iterdir()))
    except BaseException as error:
        write_new(output / "FAILURE.json", {"reason": str(error)})
        raise


def run_six(contract_path, expected_digest, encoder_path, load_batch,
            evaluate_development, output):
    """Explicit fitting entry point. A signed-off contract is required."""
    import torch
    from .spatial_comparison import load_pair, IMAGENET_V2_SHA256
    if digest(contract_path) != expected_digest:
        raise ValueError("Protocol commitment mismatch")
    contract = json.loads(Path(contract_path).read_text())
    required = ("training_membership", "normal_policy", "external_exposure",
                "duplicate_policy", "gpu_budget", "owner_fit_authorization")
    if any(contract["gates"].get(key) is not True for key in required):
        raise ValueError("Fitting gates remain open")
    if contract["runtime"] != {"torch": torch.__version__,
                               "torchvision": __import__("torchvision").__version__}:
        raise ValueError("Runtime differs from committed protocol")
    if not torch.cuda.is_available():
        raise RuntimeError("Qualified CUDA device required")
    if contract["encoder_sha256"] != IMAGENET_V2_SHA256:
        raise ValueError("Encoder identity differs")
    for path, expected in contract["input_files"].items():
        if digest(path) != expected:
            raise ValueError("Committed input changed")
    train_ids = set(contract["train_ids"])
    dev_ids = set(contract["development_ids"])
    if train_ids & dev_ids:
        raise ValueError("Source populations overlap")
    if set().union(*map(set, contract["pools"])) != train_ids:
        raise ValueError("Exposure pools differ from training membership")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "protocol.json", contract)
    started = time.monotonic()
    seals = {}
    for seed in SEEDS:
        for detector in (False, True):
            remaining = 48 * 3600 - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError("Total compute limit exhausted")
            with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
                torch.manual_seed(seed)
                classifier, spatial = load_pair(Path(encoder_path))
            model = spatial if detector else classifier
            del classifier, spatial
            name = f"{seed}-{'detector' if detector else 'classifier'}"
            seals[name] = run_arm(model, detector=detector, seed=seed,
                pools=contract["pools"], population_size=len(train_ids),
                load_batch=load_batch, evaluate_development=evaluate_development,
                output=root / name, maximum_seconds=min(8*3600, remaining))
            del model
            torch.cuda.empty_cache()
    write_new(root / "six-selections.json", seals)
    return seal(root, [root / "protocol.json", root / "six-selections.json"])
