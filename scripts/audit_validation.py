"""Reproduce a frozen Galar model's validation predictions and summarize errors.

Run against trusted, separately retained data/weights. This emits aggregate counts
only; individual labels, filenames and images are never written to its JSON report.
Exploratory boundary-window statistics must not be used for checkpoint selection.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from capsule_review.baseline import Frames, classification_metrics, load_model
from capsule_review.baseline_data import canonical, digest, read_json, safe_path


def summarize_sequence(truth, predicted, confidence, class_names, *, radius=5):
    """Summarize model behavior in sampled-frame order, not video time."""
    if not truth or len(truth) != len(predicted) or len(truth) != len(confidence):
        raise ValueError('Aligned, nonempty ground truth, predictions and scores are required.')
    transitions = [i for i in range(1, len(truth)) if truth[i] != truth[i - 1]]
    nearby = {k for t in transitions for k in range(max(0, t - radius), min(len(truth), t + radius))}
    errors = [i for i in range(len(truth)) if truth[i] != predicted[i]]
    pairs = Counter((class_names[truth[i]], class_names[predicted[i]]) for i in errors)
    longest, start = 0, None
    for i in range(len(truth) + 1):
        incorrect = i < len(truth) and truth[i] != predicted[i]
        if incorrect and start is None:
            start = i
        if not incorrect and start is not None:
            longest = max(longest, i - start)
            start = None
    correct_scores = [confidence[i] for i in range(len(truth)) if truth[i] == predicted[i]]
    wrong_scores = [confidence[i] for i in errors]
    return {
        'reference_transitions_in_sparse_sample': len(transitions),
        'near_transition_frames': len(nearby),
        'near_transition_error_rate': sum(i in nearby for i in errors) / len(nearby) if nearby else None,
        'elsewhere_error_rate': sum(i not in nearby for i in errors) / (len(truth) - len(nearby)) if len(nearby) != len(truth) else None,
        'longest_consecutive_error_run_in_sampled_frames': longest,
        'most_common_misclassifications': [
            {'actual': a, 'predicted': b, 'frames': n}
            for (a, b), n in sorted(pairs.items(), key=lambda v: (-v[1], v[0]))
        ],
        'mean_max_softmax_correct': sum(correct_scores) / len(correct_scores) if correct_scores else None,
        'mean_max_softmax_incorrect': sum(wrong_scores) / len(wrong_scores) if wrong_scores else None,
    }


def audit(manifest_path: Path, images: Path, run_dir: Path, *, expected_metrics: Path | None = None) -> dict:
    """Load a completed checkpoint, verify validation images, and evaluate once."""
    model, meta = load_model(run_dir)
    manifest = read_json(manifest_path, 20 * 1024 * 1024)
    content = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
    if digest(canonical(content)) != manifest.get('manifest_sha256'):
        raise ValueError('Manifest SHA-256 mismatch.')
    if manifest.get('data_kind') != 'galar' or meta['manifest_sha256'] != manifest['manifest_sha256']:
        raise ValueError('Galar dataset or model/manifest identity mismatch.')
    if manifest.get('classes') != meta['classes']:
        raise ValueError('Anatomy class order differs from the model.')
    rows = sorted((r for r in manifest['records'] if r['split'] == 'validation'),
                  key=lambda r: (int(r['exam_id']), int(r['frame'])))
    if not rows or any(not 1 <= int(r['exam_id']) <= 60 for r in rows):
        raise ValueError('No permitted development-validation records.')
    if {r['exam_id'] for r in rows} != set(meta['validation_exams']):
        raise ValueError('Validation examination membership changed.')
    for row in rows:
        path = safe_path(images, row['path'])
        if digest(path.read_bytes()) != row['source_sha256']:
            raise ValueError('Original image SHA-256 mismatch.')
    torch.set_num_threads(2)
    truth, predictions, confidence = [], [], []
    loader = DataLoader(Frames(images, rows, meta['classes']), batch_size=32, shuffle=False)
    with torch.inference_mode():
        for batch, labels in loader:
            probabilities = torch.softmax(model(batch), dim=1)
            if not torch.isfinite(probabilities).all():
                raise ValueError('Non-finite output encountered.')
            truth.extend(labels.tolist())
            predictions.extend(probabilities.argmax(1).tolist())
            confidence.extend(probabilities.max(1).values.tolist())
    actual = classification_metrics(truth, predictions, [r['exam_id'] for r in rows], meta['classes'])
    if expected_metrics is not None:
        expected = read_json(expected_metrics, 1024 * 1024)['model']
        if actual['confusion_matrix'] != expected['confusion_matrix']:
            raise ValueError('Predictions do not reproduce the frozen confusion matrix.')
    by_examination = {}
    for exam_id in sorted({r['exam_id'] for r in rows}, key=int):
        indices = [i for i, r in enumerate(rows) if r['exam_id'] == exam_id]
        yy, pp, cc = ([v[i] for i in indices] for v in (truth, predictions, confidence))
        measures = classification_metrics(yy, pp, [exam_id] * len(indices), meta['classes'])
        by_examination[exam_id] = {
            'frames': len(indices),
            'correct': sum(y == p for y, p in zip(yy, pp)),
            'reference_counts': {name: yy.count(i) for i, name in enumerate(meta['classes'])},
            'prediction_counts': {name: pp.count(i) for i, name in enumerate(meta['classes'])},
            'confusion_matrix': measures['confusion_matrix'],
            'accuracy': measures['accuracy'],
            **summarize_sequence(yy, pp, cc, meta['classes']),
        }
    return {
        'status': 'exploratory, post-hoc development error analysis',
        'frames': len(rows),
        'model_weights_sha256': meta['weights_sha256'],
        'manifest_sha256': manifest['manifest_sha256'],
        'frozen_confusion_matrix_matched': expected_metrics is not None,
        'class_order': meta['classes'],
        'aggregate_accuracy': actual['accuracy'],
        'examinations': by_examination,
        'limitations': [
            'Development data also selected the checkpoint; not independent final-test results.',
            'Frames are sampled sparsely; transition windows do not resolve the video boundary precisely.',
            'Softmax maximum scores are uncalibrated and are not clinical probabilities.',
            'This post-hoc analysis must not be used for model selection or patient-care decisions.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--expected-metrics', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; never overwrite a previous audit.')
    result = audit(args.manifest, args.images, args.run_dir, expected_metrics=args.expected_metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Verified {result['frames']} image hashes and saved aggregate report to {args.output}")


if __name__ == '__main__':
    main()
