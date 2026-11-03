"""Synthetic-only tests for fixed, source-identity-preserving MobileNet probe."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
base=Path(__file__).resolve().parents[1]/'scripts'/'pretrained_blood_probe.py'
spec=importlib.util.spec_from_file_location('pretrained_blood_probe',base)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_fixed_protocol_identity_and_budgets():
    assert mod.DIMENSIONS==576
    assert mod.MANIFEST_SHA256 == '4d3e0aba675383d1d5441fca0e1b6e0d226a61c2ae30c780c842cfbfd92c40fb'
    assert mod.BUDGETS == (5,10,25,50,75,100)
    assert mod.WEIGHTS_SHA256.startswith('047dcff4')


def test_per_exam_budget_and_no_positive_semantics():
    rows=([{'exam':9,'blood':0} for _ in range(512)]
          +[{'exam':10,'blood':int(i<100)} for i in range(512)])
    scores=[0.5]*512 + [1.0 if i<100 else 0.0 for i in range(512)]
    r=mod.budgets(rows,scores)
    assert r['10']['9']['model_positive_recall'] is None
    assert r['10']['10']['selected']==51
    assert r['10']['10']['model_positive_hits']==51
    assert r['100']['10']['model_positive_hits']==100
    assert r['100']['9']['model_selected_blood_label_negative']==512
    assert r==mod.budgets(rows,scores)


def test_reject_invalid_scores_and_exam_count():
    rows=[{'exam':10,'blood':1} for _ in range(512)]
    with pytest.raises(ValueError,match='finite'):
        mod.budgets(rows,[float('nan')]*512)
    with pytest.raises(ValueError,match='512'):
        mod.budgets(rows[:-1],[0.5]*511)


def test_fixed_training_uses_both_classes_and_never_needs_dev():
    torch=pytest.importorskip('torch')
    gen=torch.Generator().manual_seed(19)
    x=torch.randn(40,576, generator=gen,dtype=torch.float64)
    y=[int(v>0) for v in x[:,0].tolist()]
    h1=mod.fit_linear_probe(x,y)
    h2=mod.fit_linear_probe(x,y)
    assert h1==h2
    assert h1['train_total']==40
    scores=mod.score_probe(x,h1)
    assert len(scores)==40 and all(0<=v<=1 for v in scores)
    assert max(scores)>min(scores)
    # Validation scores do not enter the fitting function.
    with pytest.raises(ValueError,match='Both'):
        mod.fit_linear_probe(x,[0]*len(x))


def test_fail_closed_on_modified_fitted_parameters():
    torch=pytest.importorskip('torch')
    x=torch.zeros((2,576),dtype=torch.float64)
    h={'mean':[0.]*576,'scale':[1.]*576,'weight':[0.]*576,'bias':0.0}
    assert mod.score_probe(x,h)==[0.5,0.5]
    h['scale'][0]=0
    with pytest.raises(ValueError,match='Invalid probe'):
        mod.score_probe(x,h)


def test_frozen_weight_hash_rejected_before_training(tmp_path):
    specfile=tmp_path/'spec.json';specfile.write_text('{}')
    fakeweights=tmp_path/'weights.pth';fakeweights.write_bytes(b'not an official model')
    with pytest.raises(ValueError,match='weights'):
        mod.validate_inputs(tmp_path/'unused',tmp_path,fakeweights,specfile)


def test_existing_output_is_never_overwritten(tmp_path):
    existing=tmp_path/'result';existing.mkdir()
    with pytest.raises(FileExistsError):
        mod.run(tmp_path/'nothing',tmp_path,tmp_path/'weights',tmp_path/'spec',existing,tmp_path/'old')
