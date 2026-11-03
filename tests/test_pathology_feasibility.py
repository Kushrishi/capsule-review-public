"""Synthetic label-only tests; no clinical images or real performance claims."""

import csv
import importlib.util
from pathlib import Path

import pytest

script = Path(__file__).resolve().parents[1] / 'scripts/pathology_feasibility.py'
spec = importlib.util.spec_from_file_location('pathology_feasibility', script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def make_labels(path, frames, blood, active=None):
    active = active if active is not None else [0] * len(frames)
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(('frame', 'blood', 'active bleeding'))
        w.writerows(zip(frames, blood, active))


def make_plan(path, records):
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(('examination', 'role', 'frame'))
        w.writerows(records)


def test_exam_parser_rejects_reserved_and_duplicates():
    assert audit.parse_exams('1-3,5,8') == [1, 2, 3, 5, 8]
    for bad in ('61', '1-80', '1,1', '8-1', '0', '', '1,', '1-2-3', 'x'):
        with pytest.raises(ValueError):
            audit.parse_exams(bad)


def test_positive_runs_distinguish_gaps_and_missingness():
    frames = [0, 5, 10, 20, 25, 30, 35]
    labels = [1, 1, None, 1, 1, 0, 1]
    assert audit.positive_runs(frames, labels, step=5) == [[0, 1], [3, 4], [6]]
    assert audit.selection_score(labels, [[0, 1], [3, 4], [6]], {1, 5})['positive_run_hits'] == 1


def test_uniform_sampling_is_unique_label_blind_and_reproducible():
    assert audit.uniformly_spaced_indices(10, 3) == [1, 5, 8]
    assert audit.uniformly_spaced_indices(4, 4) == [0, 1, 2, 3]
    assert audit.uniformly_spaced_indices(4, 0) == []
    for n, k in ((12, 3), (12, 9), (101, 5)):
        xs = audit.uniformly_spaced_indices(n, k)
        assert len(xs) == len(set(xs)) == k
        assert all(0 <= x < n for x in xs)


def test_audit_is_training_only_with_distinct_unknowns_and_runs(tmp_path):
    labels_dir = tmp_path / 'labels'
    labels_dir.mkdir()
    make_labels(labels_dir / '1.csv', [0, 5, 10, 15, 20, 25], [1, 1, 0, 1, 0, 1], ['', 0, 0, 0, 0, 0])
    make_labels(labels_dir / '2.csv', [0, 5, 10, 15], [0, 1, 1, 0])
    # Reserved file exists but the command is prohibited from reading it.
    (labels_dir / '61.csv').write_text('do not read me')
    plan = tmp_path / 'plan.csv'
    make_plan(plan, [(1, 'train', 0), (1, 'train', 20), (2, 'train', 5), (9, 'validation', 123)])
    out = audit.build_report(labels_dir, [1, 2], plan, labels=('blood', 'active bleeding'),
                             random_repetitions=5)
    assert out['eligible_annotated_rows'] == 10
    assert out['original_sampled_rows'] == 3
    assert out['aggregate_labels']['blood']['positive_rows'] == 6
    assert out['aggregate_labels']['blood']['annotated_positive_runs'] == 4
    assert out['aggregate_labels']['blood']['sampled_positive_runs_hit'] == 2
    assert out['primary_label_annotated_run_length_distribution']['1'] == 2
    assert out['primary_label_annotated_run_length_distribution']['2-5'] == 2
    assert out['primary_label_annotated_run_length_distribution']['maximum_rows'] == 2
    assert out['aggregate_labels']['active bleeding']['unknown_rows'] == 1
    assert out['per_examination']['1']['sample_fraction'] == pytest.approx(2/6)
    assert out['budget_baselines']['budgets']['5']['selected_annotated_rows'] == 2
    again = audit.build_report(labels_dir, [1, 2], plan, labels=('blood', 'active bleeding'),
                               random_repetitions=5)
    assert out == again


def test_invalid_annotation_and_sample_plan_are_rejected(tmp_path):
    labels = tmp_path / '1.csv'
    make_labels(labels, [0, 0], [1, 0])
    with pytest.raises(ValueError, match='duplicate or unsorted'):
        audit.read_examination(labels, ('blood',))
    make_labels(labels, [0, 5], [1, 'unknown'])
    with pytest.raises(ValueError, match='Invalid value'):
        audit.read_examination(labels, ('blood',))
    make_labels(labels, [0, 5], [1, 0])
    with pytest.raises(ValueError, match='Missing required columns'):
        audit.read_examination(labels, ('ulcer',))
    plan = tmp_path / 'plan.csv'
    make_plan(plan, [(1, 'train', 0), (1, 'train', 0)])
    with pytest.raises(ValueError, match='Duplicate'):
        audit.read_selected_frames(plan, [1])
    make_plan(plan, [(1, 'validation', 0)])
    with pytest.raises(ValueError, match='fitting'):
        audit.read_selected_frames(plan, [1])


def test_audit_rejects_missing_sampled_frame(tmp_path):
    labels_dir = tmp_path / 'labels'
    labels_dir.mkdir()
    make_labels(labels_dir / '1.csv', [0, 5], [1, 0])
    plan = tmp_path / 'plan.csv'
    make_plan(plan, [(1, 'train', 10)])
    with pytest.raises(ValueError, match='no matching annotated'):
        audit.build_report(labels_dir, [1], plan, labels=('blood',), random_repetitions=2)


def test_receipt_hash_verification_detects_replaced_labels(tmp_path):
    import hashlib
    import json
    labels_dir = tmp_path / 'labels'
    labels_dir.mkdir()
    file = labels_dir / '1.csv'
    make_labels(file, [0, 5], [1, 0])
    plan = tmp_path / 'plan.csv'
    make_plan(plan, [(1, 'train', 0)])
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps({
        'official_release_version': 2,
        'source_name': '20251215_Labels_Updated.zip',
        'actual_md5': 'same', 'expected_md5': 'same',
        'source_sha256': 'source_archive_hash',
        'selected_csvs': [{'examination': 1, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                           'unmodified_source_bytes': True}],
    }))
    good = audit.build_report(labels_dir, [1], plan, labels=('blood',),
                              random_repetitions=2, label_integrity_receipt=receipt)
    assert good['source_integrity']['status'].startswith('all selected CSV bytes match')
    file.write_text(file.read_text().replace(',1,0', ',0,0'))
    with pytest.raises(ValueError, match='does not match'):
        audit.build_report(labels_dir, [1], plan, labels=('blood',),
                           random_repetitions=2, label_integrity_receipt=receipt)

