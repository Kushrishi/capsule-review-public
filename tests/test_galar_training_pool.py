"""Synthetic-data safeguards for the Galar 21–60 label-only research audit."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_galar_training_pool as m


def source_csv(frames=(0, 5, 10, 15, 20), labels=('1', '1', '0', '1', '1')):
    f = io.StringIO(newline='')
    w = csv.writer(f)
    w.writerow(('frame', *m.LABELS))
    for fr, label in zip(frames, labels):
        w.writerow((fr, label, '0', '0', '0', '0'))
    return f.getvalue()


def zip_fixture(tmp_path, overrides=None):
    overrides = overrides or {}
    p = tmp_path / 'source.zip'
    with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for exam in range(1, 81):
            # Deliberately INVALID reserved contents: an accidental read fails.
            data = overrides.get(exam, 'RESERVED: SHOULD NEVER BE OPENED' if exam not in m.TRAINING_POOL else source_csv())
            z.writestr(f'{exam}.csv', data)
    return p


def test_strict_original_frozen_protocol_and_disclosed_amendment():
    root = Path(__file__).resolve().parents[1]
    spec = root/'docs/GALAR_TRAINING_POOL_SPEC.json'
    amendment = root/'docs/GALAR_TRAINING_POOL_AMENDMENT.json'
    assert hashlib.sha256(spec.read_bytes()).hexdigest() == 'c276f887285cad10abb49ad7839e38c89e6fb2dffc854ca2f6a9e5d887c71291'
    assert hashlib.sha256(amendment.read_bytes()).hexdigest() == '41ef0b110894fe84b63d66db4b4ab57de063ff72ed62ae0c801db1230415174a'
    m.validate_spec(json.loads(spec.read_text(encoding='utf-8')))
    m.validate_amendment(json.loads(amendment.read_text(encoding='utf-8')))


def test_protocol_cannot_reassign_unopened_evaluation_as_fitting():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root/'docs/GALAR_TRAINING_POOL_SPEC.json').read_text(encoding='utf-8'))
    spec['preexisting_exam_roles']['new_training_pool_label_audit'][0] = 11
    with pytest.raises(ValueError, match='roles/source'):
        m.validate_spec(spec)


def test_amendment_cannot_change_roles_or_hide_post_inspection_status():
    root = Path(__file__).resolve().parents[1]
    a = json.loads((root/'docs/GALAR_TRAINING_POOL_AMENDMENT.json').read_text(encoding='utf-8'))
    a['role_changes'] = True
    with pytest.raises(ValueError, match='amendment'):
        m.validate_amendment(a)


@pytest.mark.parametrize('exam', [1, 9, 11, 20, 61, 80])
def test_non_fitting_exam_read_refused_before_zip_access(tmp_path, exam):
    with zipfile.ZipFile(zip_fixture(tmp_path)) as z:
        with pytest.raises(ValueError, match='Forbidden read'):
            m.summarize_exam(z, exam)


def test_summary_never_opens_any_reserved_examination(tmp_path, monkeypatch):
    p = zip_fixture(tmp_path)
    original = zipfile.ZipFile.open
    visited = []
    def recording_open(self, name, *args, **kwargs):
        visited.append(name if isinstance(name, str) else name.filename)
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, 'open', recording_open)
    with zipfile.ZipFile(p) as z:
        out = m.summarize_zip(z)
    assert set(out) == set(range(21, 61))
    assert visited == [f'{i}.csv' for i in range(21, 61)]
    assert not set(visited) & {f'{i}.csv' for i in (11, 20, 61, 80)}


def test_label_blind_stride_one_preserves_contiguous_runs(tmp_path):
    p = zip_fixture(tmp_path, {39: source_csv((0,1,2,3,4), ('1','1','0','1','1'))})
    with zipfile.ZipFile(p) as z:
        a = m.summarize_exam(z, 39)
    assert a['source_frame_stride'] == 1
    assert a['labels']['blood']['positive_rows'] == 4
    assert a['blood_positive_runs'] == 2
    assert a['blood_short_positive_runs_1_to_25_rows'] == 2


def test_gap_breaks_run_even_across_adjacent_positive_annotation_rows(tmp_path):
    frames = [i * 5 + (20 if i >= 40 else 0) for i in range(50)]
    labels = ['0'] * 50
    for i in (38, 39, 40, 41):
        labels[i] = '1'
    p = zip_fixture(tmp_path, {23: source_csv(frames, labels)})
    with zipfile.ZipFile(p) as z:
        a = m.summarize_exam(z, 23)
    assert a['source_frame_stride'] == 5
    assert a['blood_positive_runs'] == 2
    assert a['blood_longest_run_rows'] == 2


def test_missing_is_unknown_never_positive(tmp_path):
    p = zip_fixture(tmp_path, {21: source_csv(labels=('1', '', '0', '', '1'))})
    with zipfile.ZipFile(p) as z:
        a = m.summarize_exam(z, 21)
    assert a['labels']['blood'] == {'positive_rows': 2, 'unknown_rows': 2}
    assert a['blood_positive_runs'] == 2


@pytest.mark.parametrize('csv_text', [
    source_csv(labels=('0', '1', '2', '0', '1')),
    source_csv(frames=(0,5,5,15,20)),
    source_csv(frames=(0,5,15,20,25)) .replace('blood,active bleeding', 'blood,blood,active bleeding'),
])
def test_invalid_annotation_or_identity_rejected(tmp_path, csv_text):
    p = zip_fixture(tmp_path, {21: csv_text})
    with zipfile.ZipFile(p) as z:
        with pytest.raises(ValueError):
            m.summarize_exam(z, 21)


def test_mixed_gaps_without_95_percent_modal_stride_rejected(tmp_path):
    p = zip_fixture(tmp_path, {21: source_csv((0,5,11,18,26))})
    with zipfile.ZipFile(p) as z:
        with pytest.raises(ValueError, match='stable'):
            m.summarize_exam(z, 21)


def test_missing_or_path_traversal_csv_rejected_without_opening_any_values(tmp_path):
    p = tmp_path/'bad.zip'
    with zipfile.ZipFile(p, 'w') as z:
        for i in range(1,81):
            z.writestr(f'{i}.csv' if i != 61 else '../61.csv', 'invalid')
    with zipfile.ZipFile(p) as z:
        with pytest.raises(ValueError, match='80 unique'):
            m.summarize_zip(z)


def test_wrong_source_hash_rejected_before_analyzing_any_labels(tmp_path):
    p = zip_fixture(tmp_path)
    spec = Path(__file__).resolve().parents[1]/'docs/GALAR_TRAINING_POOL_SPEC.json'
    a = Path(__file__).resolve().parents[1]/'docs/GALAR_TRAINING_POOL_AMENDMENT.json'
    with pytest.raises(ValueError, match='identity mismatch'):
        m.build_report(p, spec, a)


def test_aggregate_reference_result_internal_arithmetic():
    p = Path(__file__).resolve().parents[1]/'experiments/galar-training-pool-2026-11-02/summary.json'
    report = json.loads(p.read_text(encoding='utf-8'))
    rows = list(report['by_examination'].values())
    assert len(rows) == report['exam_count'] == 40
    assert report['source']['file_sha256'] == m.SOURCE_SHA256
    assert report['annotated_rows_total'] == sum(r['annotated_rows'] for r in rows)
    assert report['blood_positive_rows_total'] == sum(r['labels']['blood']['positive_rows'] for r in rows)
    assert report['blood_positive_runs_total'] == sum(r['blood_positive_runs'] for r in rows)
    assert report['blood_positive_examinations'] == sum(r['labels']['blood']['positive_rows'] > 0 for r in rows)
    for g in report['frame_archive_groups']:
        first,last = map(int,g['examinations'].split('-'))
        rs = [report['by_examination'][str(i)] for i in range(first,last+1)]
        assert g['exam_count'] == len(rs)
        assert g['blood_positive_rows'] == sum(r['labels']['blood']['positive_rows'] for r in rs)
        assert g['blood_positive_annotation_runs'] == sum(r['blood_positive_runs'] for r in rs)
    assert report['suggested_first_archive_group'] == '21-29'
    assert report['unresolved_image_mapping']['exam'] == 30
    assert report['exam_count'] + len(m.HELD_OUT) < 81
