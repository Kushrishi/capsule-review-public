import sys
from pathlib import Path
import pytest
torch=pytest.importorskip('torch')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from short_event_support_comparison import balanced_pair_schedule

def test_equal_exam_exposures_without_repeating_runs_as_new_units():
    pairs=[{'exam':e} for e,n in ((23,23),(25,20),(29,11),(30,15)) for _ in range(n)]
    ix=balanced_pair_schedule(pairs,23,17)
    assert torch.equal(ix,balanced_pair_schedule(pairs,23,17))
    counts={e:sum(pairs[i]['exam']==e for i in ix.tolist()) for e in (25,29,30)}
    assert max(counts.values())-min(counts.values())<=1 and len(ix)==8192
    assert all(pairs[i]['exam']!=23 for i in ix.tolist())
    for e in counts:
        c=[int((ix==j).sum()) for j,p in enumerate(pairs) if p['exam']==e]
        assert min(c)>0 and max(c)-min(c)<=1

def test_unsupported_fold_refused():
    with pytest.raises(ValueError):balanced_pair_schedule([{'exam':23}],23,17)
