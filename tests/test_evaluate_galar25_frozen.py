"""Synthetic tests for locked Galar-25 model-transfer evaluation, no Torch needed."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_galar25_frozen as m


def test_frozen_models_budgets_and_label_blind_support():
    assert m.EXAM==25
    assert m.REFERENCE_COUNT==512 and m.REFERENCE_POSITIVES==14
    assert tuple(m.MODEL_HASHES)==('original_checkpoint','original_only_continued','expanded_continued')
    assert m.BUDGETS==(5,10,25,50,75,100)
    assert all(len(v)==64 for v in m.MODEL_HASHES.values())
    rows=[{'blood':int(i<14),'reference_uniform':1,'fit_enriched':0} for i in range(512)]
    scores={'good':[1-i/512 for i in range(512)],'bad':[i/512 for i in range(512)]}
    report=m.compute_metrics(rows,scores)
    assert report['n']==512 and report['blood_positive']==14
    assert report['rank_metrics']['good']['roc_auc']==1.0
    assert report['rank_metrics']['good']['average_precision']==1.0
    assert report['rank_metrics']['bad']['roc_auc']==0.0
    assert report['review_budgets']['10']['selected']==51
    assert report['review_budgets']['10']['blood_positive_images_found']['good']==14
    assert report['review_budgets']['10']['blood_positive_images_found']['bad']==0
    assert report['review_budgets']['100']['blood_positive_images_found']['good']==14
    assert report['review_budgets']['100']['blood_positive_images_found']['bad']==14
    with pytest.raises(ValueError,match='Scores and source'):
        m.compute_metrics(rows,{'bad':[0.5]*511})


def test_reference_source_sha256_enforced_before_extraction(tmp_path):
    source=tmp_path/'untrusted.zip'
    source.write_bytes(b'not a ZIP')
    with pytest.raises(ValueError,match='source ZIP differs'):
        m.extract_verified(source,'a'*64,'b'*64,tmp_path/'images')
    assert not (tmp_path/'images').exists()


def test_source_rejects_reserved_exam_and_missing_identity(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'UNION_COUNT',1)
    monkeypatch.setattr(m,'REFERENCE_COUNT',1)
    monkeypatch.setattr(m,'REFERENCE_POSITIVES',1)
    monkeypatch.setattr(m,'ENRICHED_COUNT',1)
    monkeypatch.setattr(m,'ENRICHED_POSITIVES',1)
    monkeypatch.setattr(m,'OVERLAP',1)
    raw=io.BytesIO();Image.new('RGB',(8,8),'green').save(raw,format='PNG');pixels=raw.getvalue()
    source=tmp_path/'private.zip'
    identity=[{'exam':11,'frame':0,'filename':'frame_000000.PNG',
               'blood':1,'reference_uniform':1,'fit_enriched':1,
               'source_bytes':len(pixels),'source_image_sha256':hashlib.sha256(pixels).hexdigest()}]
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('verified-private-manifest.json',json.dumps(identity))
        z.writestr('images/011/frame_000000.PNG',pixels)
    with pytest.raises(ValueError,match='Non-fitting'):
        m.extract_verified(source,m.digest(source),hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
                           tmp_path/'private_images')


def test_source_refuses_unknown_manifest_and_does_not_disclose_pixels(tmp_path):
    # Unknown source image hashes or labels are never silently accepted.
    source=tmp_path/'source.zip'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('verified-private-manifest.json','[]')
    with pytest.raises(ValueError,match='manifest digest mismatch'):
        m.extract_verified(source,m.digest(source),'c'*64,tmp_path/'images')
