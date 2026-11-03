"""Check Galar-29 aggregate evidence against immutable source and selection receipts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'experiments/galar-21-30-source-index'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def test_exam29_acquisition_reconciles_to_original_source_index_and_plan():
    result = read(EVIDENCE / 'verified-exam29.json')
    layout = read(EVIDENCE / 'layout.json')
    plan = read(ROOT / 'experiments/galar-21-30-selection/aggregate.json')
    record = result['independent_private_artifact_verification']
    original = plan['per_examination']['29']
    assert result['source']['official_file_id'] == layout['origin_file_id'] == 45258019
    assert result['source']['full_archive_bytes'] == layout['archive_bytes'] == 31989399751
    assert result['source']['frozen_private_selection_sha256'] == plan['private_request_sha256']
    assert result['acquisition']['examination'] == 29
    assert result['acquisition']['official_png_members_for_exam'] == layout['image_members_by_exam']['29'] == 16018
    assert record['unique_images'] == original['unique_requested_images'] == 1009
    assert record['fit_enriched'] == original['enriched_training_candidates'] == 512
    assert record['uniform_label_blind'] == original['label_blind_reference_candidates'] == 512
    assert record['overlap'] == original['dual_purpose_overlap'] == 15
    assert record['fit_positive'] == original['enriched_positive_candidates'] == 256
    assert record['reference_positive'] == original['reference_positive_candidates'] == 122
    assert record['explicit_blood_positive_images'] == (
        record['fit_positive'] + record['reference_positive'] - record['overlap_positive']) == 372
    assert record['unique_images'] == record['fit_enriched'] + record['uniform_label_blind'] - record['overlap']
    assert record['sha256_verified'] == record['png_decode_verified'] == record['unique_source_ids_verified'] == 1009
    assert record['duplicate_decoded_pixels_vs_prior_8120'] == 0
    assert record['zip_crc_mismatches'] == 0
    assert not result['acquisition']['full_archive_md5_verified']
    assert [b['id'] for b in result['acquisition']['allowed_blocks']] == [7,8]
    for b in result['acquisition']['allowed_blocks']:
        actual = layout['blocks'][b['id']]
        assert b['bytes'] == actual['compressed_bytes']
        assert b['offset'] == 32 + sum(s['compressed_bytes'] for s in layout['blocks'][:b['id']])
        assert len(b['source_block_sha256']) == 64
        assert all(d in '0123456789abcdef' for d in b['source_block_sha256'])
    assert result['acquisition']['source_bytes_transferred'] == 7014781133
    assert result['acquisition']['source_run_url'].startswith('https://github.com/Kushrishi/capsule-review/actions/runs/')
    for key in ('outer_github_artifact_sha256','nested_private_source_zip_sha256','private_manifest_sha256'):
        v=record[key]
        assert len(v)==64 and all(d in '0123456789abcdef' for d in v)


def test_combined_studies_and_source_data_separation():
    current = read(EVIDENCE / 'verified-exam29.json')
    previous = read(EVIDENCE / 'verified-exam30.json')
    e = current['independent_private_artifact_verification']
    group = current['cumulative_new_fitting_acquisition']
    earlier = previous['cumulative_new_exam_acquisition']
    assert group['examinations'] == [21,23,29,30]
    assert group['verified_png_images'] == earlier['verified_png_images'] + e['unique_images'] == 4009
    assert group['explicit_blood_positive_images'] == earlier['blood_positive_images'] + e['explicit_blood_positive_images'] == 886
    assert group['original_png_bytes'] == earlier['total_original_png_bytes'] + e['original_png_bytes'] == 1154652161
    assert group['unique_patients_confirmed'] is False
    assert not any(p.suffix.lower() in {'.png','.jpeg','.jpg','.csv','.zip','.7z','.pt'}
                   for p in EVIDENCE.rglob('*') if p.is_file())
    assert 'never Git' in current['storage']
