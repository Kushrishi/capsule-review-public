"""Synthetic checks: blood scores must never overwrite source or reviewer fields."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

script = Path(__file__).resolve().parents[1] / 'scripts/save_blood_predictions.py'
spec = importlib.util.spec_from_file_location('save_blood_predictions', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DummyDB:
    def __init__(self, rows): self.rows=rows
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, *args): return self.rows


class DummyStore:
    def __init__(self, rows, synthetic=False):
        self.rows=rows
        self.synthetic=synthetic
    def study(self, ident):
        return {'frame_count':512,'synthetic':self.synthetic} if ident=='study-test' else None
    def connect(self):return DummyDB(self.rows)


def example_run(tmp_path):
    run=tmp_path/'run';run.mkdir()
    weights=b'non-real-test-weights';(run/'weights.pt').write_bytes(weights)
    digest=hashlib.sha256(weights).hexdigest()
    (run/'metrics.json').write_text(json.dumps({'weights_sha256':digest,'development_examinations':[9,10]}))
    rows=[{'position':i,'source_index':i*5,'source_sha256':f'{i:064x}'} for i in range(512)]
    with (run/'predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['exam','frame','source_sha256','cnn_score'])
        for r in rows:w.writerow([10,r['source_index'],r['source_sha256'],0.75])
    return run,rows


def test_import_keeps_model_suggestions_separate(monkeypatch,tmp_path):
    run,rows=example_run(tmp_path)
    monkeypatch.setattr(module,'Store',lambda _:DummyStore(rows))
    def capture(store, study_id, payload):
        assert study_id=='study-test'
        assert payload.model.name.endswith('(research)')
        assert len(payload.predictions)==512
        assert payload.predictions[0].label==module.LABEL
        assert payload.predictions[0].score==0.75
        return {'run_id':1,'count':len(payload.predictions)}
    monkeypatch.setattr(module,'save_predictions',capture)
    assert module.import_scores(tmp_path,'study-test',10,run)=={'run_id':1,'count':512}


def test_import_rejects_bad_source_identity_and_synthetic_study(monkeypatch,tmp_path):
    run,rows=example_run(tmp_path)
    bad=[dict(r) for r in rows];bad[0]['source_sha256']='f'*64
    monkeypatch.setattr(module,'Store',lambda _:DummyStore(bad))
    with pytest.raises(ValueError,match='hashes/source indices'):
        module.import_scores(tmp_path,'study-test',10,run)
    monkeypatch.setattr(module,'Store',lambda _:DummyStore(rows,synthetic=True))
    with pytest.raises(ValueError,match='real study'):
        module.import_scores(tmp_path,'study-test',10,run)


def test_import_rejects_tampered_weights_and_unapproved_exam(tmp_path):
    run,_=example_run(tmp_path)
    (run/'weights.pt').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='weights'):
        module.import_scores(tmp_path,'study-test',10,run)
    with pytest.raises(ValueError,match='historical development'):
        module.import_scores(tmp_path,'study-test',7,run)
