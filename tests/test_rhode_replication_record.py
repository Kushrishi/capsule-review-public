"""Independent arithmetic and identity checks; no raw medical data needed."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from statistics import mean
import math

import pytest

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/'experiments'/'rhode-replication'
SPEC_HASH='c92500af677a12323ea5b8ebf43feb1b17f41bcf44ccfa80e94f28a19289399e'
EXPECTED_BYTES={'s280':103418092,'s284':115960292}
EXPECTED_CRC={'s280':'1a870799','s284':'6f1947e6'}


def load_data():
    return {s:json.loads((RECORD/f'{s}-results.json').read_text()) for s in EXPECTED_BYTES}


def test_frozen_protocol_and_split_identity():
    raw=(ROOT/'docs'/'SEQUENCE_SELECTION_SPEC.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SPEC_HASH
    x=json.loads(raw)
    assert [p['study'] for p in x['future_studies_selected_without_examining_images_or_labels']]==['s280','s284']
    for d in x['future_studies_selected_without_examining_images_or_labels']:
        assert d['source_member_bytes']==EXPECTED_BYTES[d['study']]


def test_verified_archive_receipts_are_bound_to_results():
    r=json.loads((RECORD/'acquisition-receipt.json').read_text())
    assert r['spec_sha256']==SPEC_HASH
    assert r['outer_archive_bytes']==5987150542
    assert r['cumulative_data_transfer_upper_bound_bytes']<r['cumulative_budget_bytes']==512*1024*1024
    assert r['cumulative_data_transfer_upper_bound_bytes']==(r['previous_acquisition_conservative_upper_bound_bytes']+r['new_data_transfer_bytes_upper_bound'])
    assert {a['study'] for a in r['studies']}==set(EXPECTED_BYTES)
    for id,row in load_data().items():
        a=next(x for x in r['studies'] if x['study']==id)
        assert a['inner_zip_crc_passed']
        assert a['member_bytes']==row['source_zip_bytes']==EXPECTED_BYTES[id]
        assert a['sha256']==row['source_zip_sha256']
        assert a['source_crc32']==EXPECTED_CRC[id]
        assert len(a['sha256'])==64


@pytest.mark.parametrize('id',list(EXPECTED_BYTES))
def test_real_study_outputs_obey_exact_preselected_budgets(id):
    r=load_data()[id]
    assert r['study']==id
    assert r['anatomy_boundary_count']==3 and r['source_indices_complete']
    assert r['source_index_last']-r['source_index_first']+1==r['image_count']
    assert len(r['budget_results'])==3
    assert sum(r['anatomy_counts'].values())==r['image_count']
    for row,budget in zip(r['budget_results'],[0.05,0.10,0.25]):
        assert row['budget']==budget
        assert row['k']==math.ceil(budget*r['image_count'])
        for name,stat in row['methods'].items():
            if name=='random_anchored':
                assert stat['draws']==100
                assert 0<=stat['boundary_hits_mean']['5']<=3
            else:
                assert stat['selected_count']==row['k']
                assert stat['boundary_count']==3
                assert stat['boundary_hits']['0']<=stat['boundary_hits']['2']<=stat['boundary_hits']['5']<=3
                assert stat['max_nearest_position_distance'] >= 0


def test_nonclinical_summary_regenerates_exactly_from_three_studies():
    modulepath=ROOT/'scripts'/'summarize_rhode_replication.py'
    spec=importlib.util.spec_from_file_location('summarize_rhode_replication',modulepath)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    a=load_data();a['s288']=json.loads((ROOT/'experiments'/'rhode-s288'/'sequence_selection_results.json').read_text())
    assert mod.summarize(a)==json.loads((RECORD/'three-study-summary.json').read_text())


def test_preselected_studies_do_not_repeat_exploratory_5pct_result():
    a=load_data()
    # The earlier stratified-change s288 pilot reached 3/3. Neither future study did.
    assert [a[s]['budget_results'][0]['methods']['stratified_change']['boundary_hits']['5'] for s in ('s280','s284')]==[1,2]
    # Uniform at 10% reached all three in both new studies.
    assert [a[s]['budget_results'][1]['methods']['uniform']['boundary_hits']['5'] for s in ('s280','s284')]==[3,3]
