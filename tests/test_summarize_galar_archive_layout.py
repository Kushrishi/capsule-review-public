"""Verify index-only 7z listing accounting with synthetic text; no medical pixels."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import summarize_galar_archive_layout as m

RECEIPT = {'official_file_id': 45258019, 'full_archive_downloaded': False,
           'pixels_acquired': 0, 'official_full_archive_bytes': 31989399751}
LISTING = '''7-Zip [64] ...
Path = example.7z
Type = 7z
----------
Path = root/21/a.png
Size = 100
Packed Size = 70
Folder = -
Block = 0

Path = root/21/b.png
Size = 200
Packed Size =
Folder = -
Block = 0

Path = root/22/c.PNG
Size = 300
Packed Size = 250
Folder = -
Block = 1

Path = root/22/readme.txt
Size = 10
Packed Size =
Folder = -
Block = 1
'''


def test_summarise_actual_block_accounting():
    r=m.summarise(LISTING, RECEIPT)
    assert r['image_members_by_exam']=={'21':2,'22':1}
    assert r['total_compression_blocks']==2
    assert [b['compressed_bytes'] for b in r['blocks']]==[70,250]
    assert r['blocks'][0]['uncompressed_bytes']==300
    assert r['other_file_members']==1
    assert r['pixels_read']==0


def test_unassigned_member_remains_explicit():
    listing=LISTING.replace('root/22/c.PNG','root/other/c.PNG')
    r=m.summarise(listing,RECEIPT)
    assert r['unassigned_image_members']==1
    assert r['image_members_by_exam']=={'21':2}


def test_unsafe_path_rejected():
    for x in ['../21/frame.png','/21/file.png','C:\\21\\file.png','21/../../file.png']:
        with pytest.raises(ValueError,match='Unsafe'):
            m.get_exam(x)


def test_ambiguous_exam_rejected():
    with pytest.raises(ValueError, match='Ambiguous'):
        m.get_exam('21/22/other.png')


def test_invalid_listing_and_duplicate_keys_rejected():
    with pytest.raises(ValueError, match='separator'):
        m.summarise('Path = foo',RECEIPT)
    with pytest.raises(ValueError, match='Duplicate'):
        m.records('-----\n----------\nPath = x\nPath = y\nSize = 1')


def test_no_clinical_claim_or_unverified_original_pixels():
    with pytest.raises(ValueError, match='receipt'):
        m.summarise(LISTING,{**RECEIPT,'pixels_acquired':4})
    with pytest.raises(ValueError,match='block'):
        m.summarise(LISTING.replace('Block = 1','Block = invalid'),RECEIPT)


def test_source_id_from_exact_component():
    assert m.get_exam('root/021/frame_000001.PNG')==21
    assert m.get_exam('root/21/foo.JPG')==21
    assert m.get_exam('root/other/frame_000021.PNG') is None


def test_exam30_members_are_identified_even_when_archive_filename_says_29():
    assert m.get_exam('Galar/30/frame_000005.PNG') == 30
    listing = LISTING.replace('root/22/c.PNG', 'root/30/c.PNG')
    result=m.summarise(listing, RECEIPT)
    assert result['image_members_by_exam']['30'] == 1


def test_structural_name_patterns_do_not_expose_original_frame_identifiers():
    result=m.summarise(LISTING,RECEIPT)
    assert result['exam21_basename_patterns_only']=={'a.png':1,'b.png':1}
    assert not any('000000' in name for name in result['exam21_basename_patterns_only'])


UNSEEN_RECEIPT = {
    'record_type': 'galar-11-20-7z-index-only-v1',
    'official_file_id': 44725302,
    'official_full_archive_bytes': 40_043_548_469,
    'full_archive_downloaded': False,
    'pixels_acquired': 0,
}
UNSEEN_LISTING = (
    "7-Zip (synthetic metadata listing)\n----------\n" +
    "\n\n".join(
        f"Path = archive/{exam}/frame_{exam * 5:06d}.PNG\n"
        f"Size = 100\nPacked Size = 40\nFolder = -\nBlock = {exam - 11}"
        for exam in range(11, 21)
    )
)

def test_unseen_11_to_20_listing_is_aggregate_only():
    result = m.summarise(UNSEEN_LISTING, UNSEEN_RECEIPT, source='unseen-11-20')
    assert result['origin_file_id'] == 44725302
    assert result['record_type'] == 'galar-11-20-index-only-block-summary-v1'
    assert result['image_members_by_exam'] == {str(exam): 1 for exam in range(11, 21)}
    assert result['unassigned_image_members'] == 0
    assert result['pixels_read'] == 0
    assert result['full_source_checksum_verified'] is False
    assert 'exam21_basename_patterns_only' not in result
    assert 'frame_000005' not in str(result)
    assert 'frame_000100' not in str(result)
    assert m.get_exam('frames/11/frame_000005.PNG',
                      allowed_exams=m.EXAMINATIONS_BY_SOURCE['unseen-11-20']) == 11
    assert m.get_exam('frames/61/frame_000005.PNG',
                      allowed_exams=m.EXAMINATIONS_BY_SOURCE['unseen-11-20']) is None


def test_unseen_layout_refuses_wrong_archive_and_untrusted_receipt():
    for altered in (
        {**UNSEEN_RECEIPT, 'official_file_id': 45258019},
        {**UNSEEN_RECEIPT, 'official_full_archive_bytes': 32},
        {**UNSEEN_RECEIPT, 'full_archive_downloaded': True},
        {**UNSEEN_RECEIPT, 'pixels_acquired': 1},
        {**UNSEEN_RECEIPT, 'record_type': 'galar-21-29-7z-index-only-v1'},
    ):
        with pytest.raises(ValueError, match='Trusted matching'):
            m.summarise(UNSEEN_LISTING, altered, source='unseen-11-20')
    with pytest.raises(ValueError, match='Unrecognized'):
        m.summarise(UNSEEN_LISTING, UNSEEN_RECEIPT, source='unknown')



def test_unseen_index_fails_closed_on_partial_cohort_or_wrong_group():
    # A plausible source index is insufficient if even one locked exam is absent.
    missing = UNSEEN_LISTING.replace(
        "archive/20/frame_000100.PNG", "archive/19/frame_000100.PNG",
    )
    with pytest.raises(ValueError, match="missing one or more locked examinations"):
        m.summarise(missing, UNSEEN_RECEIPT, source="unseen-11-20")
    # A retained image from any other cohort must never be silently counted.
    unexpected = UNSEEN_LISTING.replace(
        "archive/20/frame_000100.PNG", "archive/61/frame_000100.PNG",
    )
    with pytest.raises(ValueError, match="unexpected image member"):
        m.summarise(unexpected, UNSEEN_RECEIPT, source="unseen-11-20")
