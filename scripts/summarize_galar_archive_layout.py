"""Summarize 7z -slt index-only output without retaining original frame paths.

Input is private listing obtained from sparse archive whose verified metadata-only
ranges were fetched by probe_galar_archive.py. No pixels are involved. The tool
reports aggregate compression-block sizes and per-examination file counts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re

from probe_galar_archive import APPROVED_SOURCES

EXPECTED_EXAMS = frozenset(range(21, 31))
EXAMINATIONS_BY_SOURCE = {
    'fitting-21-30': EXPECTED_EXAMS,
    'unseen-11-20': frozenset(range(11, 21)),
}
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.webp'})


def records(text: str) -> list[dict[str, str]]:
    if '----------' not in text:
        raise ValueError('No 7z entry separator in -slt output.')
    _, remainder = text.split('----------', 1)
    entries = []
    for section in re.split(r'\r?\n\s*\r?\n', remainder):
        data = {}
        for line in section.splitlines():
            if ' = ' not in line:
                continue
            k, value = line.split(' = ', 1)
            if k in data:
                raise ValueError('Duplicate key in a 7z -slt listing record.')
            data[k] = value
        if data.get('Path'):
            entries.append(data)
    if not entries:
        raise ValueError('Empty 7z archive listing.')
    return entries


def get_exam(path: str, *, allowed_exams: frozenset[int] = EXPECTED_EXAMS) -> int | None:
    if (not path or path.startswith(('/', '\\')) or '\x00' in path or
            '..' in path.replace('\\', '/').split('/') or ':' in path):
        raise ValueError('Unsafe archive member path.')
    segments = path.replace('\\', '/').split('/')
    matches = {int(s) for s in segments[:-1] if s.isdigit() and int(s) in allowed_exams}
    if len(matches) > 1:
        raise ValueError('Ambiguous exam ID in archive path.')
    return next(iter(matches)) if matches else None


def summarise(text: str, index_receipt: dict, *, source: str = 'fitting-21-30') -> dict:
    if source not in EXAMINATIONS_BY_SOURCE:
        raise ValueError('Unrecognized approved Galar source profile.')
    expected = APPROVED_SOURCES[source]
    if (index_receipt.get('official_file_id') != expected['id']
            or index_receipt.get('official_full_archive_bytes') != expected['size']
            or (source == 'unseen-11-20' and index_receipt.get('record_type') != expected['receipt_type'])
            or (source == 'fitting-21-30' and index_receipt.get('record_type', expected['receipt_type']) != expected['receipt_type'])
            or index_receipt.get('full_archive_downloaded') is not False
            or index_receipt.get('pixels_acquired') != 0):
        raise ValueError('Trusted matching header-only Galar receipt is required.')
    allowed_exams = EXAMINATIONS_BY_SOURCE[source]
    images = Counter()
    exam21_basename_patterns = Counter()
    blocks: dict[int, dict] = {}
    unassigned = 0
    other = 0
    for entry in records(text):
        path = entry['Path']
        is_dir = entry.get('Folder') == '+' or entry.get('Attributes', '').startswith('D')
        if is_dir:
            get_exam(path, allowed_exams=allowed_exams)
            continue
        suffix = Path(path).suffix.lower()
        blockstr = entry.get('Block', '').strip()
        if not blockstr.isdecimal():
            raise ValueError('Missing/invalid compression block identifier.')
        block = int(blockstr)
        size = entry.get('Size', '')
        if not size.isdecimal():
            raise ValueError('Missing/invalid uncompressed member size.')
        item = blocks.setdefault(block, {'block_id': block, 'member_count': 0,
                                         'image_count': 0, 'examinations': Counter(),
                                         'compressed_bytes': None, 'uncompressed_bytes': 0})
        item['member_count'] += 1
        item['uncompressed_bytes'] += int(size)
        packed = entry.get('Packed Size', '').strip()
        if packed:
            if not packed.isdecimal() or item['compressed_bytes'] is not None:
                raise ValueError('Conflicting packed stream sizes for a block.')
            item['compressed_bytes'] = int(packed)
        if suffix not in IMAGE_EXTENSIONS:
            other += 1
            continue
        exam = get_exam(path, allowed_exams=allowed_exams)
        if exam is None:
            unassigned += 1
            continue
        images[exam] += 1
        if source == 'fitting-21-30' and exam == 21:
            # Structural pattern only. Do not export individual source frame IDs.
            exam21_basename_patterns[re.sub(r'\d+', '<digits>', PurePosixPath(path.replace('\\', '/')).name)] += 1
        item['image_count'] += 1
        item['examinations'][exam] += 1
    if not blocks or any(n < 1 for n in images.values()):
        raise ValueError('No compression blocks or files.')
    if source == 'unseen-11-20':
        if unassigned:
            raise ValueError('Unseen source index contains an unexpected image member.')
        if set(images) != allowed_exams:
            raise ValueError('Unseen source index is missing one or more locked examinations.')
    result = {
        'record_type': (
            'galar-21-29-index-only-block-summary-v1'
            if source == 'fitting-21-30' else 'galar-11-20-index-only-block-summary-v1'
        ),
        'origin_file_id': expected['id'],
        'archive_bytes': index_receipt['official_full_archive_bytes'],
        'pixels_read': 0,
        'full_source_checksum_verified': False,
        'image_members_by_exam': {str(x): images[x] for x in sorted(images)},
        'unassigned_image_members': unassigned,
        'other_file_members': other,
        'total_compression_blocks': len(blocks),
        'blocks': [{**{k:v for k,v in row.items() if k != 'examinations'},
                    'examinations': {str(x): n for x,n in sorted(row['examinations'].items())}}
                   for _, row in sorted(blocks.items())],
        'interpretation': 'Index-only candidate; compressed block sizes are not verified pixel bytes or complete source acquisition.'
    }
    if source == 'fitting-21-30':
        result['exam21_basename_patterns_only'] = dict(sorted(exam21_basename_patterns.items()))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--7z-listing', type=Path, required=True)
    p.add_argument('--source-receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source', choices=tuple(EXAMINATIONS_BY_SOURCE),
                   default='fitting-21-30')
    args = p.parse_args()
    if args.output.exists():
        p.error('Refuse to overwrite previous layout result.')
    receipt = json.loads(args.source_receipt.read_text())
    result = summarise(args.__dict__['7z_listing'].read_text(encoding='utf8'), receipt, source=args.source)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('Parsed archive index: blocks', result['total_compression_blocks'],
          'mapped examinations', len(result['image_members_by_exam']),
          'unassigned image members', result['unassigned_image_members'])


if __name__ == '__main__':
    main()