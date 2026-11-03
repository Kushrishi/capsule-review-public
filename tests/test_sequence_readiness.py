"""Guard against misreporting historical sparse Galar frames as dense video."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sequence_readiness.py"
spec = importlib.util.spec_from_file_location("sequence_readiness", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PNG = b"\x89PNG\r\n\x1a\n" + b"fixture-body"


def setup_data(tmp_path, indices=(0, 45, 90, 135)):
    root = tmp_path / "images"
    manifest = {
        "format": "capsule-blood-sparse-v1",
        "split": {"train_exams": [1], "development_exams": [9]},
        "records": [],
    }
    for exam in (1, 9):
        for idx in indices:
            path = f"{exam:03d}/frame_{idx:06d}.PNG"
            f = root / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(PNG)
            manifest["records"].append({
                "exam": exam, "frame": idx, "path": path,
                "split": "train" if exam == 1 else "development",
                "source_sha256": hashlib.sha256(PNG).hexdigest(),
            })
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest))
    return mf, root, manifest


def test_sparse_examination_not_treated_as_video(tmp_path):
    mf, root, _ = setup_data(tmp_path)
    result = mod.audit(mf, images=root)
    assert result["images"] == 8
    assert result["verified_images"] == 8
    assert result["status"] == "not_eligible_for_dense_video_evaluation"
    assert result["source_index_gaps"]["gap_5_or_less_pairs"] == 0
    assert result["per_examination"]["9"]["median_gap"] == 45


def test_no_images_does_not_claim_verification(tmp_path):
    mf, _, _ = setup_data(tmp_path)
    result = mod.audit(mf)
    assert result["image_verification"] == "not_performed"
    assert result["verified_images"] == 0


def test_edited_png_fails_digest(tmp_path):
    mf, root, _ = setup_data(tmp_path)
    (root / "001/frame_000000.PNG").write_bytes(PNG+b"tampered")
    with pytest.raises(mod.ReadinessError, match="SHA-256 mismatch"):
        mod.audit(mf, images=root)


def test_missing_png_fails(tmp_path):
    mf, root, _ = setup_data(tmp_path)
    (root / "001/frame_000000.PNG").unlink()
    with pytest.raises(mod.ReadinessError, match="missing"):
        mod.audit(mf, images=root)


def test_duplicate_identity_rejected(tmp_path):
    mf, _, manifest = setup_data(tmp_path)
    manifest["records"].append(manifest["records"][0].copy())
    mf.write_text(json.dumps(manifest))
    with pytest.raises(mod.ReadinessError, match="Duplicate"):
        mod.audit(mf)


def test_split_cross_contamination_rejected(tmp_path):
    mf, _, manifest = setup_data(tmp_path)
    manifest["split"]["development_exams"] = [1, 9]
    mf.write_text(json.dumps(manifest))
    with pytest.raises(mod.ReadinessError, match="disjoint"):
        mod.audit(mf)


def test_reserved_exam_rejected(tmp_path):
    mf, _, manifest = setup_data(tmp_path)
    manifest["split"]["development_exams"] = [61]
    mf.write_text(json.dumps(manifest))
    with pytest.raises(mod.ReadinessError, match="Reserved"):
        mod.audit(mf)


def test_path_mismatch_rejected(tmp_path):
    mf, _, manifest = setup_data(tmp_path)
    manifest["records"][0]["path"] = "../evil.PNG"
    mf.write_text(json.dumps(manifest))
    with pytest.raises(mod.ReadinessError, match="path"):
        mod.audit(mf)


def test_output_refuses_to_replace_previous_record(tmp_path):
    mf, _, _ = setup_data(tmp_path)
    dest = tmp_path / "previous.json"
    dest.write_text("KEEP")
    with pytest.raises(SystemExit):
        mod.main(["--manifest", str(mf), "--output", str(dest)])
    assert dest.read_text() == "KEEP"


def test_per_exam_small_gap_does_not_claim_dense_sequence(tmp_path):
    mf, _, _ = setup_data(tmp_path, indices=(0, 5, 10))
    result = mod.audit(mf)
    assert result["source_index_gaps"]["gap_5_or_less_pairs"] == 4
    assert result["status"] == "not_eligible_for_dense_video_evaluation"
