"""Tests for the historical, sparse-frame review-budget evaluation (not clinical metrics)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'review_budget_audit.py'
spec = importlib.util.spec_from_file_location('review_budget_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sample(n=12):
    return [{'frame': i * 5, 'label': int(i % 4 in (1, 2)),
             'cnn': (i % 5) / 5, 'red': (i % 3) / 3} for i in range(n)]


def test_annotation_runs_do_not_bridge_negative_unknown_or_missing_frames():
    rows = [(0, 1), (5, 1), (10, 0), (15, 1), (20, None),
            (25, 1), (35, 1), (40, 1)]
    runs, lookup = audit.positive_runs(rows)
    assert runs == [[0, 5], [15], [25], [35, 40]]
    assert lookup == {0: 0, 5: 0, 15: 1, 25: 2, 35: 3, 40: 3}


def test_refuse_dense_video_claim_on_sparse_snapshots():
    audit.require_dense_frames([0, 5, 10, 15])
    with pytest.raises(ValueError, match='Sparse'):
        audit.require_dense_frames([0, 45, 95])
    with pytest.raises(ValueError, match='Sparse'):
        audit.require_dense_frames([0])


def test_label_unknown_and_invalid_source_rejected():
    with pytest.raises(ValueError, match='Invalid'):
        audit.positive_runs([(0, 1), (5, -1)])
    with pytest.raises(ValueError, match='Invalid'):
        audit.positive_runs([(-5, 1)])


def test_exact_budget_and_chronological_stratification():
    rows = sample(12)
    idx = audit.select_indices(rows, 'cnn_time_stratified', 3)
    assert idx == [max(range(j * 4, (j + 1) * 4), key=lambda i: (rows[i]['cnn'], -i))
                   for j in range(3)]
    assert len(set(idx)) == 3
    assert audit.select_indices(rows, 'uniform', 3) == [2, 6, 10]
    assert audit.select_indices(rows, 'cnn_top', 3) == [4, 9, 3]


def test_tie_breaks_use_source_order_without_labels():
    rows = [{'frame': i * 5, 'label': i % 2, 'cnn': 0.5, 'red': 0.5} for i in range(10)]
    assert audit.select_indices(rows, 'cnn_top', 3) == [0, 1, 2]
    assert audit.select_indices(rows, 'cnn_time_stratified', 3) == [0, 3, 6]
    assert audit.select_indices(rows, 'red_top', 3) == [0, 1, 2]
    changed_labels = [dict(r, label=1 - r['label']) for r in rows]
    for strategy in ('cnn_top', 'cnn_time_stratified', 'red_top', 'uniform'):
        assert audit.select_indices(rows, strategy, 3) == audit.select_indices(changed_labels, strategy, 3)


def test_budget_errors_and_duplicate_selections_rejected():
    rows = sample()
    for k in (0, -1, len(rows) + 1):
        with pytest.raises(ValueError, match='budget'):
            audit.select_indices(rows, 'uniform', k)
    with pytest.raises(ValueError, match='Unknown'):
        audit.select_indices(rows, 'train_on_development_labels', 3)
    with pytest.raises(ValueError, match='duplicated'):
        audit.selection_metrics([0, 0], rows, [], {}, set())
    with pytest.raises(ValueError, match='outside'):
        audit.selection_metrics([len(rows)], rows, [], {}, set())


def test_metrics_use_unique_runs_not_positive_frame_count():
    rows = [{'frame': f, 'label': int(f in (0, 5, 10, 30)), 'cnn': 1.0, 'red': 1.0}
            for f in (0, 5, 10, 15, 20, 25, 30)]
    runs, lookup = audit.positive_runs([(0, 1), (5, 1), (10, 1), (15, 0), (20, 0), (25, 0), (30, 1)])
    x = audit.selection_metrics([0, 1, 2, 6], rows, runs, lookup, set(lookup.values()))
    assert x['positive_frames'] == 4
    assert x['positive_annotation_runs'] == 2
    assert x['max_positive_images_from_one_run'] == 3
    assert x['run_coverage_all'] == 1.0
    assert x['short_runs_le_25_positions'] == 2


def test_no_positive_exam_has_undefined_run_coverage():
    rows = [{'frame': 0, 'label': 0, 'cnn': 0.3, 'red': 0.2}]
    x = audit.selection_metrics([0], rows, [], {}, set())
    assert x['positive_frames'] == 0
    assert x['positive_annotation_runs'] == 0
    assert x['run_coverage_all'] is None and x['run_coverage_reachable'] is None


def test_positive_without_annotation_run_is_not_silently_invented():
    rows = [{'frame': 0, 'label': 1, 'cnn': 0.5, 'red': 0.5}]
    with pytest.raises(ValueError, match='matching official'):
        audit.selection_metrics([0], rows, [], {}, set())


def test_manifests_cannot_be_forged_or_relabelled(tmp_path):
    p = tmp_path / 'manifest.json'
    p.write_text('[]')
    with pytest.raises(ValueError, match='JSON object'):
        audit.load_manifest(p)
    p.write_text(json.dumps({'format': 'capsule-blood-sparse-v1', 'sha256': '0' * 64}))
    with pytest.raises(ValueError, match='identity mismatch'):
        audit.load_manifest(p)


def test_bad_release_checksum_cannot_be_used(tmp_path):
    p = tmp_path / 'incorrect-corrected-labels.zip'
    p.write_bytes(b'not the corrected release')
    with pytest.raises(ValueError, match='checksum'):
        audit.load_corrected_labels(p)


def test_saved_aggregate_is_frozen_exploratory_record():
    p = SCRIPT.parents[1] / 'experiments/galar-v2-2026-11-01/review_budget_audit.json'
    if not p.exists():
        pytest.skip('Aggregate has not been generated for the branch yet.')
    x = json.loads(p.read_text(encoding='utf-8'))
    assert x['full_video_temporal_evaluation'] is False
    assert 'post-hoc' in x['status']
    assert x['examination_summaries']['10']['total_positive_annotation_runs'] == 41
    assert x['examination_summaries']['10']['reachable_positive_annotation_runs'] == 31
    at10 = x['budget_results']['10']['per_examination']['10']['policies']
    assert at10['cnn_top']['positive_frames'] == 47
    assert at10['cnn_top']['positive_annotation_runs'] == 3
    assert at10['cnn_top']['max_positive_images_from_one_run'] == 44
    assert at10['cnn_time_stratified']['positive_annotation_runs'] == 11
    assert at10['uniform']['positive_annotation_runs'] == 10
    assert at10['red_top']['positive_annotation_runs'] == 9
    assert at10['cnn_time_stratified']['positive_frames'] == 24
    assert x['input_integrity']['source_frame_files_rehashed'] == 1024


def test_prediction_table_rejects_label_or_image_identity_drift(tmp_path):
    table = tmp_path / 'predictions.csv'
    rows = {9: [(5, 1), (10, 0)], 10: [(0, 0)]}
    dev = {(9, 5): {'blood': 1, 'source_sha256': 'a' * 64, 'path': '009/frame_000005.PNG'}}
    table.write_text('exam,frame,source_sha256,blood_label,cnn_score,red_excess_score\n'
                     + f"9,5,{'a' * 64},0,0.7,0.3\n")
    with pytest.raises(ValueError, match='hash/label'):
        audit.load_predictions(table, dev, rows)
    table.write_text('exam,frame,source_sha256,blood_label,cnn_score,red_excess_score\n'
                     + f"9,5,{'b' * 64},1,0.7,0.3\n")
    with pytest.raises(ValueError, match='hash/label'):
        audit.load_predictions(table, dev, rows)
    table.write_text('exam,frame,source_sha256,blood_label,cnn_score,red_excess_score\n'
                     + f"9,5,{'a' * 64},1,nan,0.3\n")
    with pytest.raises(ValueError, match='finite'):
        audit.load_predictions(table, dev, rows)


def test_reject_reserved_examinations_before_any_budget_calculation(tmp_path):
    table = tmp_path / 'predictions.csv'
    table.write_text('exam,frame,source_sha256,blood_label,cnn_score,red_excess_score\n'
                     + f"61,5,{'a' * 64},1,0.8,0.4\n")
    with pytest.raises(ValueError, match='reserved'):
        audit.load_predictions(table, {}, {9: [], 10: []})


def test_previous_metrics_must_match_the_frozen_audit(tmp_path):
    p = SCRIPT.parents[1] / 'experiments/galar-v2-2026-11-01/review_budget_audit.json'
    if not p.exists():
        pytest.skip('Aggregate has not been generated for the branch yet.')
    original = json.loads(p.read_text())
    base = {'cnn': {'budgets': {}}, 'fixed_red_excess_comparator': {'budgets': {}}}
    for budget, o in original['budget_results'].items():
        base['cnn']['budgets'][budget] = {'per_examination': {}}
        base['fixed_red_excess_comparator']['budgets'][budget] = {'per_examination': {}}
        for exam, v in o['per_examination'].items():
            base['cnn']['budgets'][budget]['per_examination'][exam] = {
                'model_positive_hits': v['policies']['cnn_top']['positive_frames'],
                'uniform_positive_hits': v['policies']['uniform']['positive_frames'],
                'random_mean_positive_hits': v['random_100_draws']['mean_positive_frames'],
                'selected': v['budget_images']}
            base['fixed_red_excess_comparator']['budgets'][budget]['per_examination'][exam] = {
                'model_positive_hits': v['policies']['red_top']['positive_frames']}
    path = tmp_path / 'previous.json'
    path.write_text(json.dumps(base))
    audit.verify_prior_budget_counts(original, path)
    base['cnn']['budgets']['10']['per_examination']['10']['model_positive_hits'] += 1
    path.write_text(json.dumps(base))
    with pytest.raises(ValueError, match='mismatch'):
        audit.verify_prior_budget_counts(original, path)


def test_public_record_contains_no_individual_prediction_or_frame_identity():
    p = SCRIPT.parents[1] / 'experiments/galar-v2-2026-11-01/review_budget_audit.json'
    if not p.exists():
        pytest.skip('Aggregate has not been generated for the branch yet.')
    obj = json.loads(p.read_text())
    assert obj['examinations'] == [9, 10]
    serialized = json.dumps(obj, sort_keys=True)
    assert 'source_sha256' not in serialized
    assert 'pixel_sha256' not in serialized
    assert 'source_frame_id' not in serialized
    assert 'predictions.csv' not in serialized
    assert 'training_examinations' not in obj
