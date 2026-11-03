"""Check recorded real-data metrics independently of the model implementation.

No source images or trained weights are needed to verify these arithmetics.
"""

import json
import math
from pathlib import Path


METRICS = Path(__file__).resolve().parents[1] / 'experiments/galar-v2-2026-11-01/metrics.json'


def check_record(record):
    matrix = record['confusion_matrix']
    labels = record['class_order']
    n = len(labels)
    assert n == 5 and len(matrix) == n
    assert all(len(row) == n and all(type(x) is int and x >= 0 for x in row) for row in matrix)
    support = [sum(row) for row in matrix]
    predicted = [sum(row[k] for row in matrix) for k in range(n)]
    frames = sum(support)
    assert frames == record['frames'] and frames > 0
    assert math.isclose(sum(matrix[i][i] for i in range(n)) / frames, record['accuracy'], abs_tol=1e-12)

    recalls, f1s = [], []
    for i, label in enumerate(labels):
        cls = record['per_class'][label]
        true_positive = matrix[i][i]
        precision = true_positive / predicted[i] if predicted[i] else None
        recall = true_positive / support[i] if support[i] else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and (precision + recall) else 0.0
        assert cls['reference_count'] == support[i]
        assert cls['prediction_count'] == predicted[i]
        assert (cls['precision'] is None) if precision is None else math.isclose(cls['precision'], precision, abs_tol=1e-12)
        assert (cls['recall'] is None) if recall is None else math.isclose(cls['recall'], recall, abs_tol=1e-12)
        assert math.isclose(cls['f1'], f1, abs_tol=1e-12)
        if recall is not None:
            recalls.append(recall)
            f1s.append(f1)
    assert math.isclose(sum(recalls) / len(recalls), record['balanced_accuracy_supported_classes'], abs_tol=1e-12)
    assert math.isclose(sum(f1s) / len(f1s), record['macro_f1_supported_classes'], abs_tol=1e-12)
    accuracies = record['per_examination_accuracy']
    assert len(accuracies) == record['examinations']
    assert math.isclose(sum(accuracies.values()) / len(accuracies), record['mean_examination_accuracy'], abs_tol=1e-12)


def test_frozen_development_metrics():
    metrics = json.loads(METRICS.read_text())
    assert metrics['clinical_validation'] is False
    assert metrics['evaluation_role'] == 'development validation; also used for checkpoint selection'
    assert metrics['split_unit'] == 'examination'
    assert metrics['best_epoch'] == 5
    check_record(metrics['model'])
    check_record(metrics['training_majority_baseline'])
    assert metrics['model']['accuracy'] < metrics['training_majority_baseline']['accuracy']
    assert metrics['model']['per_class']['esophagus']['prediction_count'] == 0
