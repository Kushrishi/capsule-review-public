"""Desktop-only import jobs. Paths arrive exclusively over the launcher's private IPC."""

import errno
from pathlib import Path
import secrets
import threading
import time

from fastapi import HTTPException
from pydantic import Field

from .importer import ImportCancelled, import_folder, recover_interrupted_imports
from .models import ImportMeta

MAX_DESKTOP_FILES = 100_000


class FolderImportRequest(ImportMeta):
    selection: str = Field(min_length=32, max_length=128)


class DesktopImports:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.cancelled = threading.Event()
        self.thread = None
        self.selection = None
        self.picker = {'picker_state': 'idle'}
        self.notify_picker = None
        self.closing = False
        self.status = {'state': 'idle', 'phase': 'idle', 'completed': 0, 'total': None,
                       'cancel_allowed': False, 'recovered_imports': recover_interrupted_imports(store)}

    def snapshot(self):
        with self.lock:
            result = dict(self.status) | self.picker
            if 'started_at' in result:
                end = result.get('finished_at', time.monotonic())
                result['elapsed_seconds'] = round(end - result['started_at'], 2)
            result.pop('started_at', None)
            result.pop('finished_at', None)
            return result

    def request_picker(self):
        with self.lock:
            if self.closing or self.status['state'] in {'running', 'cancelling'} or self.picker['picker_state'] == 'pending':
                raise ValueError('Wait for the current import or folder selection to finish.')
            request_id = secrets.token_urlsafe(24)
            self.selection = None
            self.picker = {'picker_state': 'pending', 'request_id': request_id}
        try:
            self.notify_picker(request_id)
        except (OSError, TypeError):
            with self.lock:
                self.picker = {'picker_state': 'failed', 'picker_error': 'The native window is unavailable. Reopen the application.'}
        return self.snapshot()

    def selected(self, request_id, folder, error=None):
        with self.lock:
            if self.picker.get('request_id') != request_id or self.closing:
                return
            if error:
                self.picker = {'picker_state': 'failed', 'picker_error': error}
            elif folder is None:
                self.picker = {'picker_state': 'cancelled'}
            else:
                token = secrets.token_urlsafe(32)
                self.selection = (token, Path(folder))
                self.picker = {'picker_state': 'selected', 'selection': token, 'folder_name': Path(folder).name}

    def grant(self, folder):
        """IPC-only. The HTTP schema has no filesystem path field."""
        with self.lock:
            if self.closing or self.status['state'] in {'running', 'cancelling'}:
                raise ValueError('Wait for the current import to finish or cancel it first.')
            token = secrets.token_urlsafe(32)
            self.selection = (token, Path(folder))
            return {'selection': token, 'folder_name': Path(folder).name}

    def start(self, request):
        with self.lock:
            if self.closing or self.status['state'] in {'running', 'cancelling'}:
                raise ValueError('An import is already running or the application is closing.')
            if not self.selection or not secrets.compare_digest(request.selection, self.selection[0]):
                raise ValueError('Choose a folder in the desktop window before importing.')
            folder = self.selection[1]
            self.selection = None  # Each native selection grants one import only.
            self.picker = {'picker_state': 'idle'}
            self.cancelled.clear()
            self.status = {'state': 'running', 'phase': 'scanning', 'completed': 0, 'total': None,
                           'ignored_files': 0, 'source_bytes': 0, 'output_bytes': 0,
                           'cancel_allowed': True, 'started_at': time.monotonic()}
            self.thread = threading.Thread(target=self._run, args=(folder, request), daemon=True)
            self.thread.start()
        return self.snapshot()

    def _progress(self, update):
        with self.lock:
            if self.cancelled.is_set():
                raise ImportCancelled('Import cancelled. No examination was added.')
            self.status.update(update)
            if update['phase'] == 'committing':
                self.status['cancel_allowed'] = False

    def _run(self, folder, request):
        try:
            study = import_folder(self.store, folder, title=request.title, source=request.source,
                                  progress=self._progress, cancelled=self.cancelled.is_set,
                                  max_files=MAX_DESKTOP_FILES)
            result = {'state': 'completed', 'phase': 'completed', 'study_id': study['id']}
        except ImportCancelled as exc:
            result = {'state': 'cancelled', 'phase': 'cancelled', 'error': str(exc)}
        except OSError as exc:
            if exc.errno in {errno.ENOSPC, getattr(errno, 'EDQUOT', -1)}:
                message = 'Not enough workspace disk space. Free space and choose the folder again.'
            elif isinstance(exc, PermissionError):
                message = 'A source image or workspace file could not be read or written. Check permissions and retry.'
            else:
                message = 'A source image or workspace operation failed. Check that the folder is available and retry.'
            if isinstance(exc, PermissionError) and exc.filename:
                message += f' File: {Path(exc.filename).name}.'
            result = {'state': 'failed', 'phase': 'failed', 'error': message}
        except ValueError as exc:
            result = {'state': 'failed', 'phase': 'failed', 'error': str(exc)}
        except Exception:
            result = {'state': 'failed', 'phase': 'failed',
                      'error': 'Import stopped unexpectedly. Reopen the workspace before retrying.'}
        with self.lock:
            self.status.update(result, cancel_allowed=False, finished_at=time.monotonic())

    def cancel(self):
        with self.lock:
            if self.status.get('cancel_allowed'):
                self.cancelled.set()
                self.status['state'] = 'cancelling'
            return self.status['state']

    def shutdown(self):
        with self.lock:
            self.closing = True
            self.selection = None
        self.cancel()
        if self.thread:
            self.thread.join(4)
        return self.thread is None or not self.thread.is_alive()


def register_desktop_imports(app, jobs):
    """Called only by the authenticated desktop backend, never by create_app()."""
    app.state.desktop_folder_import = True

    @app.post('/api/desktop-import/choose', status_code=202)
    def choose_folder():
        try:
            return jobs.request_picker()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/desktop-import')
    def import_status():
        return jobs.snapshot()

    @app.post('/api/desktop-import', status_code=202)
    def start_import(request: FolderImportRequest):
        try:
            return jobs.start(request)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/desktop-import/cancel', status_code=202)
    def cancel_import():
        jobs.cancel()
        return jobs.snapshot()
