"""Generated-only Qt exposure boundary test; no locked viewer is implemented.

Uses the real desktop launcher and DOM. A queue is an offline selected set;
the exploratory viewer deliberately allows thumbnails and omitted images.
Run on Linux with desktop dependencies, optionally QT_QPA_PLATFORM=offscreen.
"""
import argparse
import json
from pathlib import Path
import tempfile
import time
import traceback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import webview
    from capsule_review.desktop import run_window

    result = {'generated_only': True, 'status': 'RUNNING', 'queue_size': 2,
              'scope': 'Native Qt layout/decode; not a human exposure or reading-time study'}
    original = webview.create_window
    with tempfile.TemporaryDirectory(prefix='capsule-exposure-') as temporary:
        def create(*a, **kw):
            window = original(*a, **kw)

            def js(expr):
                return window.gui.evaluate_js('JSON.stringify(' + expr + ')', window.uid, True)

            def wait(expr):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    value = js(expr)
                    if value:
                        return value
                    time.sleep(.05)
                raise AssertionError('Native condition timed out: ' + expr)

            def drive():
                try:
                    wait("document.getElementById('version').textContent.startsWith('v')")
                    window.run_js("document.getElementById('demoBtn').click()")
                    wait("document.getElementById('frameImage').naturalWidth===640 && !document.getElementById('priorityBuild').disabled")
                    window.run_js("document.getElementById('priorityCount').value='2';document.getElementById('priorityMethod').value='score_bin';document.getElementById('priorityBuild').click()")
                    wait("document.getElementById('prioritySelected').textContent==='2 selected' && document.querySelectorAll('#priorityComparison tbody tr').length===5")
                    selected = js('state.priorityData.items.map(x=>x.position)')
                    assert len(set(selected)) == 2
                    result['selected_positions'] = selected
                    result['selection_count_control'] = 'PASS'
                    window.run_js("document.getElementById('filmstrip').scrollIntoView({block:'center'})")
                    visible = """Array.from(document.querySelectorAll('#filmstrip button')).filter(b=>{
                        const i=b.querySelector('img'),r=i.getBoundingClientRect();
                        return i.complete&&i.naturalWidth>0&&r.width>0&&r.height>0&&
                            r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;
                    }).map(b=>Number(b.dataset.position))"""
                    wait('(' + visible + ').length>2')
                    thumbnails = js(visible)
                    result['rendered_thumbnail_positions'] = thumbnails
                    result['omitted_thumbnail_positions'] = [p for p in thumbnails if p not in selected]
                    assert result['omitted_thumbnail_positions']
                    # Exact negative control: thumbnails/context count as pixels.
                    # Deliberately reject calling this an enforced K-image session.
                    try:
                        assert set(thumbnails) <= set(selected), 'Omitted thumbnail pixels are exposed'
                    except AssertionError as exc:
                        result['locked_exposure_negative_control'] = 'FAIL_AS_EXPECTED'
                        result['negative_control_reason'] = str(exc)
                    else:
                        raise AssertionError('The intended unrestricted negative control did not expose omissions')
                    expected = js('state.priorityData.largest_unselected_span.inspect_position')
                    window.run_js("document.querySelector('#priorityComparison tr.comparison-active button').click()")
                    wait('state.frame.position===' + str(expected) +
                         " && !document.getElementById('jumpInput').disabled && document.getElementById('frameImage').complete")
                    inspected = js('state.frame.position')
                    assert inspected not in selected
                    assert js("document.getElementById('frameImage').naturalWidth") == 640
                    result['omitted_full_resolution_position'] = inspected
                    # Direct authenticated image access is unrestricted too.
                    omitted = next(p for p in range(24) if p not in selected)
                    window.run_js('window.__access=null;fetch(imageURL(' + str(omitted) +
                                  ')).then(async r=>window.__access={status:r.status,bytes:(await r.arrayBuffer()).byteLength})')
                    access = wait('window.__access')
                    assert access['status'] == 200 and access['bytes'] > 0
                    result['direct_omitted_image_access'] = access
                    assert js('state.savedFrameCount') == 0
                    result['human_findings_created'] = 0
                    label = js("document.getElementById('reviewMode')?.textContent||''")
                    result['mode_label'] = label
                    assert 'Exploratory review' in label and 'unrestricted' in label and 'not a locked' in label
                    result['status'] = 'PASS_BOUNDARY_ASSESSMENT'
                except Exception:
                    result['status'] = 'FAIL'
                    result['error'] = traceback.format_exc()
                finally:
                    window.confirm_close = False
                    window.destroy()
            window.events.loaded += drive
            return window

        webview.create_window = create
        try:
            run_window(Path(temporary) / 'workspace')
        finally:
            webview.create_window = original
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'PASS_BOUNDARY_ASSESSMENT':
        raise AssertionError('Exposure boundary assessment failed; see generated result')


if __name__ == '__main__':
    main()
