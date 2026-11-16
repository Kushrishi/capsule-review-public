"""Opt-in real pywebview/Qt smoke; temporary generated data only.

Run separately from pytest because the native event loop owns the main thread.
QT_QPA_PLATFORM=offscreen is supported for display-less engineering checks.
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import threading
import time
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kill-backend', action='store_true')
    options = parser.parse_args()
    import webview
    from qtpy.QtWidgets import QFileDialog
    from capsule_review.desktop import run_window

    errors, checks = [], []
    with tempfile.TemporaryDirectory(prefix='capsule-desktop-gui-') as temporary:
        workspace = Path(temporary) / 'workspace'
        export = Path(temporary) / 'generated-review.zip'
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **kw: (str(export), ''))
        original = webview.create_window

        def create(*args, **kwargs):
            assert kwargs['confirm_close'] is True
            window = original(*args, **kwargs)

            def js(expression):
                # Test-only native evaluation avoids eval(), retaining production CSP.
                return window.gui.evaluate_js('JSON.stringify(' + expression + ')', window.uid, True)

            def wait(expression):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if js(expression):
                        return
                    time.sleep(.1)
                raise AssertionError('Native DOM condition failed: ' + expression)

            def drive():
                try:
                    wait("document.getElementById('version').textContent.startsWith('v')")
                    assert 'desktop-session' not in js('location.href')
                    assert 'cr_desktop_' not in js('document.cookie')
                    checks.append('native window authenticates and loads the unchanged viewer')
                    window.run_js("document.getElementById('demoBtn').click()")
                    wait("document.getElementById('frameImage').naturalWidth === 640")
                    wait("document.getElementById('frameCounter').textContent.includes('24')")
                    checks.append('generated 24-frame study renders at full resolution')
                    window.run_js("document.getElementById('reviewNote').value='Native synthetic note'; document.getElementById('reviewNote').dispatchEvent(new Event('input')); document.getElementById('saveBtn').click()")
                    wait("document.getElementById('saveStatus').textContent === 'Saved' && document.getElementById('savedCount').textContent === '1' && !document.getElementById('nextBtn').disabled")
                    window.run_js("document.getElementById('nextBtn').click()")
                    wait("document.getElementById('jumpInput').value === '2' && !document.getElementById('prevBtn').disabled")
                    window.run_js("document.getElementById('prevBtn').click()")
                    wait("document.getElementById('reviewNote').value === 'Native synthetic note'")
                    checks.append('native navigation and annotation saving work')
                    window.run_js("document.getElementById('exportBtn').click()")
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if export.exists() and zipfile.is_zipfile(export):
                            break
                        time.sleep(.1)
                    with zipfile.ZipFile(export) as archive:
                        record = json.loads(archive.read('review.json'))
                        assert record['synthetic'] and record['frames'][0]['review']['note'] == 'Native synthetic note'
                    checks.append('native blob download saves a valid illustrated review ZIP')
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    if options.kill_backend and not errors:
                        mp.active_children()[0].kill()
                    else:
                        window.confirm_close = False  # Test teardown bypasses the human confirmation.
                        window.destroy()

            window.events.loaded += drive
            return window

        webview.create_window = create
        try:
            try:
                run_window(workspace)
            except RuntimeError as exc:
                if not options.kill_backend or 'stopped unexpectedly' not in str(exc):
                    raise
                checks.append('backend failure closes the native window and reports an error')
        finally:
            webview.create_window = original
        for check in checks:
            print('PASS', check, flush=True)
        if errors:
            raise AssertionError('; '.join(errors))
        assert len(checks) == (5 if options.kill_backend else 4)
        from capsule_review.store import Store
        store = Store(workspace)
        with store.connect() as db:
            assert db.execute('SELECT note FROM reviews').fetchone()[0] == 'Native synthetic note'
        print('PASS native window closes and committed review persists', flush=True)


if __name__ == '__main__':
    main()
