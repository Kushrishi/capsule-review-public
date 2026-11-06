import importlib.util
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('benchmark_source_assessment',ROOT/'scripts/assess_benchmark_sources.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def source(values):
    return ('frame,blood,active bleeding,hematin\n'+'\n'.join(','.join(map(str,r)) for r in values)+'\n').encode()

def test_reference_runs_not_clinical_events_and_target_overlap():
    r=m.assess_rows(source([(0,1,0,0),(5,0,1,0),(10,1,1,0),(15,0,0,1)]),stride=5)
    assert r['positive_runs']==2 and r['run_lengths']['singleton']==2
    assert r['between_run_negative_gap_counts']=={'one_negative':1}
    assert r['label_relationship_counts']['active_bleeding_without_blood_label']==1
    assert not r['clinical_events_adjudicated']

def test_source_gap_splits_positive_runs_without_inventing_negative():
    r=m.assess_rows(source([(0,1,1,0),(10,1,0,0)]),stride=5)
    assert r['positive_runs']==2 and r['internal_source_gaps']==1
    assert r['between_run_negative_gap_counts']=={'source_discontinuity':1}

@pytest.mark.parametrize('rows',[[(0,'',0,0)],[(0,0,'',0)],[(0,0,0,'x')],[(5,1,0,0),(5,0,0,0)]])
def test_unknown_or_duplicate_fails_closed(rows):
    with pytest.raises(ValueError):m.assess_rows(source(rows),stride=5)

def test_zero_blood_is_not_an_assertion_of_normal_examination():
    r=m.assess_rows(source([(0,0,1,0),(1,0,0,1)]),stride=1)
    assert r['positive_runs']==0 and r['label_relationship_counts']['active_bleeding_positive']==1

def test_exhaustive_budget_uses_shared_blocks():
    import json
    index=json.loads((ROOT/'experiments/galar-31-40-index-20261105/aggregate.json').read_text())
    r=m.enumerate_costs(index)
    assert r['all_nonempty_new_case_subsets_evaluated']==255
    assert r['minimum_support_floor_cohort']['examinations']==[31,34,37]
    assert r['minimum_support_floor_cohort']['incremental_bytes']==14_065_827_988
    assert r['support_floor_subsets_within_budget']==0

@pytest.mark.parametrize('payload,stride',[(b'frame,blood,active bleeding,hematin\n',5),(b'frame,blood,active bleeding,hematin\n,,,\n',5),(source([(0,1,0,0)]),True)])
def test_empty_identity_or_boolean_stride_is_not_qualified(payload,stride):
    with pytest.raises(ValueError):m.assess_rows(payload,stride=stride)
