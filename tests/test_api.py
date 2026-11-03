import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from capsule_review.app import create_app


def route(study, suffix=''):
    return '/api/studies/' + study['id'] + suffix


def test_home(client):
    r = client.get('/')
    assert r.status_code == 200
    assert 'No model is connected.' in r.text
    assert 'unsafe-inline' not in r.headers['content-security-policy']
    assert r.headers['x-frame-options'] == 'DENY'


def test_mutation_needs_token(client):
    assert client.post('/api/demo').status_code == 403


def test_cross_origin_rejected(client, headers):
    r = client.post('/api/demo', headers={**headers, 'Origin': 'https://evil.example'})
    assert r.status_code == 403


def test_bad_host_rejected(client):
    assert client.get('/api/config', headers={'Host': 'evil.example'}).status_code == 400


def test_no_cors_access(client):
    r = client.get('/api/config', headers={'Origin': 'https://elsewhere.example'})
    assert r.status_code == 403
    assert 'access-control-allow-origin' not in r.headers


def test_upload(client, headers, image_bytes):
    r = client.post('/api/studies/import', headers=headers, data={'title': 'Upload'}, files=[
        ('files', ('frame_10.png', image_bytes, 'image/png')),
        ('files', ('frame_2.png', image_bytes, 'image/png')),
    ])
    assert r.status_code == 201, r.text
    frames = client.get(route(r.json(), '/frames')).json()
    assert [f['source_index'] for f in frames] == [2, 10]
    assert not r.json()['synthetic']


def test_bad_upload_atomic(client, headers, image_bytes):
    r = client.post('/api/studies/import', headers=headers, data={'title':'Bad'}, files=[
        ('files', ('valid.png', image_bytes, 'image/png')),
        ('files', ('bad.png', b'no', 'image/png')),
    ])
    assert r.status_code == 422
    assert client.get('/api/studies').json() == []


def test_oversized_request_rejected(client, headers):
    r = client.post('/api/demo', headers={**headers, 'Content-Length': str(600 * 1024 * 1024)})
    assert r.status_code == 413


def test_pagination(client, study):
    r = client.get(route(study, '/frames?offset=1&limit=1'))
    assert r.status_code == 200
    assert [x['position'] for x in r.json()] == [1]
    assert client.get(route(study, '/frames?limit=201')).status_code == 422
    assert client.get(route(study, '/frames?offset=-1')).status_code == 422


def test_missing_frame_and_study(client, study):
    assert client.get(route(study, '/frames/99')).status_code == 404
    assert client.get('/api/studies/missing').status_code == 404
    assert client.get(route(study, '/frames/-1/image')).status_code == 404


def test_images_and_thumbnails(client, study):
    assert client.get(route(study, '/frames/0/image')).headers['content-type'] == 'image/png'
    assert client.get(route(study, '/frames/0/image?thumbnail=true')).headers['content-type'] == 'image/jpeg'


def test_review_saved_and_reopened(client, headers, study, app):
    data = {'revision': 0, 'bookmarked': True, 'note':'Revisit this interval.', 'label':'Research note'}
    r = client.put(route(study, '/frames/1/review'), headers=headers, json=data)
    assert r.status_code == 200
    assert r.json()['revision'] == 1
    reopened = create_app(app.state.store.root)
    with TestClient(reopened, base_url='http://127.0.0.1:8765') as other:
        f = other.get(route(study, '/frames/1')).json()
        assert f['review']['note'] == data['note']
        assert f['review']['bookmarked']
        assert f['predictions'] == []


def test_conflict_does_not_overwrite(client, headers, study):
    path = route(study, '/frames/0/review')
    one = {'revision':0, 'bookmarked':True, 'note':'First reviewer', 'label':''}
    assert client.put(path, headers=headers, json=one).status_code == 200
    two = {**one, 'note':'Stale tab'}
    assert client.put(path, headers=headers, json=two).status_code == 409
    assert client.get(route(study, '/frames/0')).json()['review']['note'] == 'First reviewer'


def test_unknown_review_fields_rejected(client, headers, study):
    r = client.put(route(study, '/frames/0/review'), headers=headers, json={
        'revision':0, 'bookmarked':True, 'diagnosis':'Invented'})
    assert r.status_code == 422


def test_save_then_clear(client, headers, study):
    path = route(study, '/frames/0/review')
    first = client.put(path, headers=headers, json={'revision':0,'bookmarked':True,'note':'Note'}).json()
    assert len(client.get(route(study, '/saved')).json()) == 1
    assert client.put(path, headers=headers, json={'revision':first['revision'],'bookmarked':False}).status_code == 200
    assert client.get(route(study, '/saved')).json() == []


def test_position_persists(client, headers, study):
    assert client.put(route(study, '/position'), headers=headers, json={'position':2}).status_code == 200
    assert client.get(route(study)).json()['last_position'] == 2
    assert client.put(route(study, '/position'), headers=headers, json={'position':3}).status_code == 422


def test_export_empty_rejected(client, study):
    assert client.get(route(study, '/export')).status_code == 422


def test_export_real_review_not_model_claim(client, headers, study):
    note = '<script>alert("x")</script> & personal note'
    client.put(route(study, '/frames/0/review'), headers=headers,
               json={'revision':0,'bookmarked':True,'note':note,'label':'<b>Not HTML</b>'})
    response = client.get(route(study, '/export'))
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {'review.html','review.json','images/frame_000000.png'}
        doc = archive.read('review.html').decode()
        manifest = json.loads(archive.read('review.json'))
        assert '<script>' not in doc
        assert '&lt;script&gt;' in doc
        assert 'not a complete examination or a diagnosis' in doc
        assert manifest['frames'][0]['review']['note'] == note
        assert manifest['review_history'][0]['revision'] == 1
        assert len(manifest['frames']) == 1
        assert manifest['frames'][0]['source_index'] == 2


def test_notes_without_bookmark_are_exported(client, headers, study):
    client.put(route(study, '/frames/0/review'), headers=headers,
               json={'revision':0,'bookmarked':False,'note':'Saved without star'})
    assert client.get(route(study, '/export')).status_code == 200


def prediction_payload(client, study):
    identity = client.get(route(study, '/manifest')).json()['frames'][0]['source_sha256']
    return {'schema_version':1, 'study_id':study['id'],
            'model':{'name':'Integration fixture, not a trained model','version':'test','run_id':'fixture'},
            'predictions':[{'position':0,'image_sha256':identity,'label':'fixture label','score':0.7}]}


def test_predictions_separate_from_reference_and_review(client, headers, study):
    payload = prediction_payload(client, study)
    r = client.post(route(study, '/predictions'), headers=headers, json=payload)
    assert r.status_code == 201, r.text
    frame = client.get(route(study, '/frames/0')).json()
    assert frame['predictions'][0]['score'] == 0.7
    assert frame['reference_labels'] == {}
    assert frame['review']['revision'] == 0
    assert client.get(route(study, '/export')).status_code == 422


def test_wrong_prediction_identity_is_rejected(client, headers, study):
    payload = prediction_payload(client, study)
    payload['predictions'][0]['image_sha256'] = 'f' * 64
    assert client.post(route(study, '/predictions'), headers=headers, json=payload).status_code == 422
    assert client.get(route(study)).json()['runs'] == []


def test_prediction_duplicate_rejected(client, headers, study):
    payload = prediction_payload(client, study)
    payload['predictions'].append(payload['predictions'][0])
    assert client.post(route(study, '/predictions'), headers=headers, json=payload).status_code == 422
    assert client.get(route(study)).json()['runs'] == []


def test_run_duplicate_does_not_duplicate_data(client, headers, study):
    payload = prediction_payload(client, study)
    assert client.post(route(study, '/predictions'), headers=headers, json=payload).status_code == 201
    assert client.post(route(study, '/predictions'), headers=headers, json=payload).status_code == 409
    assert len(client.get(route(study, '/frames/0')).json()['predictions']) == 1


@pytest.mark.parametrize('score', [-0.1, 1.01])
def test_prediction_score_bounds(client, headers, study, score):
    payload = prediction_payload(client, study)
    payload['predictions'][0]['score'] = score
    assert client.post(route(study, '/predictions'), headers=headers, json=payload).status_code == 422


def test_manifest_has_identity_without_absolute_paths(client, study):
    data = client.get(route(study, '/manifest')).json()
    assert data['study_id'] == study['id']
    assert len(data['manifest_sha256']) == 64
    assert len(data['frames']) == 3
    assert '/mnt/' not in json.dumps(data)


def test_malformed_host_and_origin_are_rejected(client, headers):
    assert client.get('/api/config', headers={'Host':'['}).status_code == 400
    assert client.post('/api/demo', headers={**headers, 'Origin':'http://['}).status_code == 403


def test_nonfinite_score_is_rejected_without_server_error(client, headers, study):
    payload = prediction_payload(client, study)
    encoded = json.dumps(payload).replace('0.7', 'NaN')
    response = client.post(route(study, '/predictions'), headers={**headers, 'Content-Type':'application/json'}, content=encoded)
    assert response.status_code == 422
    assert client.get(route(study)).json()['runs'] == []
