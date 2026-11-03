"""Executable synthetic failure checks; skipped in core-only CI without Torch."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
pytest.importorskip('torch')

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fit_galar_expanded as fit
import evaluate_galar29_expanded as eva


def test_fitting_refuses_modified_manifest_and_excludes_eval_examination(tmp_path):
    old=tmp_path/'bad.json';old.write_text('{}')
    new=tmp_path/'bad.csv';new.write_text('exam,frame,blood\n29,1,1\n')
    with pytest.raises(ValueError,match='Frozen source'):
        fit.read_rows(old,tmp_path,new,tmp_path)
    assert fit.OLD_EXAMS==frozenset(range(1,9))
    assert fit.FIT_EXAMS==fit.OLD_EXAMS|{21,23,30}
    assert not fit.FIT_EXAMS.intersection(fit.FORBIDDEN)
    assert 29 in fit.FORBIDDEN and 11 in fit.FORBIDDEN and 61 in fit.FORBIDDEN
    assert fit.STEPS==666 and fit.BATCH==32


def test_evaluation_refuses_modified_origins(tmp_path):
    p=tmp_path/'fake-source.zip';p.write_bytes(b'not a valid Galar archive')
    with pytest.raises(ValueError,match='source ZIP SHA'):
        eva.records_from_verified_source(p,tmp_path)
    p=tmp_path/'fake-weights.pt';p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checkpoint identity'):
        eva.predict(p,'a'*64,[])
    assert eva.MODEL_HASHES['original_checkpoint']==fit.ORIGINAL_WEIGHTS_SHA
    assert eva.BUDGETS==(5,10,25,50,75,100)


def test_calculate_budget_without_labels_in_optimization():
    # Ten frames, two positives: independent ranking and positional controls.
    rows=[{'blood':int(i in (5,8))} for i in range(20)]
    a=[1.0 if i in (5,8) else 0.0 for i in range(20)]
    b=[float(i)/20 for i in range(20)]
    table=eva.review_budget(rows,{'good':a,'last_index':b})
    assert table['5']['selected_images']==1
    assert table['5']['hits_by_method']['good']==1
    assert table['10']['selected_images']==2
    assert table['10']['hits_by_method']['good']==2
    assert table['10']['hits_by_method']['uniform']==1
    assert table['100']['hits_by_method']=={'good':2,'last_index':2,'uniform':2}


def test_existing_private_outputs_never_overwritten(tmp_path):
    out=tmp_path/'existing';out.mkdir()
    with pytest.raises(FileExistsError,match='overwrite'):
        fit.run(SimpleNamespace(output=out))
    with pytest.raises(FileExistsError,match='overwrite'):
        eva.evaluate(SimpleNamespace(output=out))
