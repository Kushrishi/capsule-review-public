"""Reconcile genuine Galar-27 research results with prior immutable receipts.

Only nonidentifying aggregate data are read in CI. This test cannot replace
private replay of the 1005 source images and 3 frozen model checkpoints.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'experiments/galar-21-30-source-index'
G27 = ROOT / 'experiments/galar27-2026-11-02'


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf8'))


def test_exact_frozen_source_population_and_training_roles():
    result = read(G27 / 'aggregate.json')
    receipt = read(G27 / 'verification.json')
    plan = read(ROOT / 'experiments/galar-21-30-selection/aggregate.json')
    expected = plan['per_examination']['27']
    ref = result['primary_512_label_blind_reference']
    secondary = result['secondary_1005_pathology_enriched_union_descriptive_only']
    assert result['evaluation_exam'] == 27
    assert result['no_model_training_or_selection'] is True
    assert result['clinical_validation'] is False
    assert result['reserved_11_20_61_80_unopened'] is True
    assert result['original_source_image_count'] == expected['unique_requested_images'] == 1005
    assert result['explicit_blood_positive_in_enriched_union'] == secondary['blood_positive'] == receipt['positive_images_in_union'] == 273
    assert ref['n'] == expected['label_blind_reference_candidates'] == 512
    assert ref['blood_positive'] == expected['reference_positive_candidates'] == receipt['reference_positive'] == 26
    assert expected['enriched_training_candidates'] == 512
    assert expected['enriched_positive_candidates'] == receipt['enriched_positive'] == 256
    assert expected['dual_purpose_overlap'] == 19
    assert expected['annotated_positive_runs'] == 4
    assert receipt['image_count'] == 1005
    assert receipt['original_png_bytes'] == 291862996
    assert receipt['duplicate_original_file_sha256_with_earlier_10142'] == 0
    assert receipt['source_full_archive_md5_verified'] is False
    assert receipt['model_updated'] is False
    assert receipt['source_zip_sha256'] == result['source_private_package_sha256']
    assert receipt['model_checkpoint_sha256'] == result['checkpoint_sha256']
    assert receipt['aggregate_sha256'] == '565bd226ad4adc01d678cfaf1df4ef55346fc0f876990eca43a947b2c414308b'


def test_all_review_budgets_and_preserved_study_heterogeneity():
    result = read(G27 / 'aggregate.json')
    ref = result['primary_512_label_blind_reference']
    methods = ref['methods']
    assert set(methods) == {'original_checkpoint', 'original_only_continued', 'expanded_continued', 'red_excess'}
    assert methods['original_checkpoint']['roc_auc'] > methods['expanded_continued']['roc_auc']
    assert methods['original_checkpoint']['average_precision'] > methods['expanded_continued']['average_precision']
    budgets = ref['budgets']
    assert set(budgets) == {'5', '10', '25', '50', '75', '100'}
    last = {name: 0 for name in (*methods, 'uniform')}
    for percent in (5, 10, 25, 50, 75, 100):
        data = budgets[str(percent)]
        k = 512 * percent // 100
        assert data['selected_images'] == k
        hits = data['hits_by_method']
        assert set(hits) == set(last)
        for name, count in hits.items():
            assert isinstance(count, int) and last[name] <= count <= min(k, 26)
            last[name] = count
    assert all(count == 26 for count in last.values())
    assert budgets['10']['hits_by_method'] == {
        'expanded_continued': 21, 'original_checkpoint': 22,
        'original_only_continued': 21, 'red_excess': 15, 'uniform': 2}
    # A pooled reference ROC-AUC would erase these very different case outcomes.
    old = read(ROOT / 'experiments/galar25-2026-11-02/model-comparison.json')
    assert old['clinical_validity'] is False
    assert methods['original_checkpoint']['roc_auc'] > 0.9
    assert all(0.0 <= v['roc_auc'] <= 1.0 and 0.0 <= v['average_precision'] <= 1.0 for v in methods.values())


def test_full_original_source_block_coverage_is_not_claimed_as_full_archive_md5():
    coverage = read(G27 / 'source-block-coverage.json')
    index = read(INDEX / 'layout.json')
    from_previous = read(INDEX / 'verified-acquisition-summary.json')
    exam25 = read(ROOT / 'experiments/galar25-2026-11-02/acquisition-aggregate.json')
    exam29 = read(INDEX / 'verified-exam29.json')
    exam30 = read(INDEX / 'verified-exam30.json')
    assert coverage['full_original_archive_md5_verified'] is False
    assert coverage['all_source_blocks_transferred_and_sha256_hashed'] is True
    assert coverage['number_of_unique_compressed_source_blocks'] == 10
    assert coverage['publisher_file_id'] == index['origin_file_id'] == 45258019
    assert coverage['full_publisher_archive_bytes'] == index['archive_bytes'] == 31989399751
    blocks = coverage['blocks']
    assert [entry['block_id'] for entry in blocks] == list(range(10))
    for i, entry in enumerate(blocks):
        frozen = index['blocks'][i]
        assert entry['compressed_bytes'] == frozen['compressed_bytes']
        assert entry['source_offset'] == 32 + sum(x['compressed_bytes'] for x in index['blocks'][:i])
        digest = entry['compressed_sha256']
        assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
    assert coverage['source_compressed_block_bytes'] == sum(x['compressed_bytes'] for x in blocks) == 31988057679
    assert coverage['original_header_and_index_bytes_transferred'] == 1342072
    assert sum(x['compressed_bytes'] for x in blocks) + 1342072 == index['archive_bytes']
    assert blocks[0]['compressed_sha256'] == from_previous['exam_21']['source_block_sha256']
    assert blocks[1]['compressed_sha256'] == from_previous['exam_23']['source_block_sha256']
    for source in exam25['verified_compressed_block_receipts']:
        assert blocks[source['block_id']]['compressed_sha256'] == source['compressed_block_sha256']
    for source in read(G27 / 'verification.json')['compressed_blocks']:
        assert blocks[source['block_id']]['compressed_sha256'] == source['compressed_block_sha256']
    for source in exam29['acquisition']['allowed_blocks']:
        assert blocks[source['id']]['compressed_sha256'] == source['source_block_sha256']
    for source in exam30['selected_blocks']:
        assert blocks[source['block_id']]['compressed_sha256'] == source['source_sha256']
    assert coverage['source_image_examinations_partially_acquired'] == [21, 23, 25, 27, 29, 30]
    assert coverage['source_image_examinations_without_fitting_selection_acquisition'] == [22, 24, 26, 28]


def test_results_directory_does_not_commit_private_medical_material():
    assert not any(
        p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.zip', '.7z', '.csv', '.pt', '.sqlite', '.db'}
        for p in G27.rglob('*') if p.is_file()
    )
