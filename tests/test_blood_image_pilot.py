"""Synthetic regression checks for the exploratory blood-label image pilot."""
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

script = Path(__file__).resolve().parents[1] / 'scripts/blood_image_pilot.py'
spec = importlib.util.spec_from_file_location('blood_image_pilot', script)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_tie_aware_auc_and_average_precision():
    assert pilot.roc_ap([0, 1, 0, 1], [0.1, 0.8, 0.7, 0.4])['roc_auc'] == pytest.approx(0.75)
    assert pilot.roc_ap([0, 1, 0, 1], [0.1, 0.8, 0.7, 0.4])['average_precision'] == pytest.approx(5 / 6)
    tied = pilot.roc_ap([0, 1, 0, 1], [0.5] * 4)
    assert tied['roc_auc'] == pytest.approx(0.5)
    assert tied['average_precision'] == pytest.approx(0.5)


def test_absent_class_is_unknown_metric_not_fabricated_success():
    x = pilot.roc_ap([0, 0], [0.1, 0.7])
    assert x['roc_auc'] is None and x['average_precision'] is None
    assert pilot.roc_ap([1, 1], [0.2, 0.7])['roc_auc'] is None
    with pytest.raises(ValueError):
        pilot.roc_ap([0, 1], [0.1])
    with pytest.raises(ValueError):
        pilot.roc_ap([0, 1], [0.2, float('nan')])


def test_fixed_budget_selection_and_exam_level_missingness():
    rows = ([{'exam':9, 'blood':0} for _ in range(40)]
            + [{'exam':10, 'blood':int(i < 8)} for i in range(40)])
    scores = [0.0] * 40 + [1.0 if i < 8 else 0.0 for i in range(40)]
    budget = pilot.budget_report(rows, scores)
    assert budget['10']['per_examination']['9']['selected'] == 4
    assert budget['10']['per_examination']['9']['model_positive_recall'] is None
    assert budget['10']['per_examination']['10']['model_positive_hits'] == 4
    assert budget['10']['per_examination']['10']['model_positive_recall'] == 0.5
    assert budget['10']['examination_macro_positive_frame_recall'] == 0.5
    assert budget == pilot.budget_report(rows, scores)


def test_fixed_red_excess_is_not_a_label_proxy(tmp_path):
    red, gray = tmp_path / 'red.png', tmp_path / 'gray.png'
    Image.new('RGB', (24, 24), (255, 0, 0)).save(red)
    Image.new('RGB', (24, 24), (60, 60, 60)).save(gray)
    assert pilot.red_excess(red) == pytest.approx(1.0)
    assert pilot.red_excess(gray) == pytest.approx(0.0)


def test_manifest_integrity_and_split_restrictions(tmp_path):
    manifest=tmp_path/'manifest.json'
    invalid={'format':pilot.FORMAT,'split':{'train_exams':list(pilot.TRAIN_EXAMS),
                  'development_exams':list(pilot.DEV_EXAMS)},'records':[]}
    invalid['sha256']=pilot.digest(pilot.canonical(invalid))
    manifest.write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match='size'):
        pilot.validate_manifest(manifest,tmp_path,check_files=False)
    invalid['split']['train_exams'].append(61)
    manifest.write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match='SHA-256'):
        pilot.validate_manifest(manifest,tmp_path,check_files=False)


def test_reject_untrusted_or_uncorrected_labels_before_image_use(tmp_path):
    receipt=tmp_path/'receipt.json'
    receipt.write_text(json.dumps({'official_release_version':1,
       'source_name':'obsolete_labels.zip','actual_md5':'a','expected_md5':'b'}))
    selection=tmp_path/'frames.csv'
    selection.write_text('examination,role,frame,filename\n1,train,0,frame_000000.PNG\n')
    with pytest.raises(ValueError,match='provenance'):
        pilot.prepare(selection,tmp_path,tmp_path,receipt,tmp_path/'output.json')
