import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from PIL import Image

from capsule_review.spatial_data import ImageLoader
from capsule_review.spatial_executor import execute_isolated, isolation_command


def generated_manifest(tmp_path, role="train"):
    output = io.BytesIO()
    Image.new("RGB", (100, 80), "green").save(output, "PNG")
    raw = output.getvalue()
    archive = tmp_path / "generated.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("generated.png", raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"role":role, "archives":{"generated":{
        "sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}}, "records":[{
        "id":"generated", "archive":"generated", "member":"generated.png",
        "sha256":hashlib.sha256(raw).hexdigest(), "boxes":[[.1,.2,.4,.6]],
        "labels":[1], "source_status":"target", "source_label":"Angiectasia", "video":"generated"}]}))
    return manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(), {"generated":archive}


def test_authenticated_loader_transforms_and_rejects_changed_pixels(tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    path, commitment, archives = generated_manifest(tmp_path)
    loader = ImageLoader(path, commitment, archives, role="train")
    try:
        images, targets = loader.batch([(0,0,False,1.,1.)])
        assert tuple(images.shape) == (1,3,576,576)
        assert targets[0]["boxes"].tolist()[0] == pytest.approx([57.6,149.2,230.4,333.6],abs=.5)
        with pytest.raises(ValueError,match="manifest"):
            ImageLoader(path, "0"*64, archives, role="train")
        loader.records[0]["sha256"] = "0"*64
        loader.image.cache_clear()
        with pytest.raises(ValueError,match="identity"):
            loader.image(0)
    finally:
        loader.close()


def test_executor_rejects_mount_containing_labels(tmp_path):
    labels = tmp_path / "labels"
    with pytest.raises(ValueError,match="exposes"):
        isolation_command(["true"], [tmp_path], tmp_path/"output", [labels])


def test_real_namespace_cannot_open_external_labels_or_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    secret = tmp_path / "external-labels.txt"
    secret.write_text("SYNTHETIC CANARY ONLY")
    (source/"escape").symlink_to(secret)
    output = tmp_path / "output"
    code = """import pathlib,sys
for name in sys.argv[1:]:
    try:
        pathlib.Path(name).read_bytes()
    except (PermissionError,FileNotFoundError):
        continue
    raise RuntimeError('External canary was readable')
print('ISOLATED')
"""
    try:
        result = execute_isolated([sys.executable,"-c",code,str(secret),str(source/"escape")],
                                  [source],output,[secret])
    except RuntimeError as error:
        if "bubblewrap is required" not in str(error):
            raise
        pytest.skip(str(error))
    except subprocess.CalledProcessError as error:
        if "bwrap:" not in error.stderr:
            raise
        pytest.skip(f"Host namespace capability unavailable: {error.stderr}")
    assert result.stdout.strip() == "ISOLATED"


def test_cpu_generated_load_update_calibrate_and_seal(tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from torchvision.models import resnet50
    from capsule_review.spatial_comparison import build_pair, make_optimizer, update
    from capsule_review.spatial_training import development_metrics, write_new, seal, verify_selection
    train_path, train_sha, archives = generated_manifest(tmp_path)
    train = ImageLoader(train_path, train_sha, archives, role="train")
    document = json.loads(train_path.read_text())
    document["role"] = "development"
    record = document["records"][0]
    document["records"] = [{**record,"id":label,"source_label":label}
                           for label in ("Normal","Angiectasia","Erosion")]
    dev_path = tmp_path / "development.json"
    dev_path.write_text(json.dumps(document))
    dev = ImageLoader(dev_path, hashlib.sha256(dev_path.read_bytes()).hexdigest(),
                      archives, role="development")
    try:
        with torch.random.fork_rng():
            torch.manual_seed(19)
            classifier, detector = build_pair(resnet50(weights=None).state_dict())
            for name, model, spatial in (("classifier",classifier,False),("detector",detector,True)):
                images, targets = train.batch([(0,1,True,1.,1.)])
                loss = update(model, make_optimizer(model,detector=spatial), images, targets,
                              detector=spatial,microbatch_size=1)
                assert loss.isfinite()
                evidence = dev.development(model,spatial)
                metrics = development_metrics(evidence["scores"],evidence["records"])
                assert len(metrics["thresholds"]) == 2
                output = tmp_path / name
                output.mkdir()
                torch.save(model.state_dict(),output/"generated.pt")
                write_new(output/"development.json",evidence)
                write_new(output/"selection.json",metrics)
                commitment = seal(output,sorted(output.iterdir()))
                verify_selection(output,commitment)
    finally:
        train.close()
        dev.close()


def test_unknown_empty_records_and_fractional_labels_rejected(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    path, commitment, archives = generated_manifest(tmp_path)
    loader = ImageLoader(path,commitment,archives,role="train")
    try:
        loader.records[0]["labels"] = [1.5]
        with pytest.raises(ValueError,match="foreground"):
            loader.batch([(0,0,False,1.,1.)])
        loader.records[0].update(labels=[],boxes=[],source_status="unknown")
        with pytest.raises(ValueError,match="negative"):
            loader.batch([(0,0,False,1.,1.)])
        loader.records[0]["source_status"] = "source_documented_normal"
        images,targets = loader.batch([(0,0,False,1.,1.)])
        assert tuple(targets[0]["boxes"].shape) == (0,4)
    finally:
        loader.close()
