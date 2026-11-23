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
              'scope': 'Native Qt decoding and HTTP availability only; no visibility or human exposure measurement'}
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
                    decoded = """Array.from(document.querySelectorAll('#filmstrip button')).filter(b=>{
                        const i=b.querySelector('img');
                        return i.complete&&i.naturalWidth>0&&i.naturalHeight>0;
                    }).map(b=>Number(b.dataset.position))"""
                    wait('(' + decoded + ').length>2')
                    thumbnails = js(decoded)
                    result['decoded_thumbnail_positions'] = thumbnails
                    result['omitted_decoded_thumbnail_positions'] = [p for p in thumbnails if p not in selected]
                    assert result['omitted_decoded_thumbnail_positions']
                    # A hidden filmstrip still contains decoded images. This
                    # observer deliberately measures availability, not visibility.
                    window.run_js("document.getElementById('filmstrip').hidden=true")
                    wait("getComputedStyle(document.getElementById('filmstrip')).display==='none'")
                    hidden_decoded = js(decoded)
                    assert set(thumbnails) <= set(hidden_decoded)
                    result['hidden_filmstrip_control'] = {'display': 'none',
                        'previous_decoded_positions_retained': True,
                        'decoded_positions_while_hidden': hidden_decoded,
                        'not_a_visibility_measurement': True}
                    window.run_js("document.getElementById('filmstrip').hidden=false")
                    # No claim of rendered pixels or human exposure follows
                    # from decoding/availability, even outside the selected set.
                    try:
                        assert set(thumbnails) <= set(selected), 'Omitted thumbnails are decoded; visibility is unmeasured'
                    except AssertionError as exc:
                        result['locked_image_access_negative_control'] = 'FAIL_AS_EXPECTED'
                        result['negative_control_reason'] = str(exc)
                    else:
                        raise AssertionError('The unrestricted access control did not decode omitted images')
                    expected = js('state.priorityData.largest_unselected_span.inspect_position')
                    window.run_js("document.querySelector('#priorityComparison tr.comparison-active button').click()")
                    wait('state.frame.position===' + str(expected) +
                         " && !document.getElementById('jumpInput').disabled && document.getElementById('frameImage').complete")
                    inspected = js('state.frame.position')
                    assert inspected not in selected
                    assert js("document.getElementById('frameImage').naturalWidth") == 640
                    result['omitted_full_resolution_loaded_position'] = inspected
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
