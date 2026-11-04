"""Actual generated PNG/pixel and private freeze integrity regression tests.

Never reads any original medical image, model weights, or reserved source labels.
All images, source indices, review scores and ZIP members are synthetic.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from capsule_review import private_source_gate as gate


ORIGINAL_SPEC = (
    Path(__file__).resolve().parents[1] /
    "docs/GALAR_UNSEEN_11_20_EVALUATION_LOCK.json"
)
MODEL_SHA = "f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3"


def _source_csv(*, positive=(5, 6, 15, 16), unknown=(), missing=()) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=("frame", "blood"))
    writer.writeheader()
    for index in range(20):
        if index in missing:
            continue
        label = "" if index in unknown else "1" if index in positive else "0"
        writer.writerow({"frame": index * 5, "blood": label})
    return out.getvalue().encode()


def _case(tmp_path: Path, *, positive=(5, 6, 15, 16), unknown=(), missing=()):
    tmp_path.mkdir(parents=True, exist_ok=True)
    images = tmp_path / "original_synthetic_png"
    images.mkdir()
    entries = []
    for index in range(20):
        frame = 5 * index
        name = f"research-source-{frame:04d}.png"
        image = Image.new("RGB", (8, 9), (index, index * 3 % 255, 50))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        raw = buffer.getvalue()
        (images / name).write_bytes(raw)
        entries.append({
            "frame": frame,
            "name": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    # A deliberately uninspectable authors' member, plus other study entries.
    labels = tmp_path / "generated_corrected_labels.zip"
    with zipfile.ZipFile(labels, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("11.csv", _source_csv(positive=positive, unknown=unknown, missing=missing))
        archive.writestr("61.csv", b"PROTECTED AUTHORS' CSV: NEVER PARSE THIS")
        archive.writestr("12.csv", b"OTHER LOCKED EXAM: NEVER PARSE THIS")
    spec = json.loads(ORIGINAL_SPEC.read_text(encoding="utf-8"))
    spec["publisher"]["expected_sha256"] = hashlib.sha256(labels.read_bytes()).hexdigest()
    spec_file = tmp_path / "synthetic_protocol.json"
    spec_file.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    return {
        "image_root": images,
        "image_records": entries,
        "scores": [(20 - i) / 20 for i in range(20)],  # Deliberately wrong.
        "expected_first": 0,
        "expected_last": 95,
        "expected_count": 20,
        "weights_sha256": MODEL_SHA,  # Claim only; no model inferred.
        "protocol_path": spec_file,
        "destination": tmp_path / "private_frozen_queues.json",
        "labels_zip": labels,
    }


def _freeze(case: dict) -> str:
    return gate.freeze_private_queues(
        **{key: value for key, value in case.items() if key != "labels_zip"}
    )


def _evaluate(case: dict, digest: str):
    return gate.evaluate_private_snapshot(
        destination=case["destination"],
        expected_snapshot_sha256=digest,
        image_root=case["image_root"],
        protocol_path=case["protocol_path"],
        labels_zip=case["labels_zip"],
        exam=11,
    )


def test_full_synthetic_png_to_private_freeze_to_one_label_to_aggregate(tmp_path, monkeypatch):
    case = _case(tmp_path)
    labels_read: list[str] = []
    original_zip_read = zipfile.ZipFile.read

    def log_zip_read(archive, member, *args, **kwargs):
        labels_read.append(member.filename if hasattr(member, "filename") else member)
        return original_zip_read(archive, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", log_zip_read)

    digest = _freeze(case)
    assert len(digest) == 64
    assert labels_read == []  # No source labels inspected while selecting frames.
    assert case["destination"].is_file()
    if os.name == "posix":
        assert case["destination"].stat().st_mode & 0o777 == 0o600
    # The stored private record contains actual generated source identities and scores.
    # It is deliberately NOT public aggregate data.
    private = json.loads(case["destination"].read_bytes())
    assert private["source_image_names"][0] == "research-source-0000.png"
    assert private["source_frames"] == list(range(0, 100, 5))
    assert private["model_weights_sha256_claimed"] == MODEL_SHA
    assert private["source_image_sha256"] == [
        row["sha256"] for row in case["image_records"]
    ]
    assert len(private["selection_by_percent"]) == 5
    with pytest.raises(FileExistsError):
        _freeze(case)  # Immutable-by-convention and exclusive-create; no overwrite.

    report = _evaluate(case, digest)
    assert labels_read == ["11.csv"]  # No other exam member was decoded.
    assert report["positive_annotated_images"] == 4
    assert report["positive_annotation_runs"] == 2
    ten = next(r for r in report["review_results"] if r["review_percent"] == 10)
    assert ten["review_images"] == 2
    assert ten["policies"]["uniform"]["distinct_positive_annotation_runs_hit"] == 2
    assert ten["policies"]["score"]["distinct_positive_annotation_runs_hit"] == 0
    assert ten["policies"]["score_bin"]["distinct_positive_annotation_runs_hit"] == 0
    assert ten["score_bin_minus_uniform_run_recall"] == -1.0
    assert all(result["policies"]["uniform"]["annotation_run_recall"] is not None
               for result in report["review_results"])
    assert "research-source" not in json.dumps(report)
    assert "source_frames" not in json.dumps(report)
    assert "source_image_names" not in json.dumps(report)
    assert report["clinical_validation"] is False


def test_bytes_corruption_after_freeze_is_rejected_before_labels(tmp_path, monkeypatch):
    case = _case(tmp_path)
    digest = _freeze(case)
    png = case["image_root"] / case["image_records"][0]["name"]
    original_bytes = png.read_bytes()
    png.write_bytes(original_bytes[:-1] + bytes([original_bytes[-1] ^ 1]))
    touched: list[str] = []
    original = gate.load_locked_corrected_csv

    def fail_if_labels(*args, **kwargs):
        touched.append("read")
        return original(*args, **kwargs)

    monkeypatch.setattr(gate, "load_locked_corrected_csv", fail_if_labels)
    with pytest.raises(ValueError, match="byte identity"):
        _evaluate(case, digest)
    assert touched == []


def test_snapshot_mutation_requires_original_external_anchor(tmp_path, monkeypatch):
    case = _case(tmp_path)
    digest = _freeze(case)
    snapshot = case["destination"]
    data = bytearray(snapshot.read_bytes())
    data[0] ^= 1  # Change actual byte without increasing file size.
    snapshot.write_bytes(data)
    touched: list[str] = []
    monkeypatch.setattr(
        gate, "load_locked_corrected_csv",
        lambda *a, **kw: touched.append("read"),
    )
    with pytest.raises(ValueError, match="after its external digest"):
        _evaluate(case, digest)
    assert touched == []


def test_protocol_or_model_mismatch_fails_before_snapshot_and_annotations(tmp_path):
    case = _case(tmp_path)
    wrong_model = dict(case, weights_sha256="0" * 64)
    with pytest.raises(ValueError, match="pinned model"):
        _freeze(wrong_model)
    assert not case["destination"].exists()

    digest = _freeze(case)
    spec = json.loads(case["protocol_path"].read_text())
    spec["goal"] = "Changed after freezing; must not evaluate."
    case["protocol_path"].write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError, match="protocol or claimed model"):
        _evaluate(case, digest)


def test_unauthorized_label_members_and_wrong_archive_fail_closed(tmp_path, monkeypatch):
    case = _case(tmp_path)
    digest = _freeze(case)
    captured = []
    original = zipfile.ZipFile.read

    def record_read(archive, member, *a, **kw):
        captured.append(member.filename if hasattr(member, "filename") else member)
        return original(archive, member, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "read", record_read)
    with pytest.raises(ValueError, match="outside the locked"):
        gate.load_locked_corrected_csv(case["labels_zip"], exam=61,
                                       protocol_path=case["protocol_path"])
    assert captured == []
    with pytest.raises(ValueError, match="outside the locked"):
        gate.load_locked_corrected_csv(case["labels_zip"], exam=10,
                                       protocol_path=case["protocol_path"])
    assert captured == []
    modified_archive = case["labels_zip"].read_bytes() + b"mutated"
    case["labels_zip"].write_bytes(modified_archive)
    with pytest.raises(ValueError, match="archive SHA-256 changed"):
        _evaluate(case, digest)
    assert captured == []


def test_unknown_and_missing_annotations_fail_closed(tmp_path):
    for variant in ("unknown", "missing"):
        case = _case(
            tmp_path / variant,
            unknown=(7,) if variant == "unknown" else (),
            missing=(7,) if variant == "missing" else (),
        )
        digest = _freeze(case)
        # The locked protocol remains identical after freezing; only the
        # synthetic CSV outcome differs. No eligibility is silently altered.
        with pytest.raises(ValueError, match="Unknown labels|Missing, extra|stride"):
            _evaluate(case, digest)

def test_manifest_rejects_label_keys_source_gaps_symlinks_bad_png(tmp_path):
    case = _case(tmp_path)
    records = case["image_records"]
    args = dict(
        root=case["image_root"], records=records, expected_first=0,
        expected_last=95, expected_count=20,
    )
    rows, hashes = gate.verify_original_pngs(**args)
    assert rows == list(range(0, 100, 5))
    assert hashes == [r["sha256"] for r in records]

    with pytest.raises(ValueError, match="label-blind image manifest"):
        gate.verify_original_pngs(**dict(args, records=[
            dict(records[0], blood="1"), *records[1:]
        ]))
    with pytest.raises(ValueError, match="incomplete"):
        gate.verify_original_pngs(**dict(args, records=[
            records[0], *records[2:]
        ]))
    with pytest.raises(ValueError, match="pinned original"):
        gate.verify_original_pngs(**dict(args, expected_count=19))
    with pytest.raises(ValueError, match="plain names"):
        gate.verify_original_pngs(**dict(args, records=[
            dict(records[0], name="../outside.png"), *records[1:]
        ]))
    image = case["image_root"] / records[0]["name"]
    image.write_bytes(gate.PNG_MAGIC + b"broken image payload")
    altered = dict(records[0], sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="decoded safely"):
        gate.verify_original_pngs(**dict(args, records=[altered, *records[1:]]))
    image.unlink()
    image.symlink_to(case["image_root"] / records[1]["name"])
    with pytest.raises(ValueError, match="symlinked"):
        gate.verify_original_pngs(**dict(args, records=[records[0], *records[1:]]))


def test_private_snapshot_must_be_outside_public_repository(tmp_path):
    case = _case(tmp_path)
    # The project root is not a writable test target; the check rejects it
    # before any file is created.
    public_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="may not be written inside public"):
        _freeze(dict(case, destination=public_root / "never-create-freeze.json"))
    assert not (public_root / "never-create-freeze.json").exists()
