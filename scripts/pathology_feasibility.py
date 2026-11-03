"""Training-only Galar pathology-label feasibility and review-budget baselines.

Reads source annotation CSVs but never loads, trains on or stores image data.
No individual source frame identifiers are written in its aggregate output.
Connected annotated-positive runs are proxies, NOT adjudicated lesions.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from math import ceil
from pathlib import Path
from random import Random

DEFAULT_LABELS = ('blood', 'active bleeding', 'angiectasia', 'polyp', 'ulcer')
BUDGETS = (5, 10, 25)


def parse_exams(value: str) -> list[int]:
    """Accept a comma-delimited development examination list/range (1..60)."""
    ids = []
    for token in value.split(','):
        token = token.strip()
        if not token:
            raise ValueError('Empty examination token.')
        if '-' in token:
            pair = token.split('-')
            if len(pair) != 2 or not all(x.strip().isdigit() for x in pair):
                raise ValueError(f'Invalid examination range: {token!r}')
            lo, hi = (int(x) for x in pair)
            if lo > hi:
                raise ValueError('Decreasing examination range.')
            ids.extend(range(lo, hi + 1))
        elif token.isdigit():
            ids.append(int(token))
        else:
            raise ValueError(f'Invalid examination ID: {token!r}')
    if not ids or len(set(ids)) != len(ids) or any(not 1 <= x <= 60 for x in ids):
        raise ValueError('Unique development examination IDs in 1..60 are required; 61..80 are reserved.')
    return sorted(ids)


def read_selected_frames(path: Path, exam_ids: list[int]) -> dict[int, set[int]]:
    """Read pre-existing selection; validation IDs outside exam_ids are ignored."""
    selected: dict[int, set[int]] = defaultdict(set)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'examination', 'role', 'frame'}.issubset(reader.fieldnames or ()):
            raise ValueError('Sample plan needs examination, role and frame columns.')
        for row in reader:
            exam = int(row['examination'])
            if exam not in exam_ids:
                continue
            if row['role'] != 'train':
                raise ValueError('Only fitting rows may be used for the training feasibility audit.')
            frame = int(row['frame'])
            if frame < 0 or frame in selected[exam]:
                raise ValueError(f'Duplicate or invalid selected frame in examination {exam}.')
            selected[exam].add(frame)
    if any(not selected[x] for x in exam_ids):
        raise ValueError('Every included examination requires an existing sampling plan.')
    return dict(selected)


def read_examination(path: Path, labels: tuple[str, ...]) -> tuple[list[int], dict[str, list[int | None]]]:
    """Validate source ordering and distinguish missing values from explicit zeroes."""
    frames: list[int] = []
    values: dict[str, list[int | None]] = {label: [] for label in labels}
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'frame', *labels}.issubset(reader.fieldnames or ()):
            raise ValueError(f'Missing required columns in {path.name}; do not interpret absent labels as negatives.')
        for row in reader:
            raw = row['frame']
            try:
                frame = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Invalid frame identifier in {path.name}.') from exc
            if frame < 0 or (frames and frame <= frames[-1]):
                raise ValueError(f'Invalid, duplicate or unsorted source frames in {path.name}.')
            frames.append(frame)
            for label in labels:
                val = row[label]
                if val not in ('0', '1', ''):
                    raise ValueError(f'Invalid value in {path.name}/{label}; must be 0, 1 or unknown.')
                values[label].append(None if val == '' else int(val))
    if not frames:
        raise ValueError(f'No labelled rows in {path.name}.')
    return frames, values


def positive_runs(frames: list[int], labels: list[int | None], step: int) -> list[list[int]]:
    """Index runs of explicitly positive consecutive annotated rows.

    Break if source frames are not adjacent at the configured annotation stride.
    These are *label runs*, not distinct lesions or continuous video durations.
    """
    if step < 1:
        raise ValueError('annotation step must be positive.')
    runs: list[list[int]] = []
    for idx, val in enumerate(labels):
        if val != 1:
            continue
        if not runs or idx != runs[-1][-1] + 1 or frames[idx] - frames[idx - 1] != step:
            runs.append([])
        runs[-1].append(idx)
    return runs


def uniformly_spaced_indices(n: int, k: int) -> list[int]:
    """Deterministically pick k distinct positions without looking at labels."""
    if not 0 <= k <= n:
        raise ValueError('Budget must be within available positions.')
    return [(2 * j + 1) * n // (2 * k) for j in range(k)] if k else []


def selection_score(positive: list[int | None], runs: list[list[int]], indices: set[int]) -> dict:
    pos = sum(v == 1 for v in positive)
    covered = sum(bool(indices.intersection(run)) for run in runs)
    return {
        'selected_rows': len(indices),
        'sampled_positive_rows': sum(positive[i] == 1 for i in indices),
        'positive_run_hits': covered,
        'positive_run_coverage': covered / len(runs) if runs else None,
        'positive_frame_capture': (sum(positive[i] == 1 for i in indices) / pos) if pos else None,
    }



def verify_label_receipt(receipt_path: Path | None, by_exam: dict[str, dict]) -> dict:
    """Check selected CSV hashes against a previously trusted source receipt.

    The receipt itself must be independently verified against the official release;
    self-declared hashes are not proof of official provenance.
    """
    if receipt_path is None:
        return {'status': 'unverified: no trusted source receipt supplied'}
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if (receipt.get('official_release_version') != 2
            or receipt.get('source_name') != '20251215_Labels_Updated.zip'
            or receipt.get('actual_md5') != receipt.get('expected_md5')
            or not receipt.get('source_sha256')):
        raise ValueError('Source receipt is not a verified corrected Galar v2 release record.')
    expected = {str(x['examination']): x for x in receipt['selected_csvs']}
    for exam, details in by_exam.items():
        record = expected.get(exam)
        if (record is None or not record.get('unmodified_source_bytes')
                or details['annotation_csv_sha256'] != record['sha256']):
            raise ValueError(f'Examination {exam} does not match corrected-label source receipt.')
    return {
        'status': 'all selected CSV bytes match supplied corrected-source receipt',
        'official_release_version': 2,
        'source_file_id': receipt.get('source_file_id'),
        'source_zip_sha256': receipt['source_sha256'],
        'source_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }


def build_report(labels_dir: Path, exam_ids: list[int], sample_plan: Path,
                 *, labels: tuple[str, ...] = DEFAULT_LABELS, step: int = 5,
                 random_repetitions: int = 100, seed: int = 17,
                 label_integrity_receipt: Path | None = None) -> dict:
    if not exam_ids or len(set(exam_ids)) != len(exam_ids) or any(not 1 <= x <= 60 for x in exam_ids):
        raise ValueError('Only distinct development examination IDs 1..60 are permitted.')
    if not labels or len(set(labels)) != len(labels):
        raise ValueError('Distinct nonempty labels required.')
    if random_repetitions < 1 or random_repetitions > 1000:
        raise ValueError('Random repetitions must be between 1 and 1000.')
    if step < 1:
        raise ValueError('Annotation step must be positive.')
    selected = read_selected_frames(sample_plan, exam_ids)
    by_exam: dict[str, dict] = {}
    rows_by_exam = {}
    all_label_rows = 0
    for exam in exam_ids:
        frames, columns = read_examination(labels_dir / f'{exam}.csv', labels)
        missing_selection = selected[exam] - set(frames)
        if missing_selection:
            raise ValueError(f'{exam}: selected images have no matching annotated source frames.')
        lookup = {frame: i for i, frame in enumerate(frames)}
        selected_idx = {lookup[frame] for frame in selected[exam]}
        by_exam[str(exam)] = {
            'annotation_csv_sha256': hashlib.sha256((labels_dir / f'{exam}.csv').read_bytes()).hexdigest(),
            'annotated_rows': len(frames),
            'sampled_rows': len(selected_idx),
            'sample_fraction': len(selected_idx) / len(frames),
            'labels': {},
        }
        for label, vals in columns.items():
            runs = positive_runs(frames, vals, step)
            sel = selection_score(vals, runs, selected_idx)
            by_exam[str(exam)]['labels'][label] = {
                'positive_rows': sum(v == 1 for v in vals),
                'unknown_rows': sum(v is None for v in vals),
                'annotated_positive_runs': len(runs),
                'sampled_positive_rows': sel['sampled_positive_rows'],
                'sampled_positive_runs_hit': sel['positive_run_hits'],
            }
        all_label_rows += len(frames)
        rows_by_exam[exam] = (frames, columns)
    source_integrity = verify_label_receipt(label_integrity_receipt, by_exam)
    aggregate = {}
    for label in labels:
        values = [record['labels'][label] for record in by_exam.values()]
        runs_total = sum(x['annotated_positive_runs'] for x in values)
        hits_total = sum(x['sampled_positive_runs_hit'] for x in values)
        aggregate[label] = {
            'positive_rows': sum(x['positive_rows'] for x in values),
            'positive_examinations': sum(x['positive_rows'] > 0 for x in values),
            'unknown_rows': sum(x['unknown_rows'] for x in values),
            'annotated_positive_runs': runs_total,
            'sampled_positive_rows': sum(x['sampled_positive_rows'] for x in values),
            'sampled_positive_runs_hit': hits_total,
            'sample_run_coverage': hits_total / runs_total if runs_total else None,
        }
    # Budget baselines do not use image data or model predictions. Each budget is
    # applied per examination, not to a pooled frame list dominated by long videos.
    primary = labels[0]
    primary_run_lengths = [
        len(run)
        for exam in exam_ids
        for run in positive_runs(rows_by_exam[exam][0], rows_by_exam[exam][1][primary], step)
    ]
    run_length_distribution = {
        '1': sum(n == 1 for n in primary_run_lengths),
        '2-5': sum(2 <= n <= 5 for n in primary_run_lengths),
        '6-25': sum(6 <= n <= 25 for n in primary_run_lengths),
        '26-100': sum(26 <= n <= 100 for n in primary_run_lengths),
        '101+': sum(n > 100 for n in primary_run_lengths),
        'maximum_rows': max(primary_run_lengths, default=0),
    }
    budget_baselines = {}
    for budget in BUDGETS:
        exam_counts = {}
        total_runs = total_hits = total_sampled = total_pos_sampled = 0
        random_trials = [0] * random_repetitions
        macro_uniform = []
        macro_random = []
        for exam in exam_ids:
            frames, columns = rows_by_exam[exam]
            truth = columns[primary]
            runs = positive_runs(frames, truth, step)
            k = ceil(len(frames) * budget / 100)
            sel = selection_score(truth, runs, set(uniformly_spaced_indices(len(frames), k)))
            trial_hits = []
            for trial in range(random_repetitions):
                rng = Random(f'{seed}:{trial}:{exam}')
                sample = set(rng.sample(range(len(frames)), k))
                trial_hits.append(selection_score(truth, runs, sample)['positive_run_hits'])
                random_trials[trial] += trial_hits[-1]
            if runs:
                macro_uniform.append(sel['positive_run_coverage'])
                macro_random.append(sum(trial_hits) / len(trial_hits) / len(runs))
            total_runs += len(runs)
            total_hits += sel['positive_run_hits']
            total_sampled += sel['selected_rows']
            total_pos_sampled += sel['sampled_positive_rows']
            exam_counts[str(exam)] = {
                'budget_rows': k,
                'annotated_positive_runs': len(runs),
                'uniform_run_hits': sel['positive_run_hits'],
                'uniform_run_coverage': sel['positive_run_coverage'],
                'random_run_hits_mean': sum(trial_hits) / len(trial_hits),
            }
        budget_baselines[str(budget)] = {
            'budget_percent_per_examination': budget,
            'selected_annotated_rows': total_sampled,
            'uniform_positive_rows_selected': total_pos_sampled,
            'annotated_positive_runs': total_runs,
            'uniform_positive_run_hits': total_hits,
            'uniform_pooled_run_coverage': total_hits / total_runs if total_runs else None,
            'uniform_positive_examination_macro_run_coverage': sum(macro_uniform) / len(macro_uniform) if macro_uniform else None,
            'random_positive_examination_macro_run_coverage_mean': sum(macro_random) / len(macro_random) if macro_random else None,
            'random_pooled_run_coverage_mean': (sum(random_trials) / len(random_trials) / total_runs) if total_runs else None,
            'random_pooled_run_coverage_min': min(random_trials) / total_runs if total_runs else None,
            'random_pooled_run_coverage_max': max(random_trials) / total_runs if total_runs else None,
            'per_examination': exam_counts,
        }
    return {
        'status': 'training-only exploratory label feasibility; NOT a trained pathology model or clinical performance',
        'dataset_claim': 'Galar v2; independently validate the accompanying source receipt before trusting this claim',
        'source_integrity': source_integrity,
        'role': 'historical pilot fitting examinations only',
        'sample_plan_sha256': hashlib.sha256(sample_plan.read_bytes()).hexdigest(),
        'examinations': exam_ids,
        'labels': list(labels),
        'source_annotation_stride': step,
        'eligible_annotated_rows': all_label_rows,
        'original_sampled_rows': sum(x['sampled_rows'] for x in by_exam.values()),
        'per_examination': by_exam,
        'aggregate_labels': aggregate,
        'primary_label_annotated_run_length_distribution': run_length_distribution,
        'budget_baselines': {'primary_label': primary, 'random_seed': seed,
                             'random_repetitions': random_repetitions, 'budgets': budget_baselines},
        'limitations': [
            'Runs are contiguous annotation-positive rows at the configured source-frame stride, not adjudicated lesions.',
            'Frames were annotated at a source-frame stride; sampled indices are not durations or clinical reading times.',
            'A zero in one label is not a clinician-confirmed normal frame or a negative for every pathology.',
            'No images, pathology model, clinical reference adjudication, or independent test set were used.',
            'Random repetitions measure sampling variability, not independent patients or confidence intervals.',
            'Positive exam prevalence is biased by the pathology-enriched Galar cohort.',
            'Use future exams only after examination-level splits are fixed without inspecting outcome labels.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels-dir', type=Path, required=True)
    parser.add_argument('--sample-plan', type=Path, required=True)
    parser.add_argument('--exams', default='1-8', help='Preselected fitting examination IDs; never access 61-80')
    parser.add_argument('--labels', nargs='+', default=list(DEFAULT_LABELS))
    parser.add_argument('--annotation-step', type=int, default=5)
    parser.add_argument('--random-repetitions', type=int, default=100)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--label-integrity-receipt', type=Path, help='Trusted corrected Galar source file/hash receipt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite a previous feasibility result.')
    report = build_report(args.labels_dir, parse_exams(args.exams), args.sample_plan,
                          labels=tuple(args.labels), step=args.annotation_step,
                          random_repetitions=args.random_repetitions, seed=args.seed,
                          label_integrity_receipt=args.label_integrity_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f"Audited {report['eligible_annotated_rows']:,} annotation rows, "
          f"{len(report['examinations'])} fitting examinations; output: {args.output}")


if __name__ == '__main__':
    main()
