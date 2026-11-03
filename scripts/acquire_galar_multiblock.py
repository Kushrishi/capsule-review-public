"""Acquire a frozen, source-verified Galar fitting sample across known solid 7z blocks.

Approved fitting cases: exam 25 blocks 2/3/4, exam 27 blocks 5/6, exam 29 blocks 7/8, and exam 30 blocks 8/9. The official full-archive
MD5 cannot be asserted from a partial transfer. Never upload image identities,
medical pixels or private pathology labels to Git.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.request
import zipfile

from probe_galar_archive import (
    ARCHIVE_SIZE, EXPECTED_FULL_MD5, FILE_ID, SOURCE_URL,
    allowed_redirect, inspect, RangeClient,
)
from summarize_galar_archive_layout import records, get_exam

EXAM = 30
BLOCKS = (8, 9)
EXPECTED_BLOCK_BYTES = {8: 3_514_256_456, 9: 630_002_169}
EXPECTED_BLOCK_START = {8: 27_843_799_086, 9: 31_358_055_542}
EXPECTED_EXAM_BLOCK_IMAGES = {8: 13_957, 9: 2_996}
EXPECTED_EXAM_IMAGES = 16_953
EXPECTED_PRIVATE_PLAN_SHA256 = '1aedfcdecbb270687a660acd50f312803ed0884308ea9a0973102aac242409f1'
HEADER_PART_HASHES = {
    'signature-header.bin': '44191aaf136fd4cc2a5bafad2b828bc96310e235731752eaa5f39aa8f912611f',
    'next-header.bin': 'c8de7cca5b73224778e5516e0f9079f00989adbe7a3f0034a6c3fae06889ca5d',
    'encoded-index-0.bin': '61d38a2c6b0ed445a348ea11287189f9ba86f541678900cc96b8fb674c9e1043',
}
MAX_TOTAL_SOURCE_BYTES = 4_200_000_000
EXPECTED_REQUESTED_IMAGES = 1006

# Closed, source-index-verified fitting profiles. Keep exam30's proven default
# unchanged. Only the single-process CLI uses the configuration function below.
FROZEN_EXAM_PROFILES = {
    25: {
        'blocks': (2, 3, 4),
        'block_bytes': {2: 3_470_070_406, 3: 3_539_043_971, 4: 3_438_758_213},
        'block_starts': {2: 6_950_241_905, 3: 10_420_312_311, 4: 13_959_356_282},
        'block_exam_images': {2: 1_762, 3: 15_058, 4: 5_657},
        'exam_images': 22_477,
        'requested_images': 1_013,
        'max_source_bytes': 10_500_000_000,
    },
    27: {
        'blocks': (5, 6),
        'block_bytes': {5: 3_489_830_304, 6: 3_455_329_610},
        'block_starts': {5: 17_398_114_495, 6: 20_887_944_799},
        'block_exam_images': {5: 10_842, 6: 3_954},
        'exam_images': 14_796,
        'requested_images': 1_005,
        'max_source_bytes': 7_000_000_000,
    },
    29: {
        'blocks': (7, 8),
        'block_bytes': {7: 3_500_524_677, 8: 3_514_256_456},
        'block_starts': {7: 24_343_274_409, 8: 27_843_799_086},
        'block_exam_images': {7: 13_455, 8: 2_563},
        'exam_images': 16_018,
        'requested_images': 1_009,
        'max_source_bytes': 7_100_000_000,
    },
    30: {
        'blocks': (8, 9),
        'block_bytes': {8: 3_514_256_456, 9: 630_002_169},
        'block_starts': {8: 27_843_799_086, 9: 31_358_055_542},
        'block_exam_images': {8: 13_957, 9: 2_996},
        'exam_images': 16_953,
        'requested_images': 1_006,
        'max_source_bytes': 4_200_000_000,
    },
}


def configure_exam_profile(exam: int) -> None:
    """Choose one explicitly allowlisted source examination before any I/O.

    The module-level variables preserve compatibility with the original
    verified exam30 script/tests; every acquisition runs in a fresh process.
    """
    if type(exam) is not int or exam not in FROZEN_EXAM_PROFILES:
        raise ValueError('Only prespecified fitting examinations 25, 27, 29 and 30 are allowed.')
    p = FROZEN_EXAM_PROFILES[exam]
    global EXAM, BLOCKS, EXPECTED_BLOCK_BYTES, EXPECTED_BLOCK_START
    global EXPECTED_EXAM_BLOCK_IMAGES, EXPECTED_EXAM_IMAGES
    global EXPECTED_REQUESTED_IMAGES, MAX_TOTAL_SOURCE_BYTES
    EXAM = exam
    BLOCKS = p['blocks']
    EXPECTED_BLOCK_BYTES = dict(p['block_bytes'])
    EXPECTED_BLOCK_START = dict(p['block_starts'])
    EXPECTED_EXAM_BLOCK_IMAGES = dict(p['block_exam_images'])
    EXPECTED_EXAM_IMAGES = p['exam_images']
    EXPECTED_REQUESTED_IMAGES = p['requested_images']
    MAX_TOTAL_SOURCE_BYTES = p['max_source_bytes']


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check_source(layout: dict, receipt: dict, selection: Path) -> list[tuple[int, int, int]]:
    """Verify locked publisher structure, reserved split and approved exact ranges."""
    if (receipt.get('official_file_id') != FILE_ID
            or receipt.get('official_full_archive_bytes') != ARCHIVE_SIZE
            or receipt.get('full_archive_downloaded') is not False
            or receipt.get('pixels_acquired') != 0
            or layout.get('origin_file_id') != FILE_ID
            or layout.get('archive_bytes') != ARCHIVE_SIZE
            or layout.get('total_compression_blocks') != 10
            or layout.get('unassigned_image_members') != 0
            or layout.get('image_members_by_exam', {}).get(str(EXAM)) != EXPECTED_EXAM_IMAGES
            or len(layout.get('blocks', [])) != 10
            or [b['block_id'] for b in layout['blocks']] != list(range(10))):
        raise ValueError('Official Galar metadata is missing or changed.')
    if {part['name']: part['sha256'] for part in receipt.get('parts', [])} != HEADER_PART_HASHES:
        raise ValueError('Verified 7z index/header part hashes changed.')
    if sum(b['compressed_bytes'] for b in layout['blocks']) + sum(
            part['length'] for part in receipt['parts']) != ARCHIVE_SIZE:
        raise ValueError('Compressed block lengths do not reconstruct official source size.')
    if sha256_file(selection) != EXPECTED_PRIVATE_PLAN_SHA256:
        raise ValueError('Original source-frame selection manifest was changed.')
    ranges = []
    for idx in BLOCKS:
        block = layout['blocks'][idx]
        start = 32 + sum(b['compressed_bytes'] for b in layout['blocks'][:idx])
        length = block['compressed_bytes']
        if (start != EXPECTED_BLOCK_START[idx]
                or length != EXPECTED_BLOCK_BYTES[idx]
                or block['examinations'].get(str(EXAM)) != EXPECTED_EXAM_BLOCK_IMAGES[idx]):
            raise ValueError('Selected Galar block range/examination coverage mismatched.')
        ranges.append((idx, start, length))
    if sum(length for _, _, length in ranges) > MAX_TOTAL_SOURCE_BYTES:
        raise ValueError('Compressed source transfer exceeds fixed limit.')
    if sum(EXPECTED_EXAM_BLOCK_IMAGES.values()) != EXPECTED_EXAM_IMAGES:
        raise ValueError('Expected source image partition does not cover the examination.')
    return ranges


def requested_rows(private_plan: Path, exam: int | None = None) -> list[dict]:
    if exam is None:
        exam = EXAM
    if exam != EXAM:
        raise ValueError(f'Only the preregistered fitting examination {EXAM} is permitted.')
    result = []
    with private_plan.open(encoding='utf-8', newline='') as inp:
        reader = csv.DictReader(inp)
        expected = {'exam', 'frame', 'filename', 'blood', 'fit_enriched',
                    'reference_uniform', 'source_csv_sha256'}
        if set(reader.fieldnames or []) != expected:
            raise ValueError('Unrecognized private frame-selection schema.')
        for row in reader:
            source_exam = int(row['exam'])
            if source_exam not in range(21, 31):
                raise ValueError('An evaluation or unapproved examination entered fitting selection.')
            if source_exam != EXAM:
                continue
            frame = int(row['frame'])
            if (frame < 0 or row['filename'] != f'frame_{frame:06d}.PNG'
                    or row['blood'] not in ('0', '1')
                    or row['fit_enriched'] not in ('0', '1')
                    or row['reference_uniform'] not in ('0', '1')
                    or not (row['fit_enriched'] == '1' or row['reference_uniform'] == '1')):
                raise ValueError('Invalid original source-frame ID, label, or selection role.')
            result.append(row)
    if len(result) != EXPECTED_REQUESTED_IMAGES or len({int(r['frame']) for r in result}) != EXPECTED_REQUESTED_IMAGES:
        raise ValueError(f'Frozen examination-{EXAM} image request is incomplete or duplicated.')
    return result


def find_members(listing: str, wanted: list[dict]) -> list[tuple[dict, str]]:
    lookup = {int(r['frame']): r for r in wanted}
    if len(lookup) != len(wanted):
        raise ValueError('Duplicate private source-frame ID.')
    seen: dict[int, str] = {}
    per_block = {b: 0 for b in BLOCKS}
    for member in records(listing):
        path = member['Path'].replace('\\', '/')
        if member.get('Folder') == '+' or member.get('Attributes', '').startswith('D'):
            continue
        if get_exam(path) != EXAM or PurePosixPath(path).suffix.upper() != '.PNG':
            continue
        match = re.fullmatch(r'frame_(\d+)\.PNG', PurePosixPath(path).name)
        if match is None:
            raise ValueError('Unexpected actual source-image filename; no guessing.')
        block_raw = member.get('Block', '').strip()
        if block_raw not in {str(block) for block in BLOCKS}:
            raise ValueError(f'Source exam{EXAM} member unexpectedly belongs to another solid block.')
        block = int(block_raw)
        per_block[block] += 1
        frame = int(match.group(1))
        if frame in seen:
            raise ValueError('Ambiguous duplicate source image ID in original 7z index.')
        seen[frame] = path
    if per_block != EXPECTED_EXAM_BLOCK_IMAGES:
        raise ValueError(f'Real 7z listing does not match complete source exam{EXAM} block membership.')
    if not set(lookup).issubset(seen):
        raise ValueError('A frozen requested source image does not exist in the official 7z index.')
    return [(r, seen[int(r['frame'])]) for r in wanted]


def download_verified_range(sparse: Path, block_id: int, start: int, length: int,
                            *, url: str = SOURCE_URL, allow_mock_http: bool = False) -> dict:
    if (not allow_mock_http and (
            url != SOURCE_URL or block_id not in BLOCKS
            or start != EXPECTED_BLOCK_START[block_id]
            or length != EXPECTED_BLOCK_BYTES[block_id])):
        raise ValueError('Unapproved medical-image source range, URL or block.')
    if (length <= 0 or length > MAX_TOTAL_SOURCE_BYTES or start < 0
            or start + length > ARCHIVE_SIZE):
        raise ValueError('Unbounded source-byte request rejected.')
    req = urllib.request.Request(url, headers={
        'Range': f'bytes={start}-{start+length-1}',
        'Accept-Encoding': 'identity',
        'User-Agent': 'capsule-review/0.2 research source-verification',
    })
    h = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=120) as response:
        if response.status != 206:
            raise ValueError('Exact HTTP 206 byte ranges required before reading any medical pixels.')
        if not allow_mock_http and not allowed_redirect(response.geturl()):
            raise ValueError('Untrusted medical-source redirect.')
        declared_total = response.headers.get('X-Source-Size', str(ARCHIVE_SIZE)) if allow_mock_http else str(ARCHIVE_SIZE)
        if response.headers.get('Content-Range') != f'bytes {start}-{start+length-1}/{declared_total}':
            raise ValueError('Official source Content-Range disagrees with preverified block positions.')
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Unexpected compressed HTTP transfer encoding.')
        declared_length = response.headers.get('Content-Length')
        if declared_length is not None and (not declared_length.isdecimal() or int(declared_length) != length):
            raise ValueError('Source declares unexpected length.')
        with sparse.open('r+b') as out:
            out.seek(start)
            while total < length:
                part = response.read(min(1 << 20, length-total))
                if not part:
                    raise ValueError('Truncated source transfer.')
                total += len(part)
                h.update(part)
                out.write(part)
            if response.read(1):
                raise ValueError('Extra bytes outside the permitted source range.')
    return {'block_id': block_id, 'offset': start, 'compressed_bytes': total,
            'compressed_block_sha256': h.hexdigest(), 'source_archive_full_md5_verified': False}


def extract_and_package(sparse: Path, members: list[tuple[dict, str]], stage: Path,
                        target: Path) -> dict:
    from PIL import Image
    if target.exists() or (stage / 'extracted').exists():
        raise FileExistsError('Refusing overwrite of existing private medical-data output.')
    extracted = stage / 'extracted'
    extracted.mkdir()
    include = stage / 'verified-requested-member-paths-private.txt'
    include.write_text('\n'.join(path for _, path in members) + '\n', encoding='utf-8')
    completed = subprocess.run(
        ['7z', 'x', '-y', '-bso0', '-bse2', f'-o{extracted}', f'-i@{include}', str(sparse)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1000, check=False,
    )
    if completed.returncode:
        raise ValueError('7z decompression/source member CRC error; not publishing any output.')
    selected = stage / 'selected-images'
    selected.mkdir(exist_ok=False)
    verified = []
    total = 0
    for row, name in members:
        rel = PurePosixPath(name)
        if rel.is_absolute() or any(p in {'', '..'} for p in rel.parts):
            raise ValueError('Unsafe medical source image path.')
        original = (extracted / Path(*rel.parts)).resolve(strict=True)
        if not original.is_relative_to(extracted.resolve()) or not original.is_file():
            raise ValueError('Image extraction escapes controlled directory.')
        with Image.open(original) as image:
            if image.format != 'PNG':
                raise ValueError('7z source member is not a valid original PNG.')
            image.verify()
        frame = int(row['frame'])
        filename = f'frame_{frame:06d}.PNG'
        dest = selected / filename
        shutil.copyfile(original, dest)
        digest = sha256_file(dest)
        size = dest.stat().st_size
        verified.append({'exam': EXAM, 'frame': frame, 'filename': filename,
                         'source_image_sha256': digest, 'source_bytes': size,
                         'blood': int(row['blood']),
                         'fit_enriched': int(row['fit_enriched']),
                         'reference_uniform': int(row['reference_uniform'])})
        total += size
    manifest = stage / 'verified-private-manifest.json'
    manifest.write_text(json.dumps(verified, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
        for row in verified:
            bundle.write(selected / row['filename'], arcname=f'images/{EXAM:03d}/{row["filename"]}')
        bundle.write(manifest, arcname='verified-private-manifest.json')
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Corrupt final source-image ZIP.')
    return {'examination': EXAM, 'verified_source_images': len(verified),
            'blood_positive_selected_images': sum(x['blood'] for x in verified),
            'source_image_bytes': total, 'source_package_sha256': sha256_file(target),
            'private_manifest_sha256': sha256_file(manifest),
            'source_full_md5_verified': False,
            'private_source_images_committed_to_github': False}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exam', type=int, choices=(25, 27, 29, 30), default=30)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--workdir', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    a = p.parse_args()
    configure_exam_profile(a.exam)
    if a.workdir.exists() or a.package.exists():
        p.error('Refusing overwrite of existing medical data or staging directory.')
    layout = json.loads(a.layout.read_text(encoding='utf-8'))
    a.workdir.mkdir(parents=True)
    index_dir = a.workdir / 'index'
    index_client = RangeClient(SOURCE_URL, ARCHIVE_SIZE)
    receipt = inspect(index_client, index_dir, sparse_path=index_dir / 'headers-only.7z')
    ranges = check_source(layout, receipt, a.selection)
    sparse = index_dir / 'headers-only.7z'
    listing = a.workdir / 'full-source-member-index-private.txt'
    with listing.open('wb') as out:
        result = subprocess.run(['7z', 'l', '-slt', str(sparse)],
                                stdout=out, stderr=subprocess.PIPE, timeout=200, check=False)
    if result.returncode:
        raise ValueError('7z source archive listing failed before medical-image transfer.')
    matched = find_members(listing.read_text(encoding='utf-8'), requested_rows(a.selection))
    required = sum(n for _, _, n in ranges) + 5_000_000_000
    if shutil.disk_usage(a.workdir).free < required:
        raise ValueError('Insufficient runner disk for two-block original source acquisition.')
    receipts = []
    for idx, start, length in ranges:
        result = download_verified_range(sparse, idx, start, length)
        receipts.append(result)
        print(f'Actual verified source block {idx}: {length:,} bytes', flush=True)
    package_receipt = extract_and_package(sparse, matched, a.workdir, a.package)
    package_receipt.update({
        'source_archive_file_id': FILE_ID,
        'source_archive_expected_md5_not_verified': EXPECTED_FULL_MD5,
        'source_index_bytes_transferred': index_client.total,
        'block_transfers': receipts,
        'source_full_archive_bytes': ARCHIVE_SIZE,
        'clinical_validation': False,
    })
    (a.workdir / 'aggregate-receipt.json').write_text(
        json.dumps(package_receipt, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print('Original verified Galar images:', package_receipt['verified_source_images'],
          'explicit blood-positive:', package_receipt['blood_positive_selected_images'], flush=True)


if __name__ == '__main__':
    main()