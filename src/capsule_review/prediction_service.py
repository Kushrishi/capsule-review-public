"""Persist validated prediction runs without modifying reviewer notes."""

import sqlite3

from .importer import now
from .models import PredictionImport
from .store import Store


class DuplicateRunError(ValueError):
    pass


def save_predictions(store: Store, study_id: str, payload: PredictionImport) -> dict:
    if study_id != payload.study_id or store.study(study_id) is None:
        raise ValueError('Prediction study identity does not match.')
    try:
        with store.connect() as db:
            identities = {r['position']: r['source_sha256'] for r in db.execute(
                'SELECT position,source_sha256 FROM frames WHERE study_id=?', (study_id,))}
            seen = set()
            for item in payload.predictions:
                if identities.get(item.position) != item.image_sha256:
                    raise ValueError(f'Image identity mismatch at position {item.position}.')
                key = (item.position, item.label)
                if key in seen:
                    raise ValueError('Duplicate prediction for this frame and label.')
                seen.add(key)
            result = db.execute(
                'INSERT INTO prediction_runs(study_id,run_id,model_json,created_at) VALUES(?,?,?,?)',
                (study_id, payload.model.run_id, payload.model.model_dump_json(), now()))
            run_id = result.lastrowid
            db.executemany('INSERT INTO predictions VALUES(?,?,?,?,?)', [
                (run_id, study_id, p.position, p.label, p.score) for p in payload.predictions])
        return {'run_id': run_id, 'count': len(payload.predictions)}
    except sqlite3.IntegrityError as exc:
        raise DuplicateRunError('That model run already exists for this examination.') from exc
