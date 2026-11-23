"""Genuine native key input on generated data, not dispatched DOM KeyboardEvents."""
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
import time


def main():
    import webview
    from capsule_review.desktop import run_window
    errors, checks = [], []
    original = webview.create_window
    watchdog = threading.Timer(90, lambda: os._exit(124))
    watchdog.daemon = True; watchdog.start()
    def create(*a, **kw):
        window = original(*a, **kw)
        started = threading.Event()
        def js(expression):
            return window.gui.evaluate_js('JSON.stringify('+expression+')', window.uid, True)
        def wait(expression):
            deadline = time.monotonic()+15
            while time.monotonic()<deadline:
                if js(expression): return
                time.sleep(.05)
            raise AssertionError('Native key condition timed out: '+expression)
        def focus(identifier):
            window.run_js("document.getElementById('"+identifier+"').focus()")
            wait("document.activeElement.id === '"+identifier+"'")
        def drive():
            if started.is_set(): return
            started.set()
            try:
                if platform.system() == 'Darwin':
                    assert window.gui.renderer == 'wkwebview'
                    from webview.platforms import cocoa
                    def key(name, command=False):
                        done = threading.Event()
                        failures = []
                        def send():
                            try:
                                native = cocoa.BrowserView.instances[window.uid].window
                                native.makeKeyAndOrderFront_(None)
                                chars, code = {'Space':(' ',49),'Enter':('\r',36),'ArrowRight':('\uf703',124),'b':('b',11),'s':('s',1)}[name]
                                flags = cocoa.AppKit.NSEventModifierFlagCommand if command else 0
                                for kind in (cocoa.AppKit.NSEventTypeKeyDown, cocoa.AppKit.NSEventTypeKeyUp):
                                    event = cocoa.AppKit.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(kind,(0,0),flags,time.monotonic(),native.windowNumber(),None,chars,chars,False,code)
                                    native.sendEvent_(event)
                            except BaseException as exc: failures.append(repr(exc))
                            finally: done.set()
                        cocoa.AppHelper.callAfter(send)
                        assert done.wait(5) and not failures, failures
                else:
                    from qtpy.QtCore import QObject, Signal, Slot, Qt
                    from qtpy.QtTest import QTest
                    from qtpy.QtWidgets import QApplication
                    from webview.platforms import qt
                    class Driver(QObject):
                        requested = Signal(str, bool)
                        def __init__(self):
                            super().__init__(); self.requested.connect(self.send)
                        @Slot(str, bool)
                        def send(self, name, command):
                            view = qt.BrowserView.instances[window.uid].webview
                            target = view.focusProxy() or view
                            QTest.keyClick(target, {'Space':Qt.Key_Space,'Enter':Qt.Key_Return,'ArrowRight':Qt.Key_Right,'b':Qt.Key_B,'s':Qt.Key_S}[name], Qt.ControlModifier if command else Qt.NoModifier)
                    driver = Driver(); driver.moveToThread(QApplication.instance().thread())
                    def key(name, command=False): driver.requested.emit(name,command)
                wait("document.getElementById('version').textContent.startsWith('v')")
                window.run_js("document.getElementById('demoBtn').click()")
                wait('state.frame !== null && !state.busy && !state.switching')
                window.run_js("window.observedKeys=[]; document.addEventListener('keydown',e=>observedKeys.push({key:e.key,trusted:e.isTrusted,target:e.target.id}),true)")
                focus('helpBtn'); key('Space')
                wait("document.getElementById('helpDialog').open")
                assert js('state.playing') is False
                assert js('state.frame.position') == 0
                focus('helpDialog'); key('ArrowRight')
                assert js('state.frame.position') == 0
                # Focused close button retains native Enter activation in the modal.
                window.run_js("document.querySelector('[aria-label=\"Close help\"]').focus()")
                key('Enter'); wait("!document.getElementById('helpDialog').open")
                focus('nextBtn'); key('Enter'); wait('state.frame.position === 1 && !state.busy')
                window.run_js("document.getElementById('reviewNote').value='Native keyboard draft'; document.getElementById('reviewNote').dispatchEvent(new Event('input'))")
                focus('reviewNote'); key('ArrowRight')
                assert js('state.frame.position') == 1
                key('s',True); wait("!state.dirty && !state.saving && document.getElementById('saveStatus').textContent === 'Saved'")
                focus('imageStage'); key('ArrowRight'); wait('state.frame.position === 2 && !state.busy')
                key('b'); wait("document.getElementById('bookmark').checked && !state.saving")
                focus('imageStage'); key('Space'); wait('state.playing && !state.busy')
                key('Space'); wait('!state.playing')
                observations = js('window.observedKeys')
                assert observations and all(item['trusted'] for item in observations), observations
                checks.append('trusted native keys preserve Help/modal/Enter, editing, save and viewer actions')
                window.run_js("document.querySelector('a.research-link').focus()")
                key('Space'); time.sleep(.2)
                assert js('state.playing') is False
                key('Enter'); wait("location.pathname === '/static/locked-results.html'")
                window.run_js('history.back()')
                wait("location.pathname === '/' && typeof state !== 'undefined' && state.frame !== null && !state.busy")
                checks.append('focused link keeps native Space and Enter navigation without playback')
            except BaseException as exc:
                errors.append(repr(exc))
            finally:
                window.confirm_close = False; window.destroy()
        window.events.loaded += drive
        return window
    with tempfile.TemporaryDirectory(prefix='capsule-key-generated-') as root:
        webview.create_window = create
        try: run_window(Path(root)/'workspace')
        finally: webview.create_window = original
    watchdog.cancel()
    print(json.dumps({'platform':platform.platform(),'checks':checks,'errors':errors},indent=2),flush=True)
    if errors: raise AssertionError(errors)


if __name__ == '__main__': main()
