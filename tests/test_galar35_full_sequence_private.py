"""Synthetic-only end-to-end check of private Galar35 full-sequence score and audit."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("numpy")
from PIL import Image
from capsule_review.baseline import AnatomyCNN

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_galar35_full_sequence_private as full

SOURCE = list(range(100, 135, 5))
LABELS = {100:"0",105:"1",110:"1",115:"0",120:"1",125:"0",130:"0"}
SHA = lambda b: hashlib.sha256(b).hexdigest()


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "EXPECTED_IMAGES", len(SOURCE))
    monkeypatch.setattr(full, "EXPECTED_POSITIVE_IMAGES", 3)
    monkeypatch.setattr(full, "EXPECTED_ANNOTATION_RUNS", 2)
    monkeypatch.setattr(full, "MODEL_PACKAGE_SHA", "unset")
    torch.manual_seed(42)
    model = AnatomyCNN(2).eval()
    weights = io.BytesIO()
    torch.save(model.state_dict(), weights)
    weight_bytes = weights.getvalue()
    monkeypatch.setattr(full,"WEIGHTS_SHA",SHA(weight_bytes))
    model_zip = tmp_path/"private-original-cnn-test.zip"
    with zipfile.ZipFile(model_zip,"x") as z:
        z.writestr("model/model.json",json.dumps({
            "architecture":"capsule-cnn-v1",
            "input": full.MODEL_INPUT,
            "classes":["blood label absent","blood label present"],
            "model_weights_sha256":SHA(weight_bytes),
        }))
        z.writestr("model/weights.pt",weight_bytes)
        z.writestr("private/unused-labels.csv", "Do not open.")
    monkeypatch.setattr(full,"MODEL_PACKAGE_SHA",SHA(model_zip.read_bytes()))

    originals = tmp_path/"private-galar35-source-synthetic.zip"
    private_manifest = []
    with zipfile.ZipFile(originals,"x",compression=zipfile.ZIP_STORED) as z:
        for frame in SOURCE:
            image = Image.new("RGB", (32+(frame%3),24+(frame%5)),
                              (frame%255,10,frame//5))
            buffer = io.BytesIO()
            image.save(buffer,format="PNG")
            raw = buffer.getvalue()
            name=f"frame_{frame:07d}.PNG"
            z.writestr(f"images/035/{name}",raw)
            private_manifest.append({
                "examination":35,"source_frame":frame,"original_filename":name,
                "original_png_sha256":SHA(raw),
                "original_png_bytes":len(raw),"blood_label":int(LABELS[frame]),
            })
        z.writestr("source-frame-private-manifest.json",json.dumps(private_manifest))
        z.writestr("source-block-private-receipt.json",json.dumps({
            "official_file_id":44755700,"block":full.BLOCK,
            "range_start":full.BLOCK_START,
            "range_stop_exclusive":full.BLOCK_START+full.BLOCK_BYTES,
            "compressed_bytes_received":full.BLOCK_BYTES,
            "full_source_md5_verified":False,"source_block_sha256":"a"*64
        }))
    labels_zip=tmp_path/"corrected-labels-test.zip"
    with zipfile.ZipFile(labels_zip,"x") as z:
        z.writestr("35.csv", "frame,blood\n"+"\n".join(
            f"{f},{LABELS[f]}" for f in SOURCE)+"\n")
        z.writestr("11.csv","frame,blood\n101,1\n")
        z.writestr("61.csv","frame,blood\n102,1\n")
    monkeypatch.setattr(full,"verified_label_rows",lambda path:LABELS)
    return originals, SHA(originals.read_bytes()), model_zip, labels_zip


def test_synthetic_full_sequence_score_then_frozen_queues_then_run_audit(tmp_path,monkeypatch):
    original,source_sha,model,labels=fixture(tmp_path,monkeypatch)
    # A strict source/labels separation: score() must never read a manifest,
    # block receipt or corrected labels from the original source ZIP.
    real_read=zipfile.ZipFile.read
    def protective_read(self, name,*args,**kwargs):
        target=name if isinstance(name,str) else name.filename
        if target in ("source-frame-private-manifest.json",
                      "source-block-private-receipt.json","11.csv","61.csv"):
            raise AssertionError("Private source label/receipt opened before freeze")
        return real_read(self,name,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(zipfile.ZipFile,"read",protective_read)
        frozen=full.score_source_images(original,source_sha,model,batch_size=3)
    assert len(frozen["complete_original_scores"]) == 7
    assert frozen["labels_or_clinical_annotations_accessed_in_this_stage"] is False
    assert len(frozen["frozen_queues"]) == 5
    assert frozen["original_model_weights_sha256"] == SHA(
        zipfile.ZipFile(model).read("model/weights.pt"))
    for q in frozen["frozen_queues"]:
        assert q["k"] == full.exact_k(7, q["review_percent"])
        assert set(q["policies"]) == {"uniform","score","score_diverse","score_bin"}
        assert len(q["temporal_window3_score_bin"]) == q["k"]
        assert len(set(q["temporal_window3_score_bin"])) == q["k"]
        assert all(len(set(v)) == q["k"] for v in q["policies"].values())
    report=full.replay_and_audit(frozen,original,source_sha,labels)
    assert report["original_source_images_verified"] == 7
    assert report["blood_positive_original_annotated_images"] == 3
    assert report["positive_annotation_runs_not_adjudicated_lesions"] == 2
    assert len(report["review_results"]) == 5
    assert report["independent_patient_validation"] is False
    assert report["clinical_validation"] is False
    assert report["model_promoted"] is False
    assert "source_frame" not in json.dumps(report)
    for r in report["review_results"]:
        assert r["review_images"] == full.exact_k(7,r["review_percent"])
        assert "temporal_window3_score_bin" in r["policies"]
        for method,metrics in r["policies"].items():
            assert 0 <= metrics["distinct_positive_annotation_runs_hit"] <= 2
            assert 0 <= metrics["positive_annotated_images_hit"] <= 3


def test_no_label_open_when_frozen_queue_is_tampered(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    frozen=full.score_source_images(original,sha,model)
    frozen["frozen_queues"][1]["temporal_window3_score_bin"]=[]
    def forbidden(_):
        raise AssertionError("Audit read source annotation before verifying freeze.")
    monkeypatch.setattr(full,"verified_label_rows",forbidden)
    with pytest.raises(ValueError,match="frozen exact-K"):
        full.replay_and_audit(frozen,original,sha,labels)


def test_original_png_changes_cause_source_checksum_failure(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    frozen=full.score_source_images(original,sha,model)
    with zipfile.ZipFile(original,"a") as z:
        z.writestr("source-extra.txt","tampering")
    with pytest.raises(ValueError,match="SHA-256"):
        full.replay_and_audit(frozen,original,sha,labels)


def test_wrong_source_identity_blocks_scoring(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="SHA-256"):
        full.score_source_images(original,"0"*64,model)


def test_missing_unexpected_or_repeated_source_frame_disallowed(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    with zipfile.ZipFile(original) as z:
        assert len(full.source_members(z))==7
    copy=tmp_path/"bad-originals.zip"
    with zipfile.ZipFile(original) as z, zipfile.ZipFile(copy,"x") as out:
        for member in z.infolist():
            if member.filename=="images/035/frame_0000110.PNG":
                continue
            out.writestr(member,z.read(member))
    with zipfile.ZipFile(copy) as z:
        with pytest.raises(ValueError,match="Complete source examination"):
            full.source_members(z)
    extra=tmp_path/"bad-extra.zip"
    with zipfile.ZipFile(original) as z, zipfile.ZipFile(extra,"x") as out:
        for member in z.infolist():
            out.writestr(member,z.read(member))
        out.writestr("images/061/frame_0000001.PNG",b"PNG")
    with zipfile.ZipFile(extra) as z:
        with pytest.raises(ValueError,match="Unexpected private source"):
            full.source_members(z)


def test_source_manifest_hash_mismatch_rejected_after_freeze(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    frozen=full.score_source_images(original,sha,model)
    altered=tmp_path/"altered-package.zip"
    with zipfile.ZipFile(original) as z, zipfile.ZipFile(altered,"x") as out:
        for member in z.infolist():
            data=z.read(member)
            if member.filename=="source-frame-private-manifest.json":
                manifest=json.loads(data)
                manifest[0]["original_png_sha256"]="0"*64
                data=json.dumps(manifest).encode()
            out.writestr(member,data)
    altered_sha=SHA(altered.read_bytes())
    frozen["private_originals_package_sha256"]=altered_sha
    with pytest.raises(ValueError,match="byte integrity"):
        full.replay_and_audit(frozen,altered,altered_sha,labels)


def test_label_manifest_disagreement_rejected(tmp_path,monkeypatch):
    original,sha,model,labels=fixture(tmp_path,monkeypatch)
    frozen=full.score_source_images(original,sha,model)
    patched=dict(LABELS)
    patched[105]="0"
    monkeypatch.setattr(full,"verified_label_rows",lambda _:patched)
    with pytest.raises(ValueError,match="contradicts official"):
        full.replay_and_audit(frozen,original,sha,labels)


def test_private_snapshot_does_not_include_protected_eval_names(tmp_path,monkeypatch):
    original,sha,model,_=fixture(tmp_path,monkeypatch)
    frozen=full.score_source_images(original,sha,model)
    assert frozen["original_galar_11_to_20_evaluation_accessed"] is False
    assert frozen["author_galar_61_to_80_accessed"] is False
    assert frozen["complete_original_scores"][0]["source_frame"] == SOURCE[0]
    assert frozen["prelabel_original_queues_commitment_sha256"]
