"""Synthetic-only original CNN Galar36 score freeze/audit privacy regression tests."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from PIL import Image

torch=pytest.importorskip("torch")
pytest.importorskip("numpy")

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import run_galar36_fixed_policy_private as m

SHA=lambda blob:hashlib.sha256(blob).hexdigest()
FRAMES=list(range(100,135,5))
LABELS={100:"0",105:"1",110:"1",115:"0",120:"1",125:"0",130:"0"}


def private_fixtures(tmp_path,monkeypatch):
    monkeypatch.setattr(m,"EXPECTED_SOURCE_IMAGES",len(FRAMES))
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_IMAGES",3)
    monkeypatch.setattr(m,"EXPECTED_POSITIVE_RUNS",2)
    monkeypatch.setattr(m,"NEW_BYTES",12)
    monkeypatch.setattr(m,"OLD_BYTES",10)
    monkeypatch.setattr(m,"NEW_START",30)
    monkeypatch.setattr(m,"END_EXCLUSIVE",42)
    monkeypatch.setattr(m,"OLD_SHA256","a"*64)
    monkeypatch.setattr(m,"verified_labels36",lambda path:LABELS)
    class DeterministicCNN(torch.nn.Module):
        def forward(self,x):
            values=x.mean(dim=(1,2,3))
            return torch.stack((1-values,values),dim=1)
    monkeypatch.setattr(m,"load_original_model",lambda _:DeterministicCNN().eval())
    images=tmp_path/"private-study36-synthetic.zip"
    manifest=[]
    with zipfile.ZipFile(images,"x",compression=zipfile.ZIP_STORED) as z:
        for frame in FRAMES:
            buf=io.BytesIO()
            Image.new("RGB",(25+(frame%5),25),(frame%255,10,30)).save(
                buf,format="PNG")
            raw=buf.getvalue()
            name=f"frame_{frame:07d}.PNG"
            z.writestr(f"images/036/{name}",raw)
            manifest.append({
                "examination":36,"source_frame":frame,
                "original_filename":name,"original_png_sha256":SHA(raw),
                "original_png_bytes":len(raw),
                "blood_label":int(LABELS[frame]),
            })
        z.writestr("source-frame-private-manifest.json",json.dumps(manifest))
        z.writestr("source-block-private-receipt.json",json.dumps({
            "official_file_id":m.FILE_ID,
            "retained_block5_sha256":m.OLD_SHA256,
            "retained_block5_compressed_bytes":m.OLD_BYTES,
            "full_source_md5_verified":False,
            "all_other_image_blocks_absent":True,
            "source_block6":{
                "official_file_id":m.FILE_ID,"block":6,
                "range_start":m.NEW_START,"range_stop_exclusive":m.END_EXCLUSIVE,
                "compressed_bytes_received":m.NEW_BYTES,
                "source_block_sha256":"b"*64,
                "full_source_md5_verified":False,
            }
        }))
    labels=tmp_path/"labels-synthetic.zip"
    with zipfile.ZipFile(labels,"x") as z:
        z.writestr("36.csv","frame,blood\n"+"\n".join(
            f"{frame},{LABELS[frame]}" for frame in FRAMES)+"\n")
        z.writestr("11.csv","SHOULD NOT BE OPENED")
        z.writestr("61.csv","SHOULD NOT BE OPENED")
    return images,SHA(images.read_bytes()),labels


def test_complete_original_image_scoring_does_not_access_any_labels(
    tmp_path,monkeypatch
):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    original=zipfile.ZipFile.read
    def no_label_read(self,name,*args,**kwargs):
        n=name if isinstance(name,str) else name.filename
        if n in ("source-frame-private-manifest.json",
                  "source-block-private-receipt.json","36.csv","11.csv","61.csv"):
            raise AssertionError("Score stage opened a private outcome member.")
        return original(self,name,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(zipfile.ZipFile,"read",no_label_read)
        snapshot=m.score_originals(images,sha,Path("/fake/model.zip"),batch_size=3)
    assert snapshot["exam"]==36
    assert snapshot["outcome_annotations_accessed_during_scoring"] is False
    assert snapshot["protected_galar11_20_reopened"] is False
    assert snapshot["authors_galar61_80_opened"] is False
    assert len(snapshot["complete_original_scores"])==len(FRAMES)
    assert len(snapshot["frozen_queues"])==5
    assert all(len(set(q["temporal_window3_score_bin"]))==q["k"]
               for q in snapshot["frozen_queues"])
    report=m.audit_frozen(snapshot,images,sha,labels)
    assert report["original_source_images_verified"]==7
    assert report["blood_positive_original_annotated_images"]==3
    assert report["positive_annotation_runs_not_adjudicated_lesions"]==2
    assert report["independent_patient_validation"] is False
    assert report["model_promoted"] is False
    assert len(report["review_results"])==5
    assert "source_frame" not in json.dumps(report)
    for row in report["review_results"]:
        assert "temporal_window3_score_bin" in row["policies"]
        assert set(row["policies"])=={
            "uniform","score","score_diverse","score_bin",
            "temporal_window3_score_bin"
        }
        for method in row["policies"].values():
            assert 0<=method["distinct_positive_annotation_runs_hit"]<=2


def test_changes_to_frozen_scores_are_rejected_before_any_label_access(
    tmp_path,monkeypatch
):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    snapshot=m.score_originals(images,sha,Path("/fake/model.zip"))
    snapshot["complete_original_scores"][2]["original_cnn_score"]=0.999
    monkeypatch.setattr(m,"verified_labels36",
                        lambda _:pytest.fail("Premature label access"))
    with pytest.raises(ValueError,match="Frozen Galar36 score commitment"):
        m.audit_frozen(snapshot,images,sha,labels)


def test_changes_to_temporal_policy_are_rejected_before_any_label_access(
    tmp_path,monkeypatch
):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    snapshot=m.score_originals(images,sha,Path("/fake/model.zip"))
    snapshot["frozen_queues"][1]["temporal_window3_score_bin"]=[]
    monkeypatch.setattr(m,"verified_labels36",
                        lambda _:pytest.fail("Premature label access"))
    with pytest.raises(ValueError,match="Frozen Galar36 score commitment"):
        m.audit_frozen(snapshot,images,sha,labels)


def test_original_zip_sha_mismatch_refuses_model_scoring(tmp_path,monkeypatch):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="SHA-256"):
        m.score_originals(images,"0"*64,Path("/fake/model.zip"))


def test_private_source_png_tampering_rejected(tmp_path,monkeypatch):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    snapshot=m.score_originals(images,sha,Path("/fake/model.zip"))
    with zipfile.ZipFile(images,"a") as z:
        z.writestr("unexpected-member.txt",b"modified source ZIP")
    with pytest.raises(ValueError,match="SHA-256"):
        m.audit_frozen(snapshot,images,sha,labels)


def test_mismatched_private_manifest_label_is_rejected(tmp_path,monkeypatch):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    snapshot=m.score_originals(images,sha,Path("/fake/model.zip"))
    altered=dict(LABELS)
    altered[105]="0"
    monkeypatch.setattr(m,"verified_labels36",lambda _:altered)
    with pytest.raises(ValueError,match="contradicts"):
        m.audit_frozen(snapshot,images,sha,labels)


def test_corrupt_compressed_source_receipt_rejected(tmp_path,monkeypatch):
    images,sha,labels=private_fixtures(tmp_path,monkeypatch)
    snapshot=m.score_originals(images,sha,Path("/fake/model.zip"))
    corrupt=tmp_path/"corrupt-receipt.zip"
    with zipfile.ZipFile(images) as src,zipfile.ZipFile(corrupt,"x") as out:
        for member in src.infolist():
            payload=src.read(member)
            if member.filename=="source-block-private-receipt.json":
                obj=json.loads(payload)
                obj["source_block6"]["range_start"]+=1
                payload=json.dumps(obj).encode()
            out.writestr(member,payload)
    changed_sha=SHA(corrupt.read_bytes())
    snapshot["source_originals_package_sha256"]=changed_sha
    with pytest.raises(ValueError,match="source-block receipt"):
        m.audit_frozen(snapshot,corrupt,changed_sha,labels)
