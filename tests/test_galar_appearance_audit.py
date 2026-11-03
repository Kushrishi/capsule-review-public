"""Actual computation, source-identity and nonidentifying aggregate tests.

Synthetic PNGs only. No patient-level material is distributed to CI.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import galar_appearance_audit as m


def test_exact_frozen_protocol_and_source_roles():
    protocol = Path(__file__).resolve().parents[1] / 'docs/GALAR_APPEARANCE_AUDIT_SPEC.json'
    assert protocol.is_file()
    s = m.load_locked_spec(protocol)
    assert s['population']['exams'] == [25, 27, 29]
    assert list(m.EXAMS) == [25, 27, 29]
    assert tuple(s['population']['positive_support_by_exam'].values()) == (14, 26, 122)
    assert len(m.FEATURES) == 8 and len(m.MODEL_COLUMNS) == 4
    assert s['reference_model_scores']['no_new_inference_or_fitting'] is True


def test_protocol_integrity_refuses_a_changed_byte(tmp_path):
    sample = tmp_path / 'protocol.json'
    sample.write_text('{}\n')
    with pytest.raises(ValueError, match='protocol blob changed'):
        m.load_locked_spec(sample)
    assert m.git_blob_sha(sample.read_bytes()) != m.EXPECTED_SPEC_BLOB


def test_appearance_features_on_known_synthetic_red_and_black():
    red = Image.new('RGB', (96, 96), (255, 0, 0))
    f = m.appearance_features(red)
    assert set(f) == set(m.FEATURES)
    assert f['mean_luminance'] == pytest.approx(0.2126, abs=1e-9)
    assert f['mean_saturation'] == pytest.approx(1.0)
    assert f['mean_positive_red_excess'] == pytest.approx(1.0)
    assert f['mean_edge_difference'] == pytest.approx(0.0)
    assert f['padded_black_fraction'] == pytest.approx(0.0)
    assert f['high_luminance_fraction'] == pytest.approx(0.0)
    assert f['low_luminance_fraction'] == pytest.approx(0.0)
    assert f['source_width_div_height'] == pytest.approx(1.0)
    assert m.original_red_excess(red) == pytest.approx(1.0)

    black = Image.new('RGB', (96, 96), (0, 0, 0))
    b = m.appearance_features(black)
    assert b['low_luminance_fraction'] == b['padded_black_fraction'] == 1.0
    assert b['mean_saturation'] == b['mean_positive_red_excess'] == 0.0
    assert b['mean_edge_difference'] == 0.0

    tall = m.appearance_features(Image.new('RGB', (48, 96), (255, 0, 0)))
    assert tall['source_width_div_height'] == 0.5
    assert 0.48 < tall['padded_black_fraction'] < 0.52


def test_percentile_and_robust_statistics():
    assert m.percentile([1, 3, 5, 7], .25) == 2.5
    assert m.percentile([1, 3, 5, 7], .75) == 5.5
    r = m.describe([1., 3., 5., 7.])
    assert r == {'n':4, 'median':4.0, 'p25':2.5, 'p75':5.5, 'mean':4.0}
    with pytest.raises(ValueError, match='finite'):
        m.describe([])
    with pytest.raises(ValueError, match='Unknown'):
        m.check_binary_label('')
    with pytest.raises(ValueError, match='Unknown'):
        m.check_binary_label('nan')


def make_score_csv(tmp_path, *, label='1', frame='5'):
    fields = ['examination','source_frame','blood_label','original_image_sha256',
              'reference_uniform',*m.MODEL_COLUMNS]
    rawio=io.StringIO()
    writer=csv.DictWriter(rawio, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerow({'examination':'25','source_frame':frame,'blood_label':label,
                     'original_image_sha256':'a'*64,'reference_uniform':'1',
                     **{name:'0.5' for name in m.MODEL_COLUMNS}})
    data=rawio.getvalue().encode()
    src=tmp_path/'repro.zip'
    with zipfile.ZipFile(src,'w') as z:
        z.writestr('private-per-image-scores.csv',data)
    return src, m.digest_bytes(data)


def test_sha_locked_scores_do_not_accept_reserved_studies_or_unknown_labels(tmp_path):
    src,sha=make_score_csv(tmp_path)
    r=m.scores_from_verified_repro(src,25,sha)
    assert len(r)==1 and r[5]['blood']==1
    with pytest.raises(ValueError,match='SHA-256'):
        m.scores_from_verified_repro(src,25,'0'*64)
    with pytest.raises(ValueError,match='unapproved'):
        m.scores_from_verified_repro(src,11,sha)
    folder=tmp_path/'unknown';folder.mkdir()
    invalid,sha=make_score_csv(folder,label='unknown')
    with pytest.raises(ValueError,match='Unknown'):
        m.scores_from_verified_repro(invalid,25,sha)
    folder2=tmp_path/'neg';folder2.mkdir()
    invalid,sha=make_score_csv(folder2,frame='-1')
    with pytest.raises(ValueError,match='unexpected identity'):
        m.scores_from_verified_repro(invalid,25,sha)


def test_aggregate_is_stratified_and_never_promotes_model():
    studies = {}
    for exam,npos in ((25,14),(27,26),(29,122)):
        rows=[]
        for j in range(512):
            p=int(j<npos)
            row={'frame':j*5, 'blood':p,
                 **{name:float(p) for name in m.FEATURES},
                 **{name:float(p) for name in m.MODEL_COLUMNS}}
            rows.append(row)
        studies[exam]=rows
    s={'limits':['one examination is not a separate patient']}
    a=m.aggregate(studies,s)
    assert a['examinations']==[25,27,29]
    assert a['no_training_or_model_selection'] is True
    assert a['independent_clinical_validation'] is False
    assert a['per_image_identifiers_or_pixels_committed'] is False
    assert set(a['features'])==set(m.FEATURES)
    for exam,npos in ((25,14),(27,26),(29,122)):
        case=a['by_examination'][str(exam)]
        assert case['label_counts']=={'0':512-npos,'1':npos}
        assert case['prespecified_feature_descriptives_by_label']['1']['mean_luminance']['median']==1.0
        assert case['prespecified_feature_descriptives_by_label']['0']['mean_luminance']['median']==0.0
        assert case['frozen_model_reference_hits_at_10pct']['original_checkpoint']==min(npos,51)
        assert case['frozen_model_score_positive_minus_negative_median']['expanded_continued']==1.0
    assert not any('frame' in case for case in a['by_examination'].values())


def test_unapproved_source_examination_denied_before_read(tmp_path):
    with pytest.raises(ValueError, match='unapproved'):
        m.read_study_images(tmp_path/'missing.zip',11,{}, {})
