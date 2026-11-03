"""Synthetic invariants for the pinned Galar exam29 source-block acquisition.

No external medical images, source labels or live network are needed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acquire_galar_multiblock as m


@pytest.fixture
def exam29():
    """Restore verified exam30 defaults even after an assertion fails."""
    m.configure_exam_profile(29)
    try:
        yield
    finally:
        m.configure_exam_profile(30)


def synthetic_plan(path: Path, *, count=1009, forbidden=None, corrupt_blood=False):
    fields = ['exam', 'frame', 'filename', 'blood', 'fit_enriched',
              'reference_uniform', 'source_csv_sha256']
    with path.open('w', encoding='utf8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for j in range(count):
            frame = 5*j
            writer.writerow({'exam': 29, 'frame':frame, 'filename':f'frame_{frame:06d}.PNG',
                             'blood':'unknown' if corrupt_blood and j==0 else ('1' if j<256 else '0'),
                             'fit_enriched':'1', 'reference_uniform':'0',
                             'source_csv_sha256':'a'*64})
        if forbidden is not None:
            writer.writerow({'exam':forbidden, 'frame':1, 'filename':'frame_000001.PNG',
                             'blood':'0', 'fit_enriched':'1', 'reference_uniform':'0',
                             'source_csv_sha256':'b'*64})
    return path


def test_exam29_locked_profile_matches_real_official_7z_index(exam29, tmp_path, monkeypatch):
    base=Path(__file__).resolve().parents[1]/'experiments/galar-21-30-source-index'
    layout=json.loads((base/'layout.json').read_text())
    receipt=json.loads((base/'receipt.json').read_text())
    plan=synthetic_plan(tmp_path/'selection.csv')
    monkeypatch.setattr(m, 'EXPECTED_PRIVATE_PLAN_SHA256', m.sha256_file(plan))
    assert m.EXAM==29 and m.BLOCKS==(7,8)
    assert m.EXPECTED_EXAM_IMAGES==16018
    assert m.MAX_TOTAL_SOURCE_BYTES==7_100_000_000
    assert m.check_source(layout,receipt,plan)==[
        (7,24_343_274_409,3_500_524_677),
        (8,27_843_799_086,3_514_256_456),
    ]
    assert m.EXPECTED_EXAM_BLOCK_IMAGES=={7:13455,8:2563}
    assert sum(m.EXPECTED_BLOCK_BYTES.values())==7_014_781_133


def test_exam29_prevents_source_size_and_manifest_tampering(exam29,tmp_path,monkeypatch):
    base=Path(__file__).resolve().parents[1]/'experiments/galar-21-30-source-index'
    layout=json.loads((base/'layout.json').read_text())
    receipt=json.loads((base/'receipt.json').read_text())
    path=synthetic_plan(tmp_path/'selection.csv')
    monkeypatch.setattr(m,'EXPECTED_PRIVATE_PLAN_SHA256',m.sha256_file(path))
    broken=json.loads(json.dumps(layout))
    broken['blocks'][7]['compressed_bytes']+=1
    with pytest.raises(ValueError,match='source size|mismatched'):
        m.check_source(broken,receipt,path)
    altered=tmp_path/'tampered.csv';altered.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='manifest was changed'):
        m.check_source(layout,receipt,altered)
    altered_receipt=json.loads(json.dumps(receipt))
    altered_receipt['parts'][0]['sha256']='0'*64
    with pytest.raises(ValueError,match='hashes'):
        m.check_source(layout,altered_receipt,path)


def test_exam29_strict_selection_and_reserved_examinations(exam29,tmp_path):
    rows=m.requested_rows(synthetic_plan(tmp_path/'valid.csv'))
    assert len(rows)==1009
    assert all(int(v['exam'])==29 for v in rows)
    assert len({int(v['frame']) for v in rows})==1009
    with pytest.raises(ValueError,match='Only the preregistered'):
        m.requested_rows(tmp_path/'valid.csv',exam=11)
    with pytest.raises(ValueError,match='evaluation or unapproved'):
        m.requested_rows(synthetic_plan(tmp_path/'holdout.csv',forbidden=11))
    with pytest.raises(ValueError,match='evaluation or unapproved'):
        m.requested_rows(synthetic_plan(tmp_path/'authors-holdout.csv',forbidden=61))
    with pytest.raises(ValueError,match='incomplete'):
        m.requested_rows(synthetic_plan(tmp_path/'short.csv',count=1008))
    with pytest.raises(ValueError,match='Invalid original'):
        m.requested_rows(synthetic_plan(tmp_path/'unknown-label.csv',corrupt_blood=True))


def test_exam29_member_identity_and_block_firewall(exam29,monkeypatch):
    monkeypatch.setattr(m,'EXPECTED_EXAM_BLOCK_IMAGES',{7:2,8:1})
    entries=[
        'Path = Galar/29/frame_0000000.PNG\nSize = 100\nFolder = -\nBlock = 7',
        'Path = Galar/29/frame_0000005.PNG\nSize = 100\nFolder = -\nBlock = 7',
        'Path = Galar/29/frame_0000010.PNG\nSize = 100\nFolder = -\nBlock = 8',
        'Path = Galar/29/readme.txt\nSize = 40\nFolder = -\nBlock = 8',
        'Path = Galar/30/frame_0000015.PNG\nSize = 100\nFolder = -\nBlock = 8',
    ]
    listing='archive\n----------\n'+'\n\n'.join(entries)
    want=[{'frame':'0','blood':'0'},{'frame':'10','blood':'1'}]
    found=m.find_members(listing,want)
    assert len(found)==2 and [int(row['frame']) for row,_ in found]==[0,10]
    assert found[0][1].endswith('frame_0000000.PNG')
    with pytest.raises(ValueError,match='does not exist'):
        m.find_members(listing,want+[{'frame':'15','blood':'1'}])
    with pytest.raises(ValueError,match='another solid block'):
        m.find_members(listing.replace('Block = 7','Block = 9'),want)
    with pytest.raises(ValueError,match='Ambiguous'):
        m.find_members(listing+'\n\n'+entries[0],want)


def test_exam29_no_other_acquisition_profiles_or_extra_byte_ranges(exam29,tmp_path):
    source=tmp_path/'sparse.7z'; source.write_bytes(b'0'*128)
    with pytest.raises(ValueError,match='Unapproved'):
        m.download_verified_range(source,9,31_358_055_542,630_002_169)
    with pytest.raises(ValueError,match='Unapproved'):
        m.download_verified_range(source,7,24_343_274_409,3_500_524_676)
    with pytest.raises(ValueError,match='Unapproved'):
        m.download_verified_range(source,8,27_843_799_086,3_514_256_457)
    with pytest.raises(ValueError,match='Only prespecified'):
        m.configure_exam_profile(11)
    assert m.EXAM==29


def test_exam30_original_default_remains_compatible():
    m.configure_exam_profile(30)
    assert m.EXAM==30
    assert m.BLOCKS==(8,9)
    assert m.EXPECTED_EXAM_IMAGES==16953
    assert m.EXPECTED_REQUESTED_IMAGES==1006
    assert m.MAX_TOTAL_SOURCE_BYTES==4_200_000_000