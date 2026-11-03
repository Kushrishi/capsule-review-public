"""Reviewer-selected imported-image spans: real persistence and safe exports.

All images are deliberately synthetic fixtures; no medical data are required.
"""

import io
import json
import zipfile

from fastapi.testclient import TestClient

from capsule_review.app import create_app
from capsule_review.importer import import_sources


def url(study, suffix=''):
    return f"/api/studies/{study['id']}/intervals{suffix}"


def test_create_list_reopen_and_delete_study_scoped(client, headers, study, app, image_bytes):
    assert client.get(url(study)).json() == []
    data = {'start_position': 0, 'end_position': 2, 'note': 'Inspect imported span only.'}
    assert client.post(url(study), json=data).status_code == 403
    first = client.post(url(study), headers=headers, json=data)
    assert first.status_code == 201, first.text
    item = first.json()
    assert item['start_position'] == 0 and item['end_position'] == 2
    assert item['start_source_index'] == 2 and item['end_source_index'] == 15
    assert item['note'] == data['note']
    assert len(client.get(url(study)).json()) == 1
    assert client.post(url(study), headers=headers, json=data).status_code == 409

    reopened = create_app(app.state.store.root)
    with TestClient(reopened, base_url='http://127.0.0.1:8765') as other:
        assert other.get(url(study)).json()[0]['id'] == item['id']

    second_study = import_sources(
        app.state.store, [('frame_1.png', image_bytes), ('frame_2.png', image_bytes)],
        title='Separate synthetic examination', source='Test only',
    )
    assert client.get(url(second_study)).json() == []
    assert client.delete(url(second_study, f"/{item['id']}"), headers=headers).status_code == 404
    assert client.delete(url(study, f"/{item['id']}")).status_code == 403
    deleted = client.delete(url(study, f"/{item['id']}"), headers=headers)
    assert deleted.status_code == 200 and deleted.json()['deleted'] == item['id']
    assert client.get(url(study)).json() == []
    assert client.delete(url(study, f"/{item['id']}"), headers=headers).status_code == 404
    with app.state.store.connect() as db:
        actions = [x[0] for x in db.execute(
            'SELECT action FROM review_interval_events WHERE study_id=? ORDER BY id', (study['id'],))]
    assert actions == ['created', 'deleted']


def test_invalid_ranges_unknown_fields_and_note_boundaries(client, headers, study):
    for data in (
        {'start_position': 0, 'end_position': 0},
        {'start_position': 2, 'end_position': 1},
        {'start_position': 0, 'end_position': 3},
        {'start_position': -1, 'end_position': 1},
        {'start_position': 0, 'end_position': 2, 'note': 'n' * 2001},
        {'start_position': 0, 'end_position': 2, 'diagnosis': 'not permitted'},
    ):
        assert client.post(url(study), headers=headers, json=data).status_code == 422
    assert client.get(url(study)).json() == []
    assert client.get('/api/studies/not-a-study/intervals').status_code == 404


def test_interval_only_export_contains_exact_boundary_images_and_no_model_claim(client, headers, study):
    note = '<script>alert(1)</script> & reviewer note'
    response = client.post(url(study), headers=headers,
                           json={'start_position': 0, 'end_position': 2, 'note': note})
    assert response.status_code == 201
    assert client.get(f"/api/studies/{study['id']}/saved").json() == []
    exported = client.get(f"/api/studies/{study['id']}/export")
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert set(archive.namelist()) == {
            'review.json', 'review.html', 'images/frame_000000.png',
            'images/frame_000002.png'
        }
        manifest = json.loads(archive.read('review.json'))
        html = archive.read('review.html').decode()
        assert [x['position'] for x in manifest['frames']] == [0, 2]
        assert all(x['interval_boundary'] for x in manifest['frames'])
        assert all(x['review']['revision'] == 0 for x in manifest['frames'])
        assert len(manifest['intervals']) == 1
        assert manifest['intervals'][0]['note'] == note
        assert manifest['intervals'][0]['start_source_index'] == 2
        assert manifest['intervals'][0]['end_source_index'] == 15
        assert manifest['interval_history'][0]['action'] == 'created'
        assert 'only start and end image boundaries' in html.lower()
        assert 'Interior images were not automatically reviewed' in html
        assert '&lt;script&gt;' in html and '<script>' not in html
        assert 'not a complete examination or a diagnosis' in html
        assert 'No diagnostic model' in html or 'No diagnostic model' in html.capitalize()


def test_interval_exports_union_with_existing_bookmarks_without_duplication(client, headers, study):
    interval = client.post(url(study), headers=headers,
                           json={'start_position': 0, 'end_position': 2}).json()
    r = client.put(f"/api/studies/{study['id']}/frames/0/review", headers=headers,
                   json={'revision': 0, 'bookmarked': True, 'note': 'Reviewer note'})
    assert r.status_code == 200
    r = client.put(f"/api/studies/{study['id']}/frames/1/review", headers=headers,
                   json={'revision': 0, 'bookmarked': False, 'note': 'Middle note'})
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/studies/{study['id']}/export").content)) as z:
        manifest = json.loads(z.read('review.json'))
        assert [x['position'] for x in manifest['frames']] == [0, 1, 2]
        assert [x['interval_boundary'] for x in manifest['frames']] == [True, False, True]
        assert manifest['frames'][0]['review']['note'] == 'Reviewer note'
        assert manifest['frames'][1]['review']['note'] == 'Middle note'
        assert len(manifest['intervals']) == 1
    assert client.delete(url(study, f"/{interval['id']}"), headers=headers).status_code == 200
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/studies/{study['id']}/export").content)) as z:
        manifest = json.loads(z.read('review.json'))
        assert [x['position'] for x in manifest['frames']] == [0, 1]
        assert manifest['intervals'] == []
        assert [x['action'] for x in manifest['interval_history']] == ['created', 'deleted']


def test_interval_count_limit_and_unchanged_annotations(client, headers, app, image_bytes):
    study = import_sources(app.state.store,
        ((f'frame_{index:06d}.PNG', image_bytes) for index in range(16)),
        title='Synthetic interval limit', source='Software fixtures', synthetic=True)
    for start in range(15):
        for end in range(start + 1, 16):
            payload = {'start_position': start, 'end_position': end}
            response = client.post(url(study), headers=headers, json=payload)
            if len(client.get(url(study)).json()) == 100:
                assert response.status_code == 201
                break
            assert response.status_code == 201
        if len(client.get(url(study)).json()) == 100:
            break
    assert len(client.get(url(study)).json()) == 100
    assert client.post(url(study), headers=headers,
                       json={'start_position': 14, 'end_position': 15}).status_code == 422
    frame = client.get(f"/api/studies/{study['id']}/frames/0").json()
    assert frame['reference_labels'] == {}
    assert frame['predictions'] == []
    assert frame['review']['revision'] == 0
