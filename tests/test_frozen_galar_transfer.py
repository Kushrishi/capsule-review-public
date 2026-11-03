"""Local synthetic guards for original-model transfer, without private medical images."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import frozen_galar_transfer as m


def test_frozen_protocol_was_committed_and_cannot_be_rewritten(tmp_path):
    spec=ROOT/'docs/GALAR_FROZEN_TRANSFER_SPEC.json'
    a=m.validate_frozen_spec(spec)
    assert a['strict_separation']['allowed_evaluation_ids']==[21,23,30]
    assert '11–20' in a['strict_separation']['disallowed_ids']
    assert a['historical_frozen_cnn']['weights_sha256']==m.MODEL_SHA256
    edited=tmp_path/'changed.json'
    edited.write_bytes(spec.read_bytes().replace(b'"version": "1.0"',b'"version": "2.0"'))
    with pytest.raises(ValueError,match='frozen transfer spec'):
        m.validate_frozen_spec(edited)


def test_prior_history_cannot_be_replaced_by_untrusted_manifest(tmp_path):
    p=tmp_path/'fake.json';p.write_text(json.dumps({'records':[],'sha256':m.FROZEN_SOURCE_MANIFEST_SHA256}))
    with pytest.raises(ValueError,match='source bytes changed'):
        m.load_historical_pixel_sha(p)


def test_reference_ranking_fixed_budgets_and_ties():
    rows=[{'frame':i,'blood':int(i in (0,3))} for i in range(8)]
    scores=[0.9,0.0,0.0,0.9,0.0,0.0,0.0,0.0]
    # Two equal positive scores => stable tie-break by original increasing source index.
    for pct,k in [(5,0),(10,0),(25,2),(50,4),(75,6),(100,8)]:
        r=m.rank_hits(rows,scores)[str(pct)]
        assert r['selected_images']==k
        assert r['blood_positive_images']==(0 if k==0 else 2)
        assert r['positive_images_total']==2


def test_uniform_budget_does_not_look_at_blood_label():
    rows=[{'frame':i,'blood':int(i%3==0)} for i in range(8)]
    out=m.uniform_rank_hits(rows)
    assert out['25']['selected_images']==2
    assert out['25']['blood_positive_images']==1  # positions 2 and 6, only 6 positive
    assert out['100']['blood_positive_images']==3


def test_frozen_only_sources_no_reserved_and_no_duplicate_replacement(tmp_path):
    with pytest.raises(ValueError,match='Exactly the three prespecified'):
        m.extract_source_archives({21:tmp_path/'a',23:tmp_path/'b',61:tmp_path/'held-out'},tmp_path,set())
    with pytest.raises(ValueError,match='Exactly the three prespecified'):
        m.extract_source_archives({21:tmp_path/'a',23:tmp_path/'b'},tmp_path,set())
    spec=ROOT/'docs/GALAR_FROZEN_TRANSFER_SPEC.json'
    with pytest.raises(ValueError,match='Never place original medical images'):
        m.execute({21:tmp_path/'a',23:tmp_path/'b',30:tmp_path/'c'},tmp_path/'weights',tmp_path/'prior',ROOT/'private-pixels',tmp_path/'result.json',spec)


def test_summary_reports_all_three_positive_examinations_no_cherry_picking():
    records=[]
    for exam,pos in ((21,1),(23,4),(30,120)):
        for i in range(512):
            label=int(i<pos)
            records.append({'exam':exam,'frame':i*5,'blood':label,'reference_uniform':1,
                            'score_cnn':0.95 if label else 0.05,'score_red':0.95 if label else 0.05})
    output=m.summarize(records,{'pixel_identity_overlap_with_original_1_to_10':0})
    assert list(output['per_examination'])==['21','23','30']
    assert output['label_blind_total']['positive']==125
    assert output['enriched_union_secondary']['positive']==125
    assert output['per_examination']['21']['reference_support']['blood_positive']==1
    assert output['per_examination']['23']['reference_support']['blood_positive']==4
    assert output['per_examination']['30']['reference_support']['blood_positive']==120
    assert output['per_examination']['30']['reference_cnn']['budgets']['10']['selected_images']==51
    assert output['per_examination']['30']['reference_cnn']['budgets']['100']['blood_positive_images']==120
    assert output['model_training'].startswith('Original CNN')
    assert output['experimental_status'].startswith('post-acquisition')


def test_result_checks_are_not_reclassified_as_patient_level():
    d=(ROOT/'docs/GALAR_FROZEN_TRANSFER_SPEC.json').read_text(encoding='utf-8')
    assert 'not confirmed unique patient' in d
    assert 'not a blinded preregistration' in d
