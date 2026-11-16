from copy import deepcopy
from hashlib import sha256
import io

import pytest
from PIL import Image
from pydantic import ValidationError

from capsule_review.detections import DetectionImport, unletterbox_xyxy, detection_frames
from capsule_review.importer import import_sources
from detection_fixture import fixture


@pytest.fixture
def prepared(app, client, headers):
    study = client.post('/api/demo', headers=headers).json()
    return study['id'], fixture(app.state.store, study['id'])


def test_complete_import_filter_and_note_preservation(app, client, headers, prepared):
    study, payload = prepared
    base = f'/api/studies/{study}'
    before = client.get(base+'/frames/0').json()
    saved = client.put(base+'/frames/0/review', headers=headers,
                       json={'revision': 0, 'note': 'Human note', 'label': 'Human description', 'bookmarked': True}).json()
    assert client.post(base+'/detections', json=payload, headers=headers).status_code == 201
    after = client.get(base+'/frames/0').json()
    assert after['review'] == saved
    assert after['predictions'] == before['predictions']
    assert after['source_sha256'] == before['source_sha256']
    runs = client.get(base+'/detections').json()
    assert len(runs['classes']) == 12
    assert len(runs['runs']) == 1
    filtered = client.get(base+'/detections/generated-boxes?category=0').json()['frames']
    assert [f['position'] for f in filtered] == [2]
    empty = client.get(base+'/detections/generated-boxes?position=1').json()['frames'][0]
    assert empty['boxes'] == [] and len(empty['category_scores']) == 12
    assert client.post(base+'/detections', json=payload, headers=headers).status_code == 422
    assert client.post(base+'/detections', json=payload).status_code == 403


@pytest.mark.parametrize('fault', ['manifest', 'source', 'display', 'dimensions', 'missing', 'duplicate', 'reorder', 'extra', 'checkpoint', 'out_of_bounds', 'inverted', 'nan', 'category', 'score'])
def test_invalid_run_is_atomic(app, client, headers, prepared, fault):
    study, payload = prepared
    box = payload['frames'][0]['boxes'][0]
    if fault == 'manifest': payload['manifest_sha256'] = 'f'*64
    elif fault == 'source': payload['frames'][1]['source_sha256'] = 'f'*64
    elif fault == 'display': payload['frames'][1]['display_sha256'] = 'f'*64
    elif fault == 'dimensions': payload['frames'][0]['width'] += 1
    elif fault == 'missing': payload['frames'].pop()
    elif fault == 'duplicate': payload['frames'][1] = deepcopy(payload['frames'][0])
    elif fault == 'reorder': payload['frames'].reverse()
    elif fault == 'extra': box['human_confirmed'] = True
    elif fault == 'checkpoint': payload['provenance']['profile'] = 'seeai-v5-source-reviewed-v1'
    elif fault == 'out_of_bounds': box['xyxy'][2] = 100000.
    elif fault == 'inverted': box['xyxy'][2] = 0.
    elif fault == 'nan': box['xyxy'][0] = 'NaN'
    elif fault == 'category': box['category'] = 12
    elif fault == 'score': box['score'] = .99
    response = client.post(f'/api/studies/{study}/detections', headers=headers, json=payload)
    assert response.status_code == 422, response.text
    assert client.get(f'/api/studies/{study}/detections').json()['runs'] == []


def test_changed_display_rejected(app, client, headers, prepared):
    study, payload = prepared
    path = app.state.store.images / study / '0.png'
    path.write_bytes(b'changed')
    assert client.post(f'/api/studies/{study}/detections', headers=headers, json=payload).status_code == 422


def test_synthetic_fixture_cannot_label_research_study(app, client, headers, image_bytes):
    study = import_sources(app.state.store, [('frame_000001.PNG', image_bytes)], title='Research', synthetic=False)
    response = client.post(f"/api/studies/{study['id']}/detections", headers=headers,
                           json=fixture(app.state.store, study['id']))
    assert response.status_code == 422


@pytest.mark.parametrize('size,tensor,box,expected', [
    ((512,512),(576,576),[57.6,115.2,460.8,518.4],[51.2,102.4,409.6,460.8]),
    ((640,480),(576,448),[57.6,51.2,288.,224.],[64.,48.,320.,240.]),
    ((480,640),(448,576),[51.2,57.6,224.,288.],[48.,64.,240.,320.]),
    ((640,480),(576,448),[-10.,0.,700.,600.],[0.,0.,640.,480.]),
])
def test_coordinate_inverse(size,tensor,box,expected):
    assert unletterbox_xyxy(box,size,tensor) == pytest.approx(expected)


def test_exif_import_coordinates_are_display_oriented(app, client, headers):
    image = Image.new('RGB', (80,40), 'blue'); exif = image.getexif(); exif[274] = 6
    buffer = io.BytesIO(); image.save(buffer, 'JPEG', exif=exif)
    study = import_sources(app.state.store, [('rotated.jpg',buffer.getvalue())], title='Rotation', synthetic=True)
    payload = fixture(app.state.store,study['id'])
    frame = payload['frames'][0]
    assert (frame['width'],frame['height']) == (40,80)
    assert frame['source_sha256'] == sha256(buffer.getvalue()).hexdigest()
    assert client.post(f"/api/studies/{study['id']}/detections", headers=headers,json=payload).status_code == 201


def test_nonfinite_coordinates_fail(prepared):
    _, payload = prepared
    payload['frames'][0]['boxes'][0]['xyxy'][0] = float('nan')
    with pytest.raises(ValidationError): DetectionImport.model_validate(payload)


def test_large_recording_navigation_decodes_only_requested_page(app, client, headers, prepared, monkeypatch):
    """50,000 stored rows, sparse hits: keyset/limit must precede JSON decoding."""
    import json
    from contextlib import contextmanager
    study, payload = prepared
    base = f'/api/studies/{study}/detections'
    assert client.post(base, headers=headers, json=payload).status_code == 201
    store = app.state.store
    with store.connect() as db:
        run = db.execute('SELECT id FROM detection_runs WHERE study_id=?', (study,)).fetchone()[0]
        db.execute('DELETE FROM detection_frames WHERE run_id=?', (run,))
        template = payload['frames'][0]
        records = []
        for position in range(50000):
            frame = {**template, 'position': position,
                     'boxes': template['boxes'] if position in (48000,49000) else []}
            records.append((run, position, json.dumps(frame)))
        db.executemany('INSERT INTO detection_frames VALUES(?,?,?)', records)
        db.executemany('INSERT INTO detection_category_frames VALUES(?,?,?)',
                       [(run,c,p) for p in (48000,49000) for c in (-1,7)])
    decoded = []
    original_loads = json.loads
    def counted(raw, *args, **kwargs):
        decoded.append(raw)
        return original_loads(raw, *args, **kwargs)
    original_connect = store.connect
    @contextmanager
    def bounded_query():
        with original_connect() as db:
            # A full recording scan exceeds this budget; indexed lookup does not.
            calls = [0]
            def progress():
                calls[0] += 1
                return int(calls[0] > 100)
            db.set_progress_handler(progress, 100)
            yield db
    with monkeypatch.context() as patch:
        patch.setattr(json, 'loads', counted)
        patch.setattr(store, 'connect', bounded_query)
        result = detection_frames(store, study, 'generated-boxes', category=7, after=48000, limit=1)
        assert [f['position'] for f in result] == [49000]
        assert len(decoded) == 1
        decoded.clear()
        assert detection_frames(store, study, 'generated-boxes', category=0, after=0, limit=1) == []
        assert decoded == []
    response = client.get(base+'/generated-boxes?category=7&after=48000&limit=1').json()
    assert [f['position'] for f in response['frames']] == [49000]
    assert client.get(base+'/generated-boxes?limit=201').status_code == 422


def test_existing_runs_receive_one_time_navigation_index(app, client, headers, prepared):
    from capsule_review.store import Store
    study, payload = prepared
    assert client.post(f'/api/studies/{study}/detections', headers=headers,json=payload).status_code == 201
    with app.state.store.connect() as db:
        db.execute('DELETE FROM detection_category_frames')
        db.execute('DELETE FROM detection_indexed_runs')
    reopened = Store(app.state.store.root)
    assert [r['position'] for r in detection_frames(reopened,study,'generated-boxes',category=0)] == [2]
    assert [r['position'] for r in detection_frames(reopened,study,'generated-boxes',after=0,limit=1)] == [2]
    with reopened.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM detection_indexed_runs').fetchone()[0] == 1
        original = db.execute('SELECT record FROM detection_frames ORDER BY position').fetchall()
    twice = Store(app.state.store.root)
    with twice.connect() as db:
        assert db.execute('SELECT record FROM detection_frames ORDER BY position').fetchall() == original


def test_provenance_remains_an_unverified_producer_claim(client, headers, prepared):
    study, payload = prepared
    base = f'/api/studies/{study}/detections'
    assert client.post(base,headers=headers,json=payload).status_code == 201
    run = client.get(base).json()['runs'][0]
    assert run['execution_verification'] == 'IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED'
    assert run['provenance'] == payload['provenance']
