"""Check that the entire appearance audit is reported, without label fishing.

This checks aggregated, nonidentifying results only. The private PNG/CSV replay
is preserved separately and cannot be reconstructed by public repository CI.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'experiments/galar-appearance-audit-2026-11-02'
EXPECTED_AGGREGATE_SHA = '09a467b518b74eb89162b4c2fece9619486de617fd6a52523d6aa9548848db9d'
EXPECTED_PROTOCOL_BLOB = '60b790cc0919f2d80a2d708c77cb08d162149b32'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def test_protocol_was_committed_before_new_feature_computation():
    spec = ROOT / 'docs/GALAR_APPEARANCE_AUDIT_SPEC.json'
    raw = spec.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert blob == EXPECTED_PROTOCOL_BLOB
    config = json.loads(raw)
    assert config['population']['exams'] == [25,27,29]
    assert config['reference_model_scores']['no_new_inference_or_fitting'] is True
    assert config['reporting']['no_significance_testing'] is True
    assert config['reporting']['no_auc_for_cherry_picked_features'] is True
    assert config['reporting']['no_claim_of_causal_mechanism'] is True
    assert config['population']['patient_independence_known'] is False


def test_immutable_aggregate_and_all_locked_strata_appear():
    original = (RECORD / 'aggregate.json').read_bytes()
    assert hashlib.sha256(original).hexdigest() == EXPECTED_AGGREGATE_SHA
    result = json.loads(original)
    cfg = read(ROOT / 'docs/GALAR_APPEARANCE_AUDIT_SPEC.json')
    assert result['protocol_blob_sha'] == EXPECTED_PROTOCOL_BLOB
    assert result['examinations'] == cfg['population']['exams'] == [25,27,29]
    assert result['independent_clinical_validation'] is False
    assert result['no_training_or_model_selection'] is True
    assert result['patient_independence_confirmed'] is False
    assert result['per_image_identifiers_or_pixels_committed'] is False
    assert result['reference_scope'].startswith('Only previously selected label-blind')
    assert result['features'] == [x['name'] for x in cfg['predefined_appearance_features']]
    assert result['frozen_model_scores'] == cfg['reference_model_scores']['names']
    assert set(result['by_examination']) == {'25','27','29'}
    for exam,positive in ((25,14),(27,26),(29,122)):
        section = result['by_examination'][str(exam)]
        assert section['reference_images'] == 512
        assert section['label_counts'] == {'0':512-positive,'1':positive}
        assert set(section['prespecified_feature_descriptives_by_label']) == {'0','1'}
        for label, support in (('0',512-positive),('1',positive)):
            group = section['prespecified_feature_descriptives_by_label'][label]
            assert set(group) == set(result['features']) | set(result['frozen_model_scores'])
            for v in group.values():
                assert v['n'] == support
                assert all(math.isfinite(v[k]) for k in ('p25','median','p75','mean'))
                assert v['p25'] <= v['median'] <= v['p75']
        hits = section['frozen_model_reference_hits_at_10pct']
        assert set(hits) == set(result['frozen_model_scores'])
        assert all(0 <= v <= min(51,positive) for v in hits.values())
        for name in result['frozen_model_scores']:
            delta = round(section['prespecified_feature_descriptives_by_label']['1'][name]['median'] -
                          section['prespecified_feature_descriptives_by_label']['0'][name]['median'], 6)
            assert delta == section['frozen_model_score_positive_minus_negative_median'][name]
    assert result['by_examination']['25']['frozen_model_reference_hits_at_10pct']['original_checkpoint'] == 0
    assert result['by_examination']['27']['frozen_model_reference_hits_at_10pct']['original_checkpoint'] == 22
    assert result['by_examination']['29']['frozen_model_reference_hits_at_10pct']['expanded_continued'] == 35


def test_reference_only_redness_reversal_and_counterexample_are_preserved():
    report = read(RECORD / 'aggregate.json')['by_examination']
    def med(exam,label,feature):
        return report[str(exam)]['prespecified_feature_descriptives_by_label'][str(label)][feature]['median']
    assert med(25,1,'mean_positive_red_excess') < med(25,0,'mean_positive_red_excess')
    assert med(25,1,'mean_saturation') < med(25,0,'mean_saturation')
    assert med(27,1,'mean_positive_red_excess') > med(27,0,'mean_positive_red_excess')
    assert med(27,1,'mean_saturation') > med(27,0,'mean_saturation')
    # Exam29 is a counterexample to any claim that positive redness alone
    # explains good CNN rankings; the complete negative evidence must remain.
    assert med(29,1,'mean_positive_red_excess') < med(29,0,'mean_positive_red_excess')
    for name in ('original_checkpoint','expanded_continued'):
        assert med(25,1,name) < med(25,0,name)
        assert med(27,1,name) > med(27,0,name)
        assert med(29,1,name) > med(29,0,name)


def test_private_medical_source_and_individual_feature_vectors_not_in_repo():
    assert not any(p.suffix.lower() in {'.png','.jpeg','.jpg','.csv','.zip','.7z','.pt','.sqlite','.db'}
                   for p in RECORD.rglob('*') if p.is_file())
    source = (RECORD/'aggregate.json').read_text()
    assert 'source_frame' not in source and 'source_sha256' not in source
    assert 'private-per-image-features.csv' not in [p.name for p in RECORD.iterdir()]
