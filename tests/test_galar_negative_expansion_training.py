"""Optional numerical smoke tests for the frozen from-scratch CNN; no real source pixels."""
from pathlib import Path
import sys
import pytest
np=pytest.importorskip('numpy')
torch=pytest.importorskip('torch')
pytest.importorskip('sklearn')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import galar_negative_expansion_cv as study


def test_two_update_training_excludes_entire_heldout_exam_and_adds_negatives(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'OUT',tmp_path)
    monkeypatch.setattr(study,'STEPS',2)
    monkeypatch.setattr(study,'BATCH',4)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    # One synthetic 512-frame heldout examination, plus eight tiny fitting exams.
    # 22 and 24 supply negative-only images; exam 7 supplies fit positives.
    meta=[]
    for frame in range(512):
        meta.append({'exam':1,'frame':frame,'blood':int(frame%17==0),'reference':1,'enriched':1})
    for ex in (2,3,4,5,6,7,22,24):
        for frame in range(4):
            meta.append({'exam':ex,'frame':frame,'blood':int(ex==7 and frame==2),'reference':1,'enriched':1})
    rng=np.random.default_rng(4)
    bank=rng.integers(0,256,size=(len(meta),96,96,3),dtype=np.uint8)
    row=study.train(meta,'A',(1,),'pooled_weighted',bank)
    assert row['optimizer_steps']==2
    assert row['batch_size']==4
    assert row['heldout_exams']==[1]
    assert {22,24}.issubset(set(row['fit_exams']))
    assert 1 not in row['fit_exams']
    assert row['fit_blood_positive']==1
    assert row['exam_results']['1']['n']==512
    assert (tmp_path/'A-pooled_weighted.pt').is_file()
    assert (tmp_path/'A-pooled_weighted-private-predictions.json').is_file()
