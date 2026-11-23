"""Real native close events and generated drafts; no medical data or JS/Python API.

Runs Qt locally or Cocoa/WKWebView on macOS. Only user dialog choices and explicit
failure injection are automated. The real HTTP save, revision check, close event,
backend shutdown and reopened database are exercised.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--discard', action='store_true')
    args = parser.parse_args()
    import webview
    from capsule_review.desktop import Backend, run_window
    from capsule_review.store import Store
    errors, checks = [], []
    watchdog = threading.Timer(100, lambda: os._exit(124))
    watchdog.daemon = True; watchdog.start()
    original = webview.create_window
    with tempfile.TemporaryDirectory(prefix='capsule-close-generated-') as root:
        workspace = Path(root)/'workspace'
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
                raise AssertionError('Native condition timed out: '+expression)
            def native_request():
                if platform.system() == 'Darwin':
                    from webview.platforms import cocoa
                    cocoa.AppHelper.callAfter(cocoa.BrowserView.instances[window.uid].window.performClose_, None)
                else:
                    window.destroy()  # Qt closeEvent; cancelled by production handler.
            def close_request():
                native_request()
                wait("document.getElementById('draftCloseDialog').open")
            def cancel():
                window.run_js("document.getElementById('draftCloseCancel').click()")
                wait("!document.getElementById('draftCloseDialog').open")
                time.sleep(.3)  # Let the native poll consume cancellation before next request.
            def passed(message):
                checks.append(message); print('PASS', message, flush=True)
            def drive():
                if started.is_set(): return
                started.set()
                try:
                    if platform.system() == 'Darwin': assert window.gui.renderer == 'wkwebview'
                    wait("document.getElementById('version').textContent.startsWith('v')")
                    window.run_js("document.getElementById('demoBtn').click()")
                    wait("state.frame !== null && !state.busy && !state.switching")
                    if not args.discard:
                        window.run_js('window.originalClose=window.capsuleDesktopClose; window.capsuleDesktopClose=undefined')
                        native_request()
                        wait("!document.getElementById('notice').hidden && document.getElementById('notice').textContent.includes('Close confirmation is unavailable')")
                        window.run_js('window.capsuleDesktopClose=window.originalClose')
                        time.sleep(.3)
                        passed('missing close handshake fails closed with visible error')
                    if args.discard:
                        window.run_js("document.getElementById('reviewNote').value='Saved original'; document.getElementById('reviewNote').dispatchEvent(new Event('input')); document.getElementById('saveBtn').click()")
                        wait("state.frame.review.revision === 1 && !state.saving")
                    window.run_js("document.getElementById('reviewNote').value='Unsaved generated draft'; document.getElementById('reviewNote').dispatchEvent(new Event('input'))")
                    close_request(); cancel()
                    assert js("state.dirty && document.getElementById('reviewNote').value === 'Unsaved generated draft'")
                    passed('native Cancel keeps window and exact unsaved draft')
                    if args.discard:
                        # Real independent write advances the backend revision only.
                        window.run_js("api(base()+'/frames/0/review',{method:'PUT',body:JSON.stringify({revision:1,bookmarked:false,note:'Concurrent saved entry',label:''})}).then(()=>window.conflictReady=true)")
                        wait('window.conflictReady === true')
                        close_request(); window.run_js("document.getElementById('draftCloseSave').click()")
                        wait("document.getElementById('draftCloseStatus').textContent.startsWith('Save was not confirmed')")
                        assert js("state.dirty && state.frame.review.revision === 1 && document.getElementById('notice').textContent.includes('another tab')")
                        passed('real HTTP revision conflict keeps draft and native window open')
                        cancel(); close_request()
                        window.run_js("document.getElementById('draftCloseDiscard').click()")
                    else:
                        # Server failure then an abort-aware stalled transport; neither is success.
                        for failure in ('server', 'timeout'):
                            if failure == 'server':
                                body = "Promise.resolve(new Response(JSON.stringify({detail:'Generated save failure'}),{status:500,headers:{'Content-Type':'application/json'}}))"
                            else:
                                body = "new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Generated timeout','AbortError'))))"
                            window.run_js("window.originalFetch=window.fetch; window.fetch=(url,options={})=>options.method==='PUT'&&String(url).endsWith('/review')?"+body+":window.originalFetch(url,options)")
                            close_request(); window.run_js("document.getElementById('draftCloseSave').click()")
                            wait("document.getElementById('draftCloseStatus').textContent.startsWith('Save was not confirmed')")
                            assert js("state.dirty && state.frame.review.revision === 0 && document.getElementById('reviewNote').value === 'Unsaved generated draft'")
                            window.run_js('window.fetch=window.originalFetch')
                            passed('native failed save remains open: '+failure)
                            cancel()
                        close_request(); window.run_js("document.getElementById('draftCloseSave').click()")
                    # Production controller performs final consume and native teardown.
                except BaseException as exc:
                    errors.append(repr(exc)); window.confirm_close = False; window.destroy()
            window.events.loaded += drive
            return window
        webview.create_window = create
        try:
            run_window(workspace)
        finally:
            webview.create_window = original
        if errors: raise AssertionError(errors)
        with Store(workspace).connect() as db:
            row = dict(db.execute('SELECT * FROM reviews WHERE position=0').fetchone())
            count = db.execute('SELECT COUNT(*) FROM review_events').fetchone()[0]
        assert row['note'] == ('Concurrent saved entry' if args.discard else 'Unsaved generated draft')
        assert row['revision'] == (2 if args.discard else 1)
        assert count == row['revision']
        with Backend(workspace): pass  # Native shutdown released lock; saved state survives restart.
        checks.append('discard preserves prior revision' if args.discard else 'save-and-close persists exact new revision')
        checks.append('backend stopped and workspace reopened without lock or orphan')
    watchdog.cancel()
    print(json.dumps({'platform':platform.platform(),'discard':args.discard,'checks':checks,'errors':errors},indent=2),flush=True)


if __name__ == '__main__': main()
