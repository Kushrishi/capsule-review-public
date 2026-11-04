"""Train one fixed, unpromoted Galar blood-CNN photometric-robustness candidate.

FITTING DATA ONLY: original Galar examinations 1–8. It uses the previously
verified sparse fitting manifest and source PNG archives supplied by the user,
without network acquisition. No private data/weights are shipped in Git.

Reproduction (in an access-controlled local directory):
  python scripts/train_blood_photo_candidate.py \
    --private-input-dir /private/galar-inputs \
    --private-output-dir /private/new-color-jitter-experiment

Input directory requires capsule-blood-real-pilot.zip and the verified
galar-pilot-images-001-002.zip, 003-004.zip, 005-006.zip, 007-008.zip.
The historical manifest includes development metadata for 9–10, but only
Galar 1–8 source pixels and fitting labels are loaded into the training bank.
The completed 11–20 and authors' reserved 61–80 images are NEVER read. No evaluation is performed
by this script. This is exploratory, not patient-disjoint clinical validation.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_MANIFEST_BYTES_SHA256 = "0f1cec23f43023788428c0fa694f6f00f42b367fd2ed2f539b97a57443080f59"
EXPECTED_MANIFEST_ID = "4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb"
FITTING_EXAMINATIONS = tuple(range(1, 9))
SEED = 17
AUGMENTATION_SEED = 25072026
EPOCHS = 8
BATCH = 32
LR = .001
WEIGHT_DECAY = .0001

def load_fitting_bank(private_root: Path):
    """Rehash every original fitting PNG before in-memory resizing.

    No source annotations other than the 4096 previously selected fitting
    blood labels; no use of outcome labels from previously evaluated cases.
    """
    import numpy as np
    from PIL import Image, ImageOps

    with zipfile.ZipFile(private_root / "capsule-blood-real-pilot.zip") as bundle:
        raw = bundle.read("private-dataset-manifest/blood-manifest.json")
    if hashlib.sha256(raw).hexdigest() != EXPECTED_MANIFEST_BYTES_SHA256:
        raise ValueError("The private fitting manifest differs from the verified original.")
    manifest = json.loads(raw)
    if manifest.get("sha256") != EXPECTED_MANIFEST_ID:
        raise ValueError("Original fitting selection identity changed.")
    records = [r for r in manifest["records"] if r["split"] == "train"]
    if (len(records) != 4096
            or set(r["exam"] for r in records) != set(FITTING_EXAMINATIONS)
            or any(r["split"] != "train" or r["blood"] not in (0, 1)
                   for r in records)):
        raise ValueError("Unexpected or protected fitting cohort.")
    bank = np.empty((4096, 96, 96, 3), dtype=np.uint8)
    targets = np.empty(4096, dtype=np.int64)
    archives = {}
    try:
        for i, record in enumerate(records):
            exam = record["exam"]
            part = (exam + 1) // 2
            if part not in archives:
                name = f"galar-pilot-images-{2*part-1:03d}-{2*part:03d}.zip"
                archives[part] = zipfile.ZipFile(private_root / name)
            path = "images/" + record["path"]
            expected = f"{exam:03d}/frame_{record['frame']:06d}.PNG"
            if record["path"] != expected:
                raise ValueError("Fitting manifest image path is not its expected source identity.")
            source_bytes = archives[part].read(path)
            if hashlib.sha256(source_bytes).hexdigest() != record["source_sha256"]:
                raise ValueError("Fitting source PNG failed SHA-256 verification.")
            with Image.open(BytesIO(source_bytes)) as image:
                resized = ImageOps.pad(
                    ImageOps.exif_transpose(image).convert("RGB"),
                    (96, 96), method=Image.Resampling.BILINEAR,
                    color=(0, 0, 0),
                )
                bank[i] = np.asarray(resized, dtype=np.uint8)
            targets[i] = record["blood"]
    finally:
        for archive in archives.values():
            archive.close()
    if int(targets.sum()) != 239:
        raise ValueError("Original positive fitting support changed.")
    return bank, targets


def fit(bank, targets):
    """Exactly eight epochs, no iterative checkpoint selection or evaluation."""
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
    from capsule_review.baseline import AnatomyCNN
    from capsule_review.photo_robustness import photometric_jitter

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    data = TensorDataset(
        torch.from_numpy(bank).permute(0, 3, 1, 2).contiguous(),
        torch.from_numpy(targets),
    )
    loader = DataLoader(
        data, batch_size=BATCH, shuffle=True, num_workers=0,
        generator=torch.Generator().manual_seed(SEED),
    )
    model = AnatomyCNN(2).cpu().train()
    positives = int(targets.sum())
    weights = torch.tensor([
        len(targets) / (2 * (len(targets) - positives)),
        len(targets) / (2 * positives),
    ], dtype=torch.float32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    augmentation_rng = torch.Generator().manual_seed(AUGMENTATION_SEED)
    history = []
    for epoch in range(1, EPOCHS + 1):
        total, seen = 0.0, 0
        for images, labels in loader:
            altered = photometric_jitter(images.float() / 255, augmentation_rng)
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(altered), labels, weight=weights)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite fitting loss.")
            loss.backward()
            optimizer.step()
            total += loss.item() * len(labels)
            seen += len(labels)
        history.append(total / seen)
        print(f"epoch={epoch} weighted_fitting_loss={history[-1]:.6f}", flush=True)
    return {k: v.detach().cpu() for k, v in model.state_dict().items()}, history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-input-dir", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.private_output_dir.exists():
        raise ValueError("Candidate output already exists; never overwrite research evidence.")
    if not args.private_input_dir.is_dir():
        raise ValueError("Verified private data directory is missing.")
    bank, targets = load_fitting_bank(args.private_input_dir)
    state, loss = fit(bank, targets)

    import torch
    args.private_output_dir.mkdir(parents=True, exist_ok=False)
    weights_file = args.private_output_dir / "candidate-weights.pt"
    torch.save(state, weights_file)
    checksum = hashlib.sha256(weights_file.read_bytes()).hexdigest()
    receipt = {
        "schema_version": 1,
        "research_only": True,
        "model_promoted": False,
        "clinical_validation": False,
        "trained_on_original_galar_examinations": list(FITTING_EXAMINATIONS),
        "other_examinations_loaded_for_fitting": False,
        "original_manifest_sha256": EXPECTED_MANIFEST_BYTES_SHA256,
        "verified_fitting_images": len(targets),
        "positive_fitting_images": int(targets.sum()),
        "architecture": "capsule-cnn-v1",
        "model_selection": "fixed epoch eight, no development-set tuning",
        "seed": SEED, "augmentation_seed": AUGMENTATION_SEED,
        "epochs": EPOCHS, "batch_size": BATCH,
        "learning_rate": LR, "weight_decay": WEIGHT_DECAY,
        "augmentation": {
            "brightness": [.75, 1.25], "contrast": [.8, 1.2],
            "saturation": [.7, 1.3],
            "applied_after_original_96x96_preprocessing": True,
        },
        "epoch_weighted_fit_loss": loss,
        "private_checkpoint_sha256": checksum,
    }
    (args.private_output_dir / "train_receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("Private candidate checkpoint SHA-256:", checksum)


if __name__ == "__main__":
    main()
