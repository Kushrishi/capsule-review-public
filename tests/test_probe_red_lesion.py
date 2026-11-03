"""Source index audit with generated ZIP metadata, no real patient data."""
from pathlib import Path
import sys
from zipfile import ZipInfo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from probe_red_lesion import (summarize, _bucket, DEFAULT_PROBE_BYTES,
                               ORIGINAL_CAP_BYTES, CUMULATIVE_BYTES)


def entry(name, size=100, compressed=60, encrypted=False):
    i=ZipInfo(name)
    i.file_size=size
    i.compress_size=compressed
    i.flag_bits = 1 if encrypted else 0
    return i


def test_classifies_only_named_set_folders():
    assert _bucket('folder/Set 2/images/0001.jpg') == 'set_2_sequential_candidate'
    assert _bucket('Set_II/masks/0001.bmp') == 'set_2_sequential_candidate'
    assert _bucket('Set1/A/0001.png') == 'set_1_nonsequential_candidate'
    assert _bucket('Set 21/file.png') == 'other'
    assert _bucket('patient-2/0001.jpg') == 'other'


def test_aggregate_counts_and_budget_never_declares_labels_validated():
    infos=[entry('Set 2/A/0001.jpg'),entry('Set 2/B/0001.bmp'),entry('Set 1/A/001.jpg')]
    out=summarize(infos,archive_bytes=10_000,transferred_bytes=100,requests=2)
    assert out['groups']['set_2_sequential_candidate']['candidate_images']==2
    assert out['groups']['set_2_sequential_candidate']['likely_masks_by_path']==1
    assert out['groups']['set_1_nonsequential_candidate']['file_count']==1
    assert out['remaining_after_index_bytes']==ORIGINAL_CAP_BYTES-CUMULATIVE_BYTES-100
    assert out['tentatively_within_remaining_budget'] is True
    assert out['ready_for_pathology_evaluation'] is False
    assert out['frame_labels_verified'] is False


def test_encrypted_files_block_tentative_extraction():
    out=summarize([entry('Set 2/A/001.jpg',encrypted=True)],archive_bytes=9000,
                  transferred_bytes=100,requests=2)
    assert out['groups']['set_2_sequential_candidate']['encrypted_files']==1
    assert not out['tentatively_within_remaining_budget']


def test_over_budget_blocks_extraction():
    out=summarize([entry('Set 2/A/001.jpg',size=135_000_000,compressed=135_000_000)],
                  archive_bytes=460_000_000,transferred_bytes=150,requests=2)
    assert not out['tentatively_within_remaining_budget']


def test_duplicate_path_rejected():
    with pytest.raises(ValueError,match='Duplicate'):
        summarize([entry('Set 2/A/001.jpg'),entry('Set 2/A/001.jpg')],
                  archive_bytes=9000,transferred_bytes=100,requests=2)


def test_transfer_cap_rejected():
    with pytest.raises(ValueError,match='Out-of-bounds'):
        summarize([entry('Set 2/A/001.jpg')], archive_bytes=9000,
                  transferred_bytes=DEFAULT_PROBE_BYTES+1,requests=2)


def test_no_matching_set2_refuses_tentative_extraction():
    out=summarize([entry('just_images/001.jpg')],archive_bytes=9000,
                  transferred_bytes=100,requests=2)
    assert not out['tentatively_within_remaining_budget']
