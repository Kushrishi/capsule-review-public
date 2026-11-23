"""Synthetic HTTP/process tests; these do not claim native-window coverage."""
import io
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from capsule_review.app import create_app
from capsule_review.desktop import Backend, DesktopSession, create_shortcut, default_data_dir
from capsule_review.store import Store
from detection_fixture import fixture

pytest.importorskip('filelock')
pytest.importorskip('platformdirs')


def test_session_protects_every_resource_and_retains_csrf(tmp_path):
    app = DesktopSession(create_app(tmp_path), '127.0.0.1:8765', 'one-use-ticket')
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        for path in ['/', '/static/app.js', '/api/config', '/api/studies', '/openapi.json']:
            assert client.get(path).status_code == 403
        assert client.post('/api/demo').status_code == 403
        assert client.get('/desktop-session?ticket=wrong').status_code == 403
        assert client.get('/desktop-session?ticket=one-use-ticket', headers={'Origin': 'http://evil.invalid'}).status_code == 403
        r = client.get('/desktop-session?ticket=one-use-ticket', follow_redirects=False)
        assert r.status_code == 303 and r.headers['location'] == '/'
        assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
        assert r.headers['referrer-policy'] == 'no-referrer'
        assert client.get('/desktop-session?ticket=one-use-ticket').status_code == 403
        assert client.get('/').status_code == 200
        assert client.get('/api/config', headers={'Host': '127.0.0.1:8888'}).status_code == 403
        assert client.get('/api/config', headers={'Origin': 'null'}).status_code == 403
        assert client.post('/api/demo').status_code == 403
        token = client.get('/api/config').json()['token']
        assert client.post('/api/demo', headers={'X-Review-Token': token}).status_code == 201


@contextmanager
def authenticated(backend):
    with httpx.Client(base_url=backend.url.split('/desktop-session')[0], follow_redirects=True, timeout=10, trust_env=False) as client:
        assert client.get(backend.url).status_code == 200
        yield client


def wait_offline(origin):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        try:
            httpx.get(origin + '/api/config', timeout=.2, trust_env=False)
        except httpx.TransportError:
            return
        time.sleep(.1)
    pytest.fail('Backend still accepts connections after shutdown')


def test_real_backend_persistence_and_shutdown(tmp_path):
    root = tmp_path / 'persistent'
    with Backend(root) as backend, authenticated(backend) as client:
        origin = str(client.base_url).rstrip('/')
        assert urlsplit(origin).hostname == '127.0.0.1'
        assert httpx.get(origin + '/api/config', trust_env=False).status_code == 403
        token = client.get('/api/config').json()['token']
        headers = {'X-Review-Token': token}
        demo = client.post('/api/demo', headers=headers).json()
        assert demo['synthetic'] and demo['frame_count'] == 24
        buf = io.BytesIO()
        Image.new('RGB', (32, 24), 'teal').save(buf, format='PNG')
        result = client.post('/api/studies/import', headers=headers,
                             data={'title': 'Generated import'}, files={'files': ('frame_1.png', buf.getvalue(), 'image/png')})
        assert result.status_code == 201
        imported = result.json()['id']
        study_id = demo['id']
        base = f'/api/studies/{study_id}'
        image = client.get(base + '/frames/0/image').content
        assert client.put(base + '/frames/0/review', headers=headers,
                          json={'revision': 0, 'bookmarked': True, 'note': 'Synthetic persisted note', 'label': ''}).status_code == 200
        assert client.post(base + '/detections', headers=headers, json=fixture(Store(root), study_id)).status_code == 201
        assert client.post('/api/studies/import', headers=headers, data={'title': 'Invalid'},
                           files={'files': ('bad.png', b'not an image', 'image/png')}).status_code == 422
        old_cookies = dict(client.cookies)
    wait_offline(origin)
    backend.stop()  # idempotent
    with Backend(root) as backend, authenticated(backend) as client:
        base = f'/api/studies/{study_id}'
        assert len(client.get('/api/studies').json()) == 2
        assert client.get(f'/api/studies/{imported}/frames/0/image').status_code == 200
        assert client.get(base + '/frames/0/image').content == image
        assert client.get(base + '/frames/0').json()['review']['note'] == 'Synthetic persisted note'
        assert len(client.get(base + '/detections').json()['runs']) == 1
        assert client.get(base + '/export').status_code == 200
        origin = str(client.base_url).rstrip('/')
        assert httpx.get(origin + '/api/config', cookies=old_cookies, trust_env=False).status_code == 403


def test_duplicate_window_and_bad_workspace_fail_cleanly(tmp_path):
    with Backend(tmp_path / 'store'):
        other = Backend(tmp_path / 'store')
        with pytest.raises(RuntimeError, match='already open'):
            other.start()
        assert not other.process.is_alive()
    bad = tmp_path / 'file'
    bad.write_text('not a directory')
    backend = Backend(bad)
    with pytest.raises(RuntimeError, match='could not start'):
        backend.start()
    assert not backend.process.is_alive()
    timeout = Backend(tmp_path / 'late', timeout=0)
    with pytest.raises(RuntimeError, match='timeout'):
        timeout.start()
    assert not timeout.process.is_alive()


def test_backend_kill_preserves_committed_work_and_releases_lock(tmp_path):
    backend = Backend(tmp_path).start()
    with authenticated(backend) as client:
        headers = {'X-Review-Token': client.get('/api/config').json()['token']}
        study = client.post('/api/demo', headers=headers).json()['id']
    backend.process.kill()
    backend.process.join(5)
    backend.stop()
    with Backend(tmp_path) as reopened, authenticated(reopened) as client:
        assert client.get(f'/api/studies/{study}').status_code == 200
        with Store(tmp_path).connect() as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_parent_death_stops_orphan_backend(tmp_path):
    script = tmp_path / 'parent.py'
    script.write_text('''from capsule_review.desktop import Backend
import time
if __name__ == '__main__':
    b = Backend(__import__('sys').argv[1]).start()
    print(b.url.split('/desktop-session')[0], flush=True)
    time.sleep(60)
''')
    process = subprocess.Popen([sys.executable, str(script), str(tmp_path / 'workspace')], stdout=subprocess.PIPE, text=True)
    try:
        origin = process.stdout.readline().strip()
        assert origin.startswith('http://127.0.0.1:')
        assert httpx.get(origin + '/api/config', trust_env=False).status_code == 403
        process.kill()
        process.wait(5)
        wait_offline(origin)
        with Backend(tmp_path / 'workspace'):
            pass
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(5)
        process.stdout.close()


def test_platform_paths_and_shortcut(tmp_path):
    assert default_data_dir().is_absolute()
    shortcut = create_shortcut(tmp_path / 'workspace with spaces', destination=tmp_path / 'Desktop')
    assert str(sys.executable) in shortcut.read_text() or sys.platform == 'win32'
    assert '--data-dir' in shortcut.read_text()
    assert 'workspace with spaces' in shortcut.read_text()
    with pytest.raises(RuntimeError, match='already exists'):
        create_shortcut(destination=tmp_path / 'Desktop')


def test_shortcut_keeps_virtual_environment_python(tmp_path, monkeypatch):
    # Resolving this symlink would silently launch the system interpreter.
    if sys.platform == 'win32':
        pytest.skip('POSIX virtualenv interpreter symlink')
    interpreter = tmp_path / 'venv' / 'bin' / 'python'
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    monkeypatch.setattr(sys, 'executable', str(interpreter))
    shortcut = create_shortcut(destination=tmp_path / 'Desktop')
    assert str(interpreter) in shortcut.read_text()


def test_window_initialization_error_stops_backend(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from capsule_review import desktop
    class Event:
        def __iadd__(self, callback):
            return self
    fake_window = SimpleNamespace(events=SimpleNamespace(closed=Event(), closing=Event()))
    def unavailable(*args, **kwargs):
        raise RuntimeError('Native GUI unavailable')
    fake = SimpleNamespace(settings={}, create_window=lambda *a, **kw: fake_window, start=unavailable)
    monkeypatch.setitem(sys.modules, 'webview', fake)
    monkeypatch.setattr(desktop, 'configure_qt_downloads', lambda: None)
    with pytest.raises(RuntimeError, match='Native GUI unavailable'):
        desktop.run_window(tmp_path)
    with Backend(tmp_path):
        pass  # No orphan or workspace lock left behind.


def test_main_reports_startup_error_without_terminal(monkeypatch):
    from capsule_review import desktop
    monkeypatch.setattr(sys, 'argv', ['capsule-review-desktop'])
    monkeypatch.setattr(desktop, 'run_window', lambda root: (_ for _ in ()).throw(RuntimeError('Workspace already open')))
    messages = []
    monkeypatch.setattr(desktop, 'show_error', messages.append)
    assert desktop.main() == 1
    assert messages == ['Workspace already open']
