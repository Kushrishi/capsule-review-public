"""Source-annotation-only feasibility audit: candidate density versus fixed review workload.

NOT an image-backed model evaluation, clinical lesion sensitivity, or new blinded test.
Only corrected, permitted fitting-pool examinations 21-30 are ever read.
Outputs per-examination aggregates, never original frame identities or labels.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

SOURCE_ZIP_SHA256 = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
SOURCE_ZIP_BYTES = 17_931_138
EXAMS = tuple(range(21, 31))
CANDIDATES = (512, 1024, 2048, 4096, 8192, 'all')
BUDGETS = (51, 128, 256, 512)
SPEC_BLOB_SHA = '25b920096f555ea9fc09ce3e69deaadb3bce23a2'
STRATA = ('short_1_5', 'medium_6_25', 'long_26_plus')


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def validate_spec(path: Path) -> dict:
    raw = path.read_bytes()
    if git_blob(raw) != SPEC_BLOB_SHA:
        raise ValueError('Prespecified protocol changed; cannot run amended analysis silently.')
    spec = json.loads(raw)
    if (spec['source']['zip_sha256'] != SOURCE_ZIP_SHA256
            or spec['source']['allowed_exam_ids'] != list(EXAMS)
            or spec['candidate_positions_per_exam'] != list(CANDIDATES)
            or spec['fixed_reviewer_frames_per_exam'] != list(BUDGETS)):
        raise ValueError('Protocol/source/cohort definitions do not match locked methodology.')
    return spec


def uniform_positions(n: int, k: int) -> list[int]:
    if not isinstance(n, int) or not isinstance(k, int) or n < 1 or not (0 <= k <= n):
        raise ValueError('Uniform sampling requires 0 <= k <= n and n >= 1.')
    return [((2 * j + 1) * n) // (2 * k) for j in range(k)] if k else []


def parse_allowed_csv(archive: zipfile.ZipFile, exam: int) -> tuple[list[tuple[int, str]], str]:
    """Open exactly an allowed CSV; no archive-wide testzip or reading other entries."""
    if type(exam) is not int or exam not in EXAMS:
        raise ValueError('Forbidden examination: only development examinations 21-30 may be read.')
    name = f'{exam}.csv'
    info = archive.getinfo(name)
    if not 0 < info.file_size <= 64 * 1024 * 1024:
        raise ValueError('Invalid corrected source label file size.')
    # ZipFile.open verifies this ONE member's CRC when consumed completely.
    with archive.open(info, 'r') as member:
        raw = member.read()
    if len(raw) != info.file_size:
        raise ValueError('Corrected label member truncated.')
    with io.StringIO(raw.decode('utf-8-sig'), newline='') as text:
        reader = csv.DictReader(text)
        if not {'frame', 'blood'} <= set(reader.fieldnames or []):
            raise ValueError('Missing source frame/blood fields.')
        if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
            raise ValueError('Ambiguous duplicate source CSV column.')
        rows: list[tuple[int, str]] = []
        previous = -1
        differences: Counter[int] = Counter()
        for row in reader:
            if None in row or not (row.get('frame') or '').isdigit() or row.get('blood') not in ('0', '1', ''):
                raise ValueError('Invalid corrected label; unknown is never converted to negative.')
            frame = int(row['frame'])
            if frame <= previous:
                raise ValueError('Original corrected source frame IDs must increase strictly.')
            if previous >= 0:
                differences[frame - previous] += 1
            rows.append((frame, row['blood']))
            previous = frame
    if len(rows) < 512:
        raise ValueError('Too few annotated source positions for frozen candidate plan.')
    most_common = differences.most_common(2)
    if (not most_common or most_common[0][0] != 5
            or most_common[0][1] / (len(rows) - 1) < 0.95
            or (len(most_common) == 2 and most_common[0][1] == most_common[1][1])):
        raise ValueError('Original examination annotation stride deviates from expected +5.')
    return rows, hashlib.sha256(raw).hexdigest()


def run_identities(rows: list[tuple[int, str]]) -> tuple[list[int | None], list[int]]:
    """Identify runs from contiguous SOURCE annotation rows, not independent lesions."""
    assignments: list[int | None] = [None] * len(rows)
    lengths: list[int] = []
    active = None
    for index, (frame, label) in enumerate(rows):
        if label != '1':
            active = None
            continue
        if active is None or index == 0 or rows[index - 1][1] != '1' or frame - rows[index - 1][0] != 5:
            active = len(lengths)
            lengths.append(0)
        assignments[index] = active
        lengths[active] += 1
    return assignments, lengths


def length_stratum(length: int) -> str:
    if length <= 0:
        raise ValueError('Impossible empty positive run.')
    return 'short_1_5' if length <= 5 else 'medium_6_25' if length <= 25 else 'long_26_plus'


def analyze_exam(rows: list[tuple[int, str]], source_csv_sha256: str) -> dict:
    assignment, run_lengths = run_identities(rows)
    eligible = [i for i, (_, label) in enumerate(rows) if label in ('0', '1')]
    if len(eligible) < 512:
        raise ValueError('Not enough explicitly labelled source positions.')
    source_positive = sum(label == '1' for _, label in rows)
    if sum(run_lengths) != source_positive:
        raise ValueError('Annotation run arithmetic failed.')
    by_stratum = {stratum: sum(length_stratum(length) == stratum for length in run_lengths) for stratum in STRATA}
    densities = {}
    for target in CANDIDATES:
        m = len(eligible) if target == 'all' else min(target, len(eligible))
        candidates = [eligible[j] for j in uniform_positions(len(eligible), m)]
        hit_runs = {assignment[i] for i in candidates if assignment[i] is not None}
        stratum_hits = {
            stratum: sum(length_stratum(run_lengths[r]) == stratum for r in hit_runs)
            for stratum in STRATA
        }
        review = {}
        for budget in BUDGETS:
            selected = [candidates[j] for j in uniform_positions(m, budget)]
            actual = {assignment[i] for i in selected if assignment[i] is not None}
            review[str(budget)] = {
                'selected_frames': budget,
                'uniform_review_positive_frames': sum(rows[i][1] == '1' for i in selected),
                'uniform_review_distinct_runs': len(actual),
                'uniform_review_run_recall': len(actual)/len(run_lengths) if run_lengths else None,
                'label_privileged_max_distinct_runs': min(budget, len(hit_runs)),
            }
        densities[str(target)] = {
            'candidate_frames': m,
            'candidate_positive_frames': sum(rows[i][1] == '1' for i in candidates),
            'representable_annotation_runs': len(hit_runs),
            'representable_run_recall': len(hit_runs)/len(run_lengths) if run_lengths else None,
            'representable_runs_by_length': stratum_hits,
            'fixed_workload': review,
        }
    return {
        'annotated_source_positions': len(rows),
        'eligible_blood_label_positions': len(eligible),
        'unknown_blood_label_positions': len(rows) - len(eligible),
        'source_annotation_csv_sha256': source_csv_sha256,
        'original_blood_positive_positions': source_positive,
        'original_positive_annotation_runs': len(run_lengths),
        'original_run_length_strata': by_stratum,
        'densities': densities,
    }


def aggregate(exams: dict[str, dict]) -> dict:
    positive = [d for d in exams.values() if d['original_positive_annotation_runs'] > 0]
    result = {}
    for target in CANDIDATES:
        key = str(target)
        denom = sum(d['original_positive_annotation_runs'] for d in exams.values())
        numerator = sum(d['densities'][key]['representable_annotation_runs'] for d in exams.values())
        aggregate_strata = {
            stratum: {
                'source_runs': sum(d['original_run_length_strata'][stratum] for d in exams.values()),
                'represented_runs': sum(d['densities'][key]['representable_runs_by_length'][stratum] for d in exams.values()),
            } for stratum in STRATA
        }
        fixed = {}
        for budget in BUDGETS:
            k = str(budget)
            fixed[k] = {
                'total_selected_frames': budget * len(exams),
                'uniform_positive_frames': sum(d['densities'][key]['fixed_workload'][k]['uniform_review_positive_frames'] for d in exams.values()),
                'uniform_distinct_runs_hit': sum(d['densities'][key]['fixed_workload'][k]['uniform_review_distinct_runs'] for d in exams.values()),
                'label_privileged_candidate_oracle_runs': sum(d['densities'][key]['fixed_workload'][k]['label_privileged_max_distinct_runs'] for d in exams.values()),
                'forced_source_blood_negative_selected_frames': budget * sum(d['original_positive_annotation_runs'] == 0 for d in exams.values()),
            }
        result[key] = {
            'candidate_frames_total': sum(d['densities'][key]['candidate_frames'] for d in exams.values()),
            'positive_source_runs': denom,
            'representable_source_runs': numerator,
            'descriptive_pooled_recall': numerator/denom if denom else None,
            'positive_examination_macro_recall': sum(d['densities'][key]['representable_run_recall'] for d in positive)/len(positive) if positive else None,
            'length_strata': aggregate_strata,
            'fixed_workload': fixed,
        }
    return result


def execute(labels_zip: Path, spec: dict) -> dict:
    if labels_zip.stat().st_size != SOURCE_ZIP_BYTES or sha256_path(labels_zip) != SOURCE_ZIP_SHA256:
        raise ValueError('Official corrected Galar label ZIP source size/SHA-256 mismatch.')
    exams = {}
    with zipfile.ZipFile(labels_zip, 'r') as archive:
        for exam in EXAMS:
            rows, source_sha = parse_allowed_csv(archive, exam)
            exams[str(exam)] = analyze_exam(rows, source_sha)
    # The 512 candidate rule was already used for the prior fixed fitting plan.
    # Refuse a new finding if the baseline cannot be reproduced verbatim.
    for exam in EXAMS:
        key = str(exam)
        value = exams[key]['densities']['512']
        expected_positives = spec['expected_512_reference_positive_counts'][key]
        expected_runs = spec['expected_512_reference_positive_runs'][key]
        if value['candidate_positive_frames'] != expected_positives or value['representable_annotation_runs'] != expected_runs:
            raise ValueError('Previously reported 512-image reference source counts not reproducible.')
    totals = aggregate(exams)
    if sum(d['original_positive_annotation_runs'] for d in exams.values()) != 242:
        raise ValueError('Previously audited source-positive run total not reproduced.')
    return {
        'study': 'Galar 21–30 source-label-only density/coverage feasibility',
        'interpretation': 'Post-hoc exploratory; no new pixels/models; NOT independent or lesion sensitivity',
        'source_zip_sha256': SOURCE_ZIP_SHA256,
        'protocol_git_blob_sha1': SPEC_BLOB_SHA,
        'exam_count': len(exams),
        'positive_exam_count': sum(d['original_positive_annotation_runs']>0 for d in exams.values()),
        'blood_negative_label_exam_count': sum(d['original_positive_annotation_runs']==0 for d in exams.values()),
        'cohort': 'Only Galar 21–30 previously inspected fitting-pool corrected CSVs',
        'per_exam': exams,
        'summary_by_candidate_density': totals,
        'clinical_validity': False,
        'new_original_source_pixels_acquired': 0,
        'patient_independence_verified': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels-zip',type=Path,required=True)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Result exists; never overwrite previous research output.')
    spec = validate_spec(args.spec)
    report = execute(args.labels_zip, spec)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False) + '\n'
    args.out.write_text(content,encoding='utf-8')
    print('Verified ten allowed source annotations; no reserved exam accessed.')
    print('Public density summary JSON:')
    print(json.dumps(report['summary_by_candidate_density'], sort_keys=True, separators=(',',':')))
    print('Aggregate SHA-256:',hashlib.sha256(content.encode()).hexdigest())


if __name__ == '__main__':
    main()
