"""Real Chromium + authenticated spawned backend, generated inputs only."""
import argparse
import json
from pathlib import Path
import tempfile
import zipfile

from playwright.sync_api import expect, sync_playwright
from capsule_review.desktop import Backend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', help='Existing Chromium executable for cloud testing')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='restricted-browser-') as root, Backend(root, restricted_generated=True) as backend:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=args.browser)
            context = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            pixel_responses = []
            page.on('response', lambda response: pixel_responses.append((response.url, response.status))
                    if '/api/restricted/images/' in response.url else None)
            page.goto(backend.url)
            expect(page.locator('#image')).to_have_js_property('naturalWidth', 640)
            assert 'RESTRICTED GENERATED SESSION' in page.locator('#mode').inner_text()
            assert page.locator('#frames button').count() == 2
            assert page.locator('#frames button').evaluate_all('(nodes)=>nodes.map(n=>Number(n.dataset.position))') == [6, 12]
            page.locator('#frames button').nth(1).click()
            expect(page.locator('#image')).to_have_attribute('src', '/api/restricted/images/12')
            expect(page.locator('#image')).to_have_js_property('naturalWidth', 640)
            # Same-source thumbnails allowed; every other source denied, even
            # when bypassing controls or requesting browser decode directly.
            control = page.evaluate('''async () => {
              const allowed = new Image(); allowed.src='/api/restricted/images/6?thumbnail=true';
              await allowed.decode();
              const omitted = new Image(); omitted.src='/api/restricted/images/0?thumbnail=true';
              let rejected=false; try { await omitted.decode(); } catch { rejected=true; }
              const direct=await fetch('/api/restricted/images/0');
              const old=await fetch('/api/studies/anything/frames/0/image');
              return {allowed:allowed.naturalWidth>0,omitted:omitted.naturalWidth,rejected,status:direct.status,alternate:old.status};
            }''')
            assert control == {'allowed': True, 'omitted': 0, 'rejected': True, 'status': 403, 'alternate': 403}
            with page.expect_download() as download:
                page.get_by_text('Export selected images and session receipt', exact=True).click()
            path = Path(download.value.path())
            with zipfile.ZipFile(path) as archive:
                assert set(archive.namelist()) == {'selected/6.png', 'selected/12.png', 'receipt.json'}
                receipt = json.loads(archive.read('receipt.json'))
                assert receipt['restricted_claim_valid']
            page.locator('#exit').click()
            expect(page.locator('#mode')).to_contain_text('RESTRICTED CLAIM INVALID')
            assert page.locator('#frames button').count() == 0
            assert page.locator('#image').get_attribute('src') is None
            page.reload()
            expect(page.locator('#mode')).to_contain_text('RESTRICTED CLAIM INVALID')
            assert page.locator('#frames button').count() == 0
            assert all(url.split('/images/')[1].split('?')[0] in ('6', '12') for url, status in pixel_responses if status == 200)
            assert not errors, errors
            print(json.dumps({'status': 'PASS', 'generated_only': True, 'selected_positions': [6, 12],
                              'browser': browser.version, 'pixel_controls': control,
                              'scope': 'Browser decoding and permitted pixel responses, not human seeing',
                              'exit_survives_reload': True, 'javascript_errors': errors}))
            browser.close()
    assert not backend.process.is_alive()


if __name__ == '__main__':
    main()
