"""One-time source-verified Galar 22 + 24 blood-negative *annotation* acquisition.

Exact, preverified Galar 7z blocks 0/1/2 are streamed one at a time.
Only the already frozen 512-per-exam label-blind 22/24 PNG positions are
extracted and retained privately. No held-out cohort, model or clinical claims.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.request
import zipfile

from PIL import Image
from probe_galar_archive import ARCHIVE_SIZE, FILE_ID, SOURCE_URL, RangeClient, inspect, allowed_redirect
from summarize_galar_archive_layout import records, get_exam

EXAMS = (22, 24)
BLOCKS = (0, 1, 2)
EXPECTED_FRAMES = 512
EXPECTED_TOTAL = 1024
SOURCE_CORRECTED_ZIP_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
FROZEN_REQUEST_SHA = '1aedfcdecbb270687a660acd50f312803ed0884308ea9a0973102aac242409f1'
FROZEN_SPEC_BLOB = '590d5c11d5536dd4368e31cfea16af53b191941c'
COMPRESSED = {
    0: (32, 3_474_498_092, 'c678458d4ef075de1215844dd78079e2e48e9fb894140c7fa5cc1708307bf7fd'),
    1: (3_474_498_124, 3_475_743_781, 'b5086f018b7e88c57db7562af624c468796a7b1e812101d07236c184131b08f6'),
    2: (6_950_241_905, 3_470_070_406, '793b010cd7ec383daabbafeb6852646cd791decbc31982976fb6ae64adb0fd34'),
}
EXAM_SOURCE_BLOCK_COUNTS = {22: {0: 6244, 1: 1285}, 24: {1: 1225, 2: 12193}}
EXAM_SOURCE_COUNTS = {22: 7529, 24: 13418}
INDEX_SHA = {
    'signature-header.bin': '44191aaf136fd4cc2a5bafad2b828bc96310e235731752eaa5f39aa8f912611f',
    'next-header.bin': 'c8de7cca5b73224778e5516e0f9079f00989adbe7a3f0034a6c3fae06889ca5d',
    'encoded-index-0.bin': '61d38a2c6b0ed445a348ea11287189f9ba86f541678900cc96b8fb674c9e1043',
}
MAX_SOURCE_TRANSFER = 10_420_312_279
MIN_DISK_MARGIN = 2_500_000_000
EXPECTED_FIELDS = {'exam', 'frame', 'filename', 'blood', 'fit_enriched', 'reference_uniform', 'source_csv_sha256'}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def verify_protocol(path: Path) -> dict:
    raw = path.read_bytes()
    if git_blob(raw) != FROZEN_SPEC_BLOB:
        raise ValueError('Preacquisition protocol is not the immutable Git blob.')
    spec = json.loads(raw)
    source = spec['source_archive']
    requests = spec['official_corrected_annotations']
    expected = [dict(block_id=i, offset=COMPRESSED[i][0], bytes=COMPRESSED[i][1],
                     expected_sha256=COMPRESSED[i][2]) for i in BLOCKS]
    if (spec['allowed_examination_ids'] != list(EXAMS)
        or requests['sha256'] != SOURCE_CORRECTED_ZIP_SHA
        or requests['original_frozen_requested_frame_manifest_sha256'] != FROZEN_REQUEST_SHA
        or source['file_id'] != FILE_ID or source['archive_bytes'] != ARCHIVE_SIZE
        or source['exact_allowed_compressed_blocks'] != expected
        or source['total_exact_compressed_transfer_bytes'] != MAX_SOURCE_TRANSFER
        or source['verified_index_component_sha256'] != INDEX_SHA
        or spec['selection_and_privacy']['explicit_expected_pngs'] != EXPECTED_TOTAL):
        raise ValueError('Frozen source, selection or expenditure bounds changed.')
    return spec


def read_frozen_requests(path: Path) -> dict[int, dict[int, dict]]:
    if sha256_file(path) != FROZEN_REQUEST_SHA:
        raise ValueError('Original fitting-plan CSV SHA-256 mismatch.')
    out: dict[int, dict[int, dict]] = {exam: {} for exam in EXAMS}
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != EXPECTED_FIELDS or len(reader.fieldnames or []) != len(EXPECTED_FIELDS):
            raise ValueError('Frozen source-frame request columns changed.')
        for row in reader:
            if not (row['exam'].isdigit() and row['frame'].isdigit()):
                raise ValueError('Malformed original source request identity.')
            exam, frame = int(row['exam']), int(row['frame'])
            if exam not in EXAMS:
                continue  # Other previously inspected fitting requests are not acquired.
            if (frame < 0 or row['filename'] != f'frame_{frame:06d}.PNG'
                or row['blood'] != '0' or row['fit_enriched'] != '1'
                or row['reference_uniform'] != '1'
                or not re.fullmatch('[a-f0-9]{64}', row['source_csv_sha256'])):
                raise ValueError('Incorrect blood-label/fitting roles or original source frame name.')
            if frame in out[exam]:
                raise ValueError('Repeated original source frame ID in frozen plan.')
            out[exam][frame] = row
    if any(len(out[exam]) != EXPECTED_FRAMES for exam in EXAMS):
        raise ValueError('Missing frozen 512-image reference + training source selection.')
    return out


def validate_source_index(layout: dict, receipt: dict, source_blocks: dict) -> None:
    if (receipt.get('official_file_id') != FILE_ID or receipt.get('official_full_archive_bytes') != ARCHIVE_SIZE
        or receipt.get('full_archive_downloaded') is not False or receipt.get('pixels_acquired') != 0
        or {p['name']: p['sha256'] for p in receipt.get('parts', [])} != INDEX_SHA
        or layout.get('origin_file_id') != FILE_ID or layout.get('archive_bytes') != ARCHIVE_SIZE
        or layout.get('total_compression_blocks') != 10 or layout.get('unassigned_image_members') != 0
        or len(layout.get('blocks', [])) != 10
        or sum(v['compressed_bytes'] for v in layout['blocks']) + sum(p['length'] for p in receipt['parts']) != ARCHIVE_SIZE):
        raise ValueError('Original source archive index structure or header SHA changed.')
    for exam in EXAMS:
        if layout.get('image_members_by_exam', {}).get(str(exam)) != EXAM_SOURCE_COUNTS[exam]:
            raise ValueError('Original examination image count disagrees with frozen index.')
    for block in BLOCKS:
        b = layout['blocks'][block]
        if b['block_id'] != block or b['compressed_bytes'] != COMPRESSED[block][1]:
            raise ValueError('Unexpected source solid block or compressed length.')
        for exam in EXAMS:
            expected = EXAM_SOURCE_BLOCK_COUNTS[exam].get(block)
            if b.get('examinations', {}).get(str(exam), 0) != (expected or 0):
                raise ValueError('Incorrect source examination membership in solid block.')
        original = source_blocks['blocks'][block]
        if (original['block_id'] != block or original['source_offset'] != COMPRESSED[block][0]
            or original['compressed_bytes'] != COMPRESSED[block][1]
            or original['compressed_sha256'] != COMPRESSED[block][2]):
            raise ValueError('Earlier independently verified source block SHA/bounds changed.')
    if (source_blocks['publisher_file_id'] != FILE_ID or source_blocks['full_publisher_archive_bytes'] != ARCHIVE_SIZE
        or source_blocks['full_original_archive_md5_verified'] is not False):
        raise ValueError('Earlier 7z block receipts do not match original publisher context.')


def exact_archive_member_partition(listing: str, requests: dict[int, dict[int, dict]]) -> dict[int, list[tuple[int, dict, str]]]:
    """Only exact 22/24 original image paths may be extracted. No inferred frame names."""
    approved: dict[int, dict[int, str]] = {exam: {} for exam in EXAMS}
    counts = {exam: {block: 0 for block in BLOCKS} for exam in EXAMS}
    found: dict[tuple[int,int], int] = {}
    partition: dict[int, list[tuple[int, dict, str]]] = {i: [] for i in BLOCKS}
    for record in records(listing):
        path = record['Path'].replace('\\', '/')
        if record.get('Folder') == '+' or record.get('Attributes', '').startswith('D'):
            continue
        exam = get_exam(path)
        if exam not in EXAMS or PurePosixPath(path).suffix.upper() != '.PNG':
            continue
        match = re.fullmatch(r'frame_(\d+)\.PNG', PurePosixPath(path).name)
        if not match:
            raise ValueError('Unrecognized original medical image filename.')
        raw = record.get('Block', '').strip()
        if not raw.isdecimal() or int(raw) not in BLOCKS:
            raise ValueError('Original image lies outside the three allowed solid blocks.')
        block, frame = int(raw), int(match.group(1))
        if frame in approved[exam]:
            raise ValueError('Duplicate original source image identity in publisher listing.')
        approved[exam][frame] = path
        counts[exam][block] += 1
        if frame in requests[exam]:
            if (exam, frame) in found:
                raise ValueError('Duplicate requested source image in publisher listing.')
            found[(exam, frame)] = block
            partition[block].append((exam, requests[exam][frame], path))
    if any(counts[exam] != {block: EXAM_SOURCE_BLOCK_COUNTS[exam].get(block, 0) for block in BLOCKS}
           or len(approved[exam]) != EXAM_SOURCE_COUNTS[exam] for exam in EXAMS):
        raise ValueError('Official original source PNG inventory disagrees with frozen 7z mapping.')
    expected = {(ex, frame) for ex in EXAMS for frame in requests[ex]}
    if set(found) != expected or any(not partition[block] for block in BLOCKS):
        raise ValueError('Not all requested source identities can be mapped to original solid blocks.')
    return partition


def sparse_archive_from_headers(header_dir: Path, receipt: dict, output: Path) -> None:
    if output.exists():
        raise FileExistsError('Refuse to overwrite transient sparse archive.')
    parts = receipt['parts']
    if {part['name'] for part in parts} != set(INDEX_SHA):
        raise ValueError('Unexpected source index component names.')
    with output.open('xb') as stream:
        stream.truncate(ARCHIVE_SIZE)
        for part in parts:
            if part['name'] not in INDEX_SHA:
                raise ValueError('Unexpected unverified header component.')
            start, length = int(part['offset']), int(part['length'])
            if start < 0 or length < 1 or start+length > ARCHIVE_SIZE:
                raise ValueError('Verified source component outside declared original size.')
            raw = (header_dir/part['name']).read_bytes()
            if len(raw) != length or hashlib.sha256(raw).hexdigest() != part['sha256']:
                raise ValueError('Publisher index bytes differ from verified source SHA.')
            stream.seek(start)
            stream.write(raw)


def transfer_verified_block(archive: Path, block_id: int) -> dict:
    """Fail before processing bytes if HTTP, exact range, identity or SHA differs."""
    if block_id not in COMPRESSED or not archive.is_file() or archive.stat().st_size != ARCHIVE_SIZE:
        raise ValueError('Only approved original solid block may be downloaded to a sparse index archive.')
    offset, length, expected_sha = COMPRESSED[block_id]
    stop = offset + length - 1
    req = urllib.request.Request(SOURCE_URL, headers={
        'Range':f'bytes={offset}-{stop}', 'Accept-Encoding':'identity',
        'User-Agent':'capsule-review/0.2 fitting-only 22-24 bounded source acquisition'})
    sha = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(req, timeout=120) as response:
        if response.status != 206 or not allowed_redirect(response.geturl()):
            raise ValueError('Official archive did not supply verified HTTP 206 content.')
        if response.headers.get('Content-Range') != f'bytes {offset}-{stop}/{ARCHIVE_SIZE}':
            raise ValueError('Source Content-Range mismatch; refusing image bytes.')
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Unexpected compressed transfer encoding.')
        declared = response.headers.get('Content-Length')
        if declared is not None and (not declared.isdecimal() or int(declared) != length):
            raise ValueError('Official source block byte-length header mismatch.')
        with archive.open('r+b') as dest:
            dest.seek(offset)
            while total < length:
                chunk = response.read(min(1<<20, length - total))
                if not chunk:
                    raise ValueError('Truncated source solid-block transfer.')
                dest.write(chunk)
                sha.update(chunk)
                total += len(chunk)
            if response.read(1):
                raise ValueError('Unexpected additional source bytes beyond selected block.')
    if total != length or sha.hexdigest() != expected_sha:
        raise ValueError('Original compressed block digest mismatch; never extract images.')
    return {'block_id':block_id, 'compressed_bytes':total, 'compressed_sha256':sha.hexdigest(), 'source_offset':offset}


def extract_and_verify_selected(sparse: Path, requested: list[tuple[int, dict, str]], stage: Path,
                                retained: Path, identities: dict[tuple[int,int],dict]) -> None:
    """7z extracts exact allowlisted original PNG paths, never full exam archives."""
    if len(requested) < 1:
        raise ValueError('A selected source block cannot be empty.')
    included = stage/'private-allowed-member-paths.txt'
    included.write_text('\n'.join(path for _,_,path in requested)+'\n',encoding='utf-8')
    extracted = stage/'decoded-selected'
    extracted.mkdir(exist_ok=False)
    cmd = ['7z','x','-y','-bso0','-bse2',f'-o{extracted}',f'-i@{included}',str(sparse)]
    completed = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1500, check=False)
    if completed.returncode:
        raise ValueError(f'Original 7z selected PNG extraction / CRC failed (exit {completed.returncode}).')
    if sum(p.is_file() for p in extracted.rglob('*')) != len(requested):
        raise ValueError('Unexpected additional or missing original source image files extracted.')
    root = extracted.resolve()
    for exam, row, member in requested:
        original_relative = PurePosixPath(member)
        if original_relative.is_absolute() or any(part in ('','..') for part in original_relative.parts):
            raise ValueError('Source archive path traversal attempted.')
        source = (extracted/Path(*original_relative.parts)).resolve(strict=True)
        if not source.is_file() or not source.is_relative_to(root):
            raise ValueError('Selected source path escapes permitted transient extract folder.')
        with Image.open(source) as image:
            if image.format != 'PNG':
                raise ValueError('Original source member is not an original PNG.')
            image.verify()
        frame = int(row['frame'])
        key = (exam,frame)
        if key in identities:
            raise ValueError('Original medical source identity repeated across transfer blocks.')
        destdir = retained / f'{exam:03d}'
        destdir.mkdir(parents=True,exist_ok=True)
        destination = destdir / row['filename']
        if destination.exists():
            raise FileExistsError('Duplicate original image target in retained fitting source.')
        shutil.copyfile(source, destination)
        digest = sha256_file(destination)
        size = destination.stat().st_size
        if digest != sha256_file(source) or size != source.stat().st_size:
            raise ValueError('Original PNG copy digest/byte-size mismatch.')
        identities[key] = {
            'exam':exam,'frame':frame,'filename':row['filename'],'blood':0,
            'fit_enriched':1,'reference_uniform':1,
            'source_csv_sha256':row['source_csv_sha256'],
            'source_image_sha256':digest,'source_bytes':size,
        }


def build_private_archive(retained: Path, identities: dict[tuple[int,int],dict], package: Path) -> dict:
    if package.exists():
        raise FileExistsError('Refuse overwrite of original-source image artifact.')
    expected = {exam: sum(row['exam']==exam for row in identities.values()) for exam in EXAMS}
    if expected != {exam: EXPECTED_FRAMES for exam in EXAMS} or len(identities) != EXPECTED_TOTAL:
        raise ValueError('Incomplete original 22/24 source-image acquisition.')
    saved = [identities[k] for k in sorted(identities)]
    manifest_path = retained.parent / 'verified-private-manifest.json'
    manifest_path.write_text(json.dumps(saved,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for row in saved:
            archive.write(retained/f'{row["exam"]:03d}'/row['filename'],
                          arcname=f'images/{row["exam"]:03d}/{row["filename"]}')
        archive.write(manifest_path,arcname='verified-private-manifest.json')
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != EXPECTED_TOTAL+1:
            raise ValueError('Final private original-image ZIP failed CRC/member count.')
    return {
        'verified_original_pngs':EXPECTED_TOTAL,
        'source_examinations':{str(e):EXPECTED_FRAMES for e in EXAMS},
        'source_blood_positive_annotations':0,
        'source_original_png_bytes':sum(r['source_bytes'] for r in saved),
        'private_manifest_sha256':sha256_file(manifest_path),
        'private_package_sha256':sha256_file(package),
        'original_archive_full_md5_verified':False,
        'distinct_patient_independence_verified':False,
        'clinical_validity':False,
        'medical_images_source_frame_ids_and_annotations_committed_to_git':False,
    }


def acquire(spec: Path, layout: Path, source_blocks: Path, selection: Path,
            workdir: Path, package: Path) -> dict:
    if workdir.exists() or package.exists():
        raise FileExistsError('Refuse overwrite of existing private source staging or output.')
    verify_protocol(spec)
    requests = read_frozen_requests(selection)
    fixed_layout = json.loads(layout.read_text(encoding='utf-8'))
    original_source_blocks = json.loads(source_blocks.read_text(encoding='utf-8'))
    workdir.mkdir(parents=True)
    headers_dir = workdir/'publisher-verified-index'
    index_client = RangeClient(SOURCE_URL, ARCHIVE_SIZE)
    index_receipt = inspect(index_client, headers_dir, sparse_path=headers_dir/'headers-only.7z')
    validate_source_index(fixed_layout,index_receipt,original_source_blocks)
    listing = workdir/'private-original-archive-listing.txt'
    with listing.open('wb') as out:
        process = subprocess.run(['7z','l','-slt',str(headers_dir/'headers-only.7z')],
                                 stdout=out,stderr=subprocess.PIPE,timeout=200,check=False)
    if process.returncode:
        raise ValueError('Unable to read verified publisher 7z index before image transfer.')
    partition = exact_archive_member_partition(listing.read_text(encoding='utf-8'),requests)
    retained = workdir/'original-verified-image-files'
    identities: dict[tuple[int,int],dict] = {}
    block_receipts = []
    for block in BLOCKS:
        offset,length,_ = COMPRESSED[block]
        if shutil.disk_usage(workdir).free < length + MIN_DISK_MARGIN:
            raise ValueError('Insufficient available disk for the preapproved solid-source block.')
        stage = workdir/f'transient-block-{block}'
        stage.mkdir()
        sparse = stage/'original-source-block.7z'
        sparse_archive_from_headers(headers_dir,index_receipt,sparse)
        receipt = transfer_verified_block(sparse,block)
        extract_and_verify_selected(sparse,partition[block],stage,retained,identities)
        block_receipts.append({**receipt,'selected_images':len(partition[block])})
        shutil.rmtree(stage)  # Never retain 10.42 GB simultaneously.
        print(f'Galar fitting-only 22/24: verified source block {block}, extracted {len(partition[block])} PNGs.',flush=True)
    result = build_private_archive(retained,identities,package)
    result.update({
        'official_source_file_id':FILE_ID,
        'total_exact_compressed_source_bytes_transferred':sum(r['compressed_bytes'] for r in block_receipts),
        'verified_source_block_receipts':block_receipts,
        'official_source_corrected_labels_sha256':SOURCE_CORRECTED_ZIP_SHA,
        'frozen_preacquisition_spec_git_blob_sha1':FROZEN_SPEC_BLOB,
        'original_fitting_request_sha256':FROZEN_REQUEST_SHA,
        'verified_index_transfer_bytes':index_client.total,
        'protected_examination_pixels_or_labels_read':False,
        'research_only':True,
    })
    if result['total_exact_compressed_source_bytes_transferred'] != MAX_SOURCE_TRANSFER:
        raise ValueError('Source transfer exceeded or fell below preapproved bounds.')
    (workdir/'aggregate-receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('spec','layout','source-blocks','selection','workdir','package'):
        parser.add_argument('--'+key,required=True,type=Path,dest=key.replace('-','_'))
    a=parser.parse_args()
    result=acquire(a.spec,a.layout,a.source_blocks,a.selection,a.workdir,a.package)
    print('Verified 22/24 original PNGs:',result['verified_original_pngs'],
          'blood positive annotations:',result['source_blood_positive_annotations'],flush=True)

if __name__=='__main__':
    main()
