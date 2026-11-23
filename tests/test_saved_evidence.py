"""Generated saved-only archives, preserved limits and no partial delivery."""
import hashlib,io,json,zipfile
import pytest
from PIL import Image
from capsule_review.importer import import_sources
from capsule_review.full_span_evidence import verify_saved_evidence,verify_full_span_evidence


def download(client,url,path):
    r=client.get(url);assert r.status_code==200,r.text;path.write_bytes(r.content);return path


def test_251_saved_identities_zero_intervals_and_mixed_context(client,app,headers,tmp_path):
    def sources():
        for p in range(253):
            b=io.BytesIO();Image.new('RGB',(8,8),(p,17,(p*7)%256)).save(b,'PNG')
            yield f'frame_{p*5:06d}.png',b.getvalue()
    study=import_sources(app.state.store,sources(),title='Generated saved evidence',source='Generated only',synthetic=True)
    base='/api/studies/'+study['id'];manifest=client.get(base+'/manifest').json()
    assert len({f['source_sha256'] for f in manifest['frames']})==253
    for p in range(251):
        assert client.put(base+f'/frames/{p}/review',headers=headers,json={'revision':0,'bookmarked':True,'note':f'Generated entry {p}','label':'Software fixture'}).status_code==200
    assert client.put(base+'/frames/0/review',headers=headers,json={'revision':1,'bookmarked':True,'note':'Revised generated entry','label':'Software fixture'}).status_code==200
    payload={'schema_version':1,'study_id':study['id'],'model':{'name':'Generated scores, not AI','version':'1','run_id':'generated-saved-v1'},'predictions':[{'position':p,'image_sha256':f['source_sha256'],'label':'generated','score':p/252} for p,f in enumerate(manifest['frames'])]}
    assert client.post(base+'/predictions',headers=headers,json=payload).status_code==201
    assert client.get(base+'/export').status_code==422
    assert client.get(base+'/full-span-export').status_code==422
    for mixed in (False,True):
        if mixed:assert client.post(base+'/intervals',headers=headers,json={'start_position':250,'end_position':252,'note':'Context only'}).status_code==201
        path=download(client,base+'/saved-evidence-export',tmp_path/('mixed.zip' if mixed else 'saved.zip'))
        assert verify_saved_evidence(path,manifest)['exported_images']==251
        with pytest.raises(ValueError):verify_full_span_evidence(path,manifest)
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            r=json.loads(z.read('evidence.json'));assert r['kind']=='saved-image-evidence'
            assert [f['position'] for f in r['frames']]==list(range(251))
            assert len(r['review_history'])==252 and len(r['intervals'])==int(mixed)
            assert r['frames'][0]['review']['revision']==2 and r['frames'][0]['review']['note']=='Revised generated entry'
            assert r['model_suggestions']['status']=='MODEL_SUGGESTIONS_ONLY'
            assert r['model_suggestions']['execution_verification']=='IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED'
            assert len(r['model_suggestions']['prediction_runs'][0]['predictions'])==251
            assert set(z.namelist())=={'index.html','evidence.json',*[f'images/frame_{p:06d}.png' for p in range(251)]}
            for f in r['frames']:
                assert hashlib.sha256(z.read(f['image'])).hexdigest()==manifest['frames'][f['position']]['display_sha256']
                assert f['source_sha256']==manifest['frames'][f['position']]['source_sha256']
        assert not list(app.state.store.root.glob('.saved-image-evidence-*'))
    assert verify_full_span_evidence(download(client,base+'/full-span-export',tmp_path/'full.zip'),manifest)['exported_images']==253


@pytest.mark.parametrize('fault',['missing','changed','count','bytes','metadata','verify'])
def test_failure_rejects_and_cleans_partial(client,app,study,headers,monkeypatch,fault):
    import capsule_review.full_span_evidence as mod
    base='/api/studies/'+study['id']
    assert client.put(base+'/frames/0/review',headers=headers,json={'revision':0,'bookmarked':True,'note':'Generated'}).status_code==200
    if fault=='missing':(app.state.store.images/study['id']/'0.png').unlink()
    elif fault=='changed':(app.state.store.images/study['id']/'0.png').write_bytes(b'changed')
    elif fault=='count':monkeypatch.setattr(mod,'MAX_FULL_IMAGES',0)
    elif fault=='bytes':monkeypatch.setattr(mod,'MAX_TOTAL_IMAGE_BYTES',1)
    elif fault=='metadata':monkeypatch.setattr(mod,'MAX_MANIFEST_BYTES',1)
    elif fault=='verify':
        def reject(*a,**kw):raise ValueError('Generated verification failure')
        monkeypatch.setattr(mod,'verify_saved_evidence',reject)
    r=client.get(base+'/saved-evidence-export');assert r.status_code==422
    assert not r.headers.get('content-type','').startswith('application/zip')
    assert not list(app.state.store.root.glob('.saved-image-evidence-*'))
    assert client.get(base+'/frames/0').json()['review']['note']=='Generated'


def test_small_saved_requires_entry_and_does_not_expand_context(client,headers,study,tmp_path):
    base='/api/studies/'+study['id'];assert client.get(base+'/saved-evidence-export').status_code==422
    client.post(base+'/intervals',headers=headers,json={'start_position':0,'end_position':2})
    assert client.get(base+'/saved-evidence-export').status_code==422
    client.put(base+'/frames/1/review',headers=headers,json={'revision':0,'bookmarked':False,'note':'Only this image'})
    p=download(client,base+'/saved-evidence-export?position=0&full_spans=true',tmp_path/'small.zip')
    with zipfile.ZipFile(p) as z:assert [f['position'] for f in json.loads(z.read('evidence.json'))['frames']]==[1]


def test_restricted_mode_has_no_saved_route(tmp_path):
    from capsule_review.app import create_app
    from fastapi.testclient import TestClient
    app=create_app(tmp_path,restricted_generated=True)
    with TestClient(app,base_url='http://127.0.0.1:8765') as c:
        sid=c.get('/api/restricted/state').json()['commitment']['study_id']
        assert c.get('/api/studies/'+sid+'/saved-evidence-export').status_code==403


@pytest.mark.parametrize('tamper', ['identity', 'revision', 'extra', 'missing'])
def test_saved_verifier_rejects_tampering(client, study, headers, tmp_path, tamper):
    base = '/api/studies/' + study['id']
    assert client.put(base+'/frames/0/review', headers=headers,
                      json={'revision':0, 'bookmarked':True, 'note':'Generated'}).status_code == 200
    source = download(client, base+'/saved-evidence-export', tmp_path/'original.zip')
    with zipfile.ZipFile(source) as z:
        members = {n: z.read(n) for n in z.namelist()}
    record = json.loads(members['evidence.json'])
    if tamper == 'identity': record['frames'][0]['source_sha256'] = '0'*64
    elif tamper == 'revision': record['frames'][0]['review']['revision'] += 1
    elif tamper == 'extra': members['images/extra.png'] = b'not permitted'
    else: del members['images/frame_000000.png']
    members['evidence.json'] = json.dumps(record).encode()
    target = tmp_path/'tampered.zip'
    with zipfile.ZipFile(target, 'w') as z:
        for name, data in members.items(): z.writestr(name, data)
    with pytest.raises((ValueError, KeyError)):
        verify_saved_evidence(target, client.get(base+'/manifest').json())
