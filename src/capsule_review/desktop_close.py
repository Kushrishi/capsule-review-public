"""Fail-closed native close negotiation, without exposing Python to JavaScript."""
import json
import secrets
import threading
import time
from urllib.parse import urlsplit


class DraftClose:
    def __init__(self, window, url, *, timeout=120, reply_timeout=2):
        self.window = window
        parts = urlsplit(url)
        self.origin = f'{parts.scheme}://{parts.netloc}'
        self.timeout, self.reply_timeout = timeout, reply_timeout
        self.lock = threading.Lock()
        self.active = self.stalled = False
        self.closed = threading.Event()

    def request(self):
        # Signals, backend failure and test teardown explicitly bypass negotiation.
        if not self.window.confirm_close:
            return
        with self.lock:
            if not self.active and not self.stalled:
                self.active = True
                threading.Thread(target=self._negotiate, daemon=True).start()
        return False  # Never block the GUI event loop or destroy the backend here.

    def _query(self, command, nonce):
        result, done = [], threading.Event()
        script = (
            'JSON.stringify(location.origin === ' + json.dumps(self.origin) +
            " && location.pathname === '/' && typeof window.capsuleDesktopClose === 'function'"
            ' ? window.capsuleDesktopClose(' + json.dumps(command) + ',' + json.dumps(nonce) + ') : null)'
        )
        if command == 'abort':
            script = ('(() => { const answer = ' + script + '; '
                      'if (!answer && location.origin === ' + json.dumps(self.origin) +
                      " && location.pathname === '/') { const notice = document.getElementById('notice'); "
                      "if (notice) { notice.textContent = 'Close confirmation is unavailable. The window remains open; preserve your draft before restarting.'; notice.hidden = false; }} return answer; })()")
        def evaluate():
            try:
                result.append(self.window.gui.evaluate_js(script, self.window.uid, True))
            except Exception:
                result.append(None)
            finally:
                done.set()
        threading.Thread(target=evaluate, daemon=True).start()
        if not done.wait(self.reply_timeout):
            # At most one stuck toolkit call: repeated close attempts cannot grow threads.
            self.stalled = True
            raise TimeoutError('Native close confirmation did not respond; window remains open.')
        return result[0]

    def _negotiate(self):
        nonce = secrets.token_hex(16)
        try:
            deadline = time.monotonic() + self.timeout
            answer = self._query('request', nonce)
            while answer == 'pending' and not self.closed.wait(.1):
                if time.monotonic() >= deadline:
                    self._query('abort', nonce)
                    return
                answer = self._query('poll', nonce)
            if self.closed.is_set():
                return
            if answer == 'close' and self._query('consume', nonce) == 'close':
                self.window.confirm_close = False
                self.window.destroy()
            elif answer != 'cancel':
                self._query('abort', nonce)
        except Exception:
            # Toolkit failures are never interpreted as permission to discard a draft.
            if not self.stalled:
                try:
                    self._query('abort', nonce)
                except Exception:
                    pass
        finally:
            with self.lock:
                self.active = False
