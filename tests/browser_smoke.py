"""Real UI + FastAPI TestClient; browser networking is replaced with in-process delivery.

This tests UI logic, DOM/rendering and API behaviour, not a deployed/localhost
browser session, CSP enforcement, or the transport security of a real browser origin.
"""
from pathlib import Path
import argparse, json, socket, subprocess, sys, time, zipfile, tempfile
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from capsule_review.app import create_app

parser=argparse.ArgumentParser(description='Exercise the viewer, persisted review and illustrated export.')
parser.add_argument('--transport', choices=['localhost','in-process'], default='localhost')
parser.add_argument('--with-test-model', action='store_true', help='Train geometric fixtures and exercise local inference; not medical validation')
parser.add_argument('--browser', help='Optional Chromium executable; otherwise use Playwright Chromium')
parser.add_argument('--output', type=Path, default=Path('test-results/browser'))
args=parser.parse_args()
out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
workspace=Path(tempfile.mkdtemp(prefix='capsule-browser-'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
origin=f'http://127.0.0.1:{port}'
server=None
if args.transport == 'localhost':
    log=(out/'server.log').open('w')
    server=subprocess.Popen([sys.executable,'-m','capsule_review.cli','--data-dir',str(workspace),'serve','--port',str(port)],stdout=log,stderr=subprocess.STDOUT)
    import urllib.request
    for _ in range(100):
        try:
            urllib.request.urlopen(origin+'/api/config',timeout=1).close(); break
        except OSError: time.sleep(.1)
    else:
        server.terminate(); raise RuntimeError('The local server did not start. See server.log.')
    import atexit
    atexit.register(server.terminate)

app=create_app(workspace)
client=TestClient(app,base_url=origin)
errors=[]

def wait_for_js(page, expression, timeout_ms=6000):
    """CSP-safe polling for the existing browser predicates.

    Playwright 1.56 may run wait_for_function in the page's CSP-controlled
    context. Its evaluate API uses the browser automation execution context.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        if page.evaluate(expression):
            return
        if time.monotonic() >= deadline:
            raise AssertionError(f'Browser predicate timed out: {expression}')
        time.sleep(.05)

class Checks(list):
    def append(self, value):
        super().append(value); print('PASS', value, flush=True)
checks=Checks()
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
    context.set_default_timeout(6000)
    def route_to_api(route):
        req=route.request
        path=req.url.removeprefix(origin)
        # about:blank is a different origin; this is explicitly a test transport.
        heads={k:v for k,v in req.headers.items() if k not in ('host','origin','referer','content-length')}
        if req.method=='OPTIONS':
            route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-methods':'GET,POST,PUT','access-control-allow-headers':'*'});return
        response=client.request(req.method,path,headers=heads,content=req.post_data_buffer)
        if response.status_code >= 400: print('API FAILURE',req.method,path,response.status_code,response.text[:400],flush=True)
        h={k:v for k,v in response.headers.items() if k not in ('content-length','content-encoding')}
        h['access-control-allow-origin']='*'
        route.fulfill(status=response.status_code,headers=h,body=response.content)
    if args.transport == 'in-process': context.route(origin+'/**',route_to_api)
    def open_app():
        page=context.new_page()
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        if args.transport == 'in-process':
            # Playwright's intercepted postData omits file bytes from native multipart
            # requests. Serialize with the browser's Request API for this test transport.
            page.evaluate("""() => {
              const nativeFetch = window.fetch.bind(window);
              window.fetch = async (url, options = {}) => {
                if (options.body instanceof FormData) {
                  const request = new Request(new URL(url, document.baseURI), options);
                  const body = await request.arrayBuffer();
                  return nativeFetch(url, {...options, body, headers: request.headers});
                }
                return nativeFetch(url, options);
              };
            }""")
            page.set_content(client.get('/').text.replace('<head>',f'<head><base href="{origin}/">'))
        else:
            page.goto(origin+'/')
        wait_for_js(page, "document.getElementById('version').textContent.startsWith('v')")
        return page
    page=open_app()
    page.screenshot(path=str(out/'empty-state.png'),full_page=True)
    page.get_by_role('button',name='Open test sequence').click()
    page.wait_for_selector('#syntheticBanner',state='visible')
    wait_for_js(page, "document.getElementById('studyCount').textContent === '1'")
    wait_for_js(page, "document.getElementById('frameImage').complete && document.getElementById('frameImage').naturalWidth > 0")
    assert '24' in page.locator('#frameCounter').inner_text()
    assert 'No model connected' in page.locator('#predictions').inner_text()
    checks.append('24-frame synthetic sequence loads with no model predictions')
    page.locator('#reviewLabel').fill('Navigation check')
    page.locator('#reviewNote').fill('Software test: verify this frame, save the note, and reopen the review.')
    page.get_by_role('button',name='Save review',exact=True).click()
    wait_for_js(page, "document.getElementById('saveStatus').textContent === 'Saved' && document.getElementById('savedCount').textContent === '1'")
    page.get_by_label('Next frame',exact=True).click()
    wait_for_js(page, "document.getElementById('jumpInput').value === '2'")
    page.get_by_label('Bookmark this frame').check()
    wait_for_js(page, "document.getElementById('saveStatus').textContent === 'Saved' && document.getElementById('savedCount').textContent === '2'")
    checks.append('Reviewer note and bookmark saved separately')
    page.locator('#reviewNote').fill('Draft saved automatically when navigating.')
    page.get_by_label('Next frame',exact=True).click()
    wait_for_js(page, "document.getElementById('jumpInput').value === '3'")
    page.get_by_label('Previous frame',exact=True).click()
    wait_for_js(page, "document.getElementById('jumpInput').value === '2'")
    assert page.locator('#reviewNote').input_value() == 'Draft saved automatically when navigating.'
    checks.append('Navigation saves the draft before leaving the frame')
    page.close();page=open_app()
    wait_for_js(page, "document.getElementById('jumpInput').value === '2'")
    assert page.locator('#reviewNote').input_value() == 'Draft saved automatically when navigating.'
    assert page.locator('#bookmark').is_checked()
    checks.append('Closing and reopening the UI restores last frame and persisted notes')
    with page.expect_download() as event:
        page.get_by_role('button',name='Export review').click()
    export=out/'sample-review.zip'
    event.value.save_as(str(export))
    with zipfile.ZipFile(export) as archive:
        manifest=json.loads(archive.read('review.json'))
        assert manifest['synthetic'] is True and len(manifest['frames'])==2
        assert 'SYNTHETIC TEST SEQUENCE' in archive.read('review.html').decode()
        archive.extractall(out/'sample-review')
    checks.append('Export download contains two selected frames, illustrated HTML and JSON')
    page.locator('#reviewNote').focus();before=page.locator('#jumpInput').input_value()
    page.keyboard.press('ArrowRight');assert page.locator('#jumpInput').input_value()==before
    checks.append('Frame shortcuts do not override text editing')
    page.locator('#frameCounter').click();page.keyboard.press('ArrowRight')
    wait_for_js(page, "document.getElementById('jumpInput').value === '3'")
    checks.append('Keyboard frame navigation works')
    page.locator('#jumpInput').fill('24');page.locator('#jumpInput').press('Tab')
    wait_for_js(page, "document.getElementById('frameCounter').textContent.startsWith('Frame 24')")
    assert page.locator('#nextBtn').is_disabled();checks.append('End of sequence disables next-frame control')
    page.get_by_role('button',name='Help',exact=True).click();assert page.locator('#helpDialog').is_visible()
    page.get_by_label('Close help').click();checks.append('Help dialog opens and closes')
    page.get_by_role('button',name='Import frames',exact=True).click()
    frame_dir=workspace/'images'/manifest['study']['id']
    page.locator('#fileInput').set_input_files([str(frame_dir/'0.png'),str(frame_dir/'1.png')])
    page.locator('#importTitle').fill('Upload test - geometric fixtures')
    page.locator('#importSource').fill('Non-medical synthetic frames for software testing')
    page.get_by_role('button',name='Import locally',exact=True).click()
    wait_for_js(page, "document.getElementById('studyTitle').textContent === 'Upload test - geometric fixtures' && document.getElementById('studyCount').textContent === '2'")
    assert '/ 2' in page.locator('#frameCounter').inner_text();checks.append(f'UI image import succeeds using {args.transport} transport')
    page.get_by_role('button',name='Open test sequence').click()
    page.wait_for_selector('#syntheticBanner',state='visible')
    page.locator('#jumpInput').fill('2');page.locator('#jumpInput').press('Tab')
    wait_for_js(page, "document.getElementById('frameCounter').textContent.startsWith('Frame 2 /')")
    for width in [320,390,768,1440]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),width
    checks.append('No horizontal page overflow at 320, 390, 768 and 1440 pixels')
    page.locator('#toast').wait_for(state='hidden')
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'viewer-mobile.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1050})
    wait_for_js(page, "document.getElementById('frameImage').complete")
    page.screenshot(path=str(out/'viewer-desktop.png'),full_page=True)
    if args.with_test_model:
        from test_baseline_data import make_dataset
        from capsule_review.baseline_data import prepare_manifest
        from capsule_review.baseline import train, install_model
        from capsule_review.importer import import_sources
        images, labels = make_dataset(workspace / 'ml-fixtures')
        development = workspace / 'development.json'
        prepare_manifest(images, labels, development, validation_exams=[3],
                         classes=('stomach', 'colon'), data_kind='synthetic-test')
        trained = workspace / 'test-model'
        train(development, images, trained, epochs=2, batch_size=8, allow_synthetic_test=True)
        install_model(app.state.store, trained, allow_synthetic_test=True)
        heldout = import_sources(app.state.store,
            ((p.name, p.read_bytes()) for p in sorted((images / '003').glob('*.PNG'))),
            title='ML integration test — NOT MEDICAL', source='Geometric software-test patterns', synthetic=True)
        page.close(); page = open_app()
        page.get_by_role('button', name='ML integration test — NOT MEDICAL', exact=False).click()
        page.wait_for_selector('#localModelControls', state='visible')
        assert 'Software-test model' in page.locator('#localModel').inner_text()
        page.locator('#reviewNote').fill('Keep this note when the local test model runs.')
        page.get_by_role('button', name='Save review', exact=True).click()
        wait_for_js(page, "document.getElementById('saveStatus').textContent === 'Saved'")
        page.get_by_role('button', name='Run local model', exact=True).click()
        wait_for_js(page, "document.getElementById('predictions').textContent.includes('Software-test model')")
        assert page.locator('#syntheticBanner').is_visible()
        assert page.locator('#reviewNote').input_value() == 'Keep this note when the local test model runs.'
        assert not page.locator('#bookmark').is_checked()
        checks.append('Browser runs a genuinely trained software-test model on separate synthetic images')
        page.locator('#predictions details summary').first.click()
        assert 'uncalibrated' in page.locator('#predictions').inner_text()
        checks.append('Prediction meaning remains explicit and reviewer notes are not overwritten')
        page.close(); page = open_app()
        wait_for_js(page, "document.getElementById('predictions').textContent.includes('Software-test model')")
        page.wait_for_selector('#localModelControls', state='visible')
        wait_for_js(page, "!document.getElementById('runModelBtn').disabled && document.getElementById('savedCount').textContent === '1'")
        checks.append('Local model predictions persist after closing and reopening the viewer')
        page.set_viewport_size({'width':1440,'height':1050})
        page.locator('#toast').wait_for(state='hidden')
        page.screenshot(path=str(out/'local-model-software-test.png'), full_page=True)
    assert not errors,errors
    checks.append('No JavaScript errors observed')
    browser.close()
result={'transport':args.transport, 'browser':args.browser or 'Playwright Chromium','checks':checks,'javascript_errors':errors}
(out/'browser-results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))

if server is not None:
    server.terminate(); server.wait(timeout=10)
