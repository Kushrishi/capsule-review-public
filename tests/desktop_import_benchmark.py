"""Opt-in synthetic folder-import measurement; no private images or model fitting.

Run each size in a fresh process. Linux resource.ru_maxrss includes Python and
importer metadata; elapsed time excludes fixture generation and post-import API QA.
"""
import argparse
import io
import json
import os
from pathlib import Path
import random
import resource
import shutil
import tempfile
import time

from PIL import Image
from capsule_review.importer import import_folder
from capsule_review.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', type=int, default=12000)
    parser.add_argument('--desktop', action='store_true', help='Measure the actual desktop backend RSS on Linux')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='capsule-folder-measure-') as temp:
        root = Path(temp)
        sources = root / 'source'
        sources.mkdir()
        image = Image.frombytes('RGB', (256, 256), random.Random(17).randbytes(256 * 256 * 3))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=95)
        raw = output.getvalue()
        seed = root / 'generated.jpg'
        seed.write_bytes(raw)
        for n in reversed(range(args.frames)):
            dest = sources / f'frame_{n}.jpg'
            try:
                os.link(seed, dest)
            except OSError:
                shutil.copyfile(seed, dest)
        store = Store(root / 'workspace')
        samples = {}
        def progress(update):
            if update['phase'] == 'importing' and update['completed'] in {0, args.frames // 2, args.frames}:
                samples[update['completed']] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
        backend_baseline = None
        if args.desktop:
            import httpx
            from capsule_review.desktop import Backend
            with Backend(store.root) as backend, httpx.Client(follow_redirects=True, trust_env=False, timeout=30) as client:
                assert client.get(backend.url).status_code == 200
                origin = backend.url.split('/desktop-session')[0]
                headers = {'X-Review-Token': client.get(origin + '/api/config').json()['token']}
                def rss(field):
                    for line in Path(f'/proc/{backend.process.pid}/status').read_text().splitlines():
                        if line.startswith(field + ':'):
                            return int(line.split()[1]) / 1024
                backend_baseline = rss('VmRSS')
                grant = backend.select_folder(sources)
                start = time.perf_counter()
                assert client.post(origin + '/api/desktop-import', headers=headers,
                    json={'title': 'Generated backend measurement', 'selection': grant['selection']}).status_code == 202
                while True:
                    status = client.get(origin + '/api/desktop-import').json()
                    if status['state'] not in {'running', 'cancelling'}:
                        break
                    time.sleep(.1)
                elapsed = time.perf_counter() - start
                assert status['state'] == 'completed', status
                result = store.study(status['study_id'])
                import_peak = rss('VmHWM')
        else:
            start = time.perf_counter()
            result = import_folder(store, sources, title='Generated benchmark', source='Deterministic software-test images', progress=progress, max_files=100000)
            elapsed = time.perf_counter() - start
            import_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        stored = sum(p.stat().st_size for p in store.images.rglob('*') if p.is_file())
        start = time.perf_counter()
        last = store.frame(result['id'], args.frames - 1)
        assert last['source_index'] == args.frames - 1
        meta_ms = (time.perf_counter() - start) * 1000
        print(json.dumps({'frames': args.frames, 'resolution': '256x256', 'source_mib': round(len(raw)*args.frames/1024**2, 2),
            'image_output_mib': round(stored/1024**2, 2), 'seconds': round(elapsed, 3),
            'frames_per_second': round(args.frames/elapsed, 2), 'import_peak_rss_mib': round(import_peak, 2), 'mode': 'desktop-backend' if args.desktop else 'import-core',
            'backend_baseline_rss_mib': round(backend_baseline, 2) if backend_baseline else None,
            'rss_samples_mib': samples, 'last_frame_metadata_ms': round(meta_ms, 3)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
