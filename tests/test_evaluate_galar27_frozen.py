"""Synthetic invariants for locked Galar-27 transfer; no medical images needed."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluate_galar27_frozen as adapter
import evaluate_galar25_frozen as engine


@pytest.fixture
def fixed():
    adapter.configure()
    try:
        yield
    finally:
        engine.EXAM = 25
        engine.UNION_COUNT = 1013
        engine.REFERENCE_COUNT = 512
        engine.REFERENCE_POSITIVES = 14
        engine.ENRICHED_COUNT = 512
        engine.ENRICHED_POSITIVES = 256
        engine.OVERLAP = 11


def test_exact_source_roles_models_and_all_review_budgets(fixed):
    assert engine.EXAM == 27
    assert engine.UNION_COUNT == 1005
    assert engine.REFERENCE_COUNT == 512
    assert engine.REFERENCE_POSITIVES == 26
    assert engine.ENRICHED_POSITIVES == 256
    assert engine.OVERLAP == 19
    assert engine.BUDGETS == (5,10,25,50,75,100)
    assert list(engine.MODEL_HASHES) == [
        'original_checkpoint','original_only_continued','expanded_continued'
    ]
    assert engine.MODEL_HASHES['original_checkpoint']=='f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3'
    assert engine.MODEL_HASHES['original_only_continued']=='ae88ccfedc53d8f419b3da8c0c01ca6b61361ef29858b6a536e25408ba99eefb'
    assert engine.MODEL_HASHES['expanded_continued']=='2534d3b7982ee8c557cadc5ad3fcc4c7c4c557f899fa013e881d8655eab97111'


def test_locked_reference_budget_metrics_do_not_select_favorable_percentage(fixed):
    rows=[{'blood':int(i<26)} for i in range(512)]
    ranks={
       'perfect':[1.0-i/512 for i in range(512)],
       'reverse':[i/512 for i in range(512)]
    }
    result=engine.compute_metrics(rows,ranks)
    assert result['n']==512 and result['blood_positive']==26
    assert result['rank_metrics']['perfect']['roc_auc']==1.0
    assert result['rank_metrics']['reverse']['roc_auc']==0.0
    assert result['review_budgets']['5']['selected']==25
    assert result['review_budgets']['10']['selected']==51
    assert result['review_budgets']['25']['selected']==128
    assert result['review_budgets']['50']['selected']==256
    assert result['review_budgets']['75']['selected']==384
    assert result['review_budgets']['100']['selected']==512
    assert result['review_budgets']['10']['blood_positive_images_found']['perfect']==26
    assert result['review_budgets']['10']['blood_positive_images_found']['reverse']==0
    assert result['review_budgets']['100']['blood_positive_images_found']['reverse']==26


def test_source_hash_must_match_before_any_extraction(fixed,tmp_path):
    source=tmp_path/'fake.zip'
    source.write_bytes(b'unsafe')
    with pytest.raises(ValueError,match='source ZIP differs'):
        engine.extract_verified(source,'0'*64,'1'*64,tmp_path/'image_data')
    assert not (tmp_path/'image_data').exists()


def test_reserved_exam_and_duplicated_reference_cannot_be_scored(fixed,tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'UNION_COUNT',1)
    monkeypatch.setattr(engine,'REFERENCE_COUNT',1)
    monkeypatch.setattr(engine,'REFERENCE_POSITIVES',1)
    monkeypatch.setattr(engine,'ENRICHED_COUNT',1)
    monkeypatch.setattr(engine,'ENRICHED_POSITIVES',1)
    monkeypatch.setattr(engine,'OVERLAP',1)
    raw=io.BytesIO()
    Image.new('RGB',(8,8),'red').save(raw,format='PNG')
    data=raw.getvalue()
    for exam in (11,20,25,29,30,61,80):
        archive=tmp_path/f'exam{exam}.zip'
        identity=[{'exam':exam,'frame':0,'filename':'frame_000000.PNG',
                   'blood':1,'reference_uniform':1,'fit_enriched':1,
                   'source_bytes':len(data),'source_image_sha256':hashlib.sha256(data).hexdigest()}]
        manifest=json.dumps(identity).encode()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('verified-private-manifest.json',manifest)
            z.writestr(f'images/{exam:03d}/frame_000000.PNG',data)
        with pytest.raises(ValueError,match='Non-fitting'):
            engine.extract_verified(archive,engine.digest(archive),hashlib.sha256(manifest).hexdigest(),tmp_path/f'staged_{exam}')


def test_valid_exam27_synthetic_source_preserves_exact_image_identity(fixed,tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'UNION_COUNT',1)
    monkeypatch.setattr(engine,'REFERENCE_COUNT',1)
    monkeypatch.setattr(engine,'REFERENCE_POSITIVES',1)
    monkeypatch.setattr(engine,'ENRICHED_COUNT',1)
    monkeypatch.setattr(engine,'ENRICHED_POSITIVES',1)
    monkeypatch.setattr(engine,'OVERLAP',1)
    raw=io.BytesIO()
    Image.new('RGB',(9,7),(70,30,25)).save(raw,format='PNG')
    pixels=raw.getvalue()
    archive=tmp_path/'trusted.zip'
    identity=[{'exam':27,'frame':5,'filename':'frame_000005.PNG',
               'blood':1,'reference_uniform':1,'fit_enriched':1,
               'source_bytes':len(pixels),'source_image_sha256':hashlib.sha256(pixels).hexdigest()}]
    manifest=json.dumps(identity).encode()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('verified-private-manifest.json',manifest)
        z.writestr('images/027/frame_000005.PNG',pixels)
    rows=engine.extract_verified(archive,engine.digest(archive),hashlib.sha256(manifest).hexdigest(),tmp_path/'verified_pixels')
    assert len(rows)==1 and rows[0]['exam']==27 and rows[0]['frame']==5
    assert rows[0]['private_path'].read_bytes()==pixels
