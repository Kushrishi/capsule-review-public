"""Native close never treats missing, stale or timed-out replies as permission."""
import threading
import time
from types import SimpleNamespace

import pytest
from capsule_review.desktop_close import DraftClose


class Window:
    confirm_close = True
    uid = 'generated-window'
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []
        self.destroyed = threading.Event()
        self.gui = SimpleNamespace(evaluate_js=self.evaluate)
    def evaluate(self, script, uid, parse):
        self.calls.append(script)
        value = next(self.answers)
        if isinstance(value, Exception): raise value
        if callable(value): return value()
        return value
    def destroy(self): self.destroyed.set()


def finish(controller):
    deadline = time.monotonic() + 2
    while controller.active and time.monotonic() < deadline: time.sleep(.005)
    assert not controller.active


@pytest.mark.parametrize('answer', [None, False, 'cancel', 'unrecognised', RuntimeError('fixture')])
def test_rejected_reply_keeps_window_open(answer):
    w = Window([answer, 'cancel'])
    close = DraftClose(w, 'http://127.0.0.1:8765/desktop-session?ticket=secret')
    assert close.request() is False
    finish(close)
    assert not w.destroyed.is_set() and w.confirm_close
    assert all('secret' not in call for call in w.calls)
    assert 'location.origin === "http://127.0.0.1:8765"' in w.calls[0]


@pytest.mark.parametrize('answers,closed', [(['close','close'],True), (['pending','close','close'],True), (['close','cancel'],False)])
def test_close_requires_final_consumption(answers, closed):
    w = Window(answers); close = DraftClose(w, 'http://127.0.0.1:123/')
    assert close.request() is False
    finish(close)
    assert w.destroyed.is_set() is closed


def test_pending_choice_expires_without_teardown():
    w = Window(['pending','cancel']); close = DraftClose(w, 'http://127.0.0.1:123/', timeout=0)
    close.request(); finish(close)
    assert not w.destroyed.is_set()
    assert '"abort"' in w.calls[-1]


def test_hung_toolkit_is_bounded_and_not_repeated():
    release = threading.Event()
    w = Window([lambda: release.wait(3)])
    close = DraftClose(w, 'http://127.0.0.1:123/', reply_timeout=.02)
    close.request(); finish(close)
    assert close.stalled and not w.destroyed.is_set()
    for _ in range(10): assert close.request() is False
    assert len(w.calls) == 1
    release.set()


def test_explicit_forced_shutdown_skips_negotiation():
    w = Window([]); w.confirm_close = False
    assert DraftClose(w, 'http://127.0.0.1:123/').request() is None
    assert not w.calls
