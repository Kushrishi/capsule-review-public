"""Acquisition must fail closed; no real networking or medical images in tests."""
import io
from pathlib import Path
import importlib.util
import json
import zipfile
import zlib

import pytest

ROOT=Path(__file__).resolve().parents[1]


def load_script(filename):
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location(filename,ROOT/'scripts'/f'{filename}.py')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

acq=load_script('acquire_preregistered_rhode')
summary=load_script('summarize_rhode_replication')


def inner_zip_bytes():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('s280/1_esophagus/image-00001.png',b'fixture, not image')
    return b.getvalue()


class Response:
    status=206
    def __init__(self,blob,start):
        self._buffer=io.BytesIO(blob)
        self.headers={'Content-Range':f'bytes {start}-{start+len(blob)-1}/{acq.OUTER_BYTES}',
                      'Content-Length':str(len(blob)), 'Content-Encoding':'identity'}
        self.was_read=False
    def read(self,n=-1):
        self.was_read=True
        return self._buffer.read(n)
    def geturl(self): return 'https://example.org/verified-content'
    def __enter__(self): return self
    def __exit__(self,*_):pass


def test_preregistered_member_set_and_sizes():
    spec={'future_studies_selected_without_examining_images_or_labels':[
        {'study':s,'source_member':t[0],'source_member_bytes':t[1]}
        for s,t in acq.MEMBERS.items()]}
    assert set(acq.prepared_members(spec))=={'s280','s284'}
    spec['future_studies_selected_without_examining_images_or_labels'][0]['source_member_bytes'] += 1
    with pytest.raises(ValueError,match='Frozen'):acq.prepared_members(spec)


def test_exact_206_download_and_hash(tmp_path,monkeypatch):
    blob=inner_zip_bytes()
    start=5678
    resp=Response(blob,start)
    monkeypatch.setattr(acq.urllib.request,'urlopen',lambda req,timeout:resp)
    entry={'name':'Study 276-300/s280.zip','size':len(blob),'crc32':f'{zlib.crc32(blob):08x}','offset':start}
    got=acq.download_member('s280',entry,tmp_path/'s280.zip')
    assert got['source_member']==entry['name'] and got['inner_zip_crc_passed']
    assert (tmp_path/'s280.zip').read_bytes()==blob


def test_http_200_aborts_before_read_or_writing(tmp_path,monkeypatch):
    blob=inner_zip_bytes(); start=123
    resp=Response(blob,start); resp.status=200
    monkeypatch.setattr(acq.urllib.request,'urlopen',lambda req,timeout:resp)
    entry={'name':'some.zip','size':len(blob),'crc32':f'{zlib.crc32(blob):08x}','offset':start}
    with pytest.raises(ValueError,match='206'): acq.download_member('s280',entry,tmp_path/'s280.zip')
    assert not resp.was_read and not list(tmp_path.iterdir())


def test_wrong_member_crc_fails_without_publishing(tmp_path,monkeypatch):
    blob=inner_zip_bytes();start=5;resp=Response(blob,start)
    monkeypatch.setattr(acq.urllib.request,'urlopen',lambda req,timeout:resp)
    entry={'name':'s280.zip','size':len(blob),'crc32':'00000000','offset':start}
    with pytest.raises(ValueError,match='CRC'):acq.download_member('s280',entry,tmp_path/'s280.zip')
    assert not (tmp_path/'s280.zip').exists() and not (tmp_path/'s280.part').exists()


def test_length_mismatch_no_partial_publish(tmp_path,monkeypatch):
    blob=inner_zip_bytes();resp=Response(blob,1);resp.headers['Content-Length']='999'
    monkeypatch.setattr(acq.urllib.request,'urlopen',lambda req,timeout:resp)
    entry={'name':'s280.zip','size':len(blob),'crc32':f'{zlib.crc32(blob):08x}','offset':1}
    with pytest.raises(ValueError,match='206'):acq.download_member('s280',entry,tmp_path/'s280.zip')
    assert not (tmp_path/'s280.zip').exists()


def test_cannot_overwrite_existing_study(tmp_path):
    p=tmp_path/'s280.zip';p.write_bytes(b'existing')
    with pytest.raises(ValueError,match='overwrite'):
        acq.download_member('s280',{'size':1,'offset':0,'crc32':'00000000'},p)
    assert p.read_bytes()==b'existing'


def fake_result(study):
    return {'study':study,'source_zip_bytes':summary.EXPECTED[study],
            'spec_sha256':summary.SPEC_HASH,'anatomy_boundary_count':3,
            'source_indices_complete':True,'image_count':4000,'source_zip_sha256':'0'*64,
            'role':'prespecified' if study!='s288' else 'exploratory',
            'budget_results':[{'budget':budget,'k':int(4000*budget),'methods':{
              m:{'boundary_hits':{'5':3},'max_nearest_position_distance':5,
                 'mean_nearest_position_distance':2.0} for m in summary.METHODS}}
             for budget in summary.BUDGETS]}


def test_study_macro_aggregation():
    a={s:fake_result(s) for s in ('s280','s284','s288')}
    out=summary.summarize(a)
    assert out['study_macro']['new_two'][0]['methods']['uniform']['mean_anatomy_boundaries_hit_5_of_3']==3
    assert out['study_macro']['all_three'][2]['studies']==3
    assert not out['clinical_validation']


def test_rejects_unprespecified_or_misidentified_study():
    a={s:fake_result(s) for s in ('s280','s284','s288')}
    a['s280']['source_zip_bytes'] += 1
    with pytest.raises(ValueError,match='Invalid study'):summary.summarize(a)
    del a['s288']
    with pytest.raises(ValueError,match='Study set'):summary.summarize(a)
