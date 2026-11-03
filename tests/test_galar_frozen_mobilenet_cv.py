"""Synthetic tests for frozen full-field pretrained image representation experiments.

Source images/individual labels never enter public Git tests.
"""
from __future__ import annotations
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

np=pytest.importorskip('numpy')
torch=pytest.importorskip('torch')
pytest.importorskip('torchvision')
pytest.importorskip('sklearn')
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import galar_frozen_mobilenet_cv as m

SPEC=ROOT/'docs'/'GALAR_FROZEN_MOBILENET_CV_SPEC.json'


def test_frozen_protocol_and_holdout_partition():
    value=m.validate_spec(SPEC)
    assert value['feature_extractor']['official_pretrained_weights_sha256']==m.WEIGHTS_SHA
    assert set(sum((list(x) for x in m.FOLDS.values()),[]))==set(m.EXAMS)
    for heldout in m.FOLDS.values():
        assert set(heldout).issubset(set(m.EXAMS))
        assert not set(heldout).intersection({9,10,11,12,13,14,15,16,17,18,19,20,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80})


def test_changed_source_spec_must_fail(tmp_path):
    bad=tmp_path/'spec.json'
    bad.write_text(SPEC.read_text().replace('C=0.1','C=10'))
    with pytest.raises(ValueError,match='Frozen methodology'):
        m.validate_spec(bad)


def test_selection_equal_budget_tie_break_by_source_frame():
    labels=np.array([1,0,1,1,0],dtype=np.int64)
    scores=np.array([.2,.8,.8,.8,.1],dtype=np.float64)
    frames=[20,50,30,10,60]
    assert m.fixed_topk(labels,scores,frames,2)==2
    assert m.uniform_count(labels,2)==1
    assert m.fixed_topk(labels,scores,frames,5)==3
    with pytest.raises(ValueError):m.fixed_topk(labels,scores,frames,6)


def test_negative_exam_auc_must_be_undefined():
    metas=[{'exam':3,'frame':5*i,'blood':0} for i in range(512)]
    scores=np.linspace(.1,.9,512)
    value=m.evaluate_exam(3,list(range(512)),scores,metas)
    assert value['blood_positive']==0
    assert value['roc_auc'] is None and value['average_precision'] is None
    assert value['top_k_blood_positive']['51']==0
    assert value['uniform_reference_blood_positive']['51']==0


def test_heldout_exam_must_have_exact_reference_rows():
    metas=[{'exam':1,'frame':i,'blood':i%2} for i in range(511)]
    with pytest.raises(ValueError,match='exactly 512'):
        m.evaluate_exam(1,list(range(511)),np.ones(511),metas)


def test_image_preprocessing_never_crops_original_field():
    img=Image.new('RGB',(16,8),(0,0,0))
    for x in range(2):
        for y in range(8):img.putpixel((x,y),(255,0,0))
    b=io.BytesIO();img.save(b,format='PNG')
    x=m.decode(b.getvalue()).numpy()
    assert x.shape==(3,160,160)
    assert x[0,:,:15].mean()>x[0,:,100:].mean()
    with pytest.raises(ValueError,match='PNG'):
        j=io.BytesIO();img.save(j,format='JPEG');m.decode(j.getvalue())


def test_source_identity_is_verified_before_features(monkeypatch,tmp_path):
    # Dummy visual feature extractor: no original private images required.
    class Dummy(torch.nn.Module):
        def forward(self,x):
            return torch.ones((x.shape[0],576,1,1),dtype=torch.float32)
    monkeypatch.setattr(m,'N',2)
    meta=[{'exam':1,'frame':10,'blood':0,'reference':1,'enriched':1},
          {'exam':1,'frame':15,'blood':1,'reference':1,'enriched':1}]
    bank=np.memmap(tmp_path/'test.bin',dtype=np.float32,mode='w+',shape=(2,576))
    f=m.FeatureWriter(bank,meta,Dummy(),batch_size=2)
    img=Image.new('RGB',(24,24),(50,100,150));buf=io.BytesIO();img.save(buf,format='PNG');raw=buf.getvalue()
    h=hashlib.sha256(raw).hexdigest()
    f.add(1,10,0,1,1,h,raw,len(raw))
    with pytest.raises(ValueError,match='Original publisher image bytes'):
        f.add(1,15,1,1,1,'0'*64,raw,len(raw))
    # No validation is based on synthetic source-label outcomes.
