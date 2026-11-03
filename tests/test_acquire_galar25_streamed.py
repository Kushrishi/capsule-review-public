"""Safety and source-identity checks for streamed Galar 25 acquisition."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import acquire_galar25_streamed as m
import acquire_galar_multiblock as base


@pytest.fixture(autouse=True)
def restore_original_profile():
    try:
        yield
    finally:
        base.configure_exam_profile(30)


def test_exact_profile_is_single_source_and_three_blocks():
    base.configure_exam_profile(25)
    assert base.EXAM == 25
    assert base.BLOCKS == (2,3,4)
    assert base.EXPECTED_REQUESTED_IMAGES == 1013
    assert base.EXPECTED_EXAM_IMAGES == 22477
    assert base.EXPECTED_EXAM_BLOCK_IMAGES == {2:1762,3:15058,4:5657}
    assert base.EXPECTED_BLOCK_START == {2:6950241905,3:10420312311,4:13959356282}
    assert sum(base.EXPECTED_BLOCK_BYTES.values()) == 10447872590
    assert m.BLOCKS == (2,3,4)


def make_rows():
    # Exact enriched / reference role counts and positive-label support.
    rows=[]
    for i in range(1013):
        enriched = i < 512
        ref = 501 <= i < 1013
        # 245 earliest positives + 11 dual-purpose + 3 reference-only
        blood = i < 245 or 501 <= i < 515
        rows.append({'exam':'25','frame':str(5*i),'blood':str(int(blood)),
                     'fit_enriched':str(int(enriched)), 'reference_uniform':str(int(ref))})
    assert sum(int(r['blood'])*int(r['reference_uniform']) for r in rows)==14
    return rows


def test_original_frozen_roles_and_positive_support_must_match():
    rows=make_rows()
    m.check_frozen_selection(rows)
    with pytest.raises(ValueError,match='roles or label support'):
        corrupted=[dict(r) for r in rows]
        corrupted[512]['reference_uniform']='0'
        m.check_frozen_selection(corrupted)
    with pytest.raises(ValueError,match='Repeated source frame'):
        corrupted=[dict(r) for r in rows]
        corrupted[512]['frame']=corrupted[0]['frame']
        m.check_frozen_selection(corrupted)
    with pytest.raises(ValueError,match='identities changed'):
        corrupted=[dict(r) for r in rows]
        corrupted[0]['exam']='11'
        m.check_frozen_selection(corrupted)


def test_member_partition_rejects_missing_duplicate_or_bad_blocks(monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_ARCHIVE_MEMBERS',3)
    # For small synthetic fixtures, the source count is deliberately patched.
    good='archive\n----------\n'+ '\n\n'.join(
        f'Path = Galar/25/frame_{i:06d}.PNG\nSize = 100\nFolder = -\nBlock = {block}'
        for i,block in ((0,2),(5,3),(10,4)))
    wanted=[({'exam':'25','frame':str(i)}, f'Galar/25/frame_{i:06d}.PNG') for i in (0,5,10)]
    # The module locks the official 1,762 / 15,058 / 5,657 structure; we can't
    # override those constants without relaxing checks. Correct behavior is rejection.
    with pytest.raises(ValueError,match='block inventory differs'):
        m.verified_member_partition(good,wanted)
    bad=good.replace('Block = 2','Block = 9')
    with pytest.raises(ValueError,match='outside approved'):
        m.verified_member_partition(bad,wanted)


def test_sparse_index_reconstruction_uses_only_verified_small_parts(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ARCHIVE_SIZE',1000)
    h=tmp_path/'headers';h.mkdir()
    data=[('signature-header.bin',0,b'abc'),('encoded-index-0.bin',450,b'def'),('next-header.bin',997,b'xyz')]
    receipt={'parts':[]}
    for name,offset,raw in data:
        (h/name).write_bytes(raw)
        receipt['parts'].append({'name':name,'offset':offset,'length':len(raw),
                                 'sha256':hashlib.sha256(raw).hexdigest()})
    output=tmp_path/'sparse.7z'
    m.create_sparse_from_verified_headers(h,receipt,output)
    assert output.stat().st_size==1000
    with output.open('rb') as f:
        for name,offset,raw in data:
            f.seek(offset)
            assert f.read(len(raw))==raw
    with pytest.raises(FileExistsError):
        m.create_sparse_from_verified_headers(h,receipt,output)
    output.unlink()
    (h/'next-header.bin').write_bytes(b'XXX')
    with pytest.raises(ValueError,match='altered'):
        m.create_sparse_from_verified_headers(h,receipt,output)


def mini_package(tmp_path, *, bad_label=False, bad_sha=False):
    src=tmp_path/'portion.zip'
    b=io.BytesIO()
    Image.new('RGB',(8,8),(20,180,60)).save(b,format='PNG')
    raw=b.getvalue()
    row={'exam':25,'frame':50,'filename':'frame_000050.PNG','blood':int(not bad_label),
         'fit_enriched':1,'reference_uniform':0,'source_image_sha256':hashlib.sha256(raw).hexdigest(),
         'source_bytes':len(raw)}
    if bad_sha:row['source_image_sha256']='0'*64
    with zipfile.ZipFile(src,'x',compression=zipfile.ZIP_STORED) as z:
        z.writestr('images/025/frame_000050.PNG',raw)
        z.writestr('verified-private-manifest.json',json.dumps([row]))
    return src, [{'frame':'50','blood':'1',
                 'fit_enriched':'1','reference_uniform':'0'}], raw


def test_portion_image_hash_label_and_output_guards(tmp_path):
    src,requests,raw=mini_package(tmp_path)
    dest=tmp_path/'selected'
    observed={}
    m.copy_verified_selection(src,[(requests[0],'Galar/25/frame_000050.PNG')],dest,observed)
    assert len(observed)==1 and (dest/'frame_000050.PNG').read_bytes()==raw
    with pytest.raises(ValueError,match='Duplicate'):
        m.copy_verified_selection(src,[(requests[0],'Galar/25/frame_000050.PNG')],dest,observed)
    src2=tmp_path/'badlabel';src2.mkdir()
    package,requests,_=mini_package(src2,bad_label=True)
    with pytest.raises(ValueError,match='blood label'):
        m.copy_verified_selection(package,[(requests[0],'Galar/25/frame_000050.PNG')],tmp_path/'different',{})
    src3=tmp_path/'badhash';src3.mkdir()
    package,requests,_=mini_package(src3,bad_sha=True)
    with pytest.raises(ValueError,match='byte identity'):
        m.copy_verified_selection(package,[(requests[0],'Galar/25/frame_000050.PNG')],tmp_path/'different2',{})


def test_final_package_rejects_incomplete_source_selection(tmp_path):
    with pytest.raises(ValueError,match='Incomplete'):
        m.final_package(tmp_path,{},tmp_path/'output.zip')


def test_exact_official_three_block_ranges_and_source_integrity(tmp_path, monkeypatch):
    base.configure_exam_profile(25)
    root=Path(__file__).resolve().parents[1]/'experiments/galar-21-30-source-index'
    layout=json.loads((root/'layout.json').read_text())
    receipt=json.loads((root/'receipt.json').read_text())
    fake_plan=tmp_path/'synthetic-private.csv'
    fake_plan.write_text('a synthetic plan for testing immutable-source comparison')
    monkeypatch.setattr(base,'EXPECTED_PRIVATE_PLAN_SHA256',base.sha256_file(fake_plan))
    assert base.check_source(layout,receipt,fake_plan)==[
        (2,6950241905,3470070406),
        (3,10420312311,3539043971),
        (4,13959356282,3438758213),
    ]
    bad=json.loads(json.dumps(layout))
    bad['blocks'][3]['compressed_bytes']+=1
    with pytest.raises(ValueError,match='source size|mismatched'):
        base.check_source(bad,receipt,fake_plan)
    tampered=tmp_path/'changed-plan';tampered.write_bytes(fake_plan.read_bytes()+b'x')
    with pytest.raises(ValueError,match='manifest was changed'):
        base.check_source(layout,receipt,tampered)


def test_package_only_after_every_original_frame_verified(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_REQUESTED',1)
    imagedir=tmp_path/'stored'
    imagedir.mkdir()
    raw=io.BytesIO();Image.new('RGB',(3,3),'blue').save(raw,format='PNG')
    pixels=raw.getvalue()
    fname='frame_000025.PNG'
    (imagedir/fname).write_bytes(pixels)
    observed={25:{'exam':25,'frame':25,'filename':fname,
                  'blood':1,'reference_uniform':1,'fit_enriched':1,
                  'source_image_sha256':hashlib.sha256(pixels).hexdigest(),
                  'source_bytes':len(pixels)}}
    output=tmp_path/'complete.zip'
    result=m.final_package(imagedir,observed,output)
    assert result['verified_source_images']==1
    assert result['blood_positive_selected_images']==1
    assert result['original_archive_full_md5_verified'] is False
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert z.read('images/025/'+fname)==pixels
        assert json.loads(z.read('verified-private-manifest.json'))[0]['frame']==25
    with pytest.raises(FileExistsError):
        m.final_package(imagedir,observed,output)
