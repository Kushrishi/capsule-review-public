"""Optional native window around the unchanged local viewer (no JS/Python bridge)."""

import argparse
import hmac
import multiprocessing as mp
import os
from pathlib import Path
import secrets
import shlex
import signal
import subprocess
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse


class DesktopSession:
    """Protect *all* HTTP resources; exchange a one-use ticket for an HttpOnly cookie."""

    def __init__(self, app, host, ticket):
        self.app, self.host, self.ticket = app, host, ticket
        self.cookie_name = 'cr_desktop_' + secrets.token_hex(12)
        self.session = secrets.token_urlsafe(32)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
                return
            return await self.app(scope, receive, send)
        request = Request(scope)
        # Exact authority rejects DNS rebinding and credentials sent to another port.
        valid_host = request.headers.get('host') == self.host
        origin = request.headers.get('origin')
        valid_origin = origin is None or origin == 'http://' + self.host
        if not valid_host or not valid_origin:
            response = JSONResponse({'detail': 'Desktop origin rejected.'}, 403)
        elif scope['path'] == '/desktop-session':
            supplied = parse_qs(scope.get('query_string', b'').decode('ascii', errors='replace')).get('ticket', [''])[0]
            if (request.method == 'GET' and self.ticket and
                    hmac.compare_digest(supplied.encode(), self.ticket.encode())):
                self.ticket = None
                response = RedirectResponse('/', status_code=303)
                response.set_cookie(self.cookie_name, self.session, httponly=True, samesite='strict', path='/')
            else:
                response = JSONResponse({'detail': 'Desktop session rejected.'}, 403)
        elif hmac.compare_digest(request.cookies.get(self.cookie_name, '').encode(), self.session.encode()):
            return await self.app(scope, receive, send)
        else:
            response = JSONResponse({'detail': 'Desktop session required.'}, 403)
        response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                                 'X-Frame-Options': 'DENY'})
        await response(scope, receive, send)


def default_data_dir():
    from platformdirs import user_data_path
    return user_data_path('Capsule Review', appauthor=False)


def _serve(connection, root, ticket, restricted_generated=False):
    """Spawn target. EOF on the private parent pipe also stops an orphaned backend."""
    import uvicorn
    from filelock import FileLock, Timeout
    from .app import create_app

    from .desktop_import import DesktopImports, register_desktop_imports

    send_lock = threading.Lock()
    def send(message):
        with send_lock:
            connection.send(message)

    server = None
    imports = None
    try:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(root / '.desktop.lock', timeout=0):
            app = create_app(root, restricted_generated=restricted_generated)
            if not restricted_generated:
                imports = DesktopImports(app.state.store)
                imports.notify_picker = lambda request_id: send(('pick', request_id))
                register_desktop_imports(app, imports)
            # Keep the socket reserved through server startup: no free-port race.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
                app = DesktopSession(app, f'127.0.0.1:{port}', ticket)
                server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                    access_log=False, log_level='critical', proxy_headers=False,
                    timeout_graceful_shutdown=3))

                def supervise():
                    while not server.started and not server.should_exit:
                        if connection.poll(0.05):
                            # Parent shutdown or EOF during startup.
                            try:
                                connection.recv()
                            except EOFError:
                                pass
                            server.should_exit = True
                            return
                    if not server.should_exit:
                        try:
                            send(('ready', port))
                            while True:
                                command = connection.recv()
                                if imports and isinstance(command, tuple) and command[0] == 'picked':
                                    imports.selected(*command[1:])
                                    continue
                                if not imports or not isinstance(command, tuple) or command[0] != 'folder':
                                    break
                                try:
                                    value = imports.grant(command[1])
                                    send(('selection', value))
                                except ValueError as exc:
                                    send(('error', str(exc)))
                        except (EOFError, BrokenPipeError, OSError):
                            pass
                    # Arm the watchdog before waiting for cancellation/cleanup.
                    threading.Timer(6, lambda: os._exit(0)).start()
                    if imports:
                        imports.shutdown()
                    server.should_exit = True
                    # Sync import/inference work may ignore graceful cancellation.
                    # SQLite rolls back incomplete transactions on the next open.

                threading.Thread(target=supervise, daemon=True).start()
                try:
                    server.run(sockets=[sock])
                finally:
                    # Do not release the workspace lock while an import can still write.
                    if imports and not imports.shutdown():
                        os._exit(0)
    except Timeout:
        connection.send(('error', 'This workspace is already open in another desktop window.'))
    except Exception:
        # No request bodies, study titles, credentials or filenames in diagnostics.
        try:
            connection.send(('error', 'The local backend could not start. Check the workspace location and permissions.'))
        except (OSError, EOFError):
            pass
    finally:
        if imports:
            imports.shutdown()
        connection.close()


class Backend:
    """Bounded lifecycle usable without importing or initializing a GUI toolkit."""

    def __init__(self, root, timeout=20, *, restricted_generated=False):
        self.restricted_generated = restricted_generated
        self.root, self.timeout = Path(root).expanduser().resolve(), timeout
        self.process = self.connection = None
        self.url = None
        self.ipc_lock = threading.Lock()

    def start(self):
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe()
        ticket = secrets.token_urlsafe(32)
        self.process = context.Process(target=_serve, args=(child, str(self.root), ticket, self.restricted_generated), daemon=True)
        try:
            self.process.start()
            child.close()
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                if self.connection.poll(0.05):
                    try:
                        kind, value = self.connection.recv()
                    except EOFError as exc:
                        raise RuntimeError('The local backend exited during startup.') from exc
                    if kind == 'error':
                        raise RuntimeError(value)
                    self.url = f'http://127.0.0.1:{value}/desktop-session?ticket={ticket}'
                    return self
                if not self.process.is_alive():
                    raise RuntimeError('The local backend exited during startup.')
            raise RuntimeError('The local backend did not become ready within the startup timeout.')
        except BaseException:
            child.close()
            self.stop()
            raise

    def select_folder(self, folder):
        with self.ipc_lock:
            self.connection.send(('folder', str(folder)))
            if not self.connection.poll(5):
                raise RuntimeError('The backend did not confirm the folder selection. Reopen the application.')
            kind, result = self.connection.recv()
            if kind != 'selection':
                raise RuntimeError(result)
            return result

    def picker_result(self, request_id, folder, error=None):
        with self.ipc_lock:
            self.connection.send(('picked', request_id, folder, error))

    def stop(self):
        if self.connection:
            self.connection.close()  # EOF, including when the parent is killed.
            self.connection = None
        if self.process and self.process.pid:
            self.process.join(8)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(2)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


def configure_qt_downloads():
    """pywebview 6.2's Qt handler uses Qt5-only setPath; adapt Qt6 downloads.

    This is confined to the desktop shell, including blob-based review exports.
    Keep the compatibility hook covered by desktop_gui_smoke when upgrading.
    """
    from webview.platforms import qt

    def download_requested(browser, download):
        suggested = (download.downloadFileName() if hasattr(download, 'downloadFileName')
                     else download.suggestedFileName())
        path, _ = qt.QFileDialog.getSaveFileName(browser, browser.localization['global.saveFile'],
                                                suggested, '*.zip')
        if not path:
            download.cancel()
            return
        path = Path(path).absolute()
        if hasattr(download, 'setDownloadDirectory'):
            download.setDownloadDirectory(str(path.parent))
            download.setDownloadFileName(path.name)
        else:
            download.setPath(str(path))
        download.accept()

    qt.BrowserView.on_download_requested = download_requested


class FolderPicker:
    """Native picker service. No Python API is exposed to JavaScript."""
    def __init__(self, backend):
        self._backend = backend
        self._window = None
        self._lock = threading.Lock()

    def _trusted(self):
        current = urlsplit(self._window.get_current_url() or '')
        expected = urlsplit(self._backend.url)
        if (current.scheme, current.netloc, current.path) != (expected.scheme, expected.netloc, '/'):
            raise RuntimeError('Folder selection is available only in the local viewer.')

    def choose_import_folder(self):
        import webview
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('A folder picker is already open.')
        try:
            self._trusted()
            folders = self._window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=False)
            self._trusted()
            if not folders:
                return None
            return str(folders[0])
        finally:
            self._lock.release()


def run_window(root, *, restricted_generated=False):
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError('Install the desktop extra: python -m pip install -e ".[desktop]"') from exc
    webview.settings['ALLOW_DOWNLOADS'] = True
    gui = None
    if sys.platform.startswith('linux'):
        os.environ.setdefault('QT_API', 'pyqt6')
        configure_qt_downloads()
        gui = 'qt'
    with Backend(root, restricted_generated=restricted_generated) as backend:
        picker = FolderPicker(backend)
        window = webview.create_window('Capsule Review — Desktop v0.1', backend.url,
                                      width=1280, height=900, min_size=(800, 600), confirm_close=True)
        picker._window = window
        closed = threading.Event()
        failed = threading.Event()
        window.events.closed += lambda: closed.set()

        def choose_folder(request_id):
            try:
                backend.picker_result(request_id, picker.choose_import_folder())
            except Exception:
                try:
                    backend.picker_result(request_id, None, 'Folder selection failed. Try choosing the folder again.')
                except (OSError, AttributeError):
                    pass

        def watch_backend():
            while not closed.wait(0.25):
                if not backend.process.is_alive():
                    failed.set()
                    window.confirm_close = False
                    window.destroy()
                    return
                if backend.connection and backend.connection.poll():
                    try:
                        kind, value = backend.connection.recv()
                    except (EOFError, OSError):
                        continue
                    if kind == 'pick':
                        threading.Thread(target=choose_folder, args=(value,), daemon=True).start()

        def interrupted(signum, frame):
            window.confirm_close = False
            window.destroy()

        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            # Temporary profile; folder selection uses IPC, with no JS/Python bridge.
            webview.start(watch_backend, gui=gui, private_mode=True, debug=False)
        finally:
            closed.set()
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        if failed.is_set():
            raise RuntimeError('The local backend stopped unexpectedly. Reopen Capsule Review to recover saved work.')


def show_error(message):
    # pythonw/desktop shortcuts have no terminal; retain a visible error dialog.
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror('Capsule Review could not open', message, parent=root)
        root.destroy()
    except Exception:
        if sys.stderr:
            print(message, file=sys.stderr)


def create_shortcut(root=None, destination=None):
    """Create a user launch shortcut, not an installer or packaged binary."""
    from platformdirs import user_desktop_path
    destination = Path(destination) if destination else user_desktop_path()
    destination.mkdir(parents=True, exist_ok=True)
    args = [str(Path(sys.executable).absolute()), '-m', 'capsule_review.desktop']
    if root is not None:
        args += ['--data-dir', str(Path(root).expanduser().resolve())]
    if any(any(c in arg for c in '\n\r\0') for arg in args):
        raise RuntimeError('Shortcut paths cannot contain line breaks or NUL characters.')
    if sys.platform == 'win32':
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        if not pythonw.is_file():
            raise RuntimeError('pythonw.exe is required for a window-only Windows shortcut.')
        args[0] = str(pythonw)
        command = subprocess.list2cmdline(args).replace('"', '""')
        path = destination / 'Capsule Review.vbs'
        content = 'CreateObject("WScript.Shell").Run "' + command + '", 0, False\n'
    elif sys.platform == 'darwin':
        path = destination / 'Capsule Review.command'
        content = '#!/bin/sh\nexec ' + shlex.join(args) + '\n'
    else:
        path = destination / 'Capsule Review.desktop'
        # Desktop Entry Exec has its own quoting rules (not shell syntax).
        def quote(arg):
            for old, new in [('\\', '\\\\'), ('"', '\\"'), ('`', '\\`'), ('$', '\\$')]:
                arg = arg.replace(old, new)
            # Desktop Entry values unescape once before Exec argument parsing.
            return '"' + arg.replace('\\', '\\\\').replace('%', '%%') + '"'
        content = ('[Desktop Entry]\nType=Application\nName=Capsule Review\n'
                   'Terminal=false\nExec=' + ' '.join(map(quote, args)) + '\n')
    if path.exists():
        raise RuntimeError('A Capsule Review shortcut already exists. Remove it before recreating it.')
    path.write_text(content, encoding='utf-8')
    path.chmod(0o700)
    return path


def main():
    mp.freeze_support()
    parser = argparse.ArgumentParser(description='Open the optional Capsule Review desktop window.')
    parser.add_argument('--data-dir', type=Path, default=None,
                        help='Existing or new workspace; default: OS application-data directory')
    parser.add_argument('--create-shortcut', action='store_true', help='Create a launch shortcut on your Desktop, then exit')
    parser.add_argument('--restricted-generated', action='store_true',
                        help='Opt-in K=2 generated-only pixel restriction prototype; temporary workspace')
    args = parser.parse_args()
    if args.restricted_generated and (args.data_dir or args.create_shortcut):
        parser.error('Generated restriction uses a fresh temporary workspace; no existing workspace or shortcut.')
    try:
        if args.create_shortcut:
            create_shortcut(args.data_dir)
            return 0
        if args.restricted_generated:
            import tempfile
            with tempfile.TemporaryDirectory(prefix='capsule-restricted-generated-') as root:
                run_window(root, restricted_generated=True)
        else:
            run_window(args.data_dir or default_data_dir())
    except Exception as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else 'The desktop window could not open. Check the native webview dependencies.'
        show_error(message)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
