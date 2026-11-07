"""Synthetic fail-closed checks for the fixed new development cohort."""
import importlib.util
from pathlib import Path
import sys
import zipfile
import io
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('galar313437',SCRIPTS/'run_galar313437_private.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def archive(names):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        for n in names:z.writestr(n,b'synthetic')
    b.seek(0)
    return zipfile.ZipFile(b)


def test_frozen_cohort_and_budgets():
    from capsule_review.unseen_evaluation import exact_k
    assert set(m.COHORT)=={31,34,37}
    assert sum(x[0] for x in m.COHORT.values())==53911
    assert [(exact_k(m.COHORT[e][0],10),exact_k(m.COHORT[e][0],25)) for e in m.COHORT]==[(2492,6230),(1087,2717),(1813,4531)]
    assert m.COHORT[37][1:]==(0,0)


@pytest.mark.parametrize('exam,names',[(61,['images/061/frame_0.PNG']),(31,['images/031/frame_0.PNG']), (31,['images/034/frame_0.PNG']), (31,['source-frame-private-manifest.json'])])
def test_partial_reserved_and_outcome_members_rejected(exam,names):
    with archive(names) as z,pytest.raises(ValueError):m.source_members(z,exam)


def test_complete_stride_and_duplicates_checked(monkeypatch):
    monkeypatch.setitem(m.COHORT,31,(2,0,0))
    with archive(['images/031/frame_0.PNG','images/031/frame_5.PNG']) as z:
        assert [f for f,v in m.source_members(z,31)]==[0,5]
    with archive(['images/031/frame_0.PNG','images/031/frame_10.PNG']) as z,pytest.raises(ValueError):m.source_members(z,31)


def test_retention_required_before_labels(tmp_path):
    with pytest.raises(ValueError,match='readback'):m.verify_retention({},tmp_path)
    with pytest.raises(ValueError):m.verify_retention({'lock_commit':m.LOCK_COMMIT,'all_remote_bytes_readback_verified':True},tmp_path)


def test_private_boundary():
    with pytest.raises(ValueError):m.private_path(SCRIPTS/'forbidden.json')


def test_queue_replay_includes_fixed_temporal():
    frames=list(range(0,200,5));hashes=['a'*64]*40;scores=[float(i%7)/7 for i in range(40)]
    frozen,q=m.queues(frames,hashes,scores)
    assert [x['review_percent'] for x in q]==[5,10,25,50,100]
    for row in q:
        assert set(row['policies'])=={'uniform','score','score_diverse','score_bin'}
        for queue in [*row['policies'].values(),row['temporal_window3_score_bin']]:
            assert len(queue)==len(set(queue))==row['k']


def test_oracle_matching_against_all_small_binary_sequences():
    from itertools import product
    for n in range(1,8):
        for k in range(1,n+1):
            choices=[range(i*n//k,(i+1)*n//k) for i in range(k)]
            for labels in product((0,1),repeat=n):
                runs=[]
                for i,y in enumerate(labels):
                    if y:
                        if i==0 or not labels[i-1]:runs.append([])
                        runs[-1].append(i)
                actual=m.fixed_bin_oracle(runs,n,k)
                optimum=max(sum(bool(set(q).intersection(r)) for r in runs) for q in product(*choices))
                assert actual['maximum_distinct_runs']==optimum
                assert actual['positive_bins']==sum(any(labels[p] for p in c) for c in choices)


def test_oracle_handles_competing_singletons_and_unknown_order():
    assert m.fixed_bin_oracle([[0],[2]],10,1)['maximum_distinct_runs']==1
    assert m.fixed_bin_oracle([],10,1)['run_recall_ceiling'] is None
    with pytest.raises(ValueError):m.fixed_bin_oracle([[2],[1]],10,2)
