"""Synthetic matching and leakage/feasibility gates, no medical data."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('matched',Path(__file__).parents[1]/'scripts/matched_diversity_ablation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def pool():
    counts=[22,1,0,2,0,6,208,0,1,4,14,26,122,120]
    return [{'exam':e,'frame':i*5,'blood':int(i<p),'sha256':f'{e:02}:{i:04}',
             'tensor_index':j*512+i}
            for j,(e,p) in enumerate(zip(m.FIT_EXAMS,counts)) for i in range(512)]


def test_matching_and_batch_class_pairing():
    arms=m.select_arms(pool())
    a,b=arms.values()
    assert len(a)==len(b)==4096
    assert sum(r['blood'] for r in a)==sum(r['blood'] for r in b)==239
    assert [r['blood'] for r in a]==[r['blood'] for r in b]
    assert len({r['exam'] for r in b if r['blood']})==11
    assert max(sum(r['blood'] for r in b if r['exam']==e) for e in m.FIT_EXAMS)==55
    assert len({r['sha256'] for r in b})==4096
    assert m.select_arms(list(reversed(pool())))==arms


def test_infeasible_class_count_stops():
    with pytest.raises(ValueError,match='Insufficient'):
        m.balanced_sample([{'exam':1,'frame':5,'blood':1,'sha256':'a'}],2,1)


@pytest.mark.parametrize('kind',['exam','duplicate','label'])
def test_input_leaks_fail(kind):
    rows=pool()
    if kind=='exam':rows[0]['exam']=31
    if kind=='duplicate':rows[0]['sha256']=rows[1]['sha256']
    if kind=='label':rows[0]['blood']=None
    with pytest.raises(ValueError):m.select_arms(rows)
