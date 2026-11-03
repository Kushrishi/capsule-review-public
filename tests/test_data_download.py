import hashlib
import io
import json

import pytest
from capsule_review import data_download as d


class Response(io.BytesIO):
    def geturl(self):return 'https://ndownloader.figshare.com/files/123'


def catalog(payload=b'example bytes'):
    return {'id':25304616,'version':2,'doi':'example-metadata-fixture',
            'license':{'name':'CC BY 4.0'},'files':[{'id':123,'name':'example.zip','size':len(payload),
            'computed_md5':hashlib.md5(payload,usedforsecurity=False).hexdigest(),
            'download_url':'https://ndownloader.figshare.com/files/123'}]}


def test_bounded_download_checksum_and_receipt(tmp_path,monkeypatch):
    body=b'example bytes';monkeypatch.setattr(d,'urlopen',lambda *a,**kw:Response(body))
    result=d.download_file(catalog(body),123,tmp_path,max_bytes=100)
    assert (tmp_path/'example.zip').read_bytes()==body
    assert result['sha256']==hashlib.sha256(body).hexdigest()
    assert json.loads((tmp_path/'example.zip.source.json').read_text())['version']==2


def test_budget_checked_before_network(tmp_path,monkeypatch):
    monkeypatch.setattr(d,'urlopen',lambda *a,**kw:pytest.fail('should not make a request'))
    with pytest.raises(ValueError,match='budget'):d.download_file(catalog(),123,tmp_path,max_bytes=1)


def test_bad_checksum_no_partial_retained(tmp_path,monkeypatch):
    monkeypatch.setattr(d,'urlopen',lambda *a,**kw:Response(b'corrupt bytes'))
    with pytest.raises(ValueError,match='checksum'):d.download_file(catalog(),123,tmp_path,max_bytes=100)
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('name',['../escape','folder/file','..','bad\\file'])
def test_unsafe_filename(tmp_path,name):
    c=catalog();c['files'][0]['name']=name
    with pytest.raises(ValueError,match='filename'):d.download_file(c,123,tmp_path)


def test_unexpected_host_rejected(tmp_path):
    c=catalog();c['files'][0]['download_url']='https://example.com/file'
    with pytest.raises(ValueError,match='host'):d.download_file(c,123,tmp_path)


def test_old_annotations_rejected():
    c=catalog();c['version']=1
    with pytest.raises(ValueError,match='version 2'):d.validate_catalog(c)


def test_catalog_save_without_downloading_images(tmp_path,monkeypatch):
    c=catalog();monkeypatch.setattr(d,'urlopen',lambda *a,**kw:Response(json.dumps(c).encode()))
    assert d.get_catalog(tmp_path/'catalog.json')==c
    assert list(tmp_path.iterdir())==[tmp_path/'catalog.json']
    with pytest.raises(ValueError,match='exists'):d.get_catalog(tmp_path/'catalog.json')


def test_existing_download_not_replaced(tmp_path,monkeypatch):
    (tmp_path/'example.zip').write_bytes(b'existing')
    monkeypatch.setattr(d,'urlopen',lambda *a,**kw:pytest.fail('should not make a request'))
    with pytest.raises(ValueError,match='already exists'):d.download_file(catalog(),123,tmp_path)
    assert (tmp_path/'example.zip').read_bytes()==b'existing'
