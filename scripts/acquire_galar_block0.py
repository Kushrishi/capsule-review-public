"""Bounded research-only acquisition of *one* verified Galar solid 7z block.

Fetches exactly first block (~3.47 GB), not the 31.99 GB full archive. Extracts
only requested exam-21 images from a sparse 7z with official verified headers.
No original images, private frame identities or labels belong in source control.
Full archive MD5 is NOT validated by this partial-source acquisition.
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

from probe_galar_archive import (ARCHIVE_SIZE, EXPECTED_FULL_MD5, FILE_ID,
                                  SOURCE_URL, allowed_redirect, inspect, RangeClient)
from summarize_galar_archive_layout import records, get_exam

BLOCK_INDEX = 0
BLOCK_START = 32
BLOCK_BYTES = 3_474_498_092
EXAM = 21
SOURCE_CHECKSUM_NOT_VERIFIED = True
EXPECTED_SOURCE_IMAGE_COUNT = 7478
MAX_BLOCK_BYTES = 3_600_000_000
EXPECTED_PRIVATE_PLAN_SHA256 = '1aedfcdecbb270687a660acd50f312803ed0884308ea9a0973102aac242409f1'
EXPECTED_HEADER_PART_SHA256 = {
    'signature-header.bin': '44191aaf136fd4cc2a5bafad2b828bc96310e235731752eaa5f39aa8f912611f',
    'next-header.bin': 'c8de7cca5b73224778e5516e0f9079f00989adbe7a3f0034a6c3fae06889ca5d',
    'encoded-index-0.bin': '61d38a2c6b0ed445a348ea11287189f9ba86f541678900cc96b8fb674c9e1043'
}


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for v in iter(lambda:f.read(1048576),b''):
            h.update(v)
    return h.hexdigest()


def check_metadata(layout: dict,receipt: dict,private_manifest: Path) -> None:
    if (receipt.get('official_file_id')!=FILE_ID or receipt.get('official_full_archive_bytes')!=ARCHIVE_SIZE
        or receipt.get('full_archive_downloaded') is not False or receipt.get('pixels_acquired')!=0
        or layout.get('origin_file_id')!=FILE_ID
        or layout.get('image_members_by_exam',{}).get(str(EXAM))!=EXPECTED_SOURCE_IMAGE_COUNT
        or layout.get('unassigned_image_members')!=0
        or layout.get('total_compression_blocks')!=10
        or layout['blocks'][0].get('compressed_bytes')!=BLOCK_BYTES
        or layout['blocks'][0].get('examinations',{}).get(str(EXAM))!=EXPECTED_SOURCE_IMAGE_COUNT
        or sum(x['compressed_bytes'] for x in layout['blocks'])+sum(x['length'] for x in receipt['parts']) != ARCHIVE_SIZE
        or [x['block_id'] for x in layout['blocks']]!=list(range(10))):
        raise ValueError('Archive block mapping or official index-only source metadata mismatched.')
    if {x['name']:x['sha256'] for x in receipt['parts']} != EXPECTED_HEADER_PART_SHA256:
        raise ValueError('Index bytes differ from previous independent official source probe.')
    if sha256_file(private_manifest)!=EXPECTED_PRIVATE_PLAN_SHA256:
        raise ValueError('Fitting-only private selection manifest does not match frozen original.')


def download_exact_block(url: str, sparse_file: Path, *, start: int = BLOCK_START,
                         length: int = BLOCK_BYTES, allow_mock_http=False) -> dict:
    if (not allow_mock_http and (url!=SOURCE_URL or start!=BLOCK_START or length!=BLOCK_BYTES)):
        raise ValueError('Only official first packed Galar block may be fetched.')
    if length<=0 or length>MAX_BLOCK_BYTES or start<0 or start+length>ARCHIVE_SIZE:
        raise ValueError('Compressed solid-block download exceeds bounded size.')
    req=urllib.request.Request(url,headers={
        'Range': f'bytes={start}-{start+length-1}',
        'Accept-Encoding':'identity',
        'User-Agent':'capsule-review/0.2 one-block research acquisition'})
    h=hashlib.sha256()
    total=0
    with urllib.request.urlopen(req,timeout=120) as response:
        if response.status!=206:
            raise ValueError(f'Expected HTTP 206; got {response.status}, refuse before body.')
        if not allow_mock_http and not allowed_redirect(response.geturl()):
            raise ValueError('Untrusted official-source redirect.')
        if response.headers.get('Content-Range')!=f'bytes {start}-{start+length-1}/{ARCHIVE_SIZE if not allow_mock_http else response.headers.get("X-Source-Size", ARCHIVE_SIZE)}':
            raise ValueError('Source content-range mismatch; abort before pixel download.')
        if response.headers.get('Content-Encoding','identity')!='identity':
            raise ValueError('Unexpected transfer encoding.')
        declared=response.headers.get('Content-Length')
        if declared is not None and (not declared.isdecimal() or int(declared)!=length):
            raise ValueError('Incorrect declared block byte length.')
        with sparse_file.open('r+b') as out:
            out.seek(start)
            while total<length:
                part=response.read(min(1024*1024,length-total))
                if not part:
                    raise ValueError('Compressed block transfer ended before exact length.')
                total+=len(part)
                if total>length:
                    raise ValueError('Compressed block transfer exceeded expected size.')
                out.write(part)
                h.update(part)
            if response.read(1):
                raise ValueError('Extra bytes beyond verified source block range.')
    return {'file_id':FILE_ID,'block_id':BLOCK_INDEX,'offset':start,
            'transferred_compressed_bytes':total,'compressed_block_sha256':h.hexdigest(),
            'full_source_md5_verified':False}


def requested_exam_rows(private_manifest: Path, exam: int=EXAM) -> list[dict]:
    if exam!=EXAM:raise ValueError('This bounded proof is exam 21 only.')
    with private_manifest.open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        fields={'exam','frame','filename','blood','fit_enriched','reference_uniform','source_csv_sha256'}
        if set(reader.fieldnames or []) != fields:
            raise ValueError('Private source manifest schema changed.')
        wanted=[]
        for row in reader:
            if int(row['exam']) != exam:continue
            fr=int(row['frame'])
            if fr<0 or row['filename']!=f'frame_{fr:06d}.PNG' or row['blood'] not in ('0','1'):
                raise ValueError('Invalid original source-frame request.')
            if row['fit_enriched'] not in ('0','1') or row['reference_uniform'] not in ('0','1'):
                raise ValueError('Invalid selection role.')
            wanted.append(row)
    if len(wanted)!=len({int(x['frame']) for x in wanted}) or len(wanted)<100:
        raise ValueError('Expected unique exam-21 acquisition requests.')
    return wanted


def find_member_paths(listing: str, wanted: list[dict]) -> list[tuple[dict,str]]:
    lookup={int(row['frame']):row for row in wanted}
    found={}
    num_source=0
    for entry in records(listing):
        path=entry['Path'].replace('\\','/')
        if entry.get('Folder')=='+' or entry.get('Attributes','').startswith('D'):
            continue
        exam=get_exam(path)
        if exam!=EXAM:continue
        # Source 7z contains non-image metadata entries inside examination folders.
        # Ignore those explicitly; verify the COMPLETE expected PNG image count below.
        if PurePosixPath(path).suffix.upper() != '.PNG':
            continue
        if entry.get('Block','').strip()!='0':
            raise ValueError('Exam 21 image appears outside preverified first solid block.')
        match=re.fullmatch(r'frame_(\d+)\.PNG',PurePosixPath(path).name)
        if not match:
            raise ValueError('Unexpected Galar frame member name; no guessing.')
        frame=int(match.group(1));num_source+=1
        if frame in lookup:
            if frame in found:
                raise ValueError('Duplicate requested frame in source image index.')
            found[frame]=path
    if num_source!=EXPECTED_SOURCE_IMAGE_COUNT:
        raise ValueError('Cannot match all exam-21 source frame archive entries.')
    if set(found)!=set(lookup):
        raise ValueError('Planned source frames missing from original archive index.')
    return [(row,found[int(row['frame'])]) for row in wanted]


def extract_and_package(sparse_file:Path,members:list[tuple[dict,str]],workdir:Path,package:Path) -> dict:
    from PIL import Image
    if package.exists():raise FileExistsError('Output medical image package already exists.')
    extracted=workdir/'extracted'
    if extracted.exists():raise FileExistsError('Extraction stage already exists.')
    extracted.mkdir(parents=True)
    include=workdir/'requested-archive-paths-private.txt'
    include.write_text('\n'.join(member for _,member in members)+'\n',encoding='utf8')
    cmd=['7z','x','-y','-bso0','-bse2',f'-o{extracted}',f'-i@{include}',str(sparse_file)]
    completed=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                             timeout=1000,check=False)
    if completed.returncode!=0:
        raise ValueError('7-Zip failed source-member extraction/CRC checks; exit code '+str(completed.returncode))
    images=workdir/'selected-images'
    images.mkdir(parents=True,exist_ok=False)
    identity=[];size=0
    for row,member in members:
        rel=PurePosixPath(member)
        if any(part in ('','..') for part in rel.parts) or rel.is_absolute():
            raise ValueError('Invalid source member path.')
        original=(extracted/Path(*rel.parts)).resolve(strict=True)
        if not original.is_relative_to(extracted.resolve()):
            raise ValueError('Source path escapes extraction folder.')
        if not original.is_file():raise ValueError('Expected original source member missing.')
        with Image.open(original) as im:
            if im.format!='PNG':raise ValueError('Source endoscopy member is not valid PNG.')
            im.verify()
        name=f'frame_{int(row["frame"]):06d}.PNG'
        target=images/name
        shutil.copyfile(original,target)
        digest=sha256_file(target)
        identity.append({'exam':EXAM,'frame':int(row['frame']),'filename':name,
                         'source_image_sha256':digest,'source_bytes':target.stat().st_size,
                         'blood':int(row['blood']),'fit_enriched':int(row['fit_enriched']),
                         'reference_uniform':int(row['reference_uniform'])})
        size+=target.stat().st_size
    private_manifest=workdir/'verified-private-manifest.json'
    private_manifest.write_text(json.dumps(identity,sort_keys=True,indent=2)+'\n')
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as bundle:
        for row in identity:
            bundle.write(images/row['filename'],arcname=f'images/021/{row["filename"]}')
        bundle.write(private_manifest,arcname='verified-private-manifest.json')
    with zipfile.ZipFile(package) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Final original-frame package ZIP CRC failed.')
    return {'examination':EXAM,'verified_source_images':len(identity),
            'blood_positive_selected_images':sum(row['blood'] for row in identity),
            'source_bytes_saved':size,'source_package_sha256':sha256_file(package),
            'verified_private_manifest_sha256':sha256_file(private_manifest),
            'selected_source_images_not_committed':True,
            'image_source_archive_full_md5_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index-layout',type=Path,required=True)
    p.add_argument('--private-selection',type=Path,required=True)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--source-package',type=Path,required=True)
    a=p.parse_args()
    if a.workdir.exists() or a.source_package.exists():
        p.error('Acquisition staging or private package already exists; refuse overwrite.')
    layout=json.loads(a.index_layout.read_text())
    a.workdir.mkdir(parents=True)
    index_dir=a.workdir/'index'
    inspector=RangeClient(SOURCE_URL,ARCHIVE_SIZE)
    index=inspect(inspector,index_dir,sparse_path=index_dir/'headers-only.7z')
    check_metadata(layout,index,a.private_selection)
    # Fail before the large transfer if the publisher's exact archive member paths
    # cannot be mapped to all preselected original frame identifiers.
    archive=index_dir/'headers-only.7z'
    listing_path=a.workdir/'private-7z-listing.txt'
    with listing_path.open('wb') as out:
        result=subprocess.run(['7z','l','-slt',str(archive)],stdout=out,stderr=subprocess.PIPE,
                              timeout=200,check=False)
    if result.returncode!=0:
        raise ValueError('7z source index listing failed before transfer.')
    matched=find_member_paths(listing_path.read_text(encoding='utf8'),requested_exam_rows(a.private_selection))
    # Leave a substantive free-space margin before any multi-GB transfer.
    if shutil.disk_usage(a.workdir).free < BLOCK_BYTES+4_000_000_000:
        raise ValueError('Insufficient temporary disk to stage one compressed solid block safely.')
    receipt=download_exact_block(SOURCE_URL,archive)
    report=extract_and_package(archive,matched,a.workdir,a.source_package)
    report['block_transfer']=receipt
    report['index_transfer_bytes']=inspector.total
    report['source_archive_file_id']=FILE_ID
    report['source_archive_expected_full_md5']=EXPECTED_FULL_MD5
    report['medical_image_bytes_committed_to_github']=0
    report['research_use_only']=True
    (a.workdir/'aggregate-receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('Actual verified source image members:',report['verified_source_images'],
          '; blood-positive annotation selected:',report['blood_positive_selected_images'],
          '; original source compressed block bytes:',receipt['transferred_compressed_bytes'])


if __name__=='__main__':main()