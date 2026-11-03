"""Inspect only the ZIP central directory of the official Red Lesion Endoscopy release.

Never transfer an image payload or silently fall back to downloading the 451 MB ZIP.
This is a source feasibility assessment; neither index names nor a ZIP label
alone establish a clinically annotated, independently evaluated video.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZipInfo, BadZipFile

from ranged_zip import AcquisitionError, HTTPRangeReader, _index_members

OFFICIAL_LANDING_PAGE = 'https://rdm.inesctec.pt/dataset/nis-2018-003'
OFFICIAL_DATA_URL = ('https://rdm.inesctec.pt/dataset/'
    '4b80534a-a8f7-472e-8ff7-f35d046c0f62/resource/'
    'e060aa66-fc99-4bf0-be59-92355d7ef73e/download/dataset.zip')
CUMULATIVE_BYTES = 412_500_050  # frozen s288/s280/s284 upper-bound receipt
ORIGINAL_CAP_BYTES = 512 * 1024 * 1024
DEFAULT_PROBE_BYTES = 4 * 1024 * 1024
_SEQUENCE_PATTERN = re.compile(r'(?i)(?:^|/)(?:set[ _-]*2|set[ _-]*ii)(?:/|$)')
_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')


def _bucket(name: str) -> str:
    # Avoid guessing from a bare numeral; only named folder boundaries count.
    norm = name.replace('\\', '/')
    if _SEQUENCE_PATTERN.search(norm):
        return 'set_2_sequential_candidate'
    if re.search(r'(?i)(?:^|/)set[ _-]*1(?:/|$)', norm):
        return 'set_1_nonsequential_candidate'
    return 'other'


def summarize(infos: list[ZipInfo], *, archive_bytes: int,
              transferred_bytes: int, requests: int) -> dict:
    if archive_bytes < 22 or transferred_bytes < 1 or transferred_bytes > DEFAULT_PROBE_BYTES:
        raise ValueError('Out-of-bounds source or probe transfer')
    if len(infos) > 100_000 or len({f.filename for f in infos}) != len(infos):
        raise ValueError('Duplicate ZIP names or excessive index entries')
    groups: dict[str, dict] = defaultdict(lambda: {
        'file_count': 0, 'candidate_images': 0, 'candidate_nonimages': 0,
        'compressed_bytes': 0, 'uncompressed_bytes': 0, 'encrypted_files': 0,
        'likely_masks_by_path': 0,
    })
    for item in infos:
        if item.is_dir():
            continue
        group = groups[_bucket(item.filename)]
        group['file_count'] += 1
        group['compressed_bytes'] += item.compress_size
        group['uncompressed_bytes'] += item.file_size
        group['encrypted_files'] += bool(item.flag_bits & 1)
        if item.filename.casefold().endswith(_IMAGE_EXTS):
            group['candidate_images'] += 1
        else:
            group['candidate_nonimages'] += 1
        # A path suggesting a mask is NOT evidence of a correct aligned mask.
        if re.search(r'(?i)(?:^|/)(?:masks?|annotations?|labels?|ground[ _-]?truth|b)(?:/|$)', item.filename):
            group['likely_masks_by_path'] += 1
    seq = groups.get('set_2_sequential_candidate', {})
    remaining_before = ORIGINAL_CAP_BYTES - CUMULATIVE_BYTES
    remaining_after = remaining_before - transferred_bytes
    compressed = seq.get('compressed_bytes', 0)
    # Require headroom for ZIP local headers and reader overhead, and no encryption.
    tentative = (seq.get('file_count', 0) > 0
                 and seq.get('encrypted_files', 0) == 0
                 and compressed + 4 * 1024 * 1024 <= remaining_after)
    return {
        'source': OFFICIAL_LANDING_PAGE,
        'resource': OFFICIAL_DATA_URL,
        'source_identity': 'archive size and ZIP directory only; full file checksum not verified',
        'archive_bytes': archive_bytes,
        'index_request_count': requests,
        'index_bytes_transferred': transferred_bytes,
        'original_cumulative_upper_bound_bytes': CUMULATIVE_BYTES,
        'total_authorized_source_transfer_bytes': ORIGINAL_CAP_BYTES,
        'remaining_after_index_bytes': remaining_after,
        'total_index_files': sum(group['file_count'] for group in groups.values()),
        'folder_name_structure_sha256': hashlib.sha256('\n'.join(
            sorted(x.filename for x in infos)).encode('utf-8')).hexdigest(),
        'groups': dict(sorted(groups.items())),
        'tentatively_within_remaining_budget': tentative,
        'ready_for_pathology_evaluation': False,
        'frame_labels_verified': False,
        'note': 'Index only: exact frame alignment, lesion truth, permissions for any extraction, and source consistency require independent verification',
    }


def probe(url: str = OFFICIAL_DATA_URL, max_bytes: int = DEFAULT_PROBE_BYTES) -> dict:
    if not 1 <= max_bytes <= DEFAULT_PROBE_BYTES:
        raise ValueError('Hard index-only probe cap is 4 MiB')
    with HTTPRangeReader(url, max_transfer_bytes=max_bytes,
                         read_ahead_bytes=256 * 1024, timeout=25) as remote:
        with ZipFile(remote, 'r', allowZip64=True) as archive:
            infos = _index_members(archive)
        return summarize(infos, archive_bytes=remote.size,
                         transferred_bytes=remote.transferred_bytes,
                         requests=remote.request_count)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-url', default=OFFICIAL_DATA_URL)
    args = parser.parse_args(argv)
    try:
        record = {'status':'index_verified', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                  'result': probe(args.source_url)}
        code = 0
    except (AcquisitionError, BadZipFile, OSError, ValueError, NotImplementedError) as err:
        record = {'status':'source_probe_blocked', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                  'source':OFFICIAL_LANDING_PAGE, 'error':str(err),
                  'transfer_limit_bytes':DEFAULT_PROBE_BYTES,
                  'medical_image_data_downloaded':False}
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error('Refusing to overwrite existing evidence')
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(record, indent=2, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
