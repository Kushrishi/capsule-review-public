"""Real Cocoa/WKWebView smoke. Only folder/save/confirmation choices are automated.

No Qt, browser transport replacement, screenshots, real data or model dependencies.
Run separately: AppKit owns the main thread. A timeout fails, rather than skips, CI.
"""
import argparse
import base64
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import tempfile
import threading
import time
import zipfile

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kill-backend', action='store_true')
    options = parser.parse_args()
    if platform.system() != 'Darwin':
        raise SystemExit('This smoke must execute on genuine macOS with Cocoa/WKWebView.')
    import httpx
    import webview
    from webview.platforms import cocoa
    from capsule_review.desktop import run_window
    from capsule_review.store import Store

    watchdog = threading.Timer(150, lambda: (print('FAIL native smoke timed out', flush=True), os._exit(124)))
    watchdog.daemon = True
    watchdog.start()
    checks, errors = [], []
    with tempfile.TemporaryDirectory(prefix='capsule-macos-native-') as temporary:
        root = Path(temporary)
        source = root / 'generated-source'
        source.mkdir()
        data = io.BytesIO()
        Image.new('RGB', (96, 64), '#286a78').save(data, 'PNG')
        for n in reversed(range(64)):
            (source / f'frame_{n}.png').write_bytes(data.getvalue())
        workspace = root / 'workspace'
        downloads = [root / 'native-review.zip', root / 'native-spans.zip', root / 'native-suggestions.zip']
        chosen_saves = []
        original_panel = cocoa.AppKit.NSSavePanel
        original_window = webview.create_window

        class SavePanel:
            def __init__(self):
                self.path = downloads[len(chosen_saves)]
                chosen_saves.append(self.path)
            def setDirectoryURL_(self, value): pass
            def setNameFieldStringValue_(self, value): pass
            def setTitle_(self, value): pass
            def runModal(self): return cocoa.AppKit.NSFileHandlingPanelOKButton
            def filename(self): return str(self.path)

        # Replace only the human destination choice, not WKDownload/network/file IO.
        class Panels:
            @staticmethod
            def savePanel(): return SavePanel()
        cocoa.AppKit.NSSavePanel = Panels

        def create(*args, **kwargs):
            assert kwargs.get('confirm_close') is True
            window = original_window(*args, **kwargs)
            original_dialog = window.create_file_dialog
            def dialog(kind, *a, **kw):
                if kind == webview.FileDialog.FOLDER:
                    return (str(source),)
                return original_dialog(kind, *a, **kw)
            window.create_file_dialog = dialog
            started = threading.Event()

            def js(expression):
                # Native API executes a raw expression; no eval()/CSP relaxation.
                return window.gui.evaluate_js('JSON.stringify(' + expression + ')', window.uid, True)

            def wait(expression):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if js(expression): return
                    time.sleep(.05)
                raise AssertionError('Native DOM condition timed out: ' + expression)

            def download(path, member):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if path.exists() and zipfile.is_zipfile(path):
                        with zipfile.ZipFile(path) as archive:
                            return json.loads(archive.read(member))
                    time.sleep(.05)
                raise AssertionError('Native download did not produce a ZIP: ' + path.name)

            def passed(message):
                checks.append(message)
                print('PASS', message, flush=True)

            def drive():
                if started.is_set(): return
                started.set()
                try:
                    assert window.gui.renderer == 'wkwebview', window.gui.renderer
                    native = {}
                    ready = threading.Event()
                    def inspect_window():
                        try:
                            view = cocoa.BrowserView.instances[window.uid]
                            native['webkit'] = bool(view.webview.isKindOfClass_(cocoa.WebKit.WKWebView))
                            native['visible'] = bool(view.window.isVisible())
                        finally:
                            ready.set()
                    cocoa.AppHelper.callAfter(inspect_window)
                    assert ready.wait(5) and native == {'webkit': True, 'visible': True}, native
                    wait("document.getElementById('version').textContent.startsWith('v') && !document.getElementById('desktopFolderImport').hidden")
                    assert 'desktop-session' not in js('location.href')
                    assert 'cr_desktop_' not in js('document.cookie')
                    origin = js('location.origin')
                    assert httpx.get(origin + '/api/config', trust_env=False).status_code == 403
                    passed('visible NSWindow and genuine WKWebView authenticate to protected loopback backend')
                    window.run_js("document.getElementById('importBtn').click(); document.getElementById('importTitle').value='Generated macOS qualification'; document.getElementById('desktopChooseFolder').click()")
                    wait("!document.getElementById('desktopStartImport').disabled")
                    window.run_js("document.getElementById('desktopStartImport').click()")
                    wait("!document.getElementById('desktopImportOpen').hidden")
                    window.run_js("document.getElementById('desktopImportOpen').click()")
                    wait("document.getElementById('jumpInput').max === '64' && !document.getElementById('jumpInput').disabled")
                    window.run_js("document.getElementById('jumpInput').value='64'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                    wait("document.getElementById('sourceIndex').textContent === 'Source #63' && !document.getElementById('jumpInput').disabled && document.getElementById('frameImage').naturalWidth === 96")
                    assert js("document.querySelectorAll('#filmstrip img').length") == 12
                    passed('native selection IPC imports 64 generated frames and navigates to the last full-resolution frame')
                    window.run_js("document.getElementById('reviewNote').value='Generated macOS note'; document.getElementById('reviewNote').dispatchEvent(new Event('input')); document.getElementById('saveBtn').click()")
                    wait("document.getElementById('saveStatus').textContent === 'Saved' && document.getElementById('savedCount').textContent === '1' && !document.getElementById('jumpInput').disabled")
                    window.run_js("document.getElementById('exportBtn').click()")
                    record = download(downloads[0], 'review.json')
                    assert record['frames'][0]['position'] == 63
                    assert record['frames'][0]['review']['note'] == 'Generated macOS note'
                    passed('WKWebView blob export downloads a genuine saved-review ZIP')
                    window.run_js("document.getElementById('jumpInput').value='1'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                    wait("document.getElementById('jumpInput').value === '1' && !document.getElementById('jumpInput').disabled")
                    window.run_js("document.getElementById('intervalStartBtn').click(); document.getElementById('jumpInput').value='3'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                    wait("!document.getElementById('intervalEndBtn').disabled")
                    window.run_js("document.getElementById('intervalEndBtn').click()")
                    wait("document.getElementById('intervalCount').textContent === '1' && !document.getElementById('fullSpanBtn').disabled")
                    window.run_js("window.confirm=()=>true; document.getElementById('fullSpanBtn').click()")
                    spans = download(downloads[1], 'evidence.json')
                    assert [frame['position'] for frame in spans['frames']] == [0, 1, 2, 63]
                    passed('authenticated native full-span download retains interval interiors and saved frames')
                    # The existing demo imports an explicitly synthetic examination;
                    # normal local-folder studies remain ineligible for generated detections.
                    window.run_js("document.getElementById('demoBtn').click()")
                    wait("document.getElementById('jumpInput').max === '24' && !document.getElementById('jumpInput').disabled")
                    window.run_js("document.getElementById('reviewNote').value='Generated suggestion-review note'; document.getElementById('reviewNote').dispatchEvent(new Event('input')); document.getElementById('saveBtn').click()")
                    wait("document.getElementById('saveStatus').textContent === 'Saved' && document.getElementById('savedCount').textContent === '1' && !document.getElementById('jumpInput').disabled")
                    from detection_fixture import fixture
                    with Store(workspace).connect() as db:
                        demo_id = db.execute('SELECT id FROM studies WHERE synthetic=1').fetchone()[0]
                    suggestions = fixture(Store(workspace), demo_id)
                    encoded = base64.b64encode(json.dumps(suggestions).encode()).decode()
                    window.run_js("{ const file = new File([atob('" + encoded + "')], 'generated-detections.json', {type:'application/json'}); const transfer = new DataTransfer(); transfer.items.add(file); const input = document.getElementById('detectionFile'); input.files = transfer.files; input.dispatchEvent(new Event('change')); }")
                    wait("document.querySelectorAll('#detectionOverlay rect').length === 1 && document.getElementById('detectionStatus').textContent.includes('1 model suggestion')")
                    window.run_js("document.getElementById('detectionCategory').value='0'; document.getElementById('detectionCategory').dispatchEvent(new Event('change'))")
                    wait("document.querySelectorAll('#detectionOverlay rect').length === 0")
                    window.run_js("document.getElementById('nextDetection').click()")
                    wait("document.getElementById('jumpInput').value === '3' && !document.getElementById('jumpInput').disabled && document.getElementById('detectionBoxes').textContent.includes('angiodysplasia')")
                    assert js("document.getElementById('reviewNote').value") == ''
                    assert js("document.getElementById('reviewLabel').value") == ''
                    assert js("document.getElementById('bookmark').checked") is False
                    passed('native category filtering and abnormality navigation never create human findings')
                    window.run_js("document.getElementById('priorityCount').value='6'; document.getElementById('priorityMethod').value='score'; document.getElementById('priorityBuild').click()")
                    wait("document.getElementById('prioritySelected').textContent === '6 selected' && !document.getElementById('priorityBuild').disabled")
                    missing = js("Array.from({length:24}, (_,i)=>i).find(i=>!state.priorityData.items.some(x=>x.position===i) && i!==0)")
                    assert missing is not None
                    window.run_js("document.getElementById('jumpInput').value='" + str(missing + 1) + "'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                    wait("document.getElementById('jumpInput').value === '" + str(missing + 1) + "' && !document.getElementById('jumpInput').disabled")
                    assert js("document.getElementById('frameImage').naturalWidth") == 640
                    window.run_js("document.getElementById('jumpInput').value='1'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                    wait("document.getElementById('reviewNote').value === 'Generated suggestion-review note' && !document.getElementById('jumpInput').disabled")
                    assert js("document.getElementById('savedCount').textContent") == '1'
                    window.run_js("document.getElementById('exportBtn').click()")
                    evidence = download(downloads[2], 'review.json')
                    retained = evidence['model_suggestions']['detection_runs'][0]
                    assert retained['provenance'] == suggestions['provenance']
                    assert retained['frames'] == [suggestions['frames'][0]]
                    assert evidence['frames'][0]['review']['note'] == 'Generated suggestion-review note'
                    passed('native selected/unselected access and export preserve human notes and imported suggestion provenance')

                except BaseException as exc:
                    errors.append(repr(exc))
                finally:
                    if options.kill_backend and not errors:
                        mp.active_children()[0].kill()
                    else:
                        window.confirm_close = False  # Automated teardown, not a human close-dialog test.
                        window.destroy()

            window.events.loaded += drive
            return window

        webview.create_window = create
        try:
            try:
                run_window(workspace)
                assert not options.kill_backend, 'Backend failure was not reported'
            except RuntimeError as exc:
                if not options.kill_backend or 'stopped unexpectedly' not in str(exc): raise
                print('PASS native backend failure closes its window and reports the error', flush=True)
        finally:
            webview.create_window = original_window
            cocoa.AppKit.NSSavePanel = original_panel
        if errors:
            raise AssertionError('; '.join(errors))
        assert len(checks) == 6, checks
        store = Store(workspace)
        with store.connect() as db:
            study_id = db.execute("SELECT id FROM studies WHERE title='Generated macOS qualification'").fetchone()[0]
        assert store.frame(study_id, 63)['review']['note'] == 'Generated macOS note'
        assert store.study(study_id)['frame_count'] == 64
        assert not mp.active_children(), 'Backend survived window closure'
        print('PASS saved study and annotation persist after native window shutdown', flush=True)
    watchdog.cancel()


if __name__ == '__main__':
    main()
