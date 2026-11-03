"""Source-verified Galar exam-25 acquisition using one 7z solid block at a time.

Only fitting examination 25 and original source blocks 2, 3 and 4 are allowed.
Each block's compressed data is deleted after its selected PNGs are verified;
the full 10.45-GB compressed source subset is never staged at once.
Patient images, source IDs, labels, and manifests stay in private artifacts,
never in the repository or aggregate CI outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from PIL import Image
import acquire_galar_multiblock as base
from probe_galar_archive import ARCHIVE_SIZE, SOURCE_URL, RangeClient, inspect
from summarize_galar_archive_layout import records, get_exam

EXAM = 25
BLOCKS = (2, 3, 4)
EXPECTED_REQUESTED = 1_013
EXPECTED_ARCHIVE_MEMBERS = 22_477
EXPECTED_ENRICHED = 512
EXPECTED_UNIFORM = 512
EXPECTED_OVERLAP = 11
EXPECTED_ENRICHED_POSITIVE = 256
EXPECTED_UNIFORM_POSITIVE = 14
EXPECTED_BLOCK_TOTAL = 10_447_872_590
MIN_DISK_MARGIN = 2_500_000_000


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check_frozen_selection(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_REQUESTED or {int(r['exam']) for r in rows} != {EXAM}:
        raise ValueError('Galar 25 requested source identities changed.')
    if len({int(r['frame']) for r in rows}) != EXPECTED_REQUESTED:
        raise ValueError('Repeated source frame in frozen selection.')
    enriched = sum(int(r['fit_enriched']) for r in rows)
    reference = sum(int(r['reference_uniform']) for r in rows)
    overlap = sum(int(r['fit_enriched']) * int(r['reference_uniform']) for r in rows)
    ep = sum(int(r['blood']) * int(r['fit_enriched']) for r in rows)
    rp = sum(int(r['blood']) * int(r['reference_uniform']) for r in rows)
    if (enriched, reference, overlap, ep, rp) != (
        EXPECTED_ENRICHED, EXPECTED_UNIFORM, EXPECTED_OVERLAP,
        EXPECTED_ENRICHED_POSITIVE, EXPECTED_UNIFORM_POSITIVE
    ):
        raise ValueError('Galar 25 fitting/reference roles or label support changed.')


def verified_member_partition(listing: str, matched: list[tuple[dict, str]]) -> dict[int, list[tuple[dict, str]]]:
    """Use the original source listing, not inferred filename/chronology, for block assignment."""
    source_blocks: dict[str, int] = {}
    per_block_source = {block: 0 for block in BLOCKS}
    for entry in records(listing):
        path = entry['Path'].replace('\\', '/')
        if entry.get('Folder') == '+' or entry.get('Attributes', '').startswith('D'):
            continue
        if get_exam(path) != EXAM or Path(path).suffix.upper() != '.PNG':
            continue
        block_raw = entry.get('Block', '').strip()
        if not block_raw.isdecimal() or int(block_raw) not in BLOCKS:
            raise ValueError('Galar 25 source PNG outside approved solid blocks.')
        if path in source_blocks:
            raise ValueError('Duplicate archive member path in source index.')
        block = int(block_raw)
        source_blocks[path] = block
        per_block_source[block] += 1
    if len(source_blocks) != EXPECTED_ARCHIVE_MEMBERS or per_block_source != base.EXPECTED_EXAM_BLOCK_IMAGES:
        raise ValueError('Official source Galar 25 archive member block inventory differs.')
    partition = {block: [] for block in BLOCKS}
    found = set()
    for row, path in matched:
        if path not in source_blocks or int(row['frame']) in found:
            raise ValueError('Requested frame missing/duplicated in verified listing.')
        found.add(int(row['frame']))
        partition[source_blocks[path]].append((row, path))
    if len(matched) != EXPECTED_REQUESTED or any(not partition[block] for block in BLOCKS):
        raise ValueError('Incomplete or unexpectedly empty selected solid-block request.')
    return partition


def create_sparse_from_verified_headers(header_dir: Path, receipt: dict, output: Path) -> None:
    """Create a fresh sparse 7z with only header bytes, never copy the 32-GB logical file."""
    if output.exists():
        raise FileExistsError('Refuse to overwrite partial source archive.')
    parts = receipt['parts']
    if {p['name'] for p in parts} != {'signature-header.bin', 'next-header.bin', 'encoded-index-0.bin'}:
        raise ValueError('Unexpected 7z source metadata parts.')
    with output.open('xb') as dst:
        dst.truncate(ARCHIVE_SIZE)  # logical length; holes occupy almost no physical disk
        for part in parts:
            start, length = int(part['offset']), int(part['length'])
            if start < 0 or length <= 0 or start + length > ARCHIVE_SIZE:
                raise ValueError('Invalid verified metadata part span.')
            raw = (header_dir / part['name']).read_bytes()
            if len(raw) != length or sha_bytes(raw) != part['sha256']:
                raise ValueError('Verified source metadata was altered.')
            dst.seek(start)
            dst.write(raw)


def copy_verified_selection(portion: Path, selected: list[tuple[dict, str]],
                            dest: Path, observed: dict[int, dict]) -> None:
    """Check one independently extracted package before retaining its originals."""
    expected = {int(r['frame']): r for r, _ in selected}
    with zipfile.ZipFile(portion) as archive:
        if archive.testzip() is not None:
            raise ValueError('Partial source ZIP CRC failed.')
        manifest = json.loads(archive.read('verified-private-manifest.json'))
        if len(manifest) != len(expected) or {int(r['frame']) for r in manifest} != set(expected):
            raise ValueError('Extracted private manifest does not match requested frames.')
        image_names = {f'images/{EXAM:03d}/frame_{n:06d}.PNG' for n in expected}
        if set(archive.namelist()) != image_names | {'verified-private-manifest.json'}:
            raise ValueError('Extra or missing images in extracted portion.')
        dest.mkdir(parents=True, exist_ok=True)
        for identity in manifest:
            n = int(identity['frame'])
            row = expected[n]
            if n in observed or identity['exam'] != EXAM or identity['filename'] != f'frame_{n:06d}.PNG':
                raise ValueError('Duplicate or changed source identity.')
            if any(int(identity[field]) != int(row[field]) for field in ('blood', 'fit_enriched', 'reference_uniform')):
                raise ValueError('Extracted blood label or fitting role changed.')
            name = f'images/{EXAM:03d}/frame_{n:06d}.PNG'
            target = dest / identity['filename']
            data = archive.read(name)
            if len(data) != identity['source_bytes'] or sha_bytes(data) != identity['source_image_sha256']:
                raise ValueError('Extracted original PNG byte identity mismatch.')
            with target.open('xb') as stream:
                stream.write(data)
            with Image.open(target) as im:
                if im.format != 'PNG':
                    raise ValueError('Original Galar member is not a PNG.')
                im.verify()
            observed[n] = identity


def final_package(images: Path, observed: dict[int, dict], output: Path) -> dict:
    if output.exists():
        raise FileExistsError('Refuse to overwrite final private source package.')
    if len(observed) != EXPECTED_REQUESTED:
        raise ValueError('Incomplete verified Galar 25 source frames.')
    manifest = [observed[n] for n in sorted(observed)]
    manifest_path = images.parent / 'verified-private-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for row in manifest:
            archive.write(images / row['filename'], f'images/{EXAM:03d}/{row["filename"]}')
        archive.write(manifest_path, 'verified-private-manifest.json')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != EXPECTED_REQUESTED + 1:
            raise ValueError('Final private source artifact CRC/membership mismatch.')
    return {
        'examination': EXAM,
        'verified_source_images': EXPECTED_REQUESTED,
        'blood_positive_selected_images': sum(int(r['blood']) for r in manifest),
        'source_image_bytes': sum(int(r['source_bytes']) for r in manifest),
        'source_package_sha256': base.sha256_file(output),
        'private_manifest_sha256': base.sha256_file(manifest_path),
        'original_archive_full_md5_verified': False,
        'protected_evaluation_examinations_read': False,
    }


def acquire(layout_path: Path, selection: Path, workdir: Path, output: Path) -> dict:
    if workdir.exists() or output.exists():
        raise FileExistsError('Refuse overwrite of medical source staging/output.')
    base.configure_exam_profile(EXAM)
    workdir.mkdir(parents=True)
    layout = json.loads(layout_path.read_text(encoding='utf-8'))
    index_dir = workdir / 'index'
    index_client = RangeClient(SOURCE_URL, ARCHIVE_SIZE)
    source_receipt = inspect(index_client, index_dir, sparse_path=index_dir / 'headers-only.7z')
    approved_ranges = base.check_source(layout, source_receipt, selection)
    if tuple(i for i, _, _ in approved_ranges) != BLOCKS or sum(n for _, _, n in approved_ranges) != EXPECTED_BLOCK_TOTAL:
        raise ValueError('Unexpected verified source block bounds.')
    rows = base.requested_rows(selection, exam=EXAM)
    check_frozen_selection(rows)
    listing = workdir / 'original-7z-listing-private.txt'
    with listing.open('wb') as output_listing:
        completed = subprocess.run(['7z', 'l', '-slt', str(index_dir / 'headers-only.7z')],
                                   stdout=output_listing, stderr=subprocess.PIPE,
                                   check=False, timeout=180)
    if completed.returncode:
        raise ValueError('Real official 7z source index failed before compressed-frame transfer.')
    matched = base.find_members(listing.read_text(encoding='utf-8'), rows)
    partition = verified_member_partition(listing.read_text(encoding='utf-8'), matched)
    saved_images = workdir / 'verified-selected-images'
    observed: dict[int, dict] = {}
    transfers = []
    for block_id, start, length in approved_ranges:
        if shutil.disk_usage(workdir).free < length + MIN_DISK_MARGIN:
            raise ValueError('Insufficient disk margin to stream next 7z source block.')
        block_stage = workdir / f'transient-block-{block_id}'
        block_stage.mkdir()
        sparse = block_stage / 'source-block-only.7z'
        create_sparse_from_verified_headers(index_dir, source_receipt, sparse)
        digest = base.download_verified_range(sparse, block_id, start, length)
        portion_zip = block_stage / 'private-selected-portion.zip'
        result = base.extract_and_package(sparse, partition[block_id], block_stage, portion_zip)
        if result['verified_source_images'] != len(partition[block_id]):
            raise ValueError('Source block extracted a different frame count.')
        copy_verified_selection(portion_zip, partition[block_id], saved_images, observed)
        transfers.append({**digest, 'selected_images_verified': len(partition[block_id])})
        shutil.rmtree(block_stage)  # Release source compressed block before next HTTP transfer
        print(f'Exam {EXAM}: verified block {block_id}, acquired {len(partition[block_id])} selected PNGs', flush=True)
    receipt = final_package(saved_images, observed, output)
    receipt.update({
        'official_source_file_id': 45258019,
        'total_source_compressed_bytes_transferred': sum(x['compressed_bytes'] for x in transfers),
        'verified_http_block_receipts': transfers,
        'index_bytes_transferred': index_client.total,
        'source_full_archive_bytes': ARCHIVE_SIZE,
        'patient_independence_confirmed': False,
        'clinical_validity': False,
        'original_medical_images_or_frame_labels_committed_to_github': False,
    })
    (workdir / 'aggregate-receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args(argv)
    result = acquire(args.layout, args.selection, args.workdir, args.package)
    print('Verified original Galar 25 PNGs:', result['verified_source_images'],
          'blood-labelled:', result['blood_positive_selected_images'], flush=True)


if __name__ == '__main__':
    main()
