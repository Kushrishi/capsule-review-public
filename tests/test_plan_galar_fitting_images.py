"""Synthetic fitting-only Galar sampling tests; never read unseen evaluation CSVs."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import plan_galar_fitting_images as m


def example_rows(n=100, positive_ranges=((10,13),(50,60))):
    return [{'frame': i*5, 'blood': '1' if any(lo<=i<hi for lo,hi in positive_ranges) else '0'} for i in range(n)]


def make_fixture(tmp_path, *, gap_exam23=False):
    p=tmp_path/'source.zip'
    with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for exam in m.TRAIN_POOL:
            output=io.StringIO()
            w=csv.DictWriter(output,fieldnames=['frame','blood'],lineterminator='\n')
            w.writeheader()
            rows=example_rows() if exam in (21,23,27,30) else example_rows(positive_ranges=())
            if gap_exam23 and exam==23:
                rows[20:22]=[]
            w.writerows(rows)
            z.writestr(f'{exam}.csv',output.getvalue())
        # Forbidden label contents intentionally invalid. Must NOT be read.
        z.writestr('11.csv', 'do-not-open')
        z.writestr('61.csv', 'do-not-open')
    return p


def test_uses_only_fitting_examinations_and_returns_no_frame_ids_publicly(tmp_path,monkeypatch):
    source=make_fixture(tmp_path)
    monkeypatch.setattr(m,'SOURCE_SHA256',m.hash_file(source))
    x=m.plan(source,tmp_path/'output',per_exam=32)
    assert x['overall']['examinations']==10
    assert x['overall']['positive_examinations']==4
    assert x['overall']['annotated_positive_runs']==8
    assert x['overall']['annotated_positive_runs_covered_in_enriched']==8
    assert x['sampling']['no_holdout_access'] is True
    assert x['private_original_frame_identifiers_committed'] is False
    assert 'frame' not in x['per_examination']['21']
    with (tmp_path/'output'/'requested_frames.csv').open() as f:
        rows=list(csv.DictReader(f))
    assert {int(r['exam']) for r in rows}==set(m.TRAIN_POOL)
    assert all(r['blood'] in {'0','1'} for r in rows)
    assert sum(int(r['reference_uniform']) for r in rows)==32*10
    assert sum(int(r['fit_enriched']) for r in rows)==32*10
    assert hashlib.sha256((tmp_path/'output'/'requested_frames.csv').read_bytes()).hexdigest()==x['private_request_sha256']


def test_unknown_label_not_a_negative():
    rows=example_rows(20,positive_ranges=((1,4),))
    for index in (5,6,7):rows[index]['blood']=''
    selection=m.choose_enriched(rows,12)
    assert all(rows[i]['blood']!='' for i in selection)
    assert sum(rows[i]['blood']=='1' for i in selection)==3
    assert len(selection)==12


def test_first_representative_from_each_positive_run():
    rows=example_rows(100,positive_ranges=((0,1),(10,11),(25,27),(50,61),(80,85)))
    picks=m.choose_enriched(rows,32)
    assert sum(rows[i]['blood']=='1' for i in picks)==16
    for run in m.positive_runs(rows):
        assert picks & set(run)
    assert picks==m.choose_enriched(rows,32)


def test_source_gaps_do_not_join_runs():
    rows=[{'frame':0,'blood':'1'}, {'frame':5,'blood':'1'},
          {'frame':15,'blood':'1'}, {'frame':20,'blood':'1'}]
    assert [len(run) for run in m.positive_runs(rows)]==[2,2]


def test_label_blind_uniform_positions_do_not_use_positive_locations():
    y=example_rows(n=32)
    z=example_rows(n=32,positive_ranges=((0,32),))
    a=m.uniform_indices(len(y),8)
    b=m.uniform_indices(len(z),8)
    assert a==b
    assert a==sorted(set(a))


def test_holdout_access_rejected(tmp_path):
    p=make_fixture(tmp_path)
    with zipfile.ZipFile(p) as z:
        for i in [1,9,10,11,12,20,31,61,80]:
            with pytest.raises(ValueError,match='non-fitting'):
                m.read_exam(z,i)


def test_bad_source_checksum_rejected(tmp_path):
    p=make_fixture(tmp_path)
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        m.plan(p,tmp_path/'out',per_exam=32)


def test_existing_private_plan_preserved(tmp_path,monkeypatch):
    p=make_fixture(tmp_path);monkeypatch.setattr(m,'SOURCE_SHA256',m.hash_file(p))
    d=tmp_path/'out';d.mkdir()
    with pytest.raises(FileExistsError,match='exists'):
        m.plan(p,d,per_exam=32)


def test_source_gaps_supported_but_modality_guard_is_strict(tmp_path,monkeypatch):
    p=make_fixture(tmp_path,gap_exam23=True)
    monkeypatch.setattr(m,'SOURCE_SHA256',m.hash_file(p))
    x=m.plan(p,tmp_path/'out',per_exam=32)
    assert x['overall']['examinations']==10
    assert x['per_examination']['23']['annotation_rows']==98
    assert x['per_examination']['30']['source_frame_stride']==5


def test_invalid_input_params(tmp_path,monkeypatch):
    p=make_fixture(tmp_path);monkeypatch.setattr(m,'SOURCE_SHA256',m.hash_file(p))
    with pytest.raises(ValueError,match='target'):
        m.plan(p,tmp_path/'out',per_exam=1)
    with pytest.raises(ValueError,match='fraction'):
        m.plan(p,tmp_path/'out',per_exam=32,positive_fraction=1.0)


def test_modest_source_frame_distances_are_not_fake_durations():
    rows=example_rows(50,positive_ranges=((1,2),(3,6)))
    assert len(m.positive_runs(rows))==2
    assert sum(len(x) for x in m.positive_runs(rows))==4


def test_fails_malformed_missing_labels(tmp_path):
    path=tmp_path/'labels.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('21.csv','frame,blood\n0,?\n5,0\n')
    with zipfile.ZipFile(path) as z:
        with pytest.raises(ValueError,match='Malformed'):
            m.read_exam(z,21)


def test_fails_duplicate_frame_identifiers(tmp_path):
    path=tmp_path/'labels.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('21.csv','frame,blood\n0,1\n0,0\n')
    with zipfile.ZipFile(path) as z:
        with pytest.raises(ValueError,match='Unexpected'):
            m.read_exam(z,21)