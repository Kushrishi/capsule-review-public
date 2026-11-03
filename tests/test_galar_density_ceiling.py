"""Source-only density audit checks, including protected annotation access."""
import csv
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import galar_density_ceiling as d


def rows(count=1000, positive=None):
    positive = set(positive or [])
    return [(5*i,'1' if i in positive else '0') for i in range(count)]


def write_zip(path, exam=23, sequence=None, forbidden=True):
    sequence = sequence if sequence is not None else rows()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=['frame','blood'],lineterminator='\n')
    writer.writeheader()
    for frame, label in sequence:
        writer.writerow({'frame':frame,'blood':label})
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr(f'{exam}.csv',buf.getvalue())
        if forbidden:
            archive.writestr('11.csv','frame,blood\n0,1\n')
            archive.writestr('61.csv','frame,blood\n0,1\n')


def test_uniform_rule_and_fail_closed_size():
    assert d.uniform_positions(20, 4) == [2, 7, 12, 17]
    assert d.uniform_positions(5, 5) == [0,1,2,3,4]
    with pytest.raises(ValueError): d.uniform_positions(5, 6)
    with pytest.raises(ValueError): d.uniform_positions(0, 0)


def test_source_gaps_break_runs_and_unknowns_not_negative():
    data = [(0,'1'),(5,'1'),(10,''),(15,'1'),(20,'0'),(35,'1'),(45,'1')]
    assignment, lengths = d.run_identities(data)
    assert lengths == [2,1,1,1]
    assert assignment == [0,0,None,1,None,2,3]


def test_sparse_candidates_miss_short_runs_and_oracle_is_bound():
    positive = list(range(100,120)) + [321,700,800]
    outcome = d.analyze_exam(rows(1000,positive), 'synthetic')
    assert outcome['original_positive_annotation_runs'] == 4
    assert outcome['original_run_length_strata'] == {'short_1_5':3,'medium_6_25':1,'long_26_plus':0}
    assert outcome['densities']['all']['representable_annotation_runs'] == 4
    for density in outcome['densities'].values():
        assert density['representable_annotation_runs'] <= 4
        for budget, result in density['fixed_workload'].items():
            assert result['uniform_review_distinct_runs'] <= result['label_privileged_max_distinct_runs']
            assert result['selected_frames'] == int(budget)


def test_negative_examination_is_undefined_recall_not_perfect():
    value = d.analyze_exam(rows(1000), 'synthetic')
    assert value['original_positive_annotation_runs'] == 0
    assert value['densities']['512']['representable_run_recall'] is None
    assert value['densities']['1024']['fixed_workload']['51']['uniform_review_run_recall'] is None
    assert value['densities']['all']['fixed_workload']['512']['uniform_review_positive_frames'] == 0


def test_csv_access_explicitly_forbids_holdout_and_crc_archive_traversal(tmp_path,monkeypatch):
    path=tmp_path/'synth.zip'
    write_zip(path)
    with zipfile.ZipFile(path,'r') as archive:
        assert len(d.parse_allowed_csv(archive,23)[0]) == 1000
        with pytest.raises(ValueError,match='Forbidden'):
            d.parse_allowed_csv(archive,11)
        with pytest.raises(ValueError,match='Forbidden'):
            d.parse_allowed_csv(archive,61)
        def unexpected(*args,**kwargs):
            raise AssertionError('Attempted archive-wide CRC traversal')
        monkeypatch.setattr(archive,'testzip',unexpected)
        assert len(d.parse_allowed_csv(archive,23)[0]) == 1000


def test_corrupt_source_identity_and_unsupported_annotation_stride(tmp_path):
    p=tmp_path/'bad.zip'
    write_zip(p,sequence=[(i, '0') for i in range(1000)],forbidden=False)
    with zipfile.ZipFile(p,'r') as archive:
        with pytest.raises(ValueError, match='stride'):
            d.parse_allowed_csv(archive,23)
    p2=tmp_path/'source.zip'
    write_zip(p2)
    with pytest.raises(ValueError,match='size/SHA'):
        d.execute(p2,{})


def test_spec_matches_immutable_frozen_blob():
    p=Path(__file__).resolve().parents[1]/'docs'/'GALAR_DENSITY_CEILING_SPEC.json'
    spec=d.validate_spec(p)
    assert spec['expected_512_reference_positive_counts']['23'] == 4
    assert spec['expected_512_reference_positive_runs']['25'] == 3


def test_aggregate_preserves_examination_as_unit_and_fixed_workloads():
    a=d.analyze_exam(rows(1000,[2,3,5,90]),'a')
    b=d.analyze_exam(rows(1000),'b')
    summary=d.aggregate({'a':a,'b':b})
    for size in ('512','1024','2048','4096','8192','all'):
        for k in (51,128,256,512):
            assert summary[size]['fixed_workload'][str(k)]['total_selected_frames'] == 2*k
            assert summary[size]['fixed_workload'][str(k)]['forced_source_blood_negative_selected_frames'] == k
