"""Native Qt/WKWebView generated restriction; no physical-user claim."""
import json
from pathlib import Path
import tempfile
import time
import traceback


def main():
    import webview
    from capsule_review.desktop import run_window
    original = webview.create_window
    result = {'status': 'RUNNING', 'generated_only': True}
    with tempfile.TemporaryDirectory(prefix='restricted-native-') as root:
        def create(*args, **kwargs):
            window = original(*args, **kwargs)
            def js(expression):
                return window.gui.evaluate_js('JSON.stringify(' + expression + ')', window.uid, True)
            def wait(expression):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    value = js(expression)
                    if value:
                        return value
                    time.sleep(.05)
                raise AssertionError('Native generated condition timed out')
            def drive():
                try:
                    wait("document.querySelector('#image').naturalWidth===640")
                    assert js("document.querySelector('#mode').textContent").startswith('RESTRICTED GENERATED SESSION')
                    assert js("Array.from(document.querySelectorAll('#frames button')).map(b=>Number(b.dataset.position))") == [6, 12]
                    window.run_js("""window.control=null; (async()=>{
                      const omitted=new Image(); omitted.src='/api/restricted/images/0?thumbnail=true';
                      let rejected=false; try {await omitted.decode();} catch {rejected=true;}
                      const response=await fetch('/api/restricted/images/0');
                      window.control={rejected,width:omitted.naturalWidth,status:response.status};
                    })();""")
                    result['omitted_control'] = wait('window.control')
                    assert result['omitted_control'] == {'rejected': True, 'width': 0, 'status': 403}
                    window.run_js("document.querySelector('#frames button[data-position=\"12\"]').click()")
                    wait("document.querySelector('#image').src.endsWith('/12') && document.querySelector('#image').naturalWidth===640")
                    window.run_js("document.querySelector('#exit').click()")
                    wait("document.querySelector('#mode').textContent.startsWith('RESTRICTED CLAIM INVALID')")
                    assert js("document.querySelectorAll('#frames button').length") == 0
                    assert not js("document.querySelector('#image').getAttribute('src')")
                    result.update(status='PASS', selected_positions=[6, 12],
                                  scope='Native decoded pixels and DOM state only; human seeing unmeasured')
                except Exception:
                    result.update(status='FAIL', error=traceback.format_exc())
                finally:
                    window.confirm_close = False
                    window.destroy()
            window.events.loaded += drive
            return window
        webview.create_window = create
        try:
            run_window(root, restricted_generated=True)
        finally:
            webview.create_window = original
    print(json.dumps(result, sort_keys=True))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
