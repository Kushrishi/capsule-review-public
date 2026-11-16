from copy import deepcopy
from hashlib import sha256
import io

import pytest
from PIL import Image
from pydantic import ValidationError

from capsule_review.detections import DetectionImport, unletterbox_xyxy
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
