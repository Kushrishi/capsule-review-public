"""Generated images only; real folder reads, HTTP boundaries and crash recovery."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from capsule_review.app import create_app
from capsule_review.desktop import Backend, FolderPicker
from capsule_review.desktop_import import DesktopImports, FolderImportRequest
from capsule_review.importer import ImportCancelled, import_folder, import_sources, recover_interrupted_imports
from capsule_review.store import Store
from test_desktop import authenticated


def folder(tmp_path, image_bytes, count=5):
    root = tmp_path / 'generated-source'
    root.mkdir(exist_ok=True)
    for n in reversed(range(count)):
        (root / f'frame_{n}.png').write_bytes(image_bytes)
    return root


def wait_job(jobs):
    jobs.thread.join(30)
    assert not jobs.thread.is_alive()
    return jobs.snapshot()


def test_large_sequence_manifest_persistence_and_paged_navigation(tmp_path, image_bytes):
    path = folder(tmp_path, image_bytes, 2048)
    (path / 'readme.txt').write_text('Generated test data')
    (path / 'subfolder').mkdir()
    store = Store(tmp_path / 'workspace')
    updates = []
    def progress(item):
        # No partially populated examination is ever exposed to the viewer.
        with store.connect() as db:
            assert db.execute('SELECT count(*) FROM studies').fetchone()[0] == 0
        if item['phase'] in {'importing', 'committing'}:
            updates.append((item['phase'], item['completed']))
    result = import_folder(store, path, title='Generated large sequence', source='Synthetic software test', progress=progress)
    assert result['frame_count'] == 2048
    assert updates[-1] == ('committing', 2048)
    assert [value for phase, value in updates if phase == 'importing'] == list(range(2049))
    identity = [{'position': n, 'source_index': n, 'filename': f'frame_{n}.png',
                 'sha256': hashlib.sha256(image_bytes).hexdigest()} for n in range(2048)]
    assert result['manifest_sha256'] == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    shutil.rmtree(path)
    with TestClient(create_app(store.root), base_url='http://127.0.0.1:8765') as client:
        base = f'/api/studies/{result["id"]}'
        assert len(client.get(base + '/frames?offset=2036&limit=12').json()) == 12
        last = client.get(base + '/frames/2047').json()
        assert last['filename'] == 'frame_2047.png' and last['source_index'] == 2047
        raw = client.get(base + '/frames/2047/image').content
        assert Image.open(io.BytesIO(raw)).size == (64, 48)
        headers = {'X-Review-Token': client.get('/api/config').json()['token']}
        assert client.put(base + '/frames/2047/review', headers=headers,
                          json={'revision': 0, 'bookmarked': True, 'note': 'Generated last-frame review'}).status_code == 200
    assert Store(store.root).frame(result['id'], 2047)['review']['bookmarked']
    assert not list(store.root.glob('.import-*'))
    assert not list(store.images.rglob('.import*'))


def test_cancellation_rolls_back_and_retry_preserves_identity(tmp_path, image_bytes):
    path = folder(tmp_path, image_bytes, 20)
    store = Store(tmp_path / 'workspace')
    cancel = threading.Event()
    def progress(update):
        if update.get('completed') == 7:
            cancel.set()
    with pytest.raises(ImportCancelled):
        import_folder(store, path, title='Cancelled', source='Generated', progress=progress, cancelled=cancel.is_set)
    assert list(store.images.iterdir()) == []
    assert not list(store.root.glob('.import-*'))
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM frames').fetchone()[0] == 0
    assert import_folder(store, path, title='Retry', source='Generated')['frame_count'] == 20


@pytest.mark.parametrize('fault', ['decode', 'disk', 'unreadable', 'duplicate-name', 'duplicate-index', 'changed', 'symlink'])
def test_failures_leave_no_partial_study(tmp_path, image_bytes, monkeypatch, fault):
    import capsule_review.importer as importer
    path = folder(tmp_path, image_bytes)
    store = Store(tmp_path / 'workspace')
    progress = None
    if fault == 'decode':
        (path / 'frame_4.png').write_bytes(b'not an image')
    elif fault == 'disk':
        monkeypatch.setattr(importer.shutil, 'disk_usage', lambda p: SimpleNamespace(free=1))
    elif fault == 'unreadable':
        monkeypatch.setattr(importer, '_read_folder_image', lambda *a: (_ for _ in ()).throw(PermissionError('unreadable')))
    elif fault == 'duplicate-name':
        # Case-insensitive volumes cannot contain case-only filename pairs.
        # Exercise the shared source guard without assuming filesystem behavior.
        pass
    elif fault == 'duplicate-index':
        (path / 'image-00000.png').write_bytes(image_bytes)
    elif fault == 'changed':
        def progress(update):
            if update['phase'] == 'importing' and update['completed'] == 0:
                (path / 'frame_4.png').write_bytes(image_bytes + b'changed')
    else:
        (path / 'frame_9.png').symlink_to(path / 'frame_0.png')
    with pytest.raises((ValueError, OSError)) as caught:
        if fault == 'duplicate-name':
            import_sources(store, [('frame_0.png', image_bytes), ('FRAME_0.PNG', image_bytes)],
                           title='Must not appear', source='Generated')
        else:
            import_folder(store, path, title='Must not appear', source='Generated', progress=progress)
    if fault == 'decode':
        assert 'frame_4.png' in str(caught.value)
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM studies').fetchone()[0] == 0
    assert list(store.images.iterdir()) == []
    assert not list(store.root.glob('.import-*'))


def test_size_and_count_limits_are_explicit(tmp_path, image_bytes, monkeypatch):
    import capsule_review.importer as importer
    path = folder(tmp_path, image_bytes)
    store = Store(tmp_path / 'workspace')
    with pytest.raises(ValueError, match='at most 3'):
        import_folder(store, path, title='Count', source='Generated', max_files=3)
    monkeypatch.setattr(importer, 'MAX_FILE_BYTES', 1)
    with pytest.raises(ValueError, match='too large'):
        import_folder(store, path, title='Size', source='Generated')


def test_desktop_grants_replay_and_browser_boundary(tmp_path, image_bytes):
    path = folder(tmp_path, image_bytes)
    app = create_app(tmp_path / 'browser')
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        headers = {'X-Review-Token': client.get('/api/config').json()['token']}
        assert client.get('/api/desktop-import').status_code == 404
        assert client.post('/api/desktop-import', headers=headers, json={'path': str(path)}).status_code == 404
    with Backend(tmp_path / 'desktop') as backend, authenticated(backend) as client:
        origin = str(client.base_url)
        assert httpx.get(origin + '/api/desktop-import', trust_env=False).status_code == 403
        assert client.post('/api/desktop-import', json={}).status_code == 403
        headers = {'X-Review-Token': client.get('/api/config').json()['token']}
        payload = {'title': 'Native folder grant', 'source': 'Generated', 'selection': 'x' * 43}
        assert client.post('/api/desktop-import', headers=headers, json=payload).status_code == 409
        selected = backend.select_folder(path)
        assert 'path' not in selected
        payload['selection'] = selected['selection']
        assert client.post('/api/desktop-import', headers=headers, json=payload | {'path': str(path)}).status_code == 422
        assert client.post('/api/desktop-import', headers=headers, json=payload).status_code == 202
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = client.get('/api/desktop-import').json()
            if status['state'] not in {'running', 'cancelling'}:
                break
            time.sleep(.05)
        assert status['state'] == 'completed', status
        assert client.get('/api/studies').json()[0]['frame_count'] == 5
        assert client.post('/api/desktop-import', headers=headers, json=payload).status_code == 409


def test_native_picker_has_no_path_argument_and_rejects_other_origins(monkeypatch):
    backend = SimpleNamespace(url='http://127.0.0.1:8123/desktop-session?ticket=secret', select_folder=lambda p: {'selection': 'native-grant', 'folder_name': Path(p).name})
    selected = []
    window = SimpleNamespace(get_current_url=lambda: 'http://127.0.0.1:8123/', create_file_dialog=lambda *a, **k: selected.append(True) or ('/native/picked',))
    picker = FolderPicker(backend)
    picker._window = window
    monkeypatch.setitem(__import__('sys').modules, 'webview', SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=1)))
    assert picker.choose_import_folder() == '/native/picked'
    with pytest.raises(TypeError):
        picker.choose_import_folder('/arbitrary/path')
    for url in ['http://evil.invalid/', 'http://127.0.0.1:8124/', 'file:///tmp/page.html']:
        window.get_current_url = lambda: url
        with pytest.raises(RuntimeError, match='only in the local viewer'):
            picker.choose_import_folder()
    assert len(selected) == 1


def test_cancel_cannot_report_success_after_publication_starts(tmp_path, image_bytes, monkeypatch):
    import capsule_review.desktop_import as module
    jobs = DesktopImports(Store(tmp_path / 'workspace'))
    path = folder(tmp_path, image_bytes)
    gate = threading.Event()
    release = threading.Event()
    original = jobs._progress
    def progress(update):
        original(update)
        if update['phase'] == 'committing':
            gate.set()
            assert release.wait(10)
    monkeypatch.setattr(jobs, '_progress', progress)
    grant = jobs.grant(path)
    jobs.start(FolderImportRequest(title='Atomic commit', selection=grant['selection']))
    assert gate.wait(10)
    assert jobs.snapshot()['cancel_allowed'] is False
    assert jobs.cancel() == 'running'
    release.set()
    assert wait_job(jobs)['state'] == 'completed'


def test_recovery_preserves_committed_images_and_ignores_unmarked_paths(tmp_path, image_bytes):
    store = Store(tmp_path / 'workspace')
    study = import_sources(store, [('frame_0.png', image_bytes)], title='Committed')
    dest = store.images / study['id']
    (dest / '.import-pending').write_text(study['id'])
    (dest / '.import.sqlite3').write_bytes(b'interrupted post-commit cleanup')
    orphan_id = 'a' * 32
    orphan = store.images / orphan_id
    orphan.mkdir()
    (orphan / '.import-pending').write_text(orphan_id)
    stage_id = 'b' * 32
    stage = store.root / ('.import-' + stage_id)
    stage.mkdir()
    (stage / '.import-pending').write_text(stage_id)
    legacy = store.root / '.import-unmarked'
    legacy.mkdir()
    assert recover_interrupted_imports(store) == 2
    assert (dest / '0.png').exists() and not (dest / '.import.sqlite3').exists()
    assert legacy.exists() and store.study(study['id'])
    assert recover_interrupted_imports(store) == 0


@pytest.mark.parametrize('ending', ['kill', 'shutdown'])
def test_interrupted_job_recovery_and_source_preservation(tmp_path, image_bytes, ending):
    path = folder(tmp_path, image_bytes, 5000)
    workspace = tmp_path / 'workspace'
    old = import_sources(Store(workspace), [('frame_0.png', image_bytes)], title='Previously completed')
    backend = Backend(workspace).start()
    try:
        with authenticated(backend) as client:
            headers = {'X-Review-Token': client.get('/api/config').json()['token']}
            grant = backend.select_folder(path)
            assert client.post('/api/desktop-import', headers=headers,
                               json={'title': 'Interrupted', 'selection': grant['selection']}).status_code == 202
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                status = client.get('/api/desktop-import').json()
                if status['phase'] == 'importing' and status['completed'] > 1:
                    break
                time.sleep(.01)
            assert status['phase'] == 'importing' and status['completed'] < 5000
        if ending == 'kill':
            backend.process.kill()
            backend.process.join(5)
        backend.stop()
        with Backend(workspace) as reopened, authenticated(reopened) as client:
            status = client.get('/api/desktop-import').json()
            if ending == 'kill':
                assert status['recovered_imports'] == 1
            studies = client.get('/api/studies').json()
            assert [x['id'] for x in studies] == [old['id']]
            assert not list(workspace.glob('.import-*'))
            assert len(list((workspace / 'images').iterdir())) == 1
        assert len(list(path.iterdir())) == 5000
    finally:
        backend.stop()


def test_failed_final_transaction_leaves_no_orphan_images(tmp_path, image_bytes, monkeypatch):
    from contextlib import contextmanager
    store = Store(tmp_path / 'workspace')
    original = store.connect
    @contextmanager
    def failing():
        with original() as db:
            # A database error during final frame insertion must roll back the study too.
            db.execute("CREATE TEMP TRIGGER fail_frames BEFORE INSERT ON frames BEGIN SELECT RAISE(ABORT, 'synthetic disk fault'); END")
            yield db
    monkeypatch.setattr(store, 'connect', failing)
    with pytest.raises(sqlite3.IntegrityError):
        import_sources(store, [('frame_0.png', image_bytes)], title='Atomic failure')
    with original() as db:
        assert db.execute('SELECT count(*) FROM studies').fetchone()[0] == 0
    assert not list(store.images.iterdir())


def test_picker_protocol_returns_only_native_grants(tmp_path, image_bytes):
    path = folder(tmp_path, image_bytes)
    with Backend(tmp_path / 'workspace') as backend, authenticated(backend) as client:
        assert client.get('/api/config').json()['desktop_folder_import'] is True
        headers = {'X-Review-Token': client.get('/api/config').json()['token']}
        assert client.post('/api/desktop-import/choose').status_code == 403
        assert client.post('/api/desktop-import/choose', headers=headers).json()['picker_state'] == 'pending'
        kind, request_id = backend.connection.recv()
        assert kind == 'pick'
        # A stale picker response must never grant filesystem access.
        backend.picker_result('stale-request', str(path))
        assert client.get('/api/desktop-import').json()['picker_state'] == 'pending'
        assert client.post('/api/desktop-import/choose', headers=headers).status_code == 409
        backend.picker_result(request_id, None)
        deadline = time.monotonic() + 5
        while client.get('/api/desktop-import').json()['picker_state'] != 'cancelled':
            assert time.monotonic() < deadline
            time.sleep(.01)
        client.post('/api/desktop-import/choose', headers=headers)
        _, request_id = backend.connection.recv()
        backend.picker_result(request_id, str(path))
        while True:
            status = client.get('/api/desktop-import').json()
            if status['picker_state'] == 'selected':
                break
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert status['folder_name'] == path.name and 'path' not in status
        assert client.post('/api/desktop-import', headers=headers,
                           json={'title': 'Native HTTP workflow', 'selection': status['selection']}).status_code == 202
        # No new native grant while the current import is using its source folder.
        # The ordinary browser app has neither these routes nor configuration.
    with TestClient(create_app(tmp_path / 'browser'), base_url='http://127.0.0.1:8765') as browser:
        config = browser.get('/api/config').json()
        assert config['desktop_folder_import'] is False
        assert browser.post('/api/desktop-import/choose', headers={'X-Review-Token': config['token']}).status_code == 404


def test_empty_folder_and_job_disk_error_are_visible(tmp_path, image_bytes, monkeypatch):
    import capsule_review.importer as importer
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'notes.txt').write_text('No image frames')
    jobs = DesktopImports(Store(tmp_path / 'workspace'))
    grant = jobs.grant(root)
    jobs.start(FolderImportRequest(title='Empty', selection=grant['selection']))
    status = wait_job(jobs)
    assert status['state'] == 'failed' and 'No supported' in status['error']
    assert status['ignored_files'] == 1
    (root / 'frame_1.png').write_bytes(image_bytes)
    monkeypatch.setattr(importer.shutil, 'disk_usage', lambda p: SimpleNamespace(free=1))
    grant = jobs.grant(root)
    jobs.start(FolderImportRequest(title='Space failure', selection=grant['selection']))
    status = wait_job(jobs)
    assert status['state'] == 'failed' and 'disk space' in status['error']
    assert not list(jobs.store.images.iterdir())
