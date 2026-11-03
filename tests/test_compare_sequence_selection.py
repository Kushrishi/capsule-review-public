"""Pure policy and real-file guards; no clinical-data bytes in tests."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import io
import json
import zipfile

from PIL import Image
import pytest

ROOT=Path(__file__).resolve().parents[1]
modspec=importlib.util.spec_from_file_location('compare_sequence_selection',ROOT/'scripts/compare_sequence_selection.py')
mod=importlib.util.module_from_spec(modspec)
modspec.loader.exec_module(mod)


def test_endpoint_and_exact_budget():
    for n in [3,10,101]:
        scores=[0]+[float((i*7)%13) for i in range(1,n)]
        for k in [1,2,3, min(7,n), n]:
            for fun in [mod.uniform,mod.global_change,mod.stratified_change]:
                s=fun(n,k) if fun is mod.uniform else fun(scores,k)
                assert len(s)==k
                assert len(set(s))==k
                assert s==sorted(s)
                if k>1: assert (s[0],s[-1])==(0,n-1)
                else: assert s==[(n-1)//2]


def test_known_change_selection():
    x=[0,0,1,10,2,1,0,4,0,0]
    assert mod.global_change(x,4)==[0,3,7,9]
    assert mod.stratified_change(x,4)==[0,3,7,9]


def test_repeated_seed_and_label_blindness():
    s=mod.random_anchored(100,10,17)
    assert s==mod.random_anchored(100,10,17)
    assert s!=mod.random_anchored(100,10,18)
    assert len(s)==10


def test_transition_distances_and_zero_boundary():
    x=['1_esophagus']*3+['2_stomach']*4+['3_small_bowel']*5
    y=mod.coverage(len(x),[0,3,8,11],x,[0,2,5])
    assert y['boundary_count']==2
    assert y['boundary_distances']==[0,1]
    assert y['boundary_hits']=={'0':1,'2':2,'5':2}
    assert y['max_nearest_position_distance']==2
    assert mod.coverage(3,[0,2],['2_stomach']*3,[0])['boundary_count']==0


def test_duplicate_selection_rejected():
    with pytest.raises(ValueError):mod.coverage(10,[0,0,9],['2_stomach']*10,[0])


def make_jpeg_bytes(color:tuple[int,int,int]):
    buf=io.BytesIO();Image.new('RGB',(32,32),color).save(buf,format='JPEG');return buf.getvalue()


def make_archive(p:Path, name='s280', gap=False, badfolder=False):
    with zipfile.ZipFile(p,'w') as z:
        for i,folder in enumerate(mod.REGION_ORDER):
            id=1+i+(1 if gap and i>=2 else 0)
            label='incorrect' if badfolder and i==1 else folder
            z.writestr(f'{name}/{label}/image-{id:05}.png',make_jpeg_bytes((i*30,10,10)))


def test_valid_archive_and_encoded_jpeg(tmp_path):
    archive=tmp_path/'test.zip';make_archive(archive)
    ids,reg,scores,info=mod.read_study(archive,'s280')
    assert ids==[1,2,3,4]
    assert len(scores)==4
    assert scores[0]==0 and all(x>=0 for x in scores)
    assert info['actual_formats']=={'JPEG':4}


@pytest.mark.parametrize('kw', [{'gap':True},{'badfolder':True}])
def test_corrupted_sequence_rejected(tmp_path,kw):
    archive=tmp_path/'test.zip';make_archive(archive,**kw)
    with pytest.raises(ValueError):mod.read_study(archive,'s280')


def test_source_identity_required_for_future_and_unregistered_rejected(tmp_path):
    archive=tmp_path/'test.zip';make_archive(archive)
    spec=json.loads((ROOT/'docs/SEQUENCE_SELECTION_SPEC.json').read_text())
    with pytest.raises(ValueError,match='not included'):
        mod.evaluate(archive,'s001',spec)
    result=mod.evaluate(archive,'s280',spec)
    assert result['image_count']==4 and len(result['budget_results'])==3
    assert result['anatomy_boundary_count']==3
    assert result['patient_independence_known'] is False
    assert result['clinical_claims_supported'] is False
