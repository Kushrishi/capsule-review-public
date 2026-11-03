"""Public aggregate arithmetic and transfer-replay provenance tests (no private data)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'experiments/galar-frozen-transfer-2026-11-02'


def load(name):return json.loads((RUN/name).read_text(encoding='utf-8'))


def test_result_replays_are_bound_to_exact_aggregate_file():
    result_path=RUN/'aggregate.json'
    result=load('aggregate.json')
    verification=load('verification.json')
    protocol=json.loads((ROOT/'docs/GALAR_FROZEN_TRANSFER_SPEC.json').read_text(encoding='utf-8'))
    assert verification['aggregate_sha256']==hashlib.sha256(result_path.read_bytes()).hexdigest()
    assert verification['verified_model_sha256']==result['model_weights_sha256']==protocol['historical_frozen_cnn']['weights_sha256']
    assert verification['private_score_sha256']=='caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812'
    assert verification['clinical_validation'] is False
    assert verification['original_historical_replay']['historical_frames_replayed']==1024
    assert verification['original_historical_replay']['historical_cnn_max_abs_score_error']<1e-7
    assert verification['new_fitting_exam_replay']['new_fitting_images_replayed']==3000
    assert verification['new_fitting_exam_replay']['new_cnn_max_abs_score_error']<=1e-7
    assert verification['new_fitting_exam_replay']['per_examination_auc_ap_and_all_six_budgets_recomputed'] is True


def test_new_source_metadata_matches_three_fitting_only_studies():
    aggregate=load('aggregate.json')
    reference=aggregate['label_blind_total']
    union=aggregate['enriched_union_secondary']
    assert set(aggregate['per_examination'])=={'21','23','30'}
    assert reference['images']==1536 and reference['positive']==125
    assert union['images']==3000 and union['positive']==514
    assert aggregate['source_integrity']['pixel_identity_overlap_with_original_1_to_10']==0
    assert aggregate['source_integrity']['new_cross_examination_identical_pixels']==0
    assert aggregate['source_integrity']['21']['unique_images']==993
    assert aggregate['source_integrity']['23']['unique_images']==1001
    assert aggregate['source_integrity']['30']['unique_images']==1006
    assert sum(aggregate['source_integrity'][s]['blood_positive_images'] for s in ('21','23','30'))==514


def test_hard_examination_specific_outcomes_and_no_hidden_negative_comparison():
    aggregate=load('aggregate.json')
    observed={21:(1,0,1,1),23:(4,0,0,0),30:(120,40,28,13)}
    for exam,(n,c,r,u) in observed.items():
        data=aggregate['per_examination'][str(exam)]
        assert data['reference_support']['images']==512
        assert data['reference_support']['blood_positive']==n
        for key,target in (('reference_cnn',c),('reference_redness',r)):
            budget=data[key]['budgets']['10']
            assert budget['selected_images']==51 and budget['blood_positive_images']==target
        assert data['reference_uniform']['budgets']['10']['blood_positive_images']==u
        assert data['reference_cnn']['budgets']['100']['blood_positive_images']==n
    assert aggregate['per_examination']['23']['reference_cnn']['roc_auc']<0.5
    assert aggregate['per_examination']['30']['reference_cnn']['roc_auc']>0.8
    assert aggregate['experimental_status'].startswith('post-acquisition')
    assert any('unique patients' in x for x in aggregate['limitations'])


def test_public_reproducibility_outputs_have_no_private_medical_records():
    for p in RUN.rglob('*'):
        if p.is_file():assert p.suffix.lower()=='.json'
    for entry in (load('aggregate.json'),load('verification.json')):
        serialized=json.dumps(entry)
        for forbidden in ('"frame":', '"filename":', '"source_image_sha256":', '"blood_label":',
                          '"cnn_score":', '"patient_id":'):
            assert forbidden not in serialized
