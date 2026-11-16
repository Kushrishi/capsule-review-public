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
    parser.add_argument('--folder-import', action='store_true')
    options = parser.parse_args()
    import webview
    from qtpy.QtWidgets import QFileDialog
    from capsule_review.desktop import run_window

    errors, checks = [], []
    with tempfile.TemporaryDirectory(prefix='capsule-desktop-gui-') as temporary:
        workspace = Path(temporary) / 'workspace'
        export = Path(temporary) / 'generated-review.zip'
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **kw: (str(export), ''))
        sources = Path(temporary) / 'generated-folder'
        if options.folder_import:
            from PIL import Image
            import io
            sources.mkdir()
            data = io.BytesIO()
            Image.new('RGB', (128, 96), 'teal').save(data, format='PNG')
            for n in range(3000):
                (sources / f'frame_{n}.png').write_bytes(data.getvalue())
        original = webview.create_window

        def create(*args, **kwargs):
            assert kwargs['confirm_close'] is True
            window = original(*args, **kwargs)
            if options.folder_import:
                window.create_file_dialog = lambda *a, **kw: (str(sources),)

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
                    if options.folder_import:
                        wait("!document.getElementById('desktopFolderImport').hidden")
                        window.run_js("document.getElementById('importBtn').click(); document.getElementById('importTitle').value='Generated full examination'; document.getElementById('desktopChooseFolder').click()")
                        wait("!document.getElementById('desktopStartImport').disabled")
                        window.run_js("document.getElementById('desktopStartImport').click()")
                        wait("!document.getElementById('desktopImportProgress').hidden && !document.getElementById('desktopImportCancel').disabled")
                        window.run_js("document.getElementById('desktopImportCancel').click()")
                        wait("document.getElementById('desktopImportHeading').textContent === 'Import cancelled'")
                        assert js("document.getElementById('studyCount').textContent") == '0'
                        checks.append('native folder selection, import progress and cancellation leave no partial study')
                        window.run_js("document.getElementById('importBtn').click(); document.getElementById('desktopChooseFolder').click()")
                        wait("!document.getElementById('desktopStartImport').disabled")
                        window.run_js("document.getElementById('desktopStartImport').click()")
                        wait("!document.getElementById('desktopImportOpen').hidden")
                        window.run_js("document.getElementById('desktopImportOpen').click()")
                        wait("document.getElementById('jumpInput').max === '3000' && !document.getElementById('jumpInput').disabled")
                        window.run_js("document.getElementById('jumpInput').value='3000'; document.getElementById('jumpInput').dispatchEvent(new Event('change'))")
                        wait("document.getElementById('sourceIndex').textContent === 'Source #2999' && !document.getElementById('jumpInput').disabled")
                        assert js("document.querySelectorAll('#filmstrip img').length") == 12
                        assert js("document.getElementById('frameImage').naturalWidth") == 128
                        assert js("performance.getEntriesByType('resource').filter(x => x.name.includes('/image') && !x.name.includes('thumbnail=true')).length") <= 3
                        checks.append('native 3000-frame import reaches the last frame with only 12 filmstrip thumbnails')
                    window.run_js("document.getElementById('demoBtn').click()")
                    wait("document.getElementById('frameImage').naturalWidth === 640")
                    wait("document.getElementById('frameCounter').textContent.includes('24')")
                    wait("document.getElementById('jumpInput').max === '24' && !document.getElementById('nextBtn').disabled")
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
        assert len(checks) == 4 + int(options.kill_backend) + (2 if options.folder_import else 0)
        from capsule_review.store import Store
        store = Store(workspace)
        with store.connect() as db:
            assert db.execute('SELECT note FROM reviews').fetchone()[0] == 'Native synthetic note'
        print('PASS native window closes and committed review persists', flush=True)


if __name__ == '__main__':
    main()
