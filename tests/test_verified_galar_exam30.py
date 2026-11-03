"""Verify measured examination-30 acquisition totals using frozen source/selection receipts.

Repository CI uses only aggregate metadata, never original medical images or labels.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'experiments/galar-21-30-source-index'
PLAN = ROOT / 'experiments/galar-21-30-selection/aggregate.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_exam30_source_receipt_matches_frozen_image_request_and_verified_index():
    new = read(SOURCE / 'verified-exam30.json')
    earlier = read(SOURCE / 'verified-acquisition-summary.json')
    layout = read(SOURCE / 'layout.json')
    plan = read(PLAN)
    e = plan['per_examination']['30']

    assert new['record_type'] == 'galar-exam30-multiblock-fitting-source-verification-v1'
    assert new['source_file_id'] == layout['origin_file_id'] == 45258019
    assert new['official_archive_bytes'] == layout['archive_bytes'] == 31_989_399_751
    assert new['corrected_label_zip_sha256'] == plan['official_corrected_labels_sha256']
    assert new['frozen_private_selection_sha256'] == plan['private_request_sha256']
    assert new['official_full_md5_expected_not_verified'] == earlier['original_archive_md5_expected_not_verified']
    assert new['scientific_role'].startswith('Known fitting-candidate')

    assert new['examination'] == 30
    assert new['verified_png_images'] == e['unique_requested_images'] == 1006
    assert new['enriched_fit_candidates'] == e['enriched_training_candidates'] == 512
    assert new['enriched_positive_candidates'] == e['enriched_positive_candidates'] == 256
    assert new['label_blind_uniform_reference_candidates'] == e['label_blind_reference_candidates'] == 512
    assert new['label_blind_uniform_positive_candidates'] == e['reference_positive_candidates'] == 120
    assert new['enriched_uniform_overlap_images'] == e['dual_purpose_overlap'] == 18
    assert new['verified_png_images'] == 512 + 512 - 18
    assert new['annotated_positive_runs_with_enriched_representative'] == e['annotated_positive_runs'] == 47
    assert new['positive_overlap_images'] == 10
    assert new['explicit_blood_positive_images'] == (
        new['enriched_positive_candidates'] + new['label_blind_uniform_positive_candidates']
        - new['positive_overlap_images']) == 366

    lengths = 0
    assert [x['block_id'] for x in new['selected_blocks']] == [8,9]
    for info in new['selected_blocks']:
        idx = info['block_id']
        block = layout['blocks'][idx]
        assert info['compressed_bytes'] == block['compressed_bytes']
        assert info['offset'] == 32 + sum(x['compressed_bytes'] for x in layout['blocks'][:idx])
        assert block['examinations']['30'] in (13_957, 2_996)
        assert len(info['source_sha256']) == 64
        assert all(c in '0123456789abcdef' for c in info['source_sha256'])
        lengths += info['compressed_bytes']
    assert lengths == 4_144_258_625
    for key in ('nested_source_zip_sha256','private_manifest_sha256','retained_outer_artifact_sha256'):
        assert len(new[key]) == 64
        assert all(c in '0123456789abcdef' for c in new[key])

    combined = new['cumulative_new_exam_acquisition']
    old = earlier['combined']
    assert combined['examinations'] == [21,23,30]
    assert combined['verified_png_images'] == old['unique_png_images'] + new['verified_png_images'] == 3000
    assert combined['blood_positive_images'] == old['explicit_blood_positive_images'] + new['explicit_blood_positive_images'] == 514
    assert combined['total_original_png_bytes'] == old['total_saved_png_bytes'] + new['original_png_bytes'] == 882_604_279
    assert combined['confirmed_unique_patients'] is False
    assert 'run' in new['github_acquisition_run']
    assert 'independent' in new['verification']


def test_no_patient_images_or_private_frame_records_enter_repo():
    assert not any(x.suffix.lower() in {'.png','.jpg','.jpeg','.zip','.7z','.pt','.csv'}
                   for x in SOURCE.rglob('*') if x.is_file())
    record = read(SOURCE / 'verified-exam30.json')
    assert isinstance(record['verified_png_images'], int)
    assert 'frames' not in record
    assert 'private_artifact_location' in record
    assert record['official_full_md5_expected_not_verified']
