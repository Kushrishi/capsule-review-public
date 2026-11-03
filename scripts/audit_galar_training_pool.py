"""Inspect *only* Galar 21–60 corrected-label CSVs for fitting-data feasibility.

Never open reserved 11–20 / 61–80 label contents. Emits aggregate support,
not original per-frame labels, patient material, or an independent test result.
The 2026-11-02 amendment records a source-stride correction discovered after
freezing the original protocol; the audit is descriptive, not preregistered.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

SOURCE_SHA256 = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
SOURCE_MD5 = '4428f8d4341cc41ade9fd547c19b6e48'
SOURCE_SIZE = 17931138
SOURCE_FILE_ID = 60383963
TRAINING_POOL = tuple(range(21, 61))
HELD_OUT = tuple(range(11, 21)) + tuple(range(61, 81))
LABELS = ('blood', 'active bleeding', 'angiectasia', 'ulcer', 'polyp')
GROUPS = (
    ('21-29', 45258019, 31989399751, tuple(range(21, 30))),
    ('31-40', 44755700, 69219317963, tuple(range(31, 41))),
    ('41-50', 44809350, 173935092108, tuple(range(41, 51))),
    ('51-60', 44809828, 202693348645, tuple(range(51, 61))),
)
MAX_CSV_BYTES = 64 * 1024 * 1024


def digest_file(path: Path) -> tuple[str, str, int]:
    sha = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            size += len(block)
            if size > SOURCE_SIZE:
                raise ValueError('Corrected label archive exceeds official source size.')
            sha.update(block)
            md5.update(block)
    return sha.hexdigest(), md5.hexdigest(), size


def validate_spec(spec: dict) -> None:
    source = spec.get('data_source') or {}
    roles = spec.get('preexisting_exam_roles') or {}
    if (spec.get('version') != '1.0'
            or spec.get('frozen_before_new_candidate_examination_label_inspection') is not True
            or source.get('corrected_file_id') != SOURCE_FILE_ID
            or source.get('official_md5') != SOURCE_MD5
            or source.get('verified_local_source_sha256') != SOURCE_SHA256
            or source.get('bytes') != SOURCE_SIZE
            or roles.get('new_training_pool_label_audit') != list(TRAINING_POOL)
            or roles.get('already_assigned_unopened_future_evaluation') != list(range(11, 21))
            or roles.get('original_author_reserved_holdout') != list(range(61, 81))
            or roles.get('previously_inspected_historical_development') != [9, 10]
            or (spec.get('label_policy') or {}).get('primary_label') != 'blood'
            or (spec.get('label_policy') or {}).get('contiguous_annotated_run_step') != 5):
        raise ValueError('Original pre-analysis examination roles/source/specification changed.')
    options = spec.get('official_frame_archive_options')
    if options != [{'exams': group, 'file_id': file_id, 'bytes': bytes_}
                   for group, file_id, bytes_, _ in GROUPS]:
        raise ValueError('Original frame-archive options changed.')


def validate_amendment(amendment: dict) -> None:
    if (amendment.get('version') != '1.1'
            or amendment.get('original_protocol_version') != '1.0'
            or amendment.get('change_type') != 'post-inspection methodological correction'
            or amendment.get('derive_stride_from') != 'source frame identifiers only; never pathology labels'
            or amendment.get('stride_policy') != 'unique modal positive gap per examination; at least 95% of adjacent gaps'
            or amendment.get('role_changes') is not False):
        raise ValueError('Unapproved or undisclosed methodological amendment.')


def summarize_exam(zf: zipfile.ZipFile, exam: int) -> dict:
    """Only accepts explicitly fitting-eligible exam IDs; source labels stay in memory."""
    if exam not in TRAINING_POOL:
        raise ValueError('Forbidden read outside Galar training-pool examinations 21–60.')
    name = f'{exam}.csv'
    info = zf.getinfo(name)
    if info.file_size > MAX_CSV_BYTES or info.file_size == 0 or info.is_dir():
        raise ValueError(f'Unexpected source CSV size for examination {exam}.')
    frame_rows: list[tuple[int, bool]] = []
    gaps: Counter[int] = Counter()
    counts = {label: {'positive_rows': 0, 'unknown_rows': 0} for label in LABELS}
    previous = None
    with zf.open(name) as binary:
        with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as txt:
            reader = csv.DictReader(txt)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or not {'frame', *LABELS}.issubset(fields):
                raise ValueError(f'Invalid or ambiguous CSV columns in examination {exam}.')
            for row in reader:
                if None in row or any(row.get(col) is None for col in ('frame', *LABELS)):
                    raise ValueError(f'Malformed CSV row in examination {exam}.')
                raw_frame = row['frame']
                if not re.fullmatch(r'[0-9]+', raw_frame):
                    raise ValueError(f'Invalid frame ID in examination {exam}.')
                frame = int(raw_frame)
                if previous is not None:
                    if frame <= previous:
                        raise ValueError(f'Frame IDs not strictly increasing in examination {exam}.')
                    gaps[frame - previous] += 1
                previous = frame
                for label in LABELS:
                    value = row[label]
                    if value not in ('0', '1', ''):
                        raise ValueError(f'Invalid {label} label in examination {exam}.')
                    counts[label]['positive_rows'] += value == '1'
                    counts[label]['unknown_rows'] += value == ''
                frame_rows.append((frame, row['blood'] == '1'))
    if len(frame_rows) < 2 or not gaps:
        raise ValueError(f'Insufficient ordered annotation rows in examination {exam}.')
    gap, frequency = gaps.most_common(1)[0]
    if (len(gaps) > 1 and gaps.most_common(2)[1][1] == frequency) or frequency / (len(frame_rows) - 1) < .95:
        raise ValueError(f'Cannot infer a stable pathology-label-blind annotation stride for examination {exam}.')
    runs = []
    current = 0
    prev_frame = None
    for frame, positive in frame_rows:
        if positive:
            if current and prev_frame is not None and frame - prev_frame == gap:
                current += 1
            else:
                if current:
                    runs.append(current)
                current = 1
        elif current:
            runs.append(current)
            current = 0
        prev_frame = frame
    if current:
        runs.append(current)
    if sum(runs) != counts['blood']['positive_rows']:
        raise ValueError(f'Annotation-run accounting failed for examination {exam}.')
    return {
        'exam': exam,
        'annotated_rows': len(frame_rows),
        'source_frame_stride': gap,
        'stride_support_fraction': round(frequency / (len(frame_rows) - 1), 6),
        'labels': counts,
        'blood_positive_runs': len(runs),
        'blood_short_positive_runs_1_to_25_rows': sum(1 <= x <= 25 for x in runs),
        'blood_long_positive_runs_26_plus_rows': sum(x >= 26 for x in runs),
        'blood_longest_run_rows': max(runs, default=0),
    }


def summarize_zip(zf: zipfile.ZipFile) -> dict[int, dict]:
    # The ZIP index may be enumerated without reading excluded CSV *contents*.
    infos = zf.infolist()
    actual_names = [i.filename for i in infos]
    if sorted(actual_names) != sorted(f'{i}.csv' for i in range(1, 81)):
        raise ValueError('Expected 80 unique source CSV entries; unexpected path or missing examination.')
    if any(i.flag_bits & 1 or i.is_dir() for i in infos):
        raise ValueError('Encrypted/directory source entries are not supported.')
    return {exam: summarize_exam(zf, exam) for exam in TRAINING_POOL}


def build_report(labels_archive: Path, spec_path: Path, amendment_path: Path) -> dict:
    spec = json.loads(spec_path.read_text('utf-8'))
    amendment = json.loads(amendment_path.read_text('utf-8'))
    validate_spec(spec)
    validate_amendment(amendment)
    sha, md5, size = digest_file(labels_archive)
    if (sha, md5, size) != (SOURCE_SHA256, SOURCE_MD5, SOURCE_SIZE):
        raise ValueError('Corrected Galar source identity mismatch; reject data.')
    with zipfile.ZipFile(labels_archive) as zf:
        by_exam = summarize_zip(zf)
    groups = []
    for group, source_id, size_bytes, exams in GROUPS:
        positive = [by_exam[e] for e in exams if by_exam[e]['labels']['blood']['positive_rows'] > 0]
        short = [r for r in positive if r['blood_short_positive_runs_1_to_25_rows'] > 0]
        groups.append({
            'examinations': group,
            'source_file_id': source_id,
            'full_source_archive_bytes': size_bytes,
            'exam_count': len(exams),
            'blood_positive_exam_count': len(positive),
            'blood_positive_rows': sum(r['labels']['blood']['positive_rows'] for r in positive),
            'blood_positive_annotation_runs': sum(r['blood_positive_runs'] for r in positive),
            'exams_with_short_blood_runs': len(short),
            'meets_predeclared_support_threshold': len(positive) >= 3 and len(short) >= 2,
        })
    qualifies = [g for g in groups if g['meets_predeclared_support_threshold']]
    preferred = min(qualifies, key=lambda x: (x['full_source_archive_bytes'], x['examinations'])) if qualifies else None
    return {
        'status': 'descriptive fitting-pool label-only audit; modified stride rule disclosed after inspection',
        'source': {'article_id': 25304616, 'file_id': SOURCE_FILE_ID,
                   'file_sha256': sha, 'official_md5': md5, 'bytes': size},
        'frozen_spec_git_commit': 'f537eaaf85c1a0d2e29695e33d382574cdcfc6b6',
        'spec_sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        'amendment_sha256': hashlib.sha256(amendment_path.read_bytes()).hexdigest(),
        'examination_roles': {'fitting_pool': [21, 60], 'existing_fitting': [1, 8],
                              'historical_development': [9, 10], 'unopened_future_evaluation': [11, 20],
                              'unopened_author_holdout': [61, 80]},
        'exam_count': len(by_exam),
        'annotated_rows_total': sum(r['annotated_rows'] for r in by_exam.values()),
        'blood_positive_examinations': sum(r['labels']['blood']['positive_rows'] > 0 for r in by_exam.values()),
        'blood_positive_rows_total': sum(r['labels']['blood']['positive_rows'] for r in by_exam.values()),
        'blood_positive_runs_total': sum(r['blood_positive_runs'] for r in by_exam.values()),
        'other_labels': {k: {'positive_rows': sum(r['labels'][k]['positive_rows'] for r in by_exam.values()),
                             'positive_examinations': sum(r['labels'][k]['positive_rows'] > 0 for r in by_exam.values())}
                         for k in LABELS if k != 'blood'},
        'by_examination': {str(e): by_exam[e] for e in TRAINING_POOL},
        'frame_archive_groups': groups,
        'suggested_first_archive_group': preferred['examinations'] if preferred else None,
        'unresolved_image_mapping': {'exam': 30, 'reason': 'No 30-specific frame archive identified in official v2 file names; confirm membership before any image acquisition.'},
        'constraints': ['No reserved evaluation labels or frames read.',
                        'Per-exam stride derived from label-blind source-frame ID spacing, not pathology labels.',
                        'Positive runs are annotations, not independent lesions or time durations.',
                        'Examination ID is not confirmed to be a unique-patient ID.',
                        'Predefined threshold selects candidate training acquisition only, not model/checkpoint selection.',
                        'No new image download, training, clinical validation or inference performed.'],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels-archive', type=Path, required=True)
    parser.add_argument('--spec', type=Path, default=Path('docs/GALAR_TRAINING_POOL_SPEC.json'))
    parser.add_argument('--amendment', type=Path, default=Path('docs/GALAR_TRAINING_POOL_AMENDMENT.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Refusing to overwrite previous research results.')
    report = build_report(args.labels_archive, args.spec, args.amendment)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, indent=2, allow_nan=False, sort_keys=True)
        out.write('\n')
    print(f"Audited only exams 21–60: {report['exam_count']} studies, "
          f"{report['blood_positive_examinations']} with blood labels; "
          f"recommended source group: {report['suggested_first_archive_group'] or 'none'}")


if __name__ == '__main__':
    main()
