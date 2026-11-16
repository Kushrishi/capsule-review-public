"""Authenticated private-image callbacks for CR-SP-01 training and development."""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile
import zipfile


class ImageLoader:
    def __init__(self, manifest, expected_sha256, archives, *, role):
        raw = Path(manifest).read_bytes()
        if sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("Image manifest digest differs")
        document = json.loads(raw)
        if document["role"] != role or role not in ("train", "development"):
            raise ValueError("Manifest role differs")
        self.records = document["records"]
        self.role = role
        self.archives = {}
        for name, entry in document["archives"].items():
            path = Path(archives[name])
            hasher = sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(4 << 20), b""):
                    hasher.update(block)
            if hasher.hexdigest() != entry["sha256"]:
                raise ValueError("Source archive digest differs")
            if path.suffix == ".zip":
                handle = zipfile.ZipFile(path)
                names = handle.namelist()
            else:
                handle = tarfile.open(path)
                names = handle.getnames()
            if len(names) != len(set(names)):
                handle.close()
                raise ValueError("Ambiguous archive membership")
            self.archives[name] = handle
        if len({r["id"] for r in self.records}) != len(self.records):
            self.close()
            raise ValueError("Duplicate record identity")

    def close(self):
        self.image.cache_clear()
        for archive in self.archives.values():
            archive.close()

    @lru_cache(maxsize=16)
    def image(self, index):
        import numpy as np
        import torch
        from PIL import Image, ImageOps
        record = self.records[index]
        archive = self.archives[record["archive"]]
        if isinstance(archive, zipfile.ZipFile):
            raw = archive.read(record["member"])
        else:
            member = archive.getmember(record["member"])
            if not member.isfile():
                raise ValueError("Expected regular image member")
            raw = archive.extractfile(member).read()
        if sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Image identity differs")
        with Image.open(BytesIO(raw)) as original:
            if original.getexif().get(274, 1) != 1 and record["boxes"]:
                raise ValueError("Oriented annotation coordinates require qualification")
            image = ImageOps.exif_transpose(original).convert("RGB")
            array = np.asarray(image).copy()
        tensor = torch.from_numpy(array).permute(2, 0, 1).float() / 255
        return tensor

    def batch(self, plan):
        import torch
        from .spatial_comparison import transform_square
        images, targets = [], []
        for index, turns, flip, brightness, contrast in plan:
            record = self.records[index]
            image = self.image(index)
            height, width = image.shape[-2:]
            boxes = torch.tensor(record["boxes"], dtype=torch.float32).reshape(-1, 4)
            if any(type(label) is not int or label not in (1, 2) for label in record["labels"]):
                raise ValueError("Invalid foreground label")
            labels = torch.tensor(record["labels"], dtype=torch.int64)
            if len(boxes) != len(labels) or not ((labels >= 1) & (labels <= 2)).all():
                raise ValueError("Invalid target membership")
            if self.role == "train" and not len(labels) and record["source_status"] != "source_documented_normal":
                raise ValueError("Unknown images cannot supply negative targets")
            if not torch.isfinite(boxes).all() or not ((boxes >= -1e-6) & (boxes <= 1 + 1e-6)).all():
                raise ValueError("Invalid normalized coordinates")
            # Six-decimal source YOLO rounding can exceed an image edge by 5e-7.
            # Preserve raw manifest coordinates and clip only this subpixel excess.
            boxes = boxes.clamp(0, 1)
            if not (boxes[:, 2:] > boxes[:, :2]).all():
                raise ValueError("Degenerate source box")
            boxes = boxes * boxes.new_tensor([width, height, width, height])
            transformed, boxes = transform_square(image, boxes, turns, flip, brightness, contrast)
            images.append(transformed)
            targets.append({"boxes": boxes, "labels": labels})
        return torch.stack(images), targets

    def development(self, model, detector):
        if self.role != "development":
            raise ValueError("Development callback requires development manifest")
        from .spatial_comparison import frame_scores
        device = next(model.parameters()).device
        scores = []
        for index in range(len(self.records)):
            images, _ = self.batch([(index, 0, False, 1., 1.)])
            scores.extend(frame_scores(model, images.to(device), detector=detector).cpu().tolist())
        return {"scores": scores, "records": [
            {"label": r["source_label"], "video": r["video"]} for r in self.records]}


def run_authenticated(contract_path, commitment, encoder_path, output):
    """Use only the loaders bound by the private six-fit commitment."""
    from .spatial_training import digest, run_six
    if digest(contract_path) != commitment:
        raise ValueError("Protocol commitment differs")
    contract = json.loads(Path(contract_path).read_text())
    loaders = []
    try:
        for role in ("train", "development"):
            config = contract["loaders"][role]
            loaders.append(ImageLoader(config["manifest"], config["sha256"],
                                       config["archives"], role=role))
        training, development = loaders
        if contract["train_ids"] != [r["id"] for r in training.records]:
            raise ValueError("Training membership/order differs")
        if contract["development_ids"] != [r["id"] for r in development.records]:
            raise ValueError("Development membership/order differs")
        expected = [[], [], []]
        for index, record in enumerate(training.records):
            for label in set(record["labels"]):
                expected[label - 1].append(index)
            if record["source_status"] == "source_documented_normal":
                if record["labels"]:
                    raise ValueError("Normal record has foreground targets")
                expected[2].append(index)
        if contract["pools"] != expected:
            raise ValueError("Sampling pools differ from authenticated annotations")
        if {r["sha256"] for r in training.records} & {r["sha256"] for r in development.records}:
            raise ValueError("Train/development image bytes overlap")
        videos = {r["video"] for r in development.records}
        if videos != set(contract["development_videos"]) or videos & set(contract["excluded_videos"]):
            raise ValueError("Development source-video boundary differs")
        # run_six validates index sets, while source identities remain independently bound.
        indexed = dict(contract, train_ids=list(range(len(training.records))),
                       development_ids=["development:" + r["id"] for r in development.records])
        # Keep the original protocol bytes and identity in the generated executor contract.
        from .spatial_training import write_new
        derived = Path(output).with_suffix(".executor.json")
        indexed["parent_commitment"] = commitment
        write_new(derived, indexed)
        return run_six(derived, digest(derived), encoder_path, training.batch,
                       development.development, output)
    finally:
        for loader in loaders:
            loader.close()


def launch_authenticated(contract_path, commitment, encoder_path, output):
    """Public executor entry point. Mount only code, train/dev inputs and outputs."""
    import sys
    from .spatial_executor import execute_isolated
    from .spatial_training import digest
    contract_path = Path(contract_path).resolve()
    if digest(contract_path) != commitment:
        raise ValueError("Protocol commitment differs")
    contract = json.loads(contract_path.read_text())
    paths = [Path(__file__).resolve().parents[1], contract_path, Path(encoder_path).resolve()]
    paths.extend(Path(p).resolve() for p in contract["input_files"])
    for role in ("train", "development"):
        config = contract["loaders"][role]
        paths.append(Path(config["manifest"]).resolve())
        paths.extend(Path(p).resolve() for p in config["archives"].values())
    code = ("import sys; sys.path.insert(0,sys.argv[1]); "
            "from capsule_review.spatial_data import run_authenticated; "
            "run_authenticated(sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])")
    return execute_isolated([sys.executable, "-c", code, str(paths[0]),
        str(contract_path), commitment, str(Path(encoder_path).resolve()),
        str(Path(output).resolve() / "fits")], paths, output,
        contract["external_evaluation_paths"], timeout=48*3600+60,
        devices=[p for p in Path("/dev").glob("nvidia*") if p.is_char_device()] +
                [p for p in Path("/dev/nvidia-caps").glob("*") if p.is_char_device()])
