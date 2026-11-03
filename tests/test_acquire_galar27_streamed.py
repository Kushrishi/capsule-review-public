"""Safety regression tests for the frozen examination-27 streamed acquisition.

All tests use synthetic labels and local source-index fixtures, never patient data.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys
import zipfile
import hashlib

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import acquire_galar27_streamed as m
import acquire_galar25_streamed as streamer
import acquire_galar_multiblock as base


@pytest.fixture
def profile():
    m.configure()
    try:
        yield
    finally:
        # The original exam25 test suite remains isolated from this adapter.
        base.configure_exam_profile(30)
        streamer.EXAM = 25
        streamer.BLOCKS = (2, 3, 4)
        streamer.EXPECTED_REQUESTED = 1013
        streamer.EXPECTED_ARCHIVE_MEMBERS = 22477
        streamer.EXPECTED_ENRICHED = 512
        streamer.EXPECTED_UNIFORM = 512
        streamer.EXPECTED_OVERLAP = 11
        streamer.EXPECTED_ENRICHED_POSITIVE = 256
        streamer.EXPECTED_UNIFORM_POSITIVE = 14
        streamer.EXPECTED_BLOCK_TOTAL = 10447872590


def fixed_rows():
    # 512 enriched 0:511; 512 reference 493:1004; overlap 19.
    # 256 enriched positives (237 first and 19 overlapping);
    # 26 label-blind-reference positives (19 overlap and seven reference-only).
    rows = []
    for i in range(1005):
        enriched = i < 512
        uniform = i >= 493
        blood = (i < 237 or 493 <= i < 519)
        rows.append({
            'exam':'27', 'frame':str(5*i), 'filename':f'frame_{5*i:06d}.PNG',
            'blood':str(int(blood)), 'fit_enriched':str(int(enriched)),
            'reference_uniform':str(int(uniform)), 'source_csv_sha256':'a'*64
        })
    return rows


def save_rows(rows, path):
    with path.open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_verified_official_source_layout_and_bounded_compressed_ranges(profile, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1] / 'experiments/galar-21-30-source-index'
    layout = json.loads((root/'layout.json').read_text())
    receipt = json.loads((root/'receipt.json').read_text())
    rows = fixed_rows()
    plan = save_rows(rows, tmp_path/'source-selection.csv')
    monkeypatch.setattr(base, 'EXPECTED_PRIVATE_PLAN_SHA256', base.sha256_file(plan))
    assert base.EXAM == m.EXAM == 27
    assert base.BLOCKS == m.BLOCKS == (5,6)
    assert base.EXPECTED_EXAM_IMAGES == 14796
    assert base.EXPECTED_EXAM_BLOCK_IMAGES == {5:10842,6:3954}
    assert base.check_source(layout, receipt, plan) == [
        (5,17398114495,3489830304),
        (6,20887944799,3455329610)
    ]
    assert sum(base.EXPECTED_BLOCK_BYTES.values()) == m.EXPECTED_SOURCE_BLOCK_BYTES
    streamer.check_frozen_selection(rows)


def test_selection_does_not_allow_other_or_reserved_exam(profile, tmp_path):
    valid=fixed_rows()
    streamer.check_frozen_selection(valid)
    assert len(base.requested_rows(save_rows(valid,tmp_path/'ok.csv'),exam=27))==1005
    for forbidden in (9,10,11,20,25,29,30,61,80):
        corrupted=[dict(v) for v in valid]
        corrupted[0]['exam']=str(forbidden)
        with pytest.raises(ValueError, match='identities changed'):
            streamer.check_frozen_selection(corrupted)
    corrupted=[dict(v) for v in valid]
    corrupted[0]['blood']='unknown'
    with pytest.raises(ValueError):
        streamer.check_frozen_selection(corrupted)


def test_frozen_reference_counts_and_no_duplicate_source_ids(profile):
    rows=fixed_rows()
    assert len(rows)==1005
    assert sum(int(r['fit_enriched']) for r in rows)==512
    assert sum(int(r['reference_uniform']) for r in rows)==512
    assert sum(int(r['blood'])*int(r['reference_uniform']) for r in rows)==26
    assert sum(int(r['blood'])*int(r['fit_enriched']) for r in rows)==256
    assert sum(int(r['fit_enriched'])*int(r['reference_uniform']) for r in rows)==19
    corrupted=[dict(v) for v in rows]
    corrupted[-1]['reference_uniform']='0'
    with pytest.raises(ValueError,match='roles or label support'):
        streamer.check_frozen_selection(corrupted)
    duplicated=[dict(v) for v in rows]
    duplicated[1]['frame']=duplicated[0]['frame']
    with pytest.raises(ValueError,match='Repeated source frame'):
        streamer.check_frozen_selection(duplicated)


def test_member_mapping_rejects_wrong_block_or_incomplete_source_inventory(profile, monkeypatch):
    monkeypatch.setattr(streamer, 'EXPECTED_ARCHIVE_MEMBERS', 3)
    monkeypatch.setattr(streamer, 'EXPECTED_REQUESTED', 2)
    monkeypatch.setattr(base, 'EXPECTED_EXAM_BLOCK_IMAGES', {5:2,6:1})
    entries=[
      'Path = Galar/27/frame_0000000.PNG\nSize = 100\nFolder = -\nBlock = 5',
      'Path = Galar/27/frame_0000005.PNG\nSize = 100\nFolder = -\nBlock = 5',
      'Path = Galar/27/frame_0000010.PNG\nSize = 100\nFolder = -\nBlock = 6',
      'Path = Galar/27/README.txt\nSize = 40\nFolder = -\nBlock = 6'
    ]
    listing='archive\n----------\n'+'\n\n'.join(entries)
    selected=[({'frame':str(v),'blood':'1'},f'Galar/27/frame_{v:07d}.PNG') for v in (0,10)]
    partition=streamer.verified_member_partition(listing, selected)
    assert len(partition[5])==len(partition[6])==1
    bad=listing.replace('Block = 5','Block = 8')
    with pytest.raises(ValueError,match='outside approved'):
        streamer.verified_member_partition(bad,selected)
    with pytest.raises(ValueError,match='block inventory differs'):
        streamer.verified_member_partition(listing.replace('Galar/27/frame_0000005.PNG','Galar/28/frame_0000005.PNG'),selected)


def test_no_unapproved_original_block_request(profile,tmp_path):
    sparse=tmp_path/'source.7z'
    sparse.write_bytes(b'index')
    with pytest.raises(ValueError,match='Unapproved'):
        base.download_verified_range(sparse,4,13959356282,3438758213)
    with pytest.raises(ValueError,match='Unapproved'):
        base.download_verified_range(sparse,5,17398114495,3489830305)
    with pytest.raises(ValueError,match='Unapproved'):
        base.download_verified_range(sparse,6,20887944799,3455329609)


def test_package_requires_verified_unique_pngs(profile,tmp_path,monkeypatch):
    monkeypatch.setattr(streamer,'EXPECTED_REQUESTED',1)
    frame=5
    raw=io.BytesIO();Image.new('RGB',(5,5),(90,25,30)).save(raw,format='PNG')
    data=raw.getvalue()
    saved=tmp_path/'selected'
    saved.mkdir()
    filename='frame_000005.PNG'
    (saved/filename).write_bytes(data)
    image={frame:{'exam':27,'frame':frame,'filename':filename,'blood':1,
                  'fit_enriched':1,'reference_uniform':1,
                  'source_image_sha256':hashlib.sha256(data).hexdigest(),
                  'source_bytes':len(data)}}
    output=tmp_path/'private.zip'
    result=streamer.final_package(saved,image,output)
    assert result['examination']==27 and result['verified_source_images']==1
    assert result['original_archive_full_md5_verified'] is False
    with zipfile.ZipFile(output) as bundle:
        assert bundle.testzip() is None
        assert bundle.read('images/027/frame_000005.PNG')==data
    with pytest.raises(FileExistsError):
        streamer.final_package(saved,image,output)


def test_explicit_frozen_profiles_reject_other_exam_values(profile):
    with pytest.raises(ValueError,match='Only prespecified'):
        base.configure_exam_profile(11)
    assert base.EXAM==27
