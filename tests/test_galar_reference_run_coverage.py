"""Test the annotation-run ceiling and budget logic on fully synthetic records."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'galar_reference_run_coverage.py'
spec = importlib.util.spec_from_file_location('galar_reference_run_coverage', MODULE)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)


def test_run_boundaries_are_source_gaps_and_label_gaps_not_sample_gaps():
    rows=[{'frame':f,'blood':b} for f,b in [
        (0,'1'),(5,'1'),(10,'1'),(15,'0'),(20,'1'),(25,'1'),(35,'1'),
        (40,''),(45,'1'),(50,'0'),(55,'1')]]
    runs,mapping=m.positive_runs(rows)
    assert [r['length_annotated_rows'] for r in runs]==[3,2,1,1,1]
    assert mapping[0]==mapping[5]==mapping[10]==0
    assert mapping[20]==mapping[25]==1
    assert mapping[35]==2 and mapping[45]==3 and mapping[55]==4
    assert 40 not in mapping and 15 not in mapping
    with pytest.raises(ValueError,match='order'):
        m.positive_runs([{'frame':5,'blood':'1'},{'frame':0,'blood':'1'}])
    with pytest.raises(ValueError,match='Invalid'):
        m.positive_runs([{'frame':5,'blood':'nope'}])


def test_run_size_strata_are_fixed_and_nonclinical():
    assert [m.stratum(x) for x in [1,5,6,25,26,100]]==['1-5','1-5','6-25','6-25','26+','26+']
    with pytest.raises(ValueError,match='Empty'):
        m.stratum(0)


def synthetic_refs(exam=25,positive_ix=(0,1,40,100,200)):
    return [{'exam':exam,'frame':5*i,'blood':int(i in positive_ix),'reference_uniform':1,
             'source_image_sha256':'a'*64,
             'scores':{'original_checkpoint':float(512-i)/512,
                       'red_excess':i/512}} for i in range(512)]


def test_reference_ceiling_suppresses_unobserved_original_positive_runs():
    # The original source has three positive runs; the 512-image reference sees
    # two of them and cannot ever find the third, even at 100% review.
    refs=synthetic_refs(25,positive_ix=(0,1,40,100,200))
    full={'source_rows':2000,'source_positive_rows':12,
          'frame_to_run':{0:0,5:0,40*5:1,100*5:1,200*5:1,10000:2},
          'runs':[{'length_annotated_rows':5,'stratum':'1-5'},
                  {'length_annotated_rows':6,'stratum':'6-25'},
                  {'length_annotated_rows':1,'stratum':'1-5'}]}
    # Add the unseen run to full source, but not to reference.
    x=m.analyze(25,refs,full)
    assert x['source_blood_annotation_runs']==3
    assert x['reference_run_ceiling_hits']==2
    assert x['reference_run_ceiling_recall']==pytest.approx(2/3)
    assert x['budgets']['100']['methods']['original_checkpoint']['source_annotation_runs_hit']==2
    assert x['budgets']['100']['methods']['red_excess']['source_annotation_runs_hit']==2
    assert x['budgets']['100']['methods']['uniform']['source_annotation_runs_hit']==2
    assert x['budgets']['10']['selected_reference_images']==51
    assert x['budgets']['10']['methods']['original_checkpoint']['blood_positive_reference_images_found']==3
    assert x['budgets']['10']['methods']['original_checkpoint']['source_annotation_runs_hit']==2


def test_positive_images_from_one_run_are_not_multiple_runs():
    refs=synthetic_refs(25,positive_ix=(0,1,2,3,4,5,100))
    full={'source_rows':1000,'source_positive_rows':7,
          'frame_to_run':{i*5:(0 if i<6 else 1) for i in (0,1,2,3,4,5,100)},
          'runs':[{'length_annotated_rows':6,'stratum':'6-25'},
                  {'length_annotated_rows':1,'stratum':'1-5'}]}
    x=m.analyze(25,refs,full)
    selected=x['budgets']['5']['methods']['original_checkpoint']
    assert selected['blood_positive_reference_images_found']==6
    assert selected['source_annotation_runs_hit']==1
    assert x['reference_run_ceiling_hits']==2


def test_all_negative_exam_recall_is_null_and_workload_is_not_zero():
    refs=synthetic_refs(9,positive_ix=())
    full={'source_rows':4339,'source_positive_rows':0,'frame_to_run':{},'runs':[]}
    x=m.analyze(9,refs,full)
    assert x['source_blood_annotation_runs']==0
    assert x['reference_run_ceiling_recall'] is None
    assert x['budgets']['10']['methods']['original_checkpoint']['source_annotation_run_recall'] is None
    assert x['budgets']['10']['methods']['original_checkpoint']['blood_annotation_negative_images_selected']==51
    assert x['negative_source_examination_fixed_score_thresholds']['0.5']['selected_scored_images']==257
    assert x['negative_source_examination_fixed_score_thresholds']['0.9']['selected_scored_images']==52


def test_read_source_annotation_sha_failure_does_not_inspect_labels(tmp_path):
    p=tmp_path/'unknown.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('9.csv','frame,blood\n0,0\n')
    with pytest.raises(ValueError,match='SHA-256 changed'):
        m.open_labels(p)


def test_saved_prediction_schemas_and_prohibited_exam_guard():
    raw={'exam':'9','frame':'400','source_sha256':'a'*64,
         'blood_label':'0','cnn_score':'0.123','red_excess_score':'0.032'}
    r=m.normalize_row(raw,'pilot',(9,10))
    assert (r['exam'],r['frame'],r['blood'],r['reference_uniform'])==(9,400,0,1)
    assert r['scores']['original_checkpoint']==0.123
    with pytest.raises(ValueError,match='Unapproved'):
        m.normalize_row({**raw,'exam':'11'},'pilot',(9,10))
    with pytest.raises(ValueError,match='Unknown'):
        m.normalize_row({**raw,'blood_label':'missing'},'pilot',(9,10))
    with pytest.raises(ValueError,match='Invalid saved'):
        m.normalize_row({**raw,'cnn_score':'nan'},'pilot',(9,10))
    with pytest.raises(ValueError,match='SHA-256'):
        m.normalize_row({**raw,'source_sha256':'0'*63},'pilot',(9,10))


def test_source_frame_schema_aligned_reference_detects_changed_blood_label(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'EXAMS',(9,))
    monkeypatch.setattr(m,'EXPECTED_REFERENCE_POSITIVE',{9:0})
    content=io.StringIO()
    writer=csv.DictWriter(content,fieldnames=['exam','frame','source_sha256','blood_label','cnn_score','red_excess_score'],lineterminator='\n')
    writer.writeheader()
    for i in range(512):
        writer.writerow({'exam':9,'frame':5*i,'source_sha256':'a'*64,'blood_label':0,'cnn_score':0.1,'red_excess_score':0.1})
    raw=content.getvalue().encode()
    inner='private-development-predictions/predictions.csv'
    z=tmp_path/'pilot.zip'
    with zipfile.ZipFile(z,'w') as archive:archive.writestr(inner,raw)
    monkeypatch.setattr(m,'EXPECTED_CSV',{'pilot':(inner,512,m.sha(raw),(9,))})
    src={9:{'labels':{5*i:'0' for i in range(512)},'frame_to_run':{},'runs':[]}}
    assert len(m.open_scores({'pilot':z},src)[9])==512
    src[9]['labels'][5]='1'
    with pytest.raises(ValueError,match='does not match'):
        m.open_scores({'pilot':z},src)


def test_fixed_budgets_and_no_future_evaluation_roles_in_approved_exams():
    assert m.EXAMS==(9,10,21,23,25,27,29,30)
    assert all(x not in m.EXAMS for x in [11,12,13,14,15,16,17,18,19,20,61,80])
    assert m.BUDGETS==(5,10,25,50,75,100)
    assert [512*n//100 for n in m.BUDGETS]==[25,51,128,256,384,512]


def test_source_zip_reads_only_approved_exams_without_traversing_reserved(tmp_path,monkeypatch):
    # An archive can contain unapproved exams; a whole-ZIP testzip() would
    # decompress them, which is prohibited even if their values aren't used.
    p=tmp_path/'official-labelling-synthetic.zip'
    data='frame,blood\n'+''.join(f'{i*5},{int(200<=i<206)}\n' for i in range(1024))
    with zipfile.ZipFile(p,'w') as archive:
        archive.writestr('9.csv',data)
        archive.writestr('11.csv','frame,blood\n0,1\n')
        archive.writestr('61.csv','frame,blood\n0,1\n')
    monkeypatch.setattr(m,'EXAMS',(9,))
    monkeypatch.setattr(m,'SOURCE_SHA',m.sha_file(p))
    original_read=zipfile.ZipFile.read
    def guarded_read(self,name,*args,**kwargs):
        if name!='9.csv':raise AssertionError('Tried to read a reserved examination CSV')
        return original_read(self,name,*args,**kwargs)
    def disallow_full_archive_traversal(self,*args,**kwargs):
        raise AssertionError('Whole-archive CRC traverses reserved label files')
    monkeypatch.setattr(zipfile.ZipFile,'read',guarded_read)
    monkeypatch.setattr(zipfile.ZipFile,'testzip',disallow_full_archive_traversal)
    source=m.open_labels(p)
    assert list(source)==[9]
    assert source[9]['source_positive_rows']==6
