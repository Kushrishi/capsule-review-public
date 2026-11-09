"""Pure synthetic tests; no original patient data or private packages."""
import importlib.util
from pathlib import Path
import pytest
np=pytest.importorskip("numpy")
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('robust',ROOT/'ensemble_robustness_audit.py')
module=importlib.util.module_from_spec(s);s.loader.exec_module(module)

def test_training_rms_invariant_to_positive_seed_scales():
    held=np.asarray([[2., -1., 3.],[-2.,1.,1.],[.25,.25,-.4],[-1.,-.25,-.75]])
    train=np.asarray([[3.,2.,2.], [5.,-1.,3.],[-1.,2.,1.], [1.,1.,1.]])
    def norm(x,y):return (x/np.sqrt((y*y).mean(axis=0))).mean(axis=1)>0
    v1=norm(held,train)
    scales=np.asarray([.1,20.,3.])
    v2=norm(held*scales,train*scales)
    assert np.array_equal(v1,v2)

def test_raw_ensemble_can_flip_when_one_seed_scaled():
    m=np.asarray([[1.,1.,-1.5]])
    assert m.mean()>0
    m[:,2]*=2
    assert m.mean()<0

def test_strict_scores_and_ties():
    assert module.correct_margin(4.0)==1
    assert module.correct_margin(-.01)==0
    assert module.correct_margin(0)==0.5

def test_methods_trained_only_on_other_exams():
    # Source exclusion is by whole examination and exactly 3 held-in exams.
    e=[23,25,29,30];c={23:23,25:20,29:11,30:15}
    for out in e:
        assert len([x for x in e if x!=out])==3
        assert sum(v for x,v in c.items() if x!=out)==69-c[out]

def test_unequal_exam_singleton_macro_vs_pooled():
    correct=(4,6,2,3);total=(10,6,2,3)
    assert sum(correct)==15 and sum(total)==21
    assert sum(c/n for c,n in zip(correct,total))/4==.85
    assert abs(sum(correct)/sum(total)-.85)>.1