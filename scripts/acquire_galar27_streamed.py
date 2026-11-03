"""Acquire Galar examination 27 using the verified one-block-at-a-time 7z engine.

Only source blocks 5 and 6 are permitted; every original PNG is checked before
retention. This adapter does not change the proven examination-25 implementation.
All source frames, labels and model scores remain private.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import acquire_galar25_streamed as streamer
import acquire_galar_multiblock as base

EXAM = 27
BLOCKS = (5, 6)
EXPECTED_IMAGES = 1005
EXPECTED_SOURCE_BLOCK_BYTES = 6_945_159_914


def configure() -> None:
    """Select only the pre-frozen examination-27 profile, never a dynamic exam."""
    base.configure_exam_profile(EXAM)
    assert base.EXAM == EXAM and base.BLOCKS == BLOCKS
    assert base.EXPECTED_REQUESTED_IMAGES == EXPECTED_IMAGES
    assert sum(base.EXPECTED_BLOCK_BYTES.values()) == EXPECTED_SOURCE_BLOCK_BYTES
    streamer.EXAM = EXAM
    streamer.BLOCKS = BLOCKS
    streamer.EXPECTED_REQUESTED = EXPECTED_IMAGES
    streamer.EXPECTED_ARCHIVE_MEMBERS = 14796
    streamer.EXPECTED_ENRICHED = 512
    streamer.EXPECTED_UNIFORM = 512
    streamer.EXPECTED_OVERLAP = 19
    streamer.EXPECTED_ENRICHED_POSITIVE = 256
    streamer.EXPECTED_UNIFORM_POSITIVE = 26
    streamer.EXPECTED_BLOCK_TOTAL = EXPECTED_SOURCE_BLOCK_BYTES
    streamer.MIN_DISK_MARGIN = 2_500_000_000


def acquire(layout: Path, selection: Path, workdir: Path, package: Path) -> dict:
    configure()
    result = streamer.acquire(layout, selection, workdir, package)
    if (result['examination'] != EXAM or result['verified_source_images'] != EXPECTED_IMAGES
            or result['total_source_compressed_bytes_transferred'] != EXPECTED_SOURCE_BLOCK_BYTES
            or [block['block_id'] for block in result['verified_http_block_receipts']] != list(BLOCKS)):
        raise ValueError('Verified Galar-27 source acquisition disagrees with frozen protocol.')
    return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('layout', 'selection', 'workdir', 'package'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    out = acquire(args.layout, args.selection, args.workdir, args.package)
    print(json.dumps({
        'exam': EXAM,
        'verified_original_pngs': out['verified_source_images'],
        'source_compressed_bytes': out['total_source_compressed_bytes_transferred'],
        'blood_positive_images_in_enriched_union': out['blood_positive_selected_images'],
        'full_archive_md5_verified': False,
        'clinical_validation': False
    }, sort_keys=True))


if __name__ == '__main__':
    main()
