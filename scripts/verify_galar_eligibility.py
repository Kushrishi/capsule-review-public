"""Private, outcome-concealed source eligibility projection; never print CSV rows.

Use only after committing the dated amendment. CSV bytes enter this worker's
memory, but binary blood values are mapped identically and never retained.
This is trusted-code process separation, not an OS security sandbox.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_galar_archive_layout import get_exam, records

EXAMS = tuple(range(11, 21))
LABEL_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
MAX_MEMBER = 32 * 1024 * 1024
MAX_ROWS = 200_000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def project_csv(stream):
    """Interpret only source ID and binary-label availability, never polarity."""
    reader = csv.reader(stream)
    names = next(reader, [])
    if len(names) != len(set(names)) or not {'frame', 'blood'} <= set(names):
        raise ValueError('Invalid source schema.')
    frame_column, availability_column = names.index('frame'), names.index('blood')
    projection = []
    previous = -1
    # Deliberately identical outputs for both explicit binary labels.
    availability = {'0': 'binary', '1': 'binary', '': 'unknown'}
    for cells in reader:
        if len(cells) != len(names) or len(projection) >= MAX_ROWS:
            raise ValueError('Invalid source row shape or bound.')
        identifier = cells[frame_column]
        if not re.fullmatch(r'[0-9]{1,12}', identifier):
            raise ValueError('Invalid source identity.')
        frame = int(identifier)
        if frame <= previous:
            raise ValueError('Duplicate or unordered source identity.')
        if cells[availability_column] not in availability:
            raise ValueError('Unsupported source availability encoding.')
        projection.append({'frame': frame, 'eligibility': availability[cells[availability_column]]})
        previous = frame
    if not projection:
        raise ValueError('Empty source member.')
    return projection


def project_archive(path, *, expected_sha256=LABEL_SHA):
    """Outer hash first; open exactly the ten approved members, not testzip()."""
    if Path(path).is_symlink() or digest_file(path) != expected_sha256:
        raise ValueError('Publisher archive identity mismatch.')
    result = {}
    with zipfile.ZipFile(path) as archive:
        for exam in EXAMS:
            info = archive.getinfo(f'{exam}.csv')
            if info.is_dir() or not 0 < info.file_size <= MAX_MEMBER:
                raise ValueError('Invalid source member bound.')
            # Duplicate entries for an approved member are ambiguous.
            if sum(x.filename == info.filename for x in archive.filelist) != 1:
                raise ValueError('Duplicate source member.')
            with archive.open(info) as raw:
                with io.TextIOWrapper(raw, encoding='utf-8-sig', newline='') as stream:
                    result[str(exam)] = project_csv(stream)
    return result


def image_identities(listing):
    result = {str(exam): set() for exam in EXAMS}
    for entry in records(listing):
        path = entry['Path']
        if entry.get('Folder') == '+' or entry.get('Attributes', '').startswith('D'):
            continue
        # Validate even nonimage paths, without interpreting nonimage payloads.
        exam = get_exam(path, allowed_exams=frozenset(EXAMS))
        if PurePosixPath(path.replace('\\', '/')).suffix.lower() != '.png':
            continue
        name = PurePosixPath(path.replace('\\', '/')).name
        match = re.fullmatch(r'frame_([0-9]+)\.PNG', name)
        if exam is None or match is None:
            raise ValueError('Unexpected original image identity.')
        frame = int(match.group(1))
        if frame in result[str(exam)]:
            raise ValueError('Duplicate original image identity.')
        result[str(exam)].add(frame)
    if any(not frames for frames in result.values()):
        raise ValueError('Incomplete image-index cohort.')
    return result


def compare_projection(projection, image_frames):
    private, aggregate = {}, {}
    if set(projection) != {str(e) for e in EXAMS} or set(image_frames) != set(projection):
        raise ValueError('Wrong projection cohort.')
    for exam, rows in projection.items():
        images = image_frames[exam]
        row_map = {r['frame']: r['eligibility'] for r in rows}
        eligible = {f for f, flag in row_map.items() if flag == 'binary'}
        unknown = set(row_map) - eligible
        ordered = sorted(images)
        if any((b - a) % 5 for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Unsupported image grid.')
        grid_gaps = {f for a, b in zip(ordered, ordered[1:]) for f in range(a + 5, b, 5)}
        missing = eligible - images
        private[exam] = {
            'source_rows': rows,
            'eligible_source_frames': sorted(eligible),
            'missing_eligible_source_frames': sorted(missing),
            'inferred_grid_gaps': [
                {'frame': f, 'annotation_status': row_map.get(f, 'absent_row')}
                for f in sorted(grid_gaps)
            ],
        }
        aggregate[exam] = {
            'annotation_rows': len(rows), 'eligible_rows': len(eligible),
            'unknown_rows': len(unknown), 'original_png_members': len(images),
            'eligible_images_present': len(eligible & images),
            'eligible_images_missing': len(missing),
            'eligible_image_coverage': len(eligible & images) / len(eligible) if eligible else None,
            'images_without_annotation_row': len(images - set(row_map)),
            'images_with_unknown_annotation': len(images & unknown),
            'inferred_gap_absent_rows': len(grid_gaps - set(row_map)),
            'inferred_gap_unknown_rows': len(grid_gaps & unknown),
            'inferred_gap_eligible_rows': len(grid_gaps & eligible),
        }
    return {'private_examinations': private, 'aggregate': aggregate,
            'all_eligible_images_present': all(x['eligible_images_missing'] == 0
                                             and x['eligible_rows'] > 0 for x in aggregate.values())}


def deny_external_actions(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.fork', 'os.posix_spawn')) or event == 'os.system':
        raise RuntimeError('External actions are forbidden in eligibility projection.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--listing', type=Path, required=True)
    parser.add_argument('--listing-sha256', required=True)
    parser.add_argument('--amendment', type=Path, required=True)
    parser.add_argument('--amendment-sha256', required=True)
    parser.add_argument('--amendment-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
        sys.addaudithook(deny_external_actions)
        repo = Path(__file__).resolve().parents[1]
        if (a.output.resolve().is_relative_to(repo) or a.output.is_symlink()
            or a.output.exists() or not re.fullmatch(r'[0-9a-f]{40}', a.amendment_commit)
            or digest_file(a.listing) != a.listing_sha256
            or digest_file(a.amendment) != a.amendment_sha256):
            raise ValueError('Invalid private destination or provenance pins.')
        compared = compare_projection(project_archive(a.labels), image_identities(a.listing.read_text()))
        result = {
            'schema_version': 1, 'purpose': 'PRIVATE outcome-concealed eligibility; not model evaluation',
            'label_zip_sha256': LABEL_SHA, 'listing_sha256': a.listing_sha256,
            'amendment_sha256': a.amendment_sha256, 'amendment_commit': a.amendment_commit,
            'worker_sha256': digest_file(Path(__file__)),
            'eligibility_projection_sha256': hashlib.sha256(canonical(compared)).hexdigest(),
            **compared,
        }
        payload = canonical(result) + b'\n'
        fd = os.open(a.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({'status': 'eligibility_projection_complete',
                          'private_output_sha256': hashlib.sha256(payload).hexdigest()}))
        return 0
    except Exception:
        # Never echo parser exceptions, cells, filenames or tracebacks.
        print('Eligibility projection failed; no clinical values disclosed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
