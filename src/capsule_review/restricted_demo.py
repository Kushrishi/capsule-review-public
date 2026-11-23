"""Generated-only pixel-delivery prototype, NOT a human exposure study mode.

Only installed by explicit desktop opt-in in a fresh, temporary workspace.
No arbitrary study, selection, image path or model can be supplied by a client.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import threading
import zipfile
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .demo_scores import DEMO_LABEL, DEMO_RUN_ID, open_or_create_demo
from .priority import priority_queue

STATIC = Path(__file__).parent / 'static'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def configure(app, store):
    """Build a new fixture and freeze identities BEFORE serving any study pixels."""
    with store.connect() as db:
        if db.execute('SELECT 1 FROM studies LIMIT 1').fetchone():
            raise ValueError('Restricted generated prototype requires an empty workspace.')
    study = open_or_create_demo(store)
    with store.connect() as db:
        run_record = db.execute('SELECT id,model_json FROM prediction_runs WHERE study_id=? AND run_id=?',
                                (study['id'], DEMO_RUN_ID)).fetchone()
        run = run_record['id']
        score_stream = [dict(r) for r in db.execute(
            'SELECT position,score FROM predictions WHERE study_id=? AND run_id=? AND label=? ORDER BY position',
            (study['id'], run, DEMO_LABEL))]
        frames = [dict(r) for r in db.execute(
            'SELECT position,filename,source_index,source_sha256,display_sha256 FROM frames '
            'WHERE study_id=? ORDER BY position', (study['id'],))]
    queue = priority_queue(store, study['id'], run, DEMO_LABEL, 2, 'score_bin')
    selected = tuple(item['position'] for item in queue['items'])
    if len(set(selected)) != 2:
        raise ValueError('Selection is not exactly K.')
    identity = {
        'schema_version': 1, 'generated_only': True, 'session_id': secrets.token_hex(16),
        'study_id': study['id'], 'source_manifest_sha256': study['manifest_sha256'],
        'selection': {'method': 'score_bin', 'k': 2, 'positions': list(selected),
                      'run_id': DEMO_RUN_ID, 'label': DEMO_LABEL,
                      'model': json.loads(run_record['model_json']), 'score_stream': score_stream},
        'frames': frames,
        'scope': 'Unique source identities permitted for pixel delivery; not human seeing or dwell time',
    }
    # A thumbnail is another representation of the SAME source identity. Freeze
    # both forms; never authorize a filesystem path from a request.
    expected = {}
    for frame in frames:
        for suffix in ('png', 'jpg'):
            data = (store.images / study['id'] / f"{frame['position']}.{suffix}").read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if suffix == 'png' and digest != frame['display_sha256']:
                raise ValueError('Generated display identity mismatch.')
            expected[(frame['position'], suffix)] = digest
    identity['representations'] = [
        {'position': p, 'format': s, 'sha256': digest}
        for (p, s), digest in expected.items()
    ]
    commitment = hashlib.sha256(canonical(identity)).hexdigest()
    lock = threading.RLock()
    events = []
    restricted = True
    integrity_ok = True
    ledger_path = store.root / 'restricted-session.jsonl'

    def record(action, **fields):
        nonlocal integrity_ok
        event = {'sequence': len(events), 'action': action,
                 'previous_sha256': events[-1]['sha256'] if events else commitment, **fields}
        event['sha256'] = hashlib.sha256(canonical(event)).hexdigest()
        # A write failure MUST prevent pixel delivery or mode exit. A partial
        # final record remains a failure, never a successful access receipt.
        try:
            with ledger_path.open('ab') as handle:
                handle.write(canonical(event) + b'\n')
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            integrity_ok = False
            raise HTTPException(503, 'Audit persistence failed; session invalidated.') from None
        events.append(event)

    def receipt():
        return {'commitment': identity, 'commitment_sha256': commitment,
                'restricted': restricted, 'integrity_ok': integrity_ok,
                'restricted_claim_valid': restricted and integrity_ok,
                'events': list(events), 'actual_human_exposure': 'UNMEASURED',
                'prior_exposure_outside_this_process': 'UNKNOWN'}

    def image_bytes(position, suffix):
        nonlocal integrity_ok
        if not 0 <= position < len(frames):
            record('deny', position=position, representation=suffix, reason='unknown identity')
            raise HTTPException(404, 'Unknown generated frame.')
        if not integrity_ok:
            record('deny', position=position, representation=suffix, reason='integrity failure')
            raise HTTPException(409, 'Session invalidated by source integrity failure.')
        if position not in selected:
            record('deny', position=position, representation=suffix, reason='outside frozen selection')
            raise HTTPException(403, 'Outside the frozen selected set.')
        try:
            data = (store.images / study['id'] / f'{position}.{suffix}').read_bytes()
        except OSError:
            data = b''
        if hashlib.sha256(data).hexdigest() != expected[(position, suffix)]:
            record('integrity_failure', position=position, representation=suffix)
            integrity_ok = False
            raise HTTPException(409, 'Generated image bytes changed or are unavailable.')
        record('authorize_pixels', position=position, representation=suffix,
               image_sha256=expected[(position, suffix)], restricted=restricted)
        return data

    with lock:
        record('start', selected_positions=list(selected), k=2)
    app.state.restricted_receipt = receipt

    @app.get('/')
    def page():
        return FileResponse(STATIC / 'restricted-demo.html')

    @app.get('/restricted-demo.js')
    def script():
        return FileResponse(STATIC / 'restricted-demo.js', media_type='text/javascript')

    @app.get('/api/restricted/state')
    def state():
        with lock:
            return receipt()

    @app.get('/api/restricted/images/{position}')
    def image(position: int, thumbnail: bool = False):
        with lock:
            data = image_bytes(position, 'jpg' if thumbnail else 'png')
            return Response(data, media_type='image/jpeg' if thumbnail else 'image/png')

    @app.post('/api/restricted/exit')
    def exit_mode():
        nonlocal restricted
        with lock:
            if restricted:
                record('exit', restricted_claim_valid=False,
                       reason='Mode exit permanently ends this restricted session; no omitted pixels enabled')
                restricted = False
            return receipt()

    @app.get('/api/restricted/export')
    def export():
        with lock:
            # Export cannot change K or include context, interval interiors,
            # omitted previews, or supplied arbitrary paths. It contains K only.
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for p in selected:
                    archive.writestr(f'selected/{p}.png', image_bytes(p, 'png'))
                record('export', selected_positions=list(selected), restricted=restricted)
                archive.writestr('receipt.json', canonical(receipt()))
            return Response(output.getvalue(), media_type='application/zip',
                            headers={'Content-Disposition': 'attachment; filename="generated-restricted-evidence.zip"'})

    # Fail closed on EVERY other path, including ordinary viewer image/export,
    # import, static assets and model APIs. The app was returned before those
    # routes were registered. Log attempted alternate access after local auth.
    @app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def deny_path(path: str, request: Request):
        with lock:
            # Do not persist user-controlled bodies, titles, notes or filenames.
            record('deny_route', method=request.method, reason='route unavailable in generated prototype')
        return JSONResponse({'detail': 'Unavailable in restricted generated prototype.'}, 403)
