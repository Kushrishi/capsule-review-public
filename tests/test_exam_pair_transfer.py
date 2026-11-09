import sys
from pathlib import Path
import pytest

torch = pytest.importorskip('torch')

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from exam_heldout_pair_transfer import fold_indices, shuffled_cycles
from evaluate_exam_pair_transfer import pair_metrics

def test_entire_exam_removed_from_core_and_pairs():
    m={'images':[{'exam':e,'sha256':str(i)} for i,e in enumerate([21,21,23,23,25])],
       'core_indices':[0,2,4],
       'pairs':[{'exam':21,'run_id':1,'positive_index':0,'negative_index':1},
                {'exam':23,'run_id':1,'positive_index':2,'negative_index':3}]}
    core,train,held=fold_indices(m,21)
    assert core==[2,4] and len(train)==len(held)==1
    m['images'][2]['sha256']='0'
    with pytest.raises(ValueError,match='byte identity'):
        fold_indices(m,21)

def test_shuffled_cycles_balance_and_reproduce():
    x=shuffled_cycles(11,8192,17)
    assert torch.equal(x,shuffled_cycles(11,8192,17))
    count=torch.bincount(x)
    assert int(count.max()-count.min())<=1
    with pytest.raises(ValueError):shuffled_cycles(0,1,17)

def test_ties_singletons_and_nonfinite():
    x=pair_metrics([1,0,-2],[1,2,1])
    assert x['ordering']==.5 and x['singleton_ordering']==.5
    assert x['correct']==1 and x['ties']==1
    with pytest.raises(ValueError):pair_metrics([float('nan')],[1])
