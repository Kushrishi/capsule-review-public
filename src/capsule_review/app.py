"""Local-only API and browser application. No external analytics or model calls."""

import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import __version__
from .exporter import export_review
from .full_span_evidence import export_full_span_evidence
from .evidence_receipt import account_review_evidence
from .interval_evidence import read_review_export
from .importer import MAX_FILE_BYTES, create_demo, import_sources, natural_key, now, validate_filename
from .models import ImportMeta, IntervalCreate, LocalPredictionRequest, PositionUpdate, PredictionImport, ReviewUpdate
from .store import Store
from .source_coverage import summarize_source_spacing
from .prediction_service import DuplicateRunError, save_predictions
from .baseline_data import read_json

STATIC = Path(__file__).parent / 'static'
MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    root = Path(data_dir or os.getenv('CAPSULE_REVIEW_DATA', Path.home() / '.capsule-review'))
    store = Store(root)
    token = secrets.token_urlsafe(32)
    inference_lock = threading.Lock()
    app = FastAPI(title='Capsule Review', version=__version__, docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.csrf_token = token

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        try:
            host = urlsplit('http://' + request.headers.get('host', '')).hostname
        except ValueError:
            return JSONResponse({'detail': 'Invalid Host header.'}, 400)
        if host not in {'127.0.0.1', 'localhost', '::1'}:
            return JSONResponse({'detail': 'Use localhost; this app is not a hosted service.'}, 400)
        origin = request.headers.get('origin')
        try:
            foreign_origin = origin and (urlsplit(origin).netloc != request.headers.get('host') or
                                         urlsplit(origin).scheme != request.url.scheme)
        except ValueError:
            foreign_origin = True
        if foreign_origin:
            return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, 403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            supplied = request.headers.get('x-review-token', '')
            if not hmac.compare_digest(supplied.encode('utf-8'), token.encode('utf-8')):
                return JSONResponse({'detail': 'Reload the application before saving.'}, 403)
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                return JSONResponse({'detail': 'Invalid request length.'}, 400)
            if size < 0 or size > MAX_UPLOAD_BYTES:
                return JSONResponse({'detail': 'Upload exceeds the 512-MiB limit.'}, 413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Do not echo rejected input (which may include non-finite numbers or notes).
        errors = [{k: item[k] for k in ('loc', 'msg', 'type')} for item in exc.errors()]
        return JSONResponse({'detail': errors}, status_code=422)

    def require_study(study_id: str):
        study = store.study(study_id)
        if study is None:
            raise HTTPException(404, 'Examination not found.')
        return study

    @app.get('/api/config')
    def config():
        return {'version': __version__, 'token': token, 'model_bundled': False,
                'max_upload_files': 1000, 'max_upload_bytes': MAX_UPLOAD_BYTES}

    @app.get('/api/studies')
    def studies():
        with store.connect() as db:
            rows = db.execute(
                "SELECT s.*, (SELECT COUNT(*) FROM reviews r WHERE r.study_id=s.id AND "
                "(r.bookmarked=1 OR r.note<>'' OR r.label<>'')) AS saved_count "
                "FROM studies s ORDER BY s.created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @app.post('/api/demo', status_code=201)
    async def demo():
        return await run_in_threadpool(create_demo, store)

    @app.post('/api/studies/import', status_code=201)
    async def upload(title: str = Form(...), source: str = Form('Local research images'),
                     files: list[UploadFile] = File(...)):
        if len(files) > 1000:
            raise HTTPException(413, 'Browser import supports 1,000 frames; use the CLI for larger folders.')
        try:
            meta = ImportMeta(title=title, source=source)
        except ValueError as exc:
            raise HTTPException(422, 'Check the title and source lengths.') from exc
        total, staged = 0, []
        try:
            with tempfile.TemporaryDirectory(prefix='upload-', dir=store.root) as folder:
                for n, upload_file in enumerate(files):
                    name = validate_filename(upload_file.filename or '')
                    dest = Path(folder) / str(n)
                    count = 0
                    with dest.open('wb') as handle:
                        while block := await upload_file.read(1024 * 1024):
                            count += len(block)
                            total += len(block)
                            if count > MAX_FILE_BYTES or total > MAX_UPLOAD_BYTES:
                                raise HTTPException(413, 'Image or examination upload exceeds the limit.')
                            handle.write(block)
                    staged.append((name, dest))
                staged.sort(key=lambda x: natural_key(x[0]))
                def import_staged():
                    return import_sources(store, ((name, p.read_bytes()) for name, p in staged),
                                          title=meta.title, source=meta.source)
                return await run_in_threadpool(import_staged)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            for upload_file in files:
                await upload_file.close()

    @app.get('/api/studies/{study_id}')
    def get_study(study_id: str):
        return require_study(study_id)

    @app.get('/api/studies/{study_id}/source-coverage')
    def source_coverage(study_id: str):
        require_study(study_id)
        with store.connect() as db:
            indices = [row[0] for row in db.execute(
                'SELECT source_index FROM frames WHERE study_id=? ORDER BY position',
                (study_id,))]
        return summarize_source_spacing(indices)

    @app.get('/api/studies/{study_id}/frames')
    def frames(study_id: str, offset: int = Query(0, ge=0), limit: int = Query(60, ge=1, le=200)):
        require_study(study_id)
        with store.connect() as db:
            return [dict(r) for r in db.execute(
                'SELECT position,filename,source_index FROM frames WHERE study_id=? '
                'ORDER BY position LIMIT ? OFFSET ?', (study_id, limit, offset))]

    @app.get('/api/studies/{study_id}/frames/{position}')
    def frame(study_id: str, position: int):
        result = store.frame(study_id, position)
        if result is None:
            raise HTTPException(404, 'Frame not found.')
        return result

    @app.get('/api/studies/{study_id}/frames/{position}/image')
    def image(study_id: str, position: int, thumbnail: bool = False):
        if store.frame(study_id, position) is None:
            raise HTTPException(404, 'Frame not found.')
        suffix = '.jpg' if thumbnail else '.png'
        return FileResponse(store.images / study_id / f'{position}{suffix}',
                            media_type='image/jpeg' if thumbnail else 'image/png')

    @app.put('/api/studies/{study_id}/frames/{position}/review')
    def update_review(study_id: str, position: int, change: ReviewUpdate):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM frames WHERE study_id=? AND position=?',
                          (study_id, position)).fetchone() is None:
                raise HTTPException(404, 'Frame not found.')
            row = db.execute('SELECT revision FROM reviews WHERE study_id=? AND position=?',
                             (study_id, position)).fetchone()
            current = row['revision'] if row else 0
            if current != change.revision:
                raise HTTPException(409, 'This frame changed in another tab. Reload before saving; your draft has not been overwritten.')
            revision, timestamp = current + 1, now()
            db.execute(
                'INSERT INTO reviews VALUES(?,?,?,?,?,?,?) ON CONFLICT(study_id,position) DO UPDATE SET '
                'revision=excluded.revision,bookmarked=excluded.bookmarked,note=excluded.note,'
                'label=excluded.label,updated_at=excluded.updated_at',
                (study_id, position, revision, int(change.bookmarked), change.note, change.label, timestamp)
            )
            content = change.model_dump()
            content['revision'] = revision
            db.execute('INSERT INTO review_events(study_id,position,revision,content,created_at) '
                       'VALUES(?,?,?,?,?)', (study_id, position, revision, json.dumps(content), timestamp))
        return store.frame(study_id, position)['review']

    @app.put('/api/studies/{study_id}/position')
    def position(study_id: str, change: PositionUpdate):
        study = require_study(study_id)
        if change.position >= study['frame_count']:
            raise HTTPException(422, 'Position is outside this examination.')
        with store.connect() as db:
            db.execute('UPDATE studies SET last_position=? WHERE id=?', (change.position, study_id))
        return {'position': change.position}

    @app.get('/api/studies/{study_id}/saved')
    def saved(study_id: str):
        require_study(study_id)
        with store.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT position,label,note,bookmarked,revision,updated_at FROM reviews WHERE study_id=? "
                "AND (bookmarked=1 OR note<>'' OR label<>'') ORDER BY position", (study_id,))]

    def interval_rows(study_id: str) -> list[dict]:
        with store.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT i.id,i.start_position,i.end_position,i.note,i.created_at,"
                "a.source_index AS start_source_index,b.source_index AS end_source_index "
                "FROM review_intervals i "
                "JOIN frames a ON a.study_id=i.study_id AND a.position=i.start_position "
                "JOIN frames b ON b.study_id=i.study_id AND b.position=i.end_position "
                "WHERE i.study_id=? ORDER BY i.start_position,i.end_position,i.id",
                (study_id,),
            )]

    @app.get('/api/studies/{study_id}/intervals')
    def intervals(study_id: str):
        require_study(study_id)
        return interval_rows(study_id)

    @app.post('/api/studies/{study_id}/intervals', status_code=201)
    def add_interval(study_id: str, data: IntervalCreate):
        study = require_study(study_id)
        if data.start_position >= data.end_position or data.end_position >= study['frame_count']:
            raise HTTPException(422, 'Choose a start and a later end within the imported examination.')
        timestamp = now()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute(
                'SELECT COUNT(*) FROM review_intervals WHERE study_id=?', (study_id,)
            ).fetchone()[0]
            if count >= 100:
                raise HTTPException(422, 'At most 100 reviewer intervals per examination.')
            try:
                cursor = db.execute(
                    'INSERT INTO review_intervals(study_id,start_position,end_position,note,created_at) '
                    'VALUES(?,?,?,?,?)',
                    (study_id, data.start_position, data.end_position, data.note, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, 'This image interval is already marked.') from exc
            db.execute(
                "INSERT INTO review_interval_events"
                "(study_id,interval_id,action,start_position,end_position,note,created_at) "
                "VALUES(?,?,'created',?,?,?,?)",
                (study_id, cursor.lastrowid, data.start_position, data.end_position,
                 data.note, timestamp),
            )
            interval_id = cursor.lastrowid
        return next(row for row in interval_rows(study_id) if row['id'] == interval_id)

    @app.delete('/api/studies/{study_id}/intervals/{interval_id}')
    def delete_interval(study_id: str, interval_id: int):
        require_study(study_id)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute(
                'SELECT * FROM review_intervals WHERE study_id=? AND id=?',
                (study_id, interval_id),
            ).fetchone()
            if row is None:
                raise HTTPException(404, 'Reviewer interval not found.')
            db.execute(
                "INSERT INTO review_interval_events"
                "(study_id,interval_id,action,start_position,end_position,note,created_at) "
                "VALUES(?,?,'deleted',?,?,?,?)",
                (study_id, interval_id, row['start_position'], row['end_position'],
                 row['note'], now()),
            )
            db.execute(
                'DELETE FROM review_intervals WHERE study_id=? AND id=?',
                (study_id, interval_id),
            )
        return {'deleted': interval_id}

    @app.get('/api/studies/{study_id}/manifest')
    def manifest(study_id: str):
        study = require_study(study_id)
        with store.connect() as db:
            frames = [dict(r) for r in db.execute(
                'SELECT position,source_index,filename,source_sha256,display_sha256 FROM frames '
                'WHERE study_id=? ORDER BY position', (study_id,))]
        return {'schema_version': 1, 'study_id': study_id, 'manifest_sha256': study['manifest_sha256'],
                'synthetic': bool(study['synthetic']), 'frames': frames}

    @app.post('/api/studies/{study_id}/predictions', status_code=201)
    def predictions(study_id: str, payload: PredictionImport):
        require_study(study_id)
        try:
            return save_predictions(store, study_id, payload)
        except DuplicateRunError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get('/api/models')
    def models():
        root = store.root / 'models'
        entries = []
        if root.is_dir():
            for folder in sorted(root.iterdir()):
                if not folder.is_dir() or folder.is_symlink() or not re.fullmatch(r'[a-f0-9]{24}', folder.name):
                    continue
                try:
                    meta = read_json(folder / 'model.json', 8 * 1024 * 1024)
                    if meta.get('format') != 'capsule-anatomy-model-v1' or read_json(folder / 'status.json').get('status') != 'complete':
                        continue
                    if meta.get('data_kind') not in {'galar', 'synthetic-test'}:
                        continue
                    entries.append({'id': folder.name, 'classes': meta['classes'],
                                    'synthetic_test': meta['data_kind'] == 'synthetic-test',
                                    'name': 'Software-test model — NOT MEDICAL' if meta['data_kind'] == 'synthetic-test'
                                            else 'Anatomy baseline — research only'})
                except (OSError, ValueError, KeyError):
                    continue
        return entries

    @app.post('/api/studies/{study_id}/predict', status_code=201)
    async def run_local_model(study_id: str, choice: LocalPredictionRequest):
        require_study(study_id)
        model_dir = store.root / 'models' / choice.model_id
        if model_dir.is_symlink() or not model_dir.is_dir():
            raise HTTPException(404, 'Installed model not found.')
        if not inference_lock.acquire(blocking=False):
            raise HTTPException(409, 'A model run is already in progress.')
        try:
            def compute():
                from .baseline import predict_study
                payload = predict_study(store, study_id, model_dir, allow_synthetic_test=True)
                return save_predictions(store, study_id, payload)
            return await run_in_threadpool(compute)
        except ImportError as exc:
            raise HTTPException(503, 'Install the optional ML dependencies with pip install -e ".[ml]".') from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            inference_lock.release()

    @app.get('/api/studies/{study_id}/evidence-audit')
    async def evidence_audit(study_id: str):
        """Reconstruct and verify the exact locally exportable selection.

        The original ZIP (including note content and PNG bytes) is transient,
        and the response is aggregate-only, with no per-frame source details.
        """
        require_study(study_id)

        def compute():
            # Use the same application exporter that creates the user's ZIP,
            # then independently reopen its bytes using the offline auditor.
            with tempfile.TemporaryDirectory(prefix='.evidence-audit-', dir=store.root) as folder:
                archive = Path(folder) / 'review.zip'
                archive.write_bytes(export_review(store, study_id))
                verified_review = read_review_export(archive)
            return account_review_evidence(verified_review, manifest(study_id))

        try:
            return await run_in_threadpool(compute)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(422, 'The local selected images could not be verified.') from exc

    @app.get('/api/studies/{study_id}/full-span-export')
    async def full_span_export(study_id: str):
        """Opt-in, locally streamed evidence ZIP; standard review export unchanged."""
        require_study(study_id)
        folder = Path(tempfile.mkdtemp(prefix='.full-span-evidence-', dir=store.root))
        archive = folder / 'full-span-evidence.zip'
        try:
            # Export and independently verify the written ZIP before serving it.
            await run_in_threadpool(export_full_span_evidence, store, study_id, archive)
            return FileResponse(
                archive, media_type='application/zip',
                headers={'Content-Disposition': 'attachment; filename="full-span-evidence.zip"'},
                background=BackgroundTask(shutil.rmtree, folder, ignore_errors=True),
            )
        except (ValueError, FileNotFoundError) as exc:
            shutil.rmtree(folder, ignore_errors=True)
            # Errors must not disclose private local file paths in HTTP bodies.
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else
                                'A selected local image is unavailable.') from exc
        except OSError as exc:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(422, 'The selected local images could not be archived.') from exc

    @app.get('/api/studies/{study_id}/export')
    async def export(study_id: str):
        require_study(study_id)
        try:
            data = await run_in_threadpool(export_review, store, study_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(data, media_type='application/zip', headers={
            'Content-Disposition': f'attachment; filename="review-{study_id[:8]}.zip"'})

    @app.get('/')
    def home():
        return FileResponse(STATIC / 'index.html')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    return app
