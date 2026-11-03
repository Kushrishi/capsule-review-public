"""Historical Galar blood-label *annotation-run* review-budget audit.

Read private corrected labels and frozen image scores; publish aggregate results
only. Frames are sparse. Annotation runs are not adjudicated lesions.
No temporal inference, model selection, or clinical review-time claims are made.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from statistics import median
from zipfile import ZipFile

BUDGETS = (5, 10, 25)
EXAMS = (9, 10)  # historical, already inspected development; never blind test
SOURCE_STRIDE = 5  # observed official Galar annotation spacing for 9–10
RELEASE_SHA256 = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
CSV_SHA256 = {9: 'b206f24dc80aac7ac3208114aca1e4214df15365bb896190ccf4ddc8634f2369',
              10: 'a37d485f583bfc3e848d9dad6cd154757b125aeb09a6fef41d524bd566f8789e'}
SOURCE_MANIFEST_FORMAT = 'capsule-blood-sparse-v1'
SHA_RE = re.compile(r'^[0-9a-f]{64}$')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def load_manifest(path: Path) -> tuple[dict, dict[tuple[int, int], dict]]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('Frozen manifest must be a JSON object.')
    claimed = raw.get('sha256')
    if not isinstance(claimed, str):
        raise ValueError('Missing frozen manifest digest.')
    unsigned = {key: val for key, val in raw.items() if key != 'sha256'}
    if sha256(canonical(unsigned)) != claimed or raw.get('format') != SOURCE_MANIFEST_FORMAT:
        raise ValueError('Frozen blood manifest identity mismatch.')
    if raw.get('split', {}).get('development_exams') != list(EXAMS) or raw.get('split', {}).get('train_exams') != list(range(1, 9)):
        raise ValueError('Unexpected frozen examination split.')
    if raw.get('source', {}).get('corrected_label_release_sha256') != RELEASE_SHA256:
        raise ValueError('Frozen manifest uses an unexpected corrected-label source.')
    all_records = raw.get('records')
    if not isinstance(all_records, list) or len(all_records) != 5120:
        raise ValueError('Frozen training/development manifest is incomplete.')
    dev = {}
    seen_all: set[tuple[int, int]] = set()
    for r in all_records:
        if not isinstance(r, dict) or type(r.get('exam')) is not int or type(r.get('frame')) is not int:
            raise ValueError('Manifest contains an invalid frame identity.')
        key = (r['exam'], r['frame'])
        if key in seen_all:
            raise ValueError('Manifest contains duplicate frame identity.')
        seen_all.add(key)
        if r['exam'] in EXAMS:
            if r['split'] != 'development' or r['blood'] not in (0, 1) or not SHA_RE.fullmatch(r['source_sha256']):
                raise ValueError('Malformed development frame manifest record.')
            dev[key] = r
        elif r['exam'] not in range(1, 9) or r['split'] != 'train':
            raise ValueError('Manifest unexpectedly includes reserved/unapproved examination.')
    if len(dev) != 1024 or any(sum(ex == e for ex, _ in dev) != 512 for e in EXAMS):
        raise ValueError('Expected 512 development images per examination.')
    return raw, dev


def load_corrected_labels(path: Path) -> dict[int, list[tuple[int, int | None]]]:
    if sha256(path.read_bytes()) != RELEASE_SHA256:
        raise ValueError('Incorrect corrected Galar v2 ZIP checksum.')
    out = {}
    with ZipFile(path) as z:
        for exam in EXAMS:
            name = f'{exam}.csv'
            if z.namelist().count(name) != 1:
                raise ValueError(f'Corrected label ZIP missing unique {name}.')
            raw = z.read(name)
            if sha256(raw) != CSV_SHA256[exam]:
                raise ValueError(f'Corrected Galar CSV identity mismatch for exam {exam}.')
            rd = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if not {'frame', 'blood'}.issubset(rd.fieldnames or []):
                raise ValueError('Required Galar frame/blood columns are missing.')
            items = []
            for row in rd:
                if not str(row['frame']).isdigit():
                    raise ValueError('Invalid Galar source-frame index.')
                frame = int(row['frame'])
                value = row['blood']
                if value not in ('0', '1', ''):
                    raise ValueError('Unknown/unexpected Galar blood label value.')
                if items and frame - items[-1][0] != SOURCE_STRIDE:
                    raise ValueError('Annotation continuity violated: do not infer labels across gaps.')
                items.append((frame, int(value) if value else None))
            if not items:
                raise ValueError('Empty Galar label sequence.')
            out[exam] = items
    return out


def load_predictions(path: Path, dev: dict[tuple[int, int], dict],
                     labels: dict[int, list[tuple[int, int | None]]],
                     images: Path | None = None) -> dict[int, list[dict]]:
    reference = {e: dict(rows) for e, rows in labels.items()}
    output = {e: [] for e in EXAMS}
    seen: set[tuple[int, int]] = set()
    expected_fields = {'exam', 'frame', 'source_sha256', 'blood_label', 'cnn_score', 'red_excess_score'}
    with path.open(encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        if set(rd.fieldnames or []) != expected_fields:
            raise ValueError('Prediction table columns are missing/changed.')
        for row in rd:
            if not row['exam'].isdigit() or not row['frame'].isdigit() or row['blood_label'] not in ('0', '1'):
                raise ValueError('Invalid prediction identity or label.')
            exam, frame = int(row['exam']), int(row['frame'])
            key = (exam, frame)
            if exam not in EXAMS or key in seen or key not in dev:
                raise ValueError('Duplicate, reserved or unexpected predicted frame.')
            seen.add(key)
            if row['source_sha256'] != dev[key]['source_sha256'] or int(row['blood_label']) != dev[key]['blood']:
                raise ValueError('Prediction frame hash/label differs from frozen manifest.')
            if reference[exam].get(frame) != dev[key]['blood']:
                raise ValueError('Prediction blood label differs from corrected official annotation.')
            try:
                scores = [float(row[name]) for name in ('cnn_score', 'red_excess_score')]
            except (TypeError, ValueError) as exc:
                raise ValueError('Non-numeric model score.') from exc
            if any(not math.isfinite(s) or not 0.0 <= s <= 1.0 for s in scores):
                raise ValueError('Model score outside finite [0,1] range.')
            if images is not None:
                source = (images / dev[key]['path']).resolve()
                if not source.is_relative_to(images.resolve()) or not source.is_file() or sha256(source.read_bytes()) != row['source_sha256']:
                    raise ValueError('Actual PNG does not match its frozen source-image hash.')
            output[exam].append({'frame': frame, 'label': dev[key]['blood'],
                                 'cnn': scores[0], 'red': scores[1]})
    if seen != set(dev):
        raise ValueError('Missing previously saved development model predictions.')
    for exam, rows in output.items():
        rows.sort(key=lambda x: x['frame'])
        if len(rows) != 512 or any(b['frame'] <= a['frame'] for a, b in zip(rows, rows[1:])):
            raise ValueError(f'Unexpected sparse sample size/order in examination {exam}.')
    return output


def positive_runs(annotations: list[tuple[int, int | None]]) -> tuple[list[list[int]], dict[int, int]]:
    """Positive label-row runs; only consecutive *annotated* frame IDs join."""
    runs: list[list[int]] = []
    frame_to_run: dict[int, int] = {}
    last_frame = None
    for frame, label in annotations:
        if type(frame) is not int or frame < 0 or (label is not None and label not in (0, 1)):
            raise ValueError('Invalid reference annotation.')
        if label != 1:
            last_frame = None
            continue
        if last_frame is None or frame != last_frame + SOURCE_STRIDE:
            runs.append([])
        runs[-1].append(frame)
        frame_to_run[frame] = len(runs) - 1
        last_frame = frame
    return runs, frame_to_run


def require_dense_frames(frames: list[int]) -> None:
    """Protect future temporal inference from being applied to sparse snapshots."""
    if len(frames) < 2 or any(b - a != SOURCE_STRIDE for a, b in zip(frames, frames[1:])):
        raise ValueError('Sparse source frames: dense chronological context is unavailable.')


def select_indices(rows: list[dict], method: str, k: int) -> list[int]:
    """Outcome-blind within-examination selection at exactly k image positions."""
    n = len(rows)
    if not isinstance(k, int) or not 0 < k <= n:
        raise ValueError('The review budget must select between 1 and n positions.')
    if method == 'uniform':
        return [(2 * j + 1) * n // (2 * k) for j in range(k)]
    if method in ('cnn_top', 'red_top'):
        field = 'cnn' if method == 'cnn_top' else 'red'
        return sorted(range(n), key=lambda i: (-rows[i][field], i))[:k]
    if method == 'cnn_time_stratified':
        # One highest-scored sample per chronological bin. No label access.
        # Adjacent candidate samples are NOT consecutive full-video frames.
        return [max(range(j * n // k, (j + 1) * n // k),
                    key=lambda i: (rows[i]['cnn'], -i)) for j in range(k)]
    raise ValueError(f'Unknown fixed review-budget policy: {method}.')


def selection_metrics(selected: list[int], rows: list[dict],
                      runs: list[list[int]], frame_to_run: dict[int, int],
                      reachable: set[int]) -> dict:
    if len(selected) != len(set(selected)) or any(i not in range(len(rows)) for i in selected):
        raise ValueError('Selected frames are duplicated or outside the examination.')
    hits = [rows[i] for i in selected if rows[i]['label'] == 1]
    if any(row['frame'] not in frame_to_run for row in hits):
        raise ValueError('A selected positive has no matching official annotation run.')
    touched = Counter(frame_to_run[row['frame']] for row in hits)
    if set(touched) - reachable:
        raise ValueError('Selection reaches a run outside the frozen image sample.')
    return {'selected_frames': len(selected), 'positive_frames': len(hits),
            'blood_label_zero_frames': len(selected) - len(hits),
            'positive_annotation_runs': len(touched),
            'short_runs_le_25_positions': sum(len(runs[r]) <= 25 for r in touched),
            'max_positive_images_from_one_run': max(touched.values(), default=0),
            'run_coverage_all': len(touched) / len(runs) if runs else None,
            'run_coverage_reachable': len(touched) / len(reachable) if reachable else None}


def audit(predictions: dict[int, list[dict]],
          labels: dict[int, list[tuple[int, int | None]]]) -> dict:
    result = {
        'status': 'post-hoc historical development only; no independent test',
        'dataset': 'Galar v2 (corrected December 2025), CC BY 4.0',
        'source_corrected_label_zip_sha256': RELEASE_SHA256,
        'examinations': list(EXAMS),
        'task': 'blood label visibility, not active bleeding diagnosis',
        'budget_denominator': '512 previously uniformly sampled images per examination',
        'full_video_temporal_evaluation': False,
        'image_model_retrained': False,
        'selection_design_status': 'time-stratified rule investigated after historical development outputs; exploratory only',
        'annotation_runs_are_not_adjudicated_lesions': True,
        'budgets_percent': list(BUDGETS),
        'random_policy': '100 independent seeded sample draws per examination and budget; draws are not independent patients',
        'examination_summaries': {},
        'budget_results': {},
        'limitations': [
            'Exams 9–10 previously inspected and used for checkpoint selection; comparisons are post-hoc.',
            'Only exam 10 contains positive blood-label frames among these two development examinations.',
            'Source-frame gaps are 40–100 versus annotated step 5; no adjacent full-video image pairs.',
            'Consecutive positive annotation rows are proxies, not independent clinical lesions.',
            'Each policy selects exactly k already-sampled images, not k positions from the original complete video.',
            'Positive-run coverage is limited by which annotated runs were ever sampled.',
            'No independent patient/site/device evaluation or clinician reading-time measurement.',
        ],
    }
    by_exam = {}
    for exam in EXAMS:
        samples = predictions[exam]
        source = labels[exam]
        if len(samples) != 512 or not source:
            raise ValueError('Unexpected historical evaluation sample.')
        runs, lookup = positive_runs(source)
        sampled_run_ids = {lookup[r['frame']] for r in samples if r['label'] == 1}
        gaps = [b['frame'] - a['frame'] for a, b in zip(samples, samples[1:])]
        if any(gap <= 0 for gap in gaps):
            raise ValueError('Predicted frames are not strictly ordered.')
        if all(gap == SOURCE_STRIDE for gap in gaps):
            raise ValueError('Unexpected dense input: this audit is explicitly sparse-sample only.')
        by_exam[exam] = (samples, runs, lookup, sampled_run_ids)
        result['examination_summaries'][str(exam)] = {
            'source_annotation_positions': len(source),
            'positive_source_annotation_positions': sum(label == 1 for _, label in source),
            'unknown_source_annotation_positions': sum(label is None for _, label in source),
            'available_scored_images': len(samples),
            'positive_scored_images': sum(row['label'] for row in samples),
            'sampled_source_gap_min': min(gaps),
            'sampled_source_gap_median': median(gaps),
            'sampled_source_gap_max': max(gaps),
            'full_video_adjacent_images_available': False,
            'total_positive_annotation_runs': len(runs),
            'reachable_positive_annotation_runs': len(sampled_run_ids),
            'unreachable_positive_annotation_runs': len(runs) - len(sampled_run_ids),
            'short_positive_runs_le_25_positions': sum(len(r) <= 25 for r in runs),
            'reachable_short_runs_le_25_positions': sum(len(runs[i]) <= 25 for i in sampled_run_ids),
            'longest_positive_run_positions': max(map(len, runs), default=0),
        }
    methods = ('cnn_top', 'cnn_time_stratified', 'red_top', 'uniform')
    for percent in BUDGETS:
        per = {}
        for exam, (samples, runs, lookup, reachable) in by_exam.items():
            k = len(samples) * percent // 100
            results = {method: selection_metrics(select_indices(samples, method, k), samples,
                                                  runs, lookup, reachable) for method in methods}
            rng = random.Random(17 + exam * 1009 + percent)
            draws = [selection_metrics(rng.sample(range(len(samples)), k), samples, runs,
                                       lookup, reachable) for _ in range(100)]
            per[str(exam)] = {
                'budget_images': k, 'policies': results,
                'random_100_draws': {
                    'mean_positive_frames': sum(x['positive_frames'] for x in draws) / len(draws),
                    'mean_positive_annotation_runs': sum(x['positive_annotation_runs'] for x in draws) / len(draws),
                    'min_positive_annotation_runs': min(x['positive_annotation_runs'] for x in draws),
                    'max_positive_annotation_runs': max(x['positive_annotation_runs'] for x in draws),
                },
            }
        result['budget_results'][str(percent)] = {'per_examination': per}
    return result


def verify_prior_budget_counts(audit_result: dict, historical_metrics: Path) -> None:
    previous = json.loads(historical_metrics.read_text(encoding='utf-8'))
    for pct in BUDGETS:
        for exam in EXAMS:
            new = audit_result['budget_results'][str(pct)]['per_examination'][str(exam)]
            base_cnn = previous['cnn']['budgets'][str(pct)]['per_examination'][str(exam)]
            base_red = previous['fixed_red_excess_comparator']['budgets'][str(pct)]['per_examination'][str(exam)]
            if (new['policies']['cnn_top']['positive_frames'] != base_cnn['model_positive_hits']
                    or new['policies']['red_top']['positive_frames'] != base_red['model_positive_hits']
                    or new['policies']['uniform']['positive_frames'] != base_cnn['uniform_positive_hits']
                    or abs(new['random_100_draws']['mean_positive_frames'] - base_cnn['random_mean_positive_hits']) > 1e-9
                    or new['budget_images'] != base_cnn['selected']):
                raise ValueError('Historical frozen sparse-frame budget comparator mismatch.')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corrected-label-zip', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--predictions', required=True, type=Path)
    p.add_argument('--historical-metrics', required=True, type=Path)
    p.add_argument('--images', type=Path, help='Optional original image-root rehash for all 1024 frames')
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists: refusing to overwrite a historical experiment artifact.')
    manifest, dev = load_manifest(args.manifest)
    labels = load_corrected_labels(args.corrected_label_zip)
    scores = load_predictions(args.predictions, dev, labels, images=args.images)
    result = audit(scores, labels)
    verify_prior_budget_counts(result, args.historical_metrics)
    result['input_integrity'] = {
        'manifest_sha256': manifest['sha256'],
        'predictions_sha256': sha256(args.predictions.read_bytes()),
        'historical_metrics_sha256': sha256(args.historical_metrics.read_bytes()),
        'source_frame_files_rehashed': 1024 if args.images else 0,
        'historical_frame_budget_reproduced': True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, ensure_ascii=False, allow_nan=False)
        out.write('\n')
    print(json.dumps({'output': str(args.output), 'historical_metrics_verified': True,
                      'frames_rehashed': result['input_integrity']['source_frame_files_rehashed'],
                      'runs_exam_10': result['examination_summaries']['10']['total_positive_annotation_runs']}, sort_keys=True))


if __name__ == '__main__':
    main()
