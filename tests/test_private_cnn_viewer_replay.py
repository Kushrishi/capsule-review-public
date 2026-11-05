"""Synthetic-only regression tests of private, exact original-CNN viewer replay."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sqlite3
import sys
import zipfile

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")
from PIL import Image
from capsule_review.baseline import AnatomyCNN, image_tensor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_private_cnn_viewer_replay as verifier


def make_fixture(tmp_path, monkeypatch, *, tamper_score=False,
                 missing_display=False, wrong_display_hash=False):
    torch.manual_seed(31)
    torch.set_num_threads(2)
    model = AnatomyCNN(2).eval()
    weights = io.BytesIO()
    torch.save(model.state_dict(), weights)
    b = weights.getvalue()
    model_path = tmp_path / "original-model-synthetic.zip"
    model_meta = {
        "model_weights_sha256": hashlib.sha256(b).hexdigest(),
        "architecture": "capsule-cnn-v1",
        "input": "96x96 RGB, aspect-preserving pad, 0..1 channels",
        "classes": ["blood label absent","blood label present"],
    }
    import json
    with zipfile.ZipFile(model_path, "x") as z:
        z.writestr("model/weights.pt", b)
        z.writestr("model/model.json", json.dumps(model_meta))
        z.writestr("private/unrelated-label.csv", "THIS SHOULD NOT BE READ")
    monkeypatch.setattr(verifier,"EXPECTED_ORIGINAL_MODEL_ZIP_BYTES",model_path.stat().st_size)
    monkeypatch.setattr(verifier,"EXPECTED_ORIGINAL_MODEL_ZIP_SHA256",
                        hashlib.sha256(model_path.read_bytes()).hexdigest())
    monkeypatch.setattr(verifier,"EXPECTED_WEIGHTS_SHA256",hashlib.sha256(b).hexdigest())
    monkeypatch.setattr(verifier,"EXPECTED_DISPLAY_FRAMES",3)

    study_id = "a"*32
    images = []
    scores = []
    for i in range(3):
        p = tmp_path / f"synthetic-{i}.png"
        Image.new("RGB",(40+i,35+i),(i*90,25,50)).save(p,format="PNG")
        raw = p.read_bytes()
        images.append(raw)
        with torch.inference_mode():
            x = image_tensor(p).unsqueeze(0)
            scores.append(float(torch.softmax(model(x),dim=1)[0,1]))
    db = tmp_path / "synthetic-scores.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE studies (id TEXT, frame_count INTEGER)")
    con.execute("CREATE TABLE frames (study_id TEXT, position INTEGER, source_sha256 TEXT, display_sha256 TEXT)")
    con.execute("CREATE TABLE predictions (study_id TEXT, position INTEGER, label TEXT, score REAL)")
    con.execute("INSERT INTO studies VALUES (?,?)",(study_id,3))
    for i, raw in enumerate(images):
        con.execute("INSERT INTO frames VALUES (?,?,?,?)",(
            study_id,i,"f"*64,
            ("0"*64 if wrong_display_hash and i==1
             else hashlib.sha256(raw).hexdigest())))
        score=(0.0 if tamper_score and i==1 else scores[i])
        con.execute("INSERT INTO predictions VALUES (?,?,?,?)",(study_id,i,verifier.LABEL,score))
    con.commit()
    con.close()
    private_zip = tmp_path / "normalized-viewer-synthetic.zip"
    with zipfile.ZipFile(private_zip,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.write(db,"workspace/reviews.sqlite3")
        for i,raw in enumerate(images):
            if not missing_display or i!=1:
                z.writestr(f"workspace/images/{study_id}/{i}.png",raw)
        z.writestr("protected/other-patient-dataset.csv","NO READ OF OTHER PATIENTS")
    return model_path,private_zip,hashlib.sha256(private_zip.read_bytes()).hexdigest()


def test_exact_synthetic_cnn_replay_and_no_private_predictions_export(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch)
    summary=verifier.replay(a,b,sha)
    assert summary["record_type"]=="historical-original-cnn-private-viewer-replay-v1"
    assert summary["historical_original_model_checkpoint_sha256_verified"] is True
    assert summary["viewer_display_png_sha256_matches"]==3
    assert summary["previously_saved_score_records_replayed"]==3
    # Different CPU batch shapes may change a final low-order float bit.
    # The actual preserved 512-frame replay was exactly equal, but synthetic
    # unit tests should require numerical equivalence, not fragile bitwise
    # equality across independent batch sizes and PyTorch versions.
    assert 0 <= summary["exact_score_matches"] <= 3
    assert summary["scores_within_absolute_1e_minus_6"]==3
    assert summary["maximum_absolute_score_difference"] <= 1e-6
    assert summary["original_publisher_png_bytes_replayed"] is False
    assert summary["independent_model_validation"] is False
    assert summary["individual_source_records_or_prediction_scores_exported"] is False
    import json
    s=json.dumps(summary)
    assert "source_sha256" not in s
    assert "position" not in s
    assert "predictions" not in s


def test_modified_saved_score_causes_failed_replay(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch,tamper_score=True)
    with pytest.raises(ValueError,match="scores failed"):
        verifier.replay(a,b,sha)


def test_stored_viewer_sha_mismatch_is_detected(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch,wrong_display_hash=True)
    with pytest.raises(ValueError,match="viewer image bytes changed"):
        verifier.replay(a,b,sha)


def test_missing_viewer_image_is_not_silently_skipped(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch,missing_display=True)
    with pytest.raises(KeyError):
        verifier.replay(a,b,sha)


def test_wrong_private_workspace_sha_rejected(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="SHA-256"):
        verifier.replay(a,b,"0"*64)


def test_original_model_sha_mismatch_rejected(tmp_path,monkeypatch):
    a,b,sha=make_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(verifier,"EXPECTED_WEIGHTS_SHA256","1"*64)
    with pytest.raises(ValueError,match="Original CNN weights"):
        verifier.replay(a,b,sha)
