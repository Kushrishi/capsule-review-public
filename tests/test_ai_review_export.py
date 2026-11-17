"""Generated-study suggestions remain separate from human review through both exports."""
import io
import json
import zipfile
from hashlib import sha256

from detection_fixture import fixture


def prepared(client, headers, app):
    study = client.post('/api/demo', headers=headers).json()
    base = '/api/studies/' + study['id']
    assert client.put(base + '/frames/0/review', headers=headers,
                      json={'revision': 0, 'bookmarked': True, 'note': 'Generated human note', 'label': 'Reviewer entry'}).status_code == 200
    payload = fixture(app.state.store, study['id'])
    assert client.post(base + '/detections', headers=headers, json=payload).status_code == 201
    return study, base, payload


def read(response, member):
    assert response.status_code == 200, response.text[:200]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        record = json.loads(archive.read(member))
        for frame in record['frames']:
            assert sha256(archive.read(frame['image'])).hexdigest() == frame['display_sha256']
    return record


def test_review_retains_suggestions_and_provenance_separately(client, headers, app):
    study, base, payload = prepared(client, headers, app)
    before = client.get(base + '/frames/0').json()['review']
    record = read(client.get(base + '/export'), 'review.json')
    suggestions = record['model_suggestions']
    assert suggestions['status'] == 'MODEL_SUGGESTIONS_ONLY'
    assert suggestions['scope'] == 'exported_frames_only'
    assert suggestions['execution_verification'] == 'IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED'
    assert suggestions['detection_runs'][0]['provenance'] == payload['provenance']
    assert suggestions['detection_runs'][0]['frames'] == [payload['frames'][0]]
    assert suggestions['prediction_runs'][0]['model']['name'] == 'Generated ranking example (not AI)'
    assert suggestions['prediction_runs'][0]['predictions'][0]['image_sha256'] == record['frames'][0]['source_sha256']
    assert record['frames'][0]['review'] == {key: before[key] for key in record['frames'][0]['review']}
    assert client.get(base + '/frames/2').json()['review']['revision'] == 0
    assert client.get(base + '/frames/23/image').status_code == 200


def test_full_span_retains_suggestions_for_only_exported_frames(client, headers, app):
    study, base, payload = prepared(client, headers, app)
    assert client.post(base + '/intervals', headers=headers,
                       json={'start_position': 0, 'end_position': 3, 'note': 'Generated span'}).status_code == 201
    record = read(client.get(base + '/full-span-export'), 'evidence.json')
    suggestions = record['model_suggestions']
    assert [frame['position'] for frame in suggestions['detection_runs'][0]['frames']] == [0, 1, 2, 3]
    assert len(suggestions['prediction_runs'][0]['predictions']) == 4
    assert record['frames'][2]['review']['revision'] == 0
    assert record['frames'][0]['review']['note'] == 'Generated human note'


def test_standard_export_rejects_changed_display_bytes(client, headers, app):
    study, base, payload = prepared(client, headers, app)
    image = app.state.store.images / study['id'] / '0.png'
    image.write_bytes(image.read_bytes() + b'changed after import')
    response = client.get(base + '/export')
    assert response.status_code == 422
    assert 'SHA-256' in response.json()['detail']


def test_models_alone_never_create_exportable_human_findings(client, headers, app):
    study = client.post('/api/demo', headers=headers).json()
    base = '/api/studies/' + study['id']
    payload = fixture(app.state.store, study['id'])
    assert client.post(base + '/detections', headers=headers, json=payload).status_code == 201
    assert client.get(base + '/export').status_code == 422
    assert client.get(base + '/frames/0').json()['review']['revision'] == 0


def test_omitted_frame_model_records_are_not_leaked_into_export(client, headers, app):
    study, base, payload = prepared(client, headers, app)
    identity = client.get(base + '/frames/23').json()['source_sha256']
    assert client.post(base + '/predictions', headers=headers, json={
        'schema_version': 1, 'study_id': study['id'],
        'model': {'name': 'Unexported generated fixture', 'version': '1', 'run_id': 'unexported-fixture'},
        'predictions': [{'position': 23, 'image_sha256': identity, 'label': 'Generated fixture', 'score': .4}],
    }).status_code == 201
    record = read(client.get(base + '/export'), 'review.json')
    assert [run['run_id'] for run in record['model_suggestions']['prediction_runs']] == ['capsule-review-synthetic-demo-v1']
    run = record['model_suggestions']['detection_runs'][0]
    original = client.get(base + '/detections').json()['runs'][0]
    assert run['payload_sha256'] == original['payload_sha256']
    assert run['payload_digest_scope'] == 'original_complete_imported_run'


def test_suggestion_export_budget_fails_closed(client, headers, app, monkeypatch):
    from capsule_review import suggestion_evidence
    study, base, payload = prepared(client, headers, app)
    monkeypatch.setattr(suggestion_evidence, 'MAX_SUGGESTION_BYTES', 1)
    response = client.get(base + '/export')
    assert response.status_code == 422
    assert 'metadata limit' in response.json()['detail']
