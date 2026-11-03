"""Exam23 source-pixel experiment: fixed-method and source-integrity regression."""
import hashlib
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import galar23_pixel_density as p


def test_frozen_protocol_is_exact_original_blob():
    spec=p.validate_protocol(Path(__file__).resolve().parents[1]/'docs'/'GALAR23_PIXEL_DENSITY_SPEC.json')
    assert spec['locked_examination']==23
    assert spec['source_images']['block_id']==1
    assert spec['fixed_absolute_reviewer_frames']==[51,128,256,512]


def test_review_selection_is_equal_budget_and_label_blind():
    seq=list(range(6));scores=[.1,.9,.8,.7,.6,.5]
    methods=p.select_methods(seq,scores,[10,20,30,40,50,60],2)
    assert methods=={'uniform':[1,4],'global_red':[1,2],'bin_stratified_red':[1,3]}
    assert all(len(x)==len(set(x))==2 for x in methods.values())


def test_ties_resolved_by_original_source_index():
    outcomes=p.select_methods(list(range(6)),[.7]*6,[90,20,10,70,50,40],2)
    assert outcomes['global_red']==[2,1]
    assert outcomes['bin_stratified_red']==[2,5]


def test_invalid_ranking_fail_closed():
    for scores in ([.1],[float('nan'),.1]):
        with pytest.raises(ValueError):p.select_methods([0,1],scores,[0,1],1)
    with pytest.raises(ValueError):p.select_methods([0,1],[.2,.4],[1,2],3)


def test_review_source_gap_is_annotation_rows_not_seconds():
    assert p.max_nearest_source_annotation_gap(10,[2,7])==2
    assert p.max_nearest_source_annotation_gap(5,[0,4])==2
    with pytest.raises(ValueError):p.max_nearest_source_annotation_gap(5,[-1])


def test_member_listing_must_match_all_original_image_identities(monkeypatch):
    monkeypatch.setattr(p,'SOURCE_ROWS',3)
    listing='Archive = synthetic.7z\n----------\n\n'+'\n\n'.join(
        f'Path = 23/frame_{n:06d}.PNG\nFolder = -\nSize = 100\nBlock = 1' for n in [0,5,10])+'\n'
    result=p.find_exact_members(listing,{0,5,10})
    assert set(result)=={0,5,10}
    with pytest.raises(ValueError,match='Not all source'):
        p.find_exact_members(listing,{0,5,15})
    with pytest.raises(ValueError,match='Duplicate'):
        p.find_exact_members(listing+'\n\nPath = 23/frame_000000.PNG\nFolder = -\nSize = 100\nBlock = 1\n',{0,5,10})
    with pytest.raises(ValueError,match='frozen source block'):
        p.find_exact_members(listing.replace('Block = 1','Block = 2'),{0,5,10})


def test_source_block_refuses_missing_or_truncated_source(tmp_path):
    f=tmp_path/'sparse.7z';f.write_bytes(b'fake')
    with pytest.raises(ValueError,match='logical-length'):
        p.exact_download_source_block(f)


def test_real_png_in_memory_image_ranking_is_not_label_input(tmp_path,monkeypatch):
    # Exercise original PIL score pipeline against actual test PNG pixels, no external dataset.
    monkeypatch.setattr(p,'REVIEW_COUNTS',(1,2,3,4))
    rows=[(5*i,'1' if i in (1,6) else '0') for i in range(8)]
    pools={4:[0,2,4,6],8:list(range(8))}
    images={}
    for i,(frame,label) in enumerate(rows):
        path=tmp_path/f'frame_{frame:06d}.PNG'
        Image.new('RGB',(32,32),color=(100+i*8,30,15)).save(path)
        images[frame]=path
    outcome=p.evaluate_image_scores(rows,pools,images)
    assert outcome['original_source_pngs_verified']==8
    assert outcome['methods']['8']['candidate_positive_labelled_images']==2
    for candidate in outcome['methods'].values():
        for size,methods in candidate['methods_at_fixed_workload'].items():
            for method,record in methods.items():
                assert record['reviewed_frames']==int(size)
                assert record['distinct_source_annotation_runs_hit'] <= 2
                assert record['source_annotation_row_nearest_review_max_gap']>=0
    assert outcome['clinical_validity'] is False
