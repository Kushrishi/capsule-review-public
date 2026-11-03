"""Bounded original-PNG Galar23 density-versus-evidence-diversity experiment.

One previously SHA-verified 3.476-GB solid source block, only examination 23.
No reserved data, pathology enrichment, new model fitting or clinical validation.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.request
import zipfile

from PIL import Image
from blood_image_pilot import red_excess, roc_ap
from galar_density_ceiling import (SOURCE_ZIP_SHA256, sha256_path,
                                  uniform_positions, parse_allowed_csv, run_identities)
from probe_galar_archive import (ARCHIVE_SIZE, FILE_ID, SOURCE_URL, RangeClient,
                                 allowed_redirect, inspect)
from summarize_galar_archive_layout import records, get_exam

EXAM = 23
BLOCK_ID = 1
BLOCK_OFFSET = 3_474_498_124
BLOCK_BYTES = 3_475_743_781
BLOCK_SHA = 'b5086f018b7e88c57db7562af624c468796a7b1e812101d07236c184131b08f6'
SPEC_BLOB_SHA = '1eb7c7e6ee9578800de2c15bcfec9ba520a63e97'
SOURCE_ROWS = 11_785
CANDIDATE_COUNTS = (512, 4096)
REVIEW_COUNTS = (51, 128, 256, 512)
HEADER_SHA = {
    'signature-header.bin': '44191aaf136fd4cc2a5bafad2b828bc96310e235731752eaa5f39aa8f912611f',
    'next-header.bin': 'c8de7cca5b73224778e5516e0f9079f00989adbe7a3f0034a6c3fae06889ca5d',
    'encoded-index-0.bin': '61d38a2c6b0ed445a348ea11287189f9ba86f541678900cc96b8fb674c9e1043',
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def validate_protocol(path: Path) -> dict:
    raw=path.read_bytes()
    if git_blob(raw)!=SPEC_BLOB_SHA:
        raise ValueError('Immutable pre-acquisition protocol Git blob differs.')
    data=json.loads(raw)
    source=data['source_images'];labels=data['source_labels']
    if (data['locked_examination']!=EXAM or source['file_id']!=FILE_ID
        or source['original_archive_bytes']!=ARCHIVE_SIZE
        or source['block_id']!=BLOCK_ID or source['block_offset']!=BLOCK_OFFSET
        or source['block_compressed_bytes']!=BLOCK_BYTES
        or source['verified_block_sha256']!=BLOCK_SHA
        or labels['sha256']!=SOURCE_ZIP_SHA256 or labels['member']!='23.csv'
        or data['input_sampling']['candidate_sizes']!=list(CANDIDATE_COUNTS)
        or data['fixed_absolute_reviewer_frames']!=list(REVIEW_COUNTS)):
        raise ValueError('Frozen data source or workload settings changed.')
    return data


def candidates_by_size(rows: list[tuple[int, str]]) -> dict[int, list[int]]:
    if len(rows)!=SOURCE_ROWS or any(label not in ('0','1') for _,label in rows):
        raise ValueError('Expected exact explicitly labelled original Galar23 source population.')
    assignment, lengths=run_identities(rows)
    if len(lengths)!=28 or sum(lengths)!=135:
        raise ValueError('Historical corrected annotation runs changed.')
    pools={m:uniform_positions(len(rows),m) for m in CANDIDATE_COUNTS}
    for m,expected_pos,expected_runs in ((512,4,4),(4096,None,21)):
        indices=pools[m]
        if len(indices)!=len(set(indices)) or len(indices)!=m:
            raise ValueError('Nonunique label-blind candidate positions.')
        positive=sum(rows[i][1]=='1' for i in indices)
        touched={assignment[i] for i in indices if assignment[i] is not None}
        if (expected_pos is not None and positive!=expected_pos) or len(touched)!=expected_runs:
            raise ValueError('Candidate source annotation support fails frozen baseline.')
    return pools


def verify_index_layout(layout: dict, receipt: dict) -> None:
    if (receipt.get('official_file_id')!=FILE_ID
        or receipt.get('official_full_archive_bytes')!=ARCHIVE_SIZE
        or receipt.get('full_archive_downloaded') is not False
        or receipt.get('pixels_acquired')!=0
        or {p['name']:p['sha256'] for p in receipt.get('parts', [])}!=HEADER_SHA
        or layout.get('origin_file_id')!=FILE_ID
        or layout.get('archive_bytes')!=ARCHIVE_SIZE
        or layout.get('total_compression_blocks')!=10
        or len(layout.get('blocks', []))!=10
        or layout['image_members_by_exam'].get('23')!=SOURCE_ROWS
        or layout['blocks'][BLOCK_ID]['block_id']!=BLOCK_ID
        or layout['blocks'][BLOCK_ID]['compressed_bytes']!=BLOCK_BYTES
        or layout['blocks'][BLOCK_ID]['examinations'].get('23')!=SOURCE_ROWS
        or layout.get('unassigned_image_members')!=0):
        raise ValueError('Previously verified publisher metadata/block layout disagrees.')


def find_exact_members(listing: str, requested_frames: set[int]) -> dict[int,str]:
    members={}; seen=set(); count=0
    for record in records(listing):
        path=record['Path'].replace('\\','/')
        if record.get('Folder')=='+' or record.get('Attributes','').startswith('D'):
            continue
        if get_exam(path)!=EXAM or PurePosixPath(path).suffix.upper()!='.PNG':
            continue
        if record.get('Block','').strip()!=str(BLOCK_ID):
            raise ValueError('Original exam23 image crosses the frozen source block.')
        name=PurePosixPath(path).name
        match=re.fullmatch(r'frame_(\d+)\.PNG',name)
        if match is None:
            raise ValueError('Unrecognized original source image identity.')
        frame=int(match.group(1))
        if frame in seen:
            raise ValueError('Duplicate original source-frame image in 7z listing.')
        seen.add(frame);count+=1
        if frame in requested_frames:
            members[frame]=path
    if count!=SOURCE_ROWS or set(members)!=requested_frames:
        raise ValueError('Not all source frame names matched independently verified index.')
    return members


def exact_download_source_block(archive_path: Path) -> str:
    """Refuse changed host, 200 OK, partial length, unexpected range or SHA."""
    if not archive_path.is_file() or archive_path.stat().st_size!=ARCHIVE_SIZE:
        raise ValueError('A complete logical-length verified sparse archive is required.')
    stop=BLOCK_OFFSET+BLOCK_BYTES-1
    req=urllib.request.Request(SOURCE_URL,headers={
        'Range':f'bytes={BLOCK_OFFSET}-{stop}',
        'Accept-Encoding':'identity',
        'User-Agent':'capsule-review/0.2 prespecified exam23 source-PNG experiment'})
    actual=0;sha=hashlib.sha256()
    with urllib.request.urlopen(req,timeout=120) as response:
        if response.status!=206 or not allowed_redirect(response.geturl()):
            raise ValueError('Official source rejected exact, secure partial-content request.')
        if response.headers.get('Content-Range')!=f'bytes {BLOCK_OFFSET}-{stop}/{ARCHIVE_SIZE}':
            raise ValueError('Original source content-range does not match preverified block.')
        if response.headers.get('Content-Encoding','identity')!='identity':
            raise ValueError('Unexpected encoded original source transfer.')
        declared=response.headers.get('Content-Length')
        if declared is not None and (not declared.isdigit() or int(declared)!=BLOCK_BYTES):
            raise ValueError('Incorrect official block Content-Length.')
        with archive_path.open('r+b') as out:
            out.seek(BLOCK_OFFSET)
            while actual<BLOCK_BYTES:
                chunk=response.read(min(1024*1024,BLOCK_BYTES-actual))
                if not chunk:
                    raise ValueError('Source compressed block transfer truncated.')
                actual+=len(chunk);sha.update(chunk);out.write(chunk)
            if response.read(1):
                raise ValueError('Unexpected extra compressed original-source data.')
    if actual!=BLOCK_BYTES or sha.hexdigest()!=BLOCK_SHA:
        raise ValueError('Original image source block SHA-256 mismatch; refuse decoding.')
    return sha.hexdigest()


def extract_selected(archive: Path, members: dict[int,str], workdir: Path) -> dict[int,Path]:
    destination=workdir/'decoded-source'
    destination.mkdir(parents=True,exist_ok=False)
    paths=workdir/'allowed-source-paths-private.txt'
    paths.write_text('\n'.join(members[key] for key in sorted(members))+'\n',encoding='utf-8')
    cmd=['7z','x','-y','-bso0','-bse2',f'-o{destination}',f'-i@{paths}',str(archive)]
    result=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=1800,check=False)
    if result.returncode!=0:
        raise ValueError('7z original source-member extraction/CRC failed; code '+str(result.returncode))
    found={}
    root=destination.resolve()
    for frame,member in members.items():
        rel=PurePosixPath(member)
        if rel.is_absolute() or any(x in ('','..') for x in rel.parts):
            raise ValueError('Unsafe original publisher member path.')
        path=(destination/Path(*rel.parts)).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Original medical image destination escaped allowed stage.')
        found[frame]=path
    if sum(path.is_file() for path in destination.rglob('*'))!=len(members):
        raise ValueError('Unexpected other source members extracted.')
    return found


def max_nearest_source_annotation_gap(n: int, selected_positions: list[int]) -> int:
    """Source annotation ROWS, not elapsed time or actual unseen device frames."""
    if n<=0 or not selected_positions:
        raise ValueError('Review selections must be nonempty and ordered.')
    position=sorted(set(selected_positions))
    if position[0]<0 or position[-1]>=n:
        raise ValueError('Invalid selected original annotation position.')
    maximum=0
    for i in range(n):
        j=bisect_left(position,i)
        nearest=min((abs(position[x]-i) for x in (j-1,j) if 0<=x<len(position)),default=n)
        maximum=max(maximum,nearest)
    return maximum


def select_methods(indices: list[int], scores: list[float], frames: list[int], k:int) -> dict[str,list[int]]:
    """Return ordinal positions within one candidate pool; no labels used."""
    n=len(indices)
    if n!=len(scores) or n!=len(frames) or not 0<k<=n or any(not math.isfinite(v) for v in scores):
        raise ValueError('Cannot rank invalid or unaligned candidate scores.')
    uniform=uniform_positions(n,k)
    rank=sorted(range(n),key=lambda i:(-scores[i],frames[i]))[:k]
    binned=[]
    for bin_id in range(k):
        lo=(bin_id*n)//k;hi=((bin_id+1)*n)//k
        if hi<=lo:
            raise ValueError('Review bin was empty, not an equal-budget selection.')
        best=min(range(lo,hi),key=lambda i:(-scores[i],frames[i]))
        binned.append(best)
    if any(len(set(values))!=k for values in (uniform,rank,binned)):
        raise ValueError('Duplicate or incomplete review selections.')
    return {'uniform':uniform,'global_red':rank,'bin_stratified_red':binned}


def evaluate_image_scores(rows: list[tuple[int,str]], pools: dict[int,list[int]], paths: dict[int,Path]) -> dict:
    assignment,run_lengths=run_identities(rows)
    wanted={rows[i][0] for pool in pools.values() for i in pool}
    if set(paths)!=wanted:
        raise ValueError('Imported source image identities do not match label-blind requested union.')
    source_identity=hashlib.sha256()
    red={}
    total_image_bytes=0
    for frame in sorted(wanted):
        path=paths[frame]
        source_size=path.stat().st_size
        sha=sha256_path(path)
        with Image.open(path) as im:
            if im.format!='PNG':
                raise ValueError('Original Galar source image is not PNG.')
            im.verify()
        score=float(red_excess(path))
        if not math.isfinite(score) or score<0 or score>1:
            raise ValueError('Nonfinite or impossible original red score.')
        red[frame]=score
        total_image_bytes+=source_size
        source_identity.update(f'{frame},{source_size},{sha},{score:.17g}\n'.encode())
    measured={}
    for size,candidates in pools.items():
        frames=[rows[index][0] for index in candidates]
        scores=[red[frame] for frame in frames]
        labels=[int(rows[index][1]) for index in candidates]
        support=roc_ap(labels,scores)
        if size==512 and abs(support['roc_auc']-0.417)>0.001:
            raise ValueError('Original 512-reference redness AUC fails published baseline replay.')
        candidate_runs={assignment[i] for i in candidates if assignment[i] is not None}
        methods={}
        for k in REVIEW_COUNTS:
            outcomes={}
            for method,ordinal in select_methods(candidates,scores,frames,k).items():
                reviewed=[candidates[i] for i in ordinal]
                hits={assignment[i] for i in reviewed if assignment[i] is not None}
                outcomes[method]={
                    'reviewed_frames':k,
                    'blood_label_positive_image_hits':sum(rows[i][1]=='1' for i in reviewed),
                    'distinct_source_annotation_runs_hit':len(hits),
                    'source_annotation_row_nearest_review_max_gap':max_nearest_source_annotation_gap(len(rows),reviewed),
                }
            methods[str(k)]=outcomes
        measured[str(size)]={
            'candidate_images':size,
            'candidate_positive_labelled_images':sum(labels),
            'source_annotation_positive_runs_represented':len(candidate_runs),
            'original_red_roc_auc':support['roc_auc'],
            'original_red_average_precision':support['average_precision'],
            'methods_at_fixed_workload':methods,
        }
    return {
        'experiment':'Galar23 original-PNG input-density versus original untrained redness and fixed chronological bin selection',
        'study_role':'Previously inspected fitting examination only; post-hoc exploratory',
        'examination':EXAM,
        'original_source_annotation_positions':len(rows),
        'original_source_blood_positive_positions':sum(x[1]=='1' for x in rows),
        'original_source_positive_annotation_runs':len(run_lengths),
        'original_source_pngs_verified':len(wanted),
        'original_source_png_bytes_verified':total_image_bytes,
        'private_original_image_and_score_fingerprint_sha256':source_identity.hexdigest(),
        'methods':measured,
        'patient_or_lesion_independence_verified':False,
        'image_model_trained_or_promoted':False,
        'clinical_validity':False,
    }


def execute(labels_zip:Path, layout_path:Path, protocol_path:Path, workdir:Path, output:Path) -> dict:
    if workdir.exists() or output.exists():
        raise FileExistsError('Research staging/output already exists; never overwrite prior results.')
    validate_protocol(protocol_path)
    if labels_zip.stat().st_size!=17_931_138 or sha256_path(labels_zip)!=SOURCE_ZIP_SHA256:
        raise ValueError('Corrected label source bytes are not the locked release.')
    with zipfile.ZipFile(labels_zip) as z:
        rows, label_source_sha = parse_allowed_csv(z,EXAM)
    pools=candidates_by_size(rows)
    frames_wanted={rows[i][0] for indices in pools.values() for i in indices}
    if len(frames_wanted)!=4608:
        raise ValueError('Unexpected source candidate union size: possible changed spacing rule.')
    layout=json.loads(layout_path.read_text())
    workdir.mkdir(parents=True)
    client=RangeClient(SOURCE_URL,ARCHIVE_SIZE)
    index_dir=workdir/'verified-index'
    receipt=inspect(client,index_dir,sparse_path=index_dir/'sparse.7z')
    verify_index_layout(layout,receipt)
    archive=index_dir/'sparse.7z'
    listing=workdir/'private-official-listing.txt'
    with listing.open('wb') as dest:
        check=subprocess.run(['7z','l','-slt',str(archive)],stdout=dest,stderr=subprocess.PIPE,timeout=180,check=False)
    if check.returncode!=0:
        raise ValueError('Could not list verified original 7z index before acquiring pixels.')
    members=find_exact_members(listing.read_text('utf-8'),frames_wanted)
    # Safety margin includes the compressed block and extracted requested PNGs.
    if shutil.disk_usage(workdir).free < 8_000_000_000:
        raise ValueError('Insufficient disk for bounded 3.476-GB source and verified extraction.')
    verified_block=exact_download_source_block(archive)
    paths=extract_selected(archive,members,workdir)
    result=evaluate_image_scores(rows,pools,paths)
    result.update({
        'official_source_file_id':FILE_ID,
        'official_source_archive_full_md5_verified':False,
        'official_source_compressed_block_id':BLOCK_ID,
        'official_source_compressed_block_sha256':verified_block,
        'source_corrected_labels_zip_sha256':SOURCE_ZIP_SHA256,
        'source_corrected_exam23_csv_sha256':label_source_sha,
        'frozen_spec_git_blob_sha1':SPEC_BLOB_SHA,
        'source_index_transfer_bytes':client.total,
        'original_compressed_block_transferred_bytes':BLOCK_BYTES,
        'forbidden_studies_read':False,
    })
    output.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(result,sort_keys=True,indent=2)+'\n'
    output.write_text(content,encoding='utf-8')
    print('Verified original exam23 image count:',result['original_source_pngs_verified'])
    print('All fixed-method comparisons:',json.dumps(result['methods'],sort_keys=True,separators=(',',':')))
    print('Public aggregate SHA-256:',hashlib.sha256(content.encode()).hexdigest())
    return result


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels-zip',type=Path,required=True)
    parser.add_argument('--layout',type=Path,required=True)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    execute(args.labels_zip,args.layout,args.spec,args.workdir,args.out)


if __name__=='__main__':main()
