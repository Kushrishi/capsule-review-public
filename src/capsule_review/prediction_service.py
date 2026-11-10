"""Persist validated prediction runs without modifying reviewer notes."""

import sqlite3

from .importer import now
from .models import Prediction, PredictionImport
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


def align_fixed_development_scores(
    store: Store, study_id: str, scores: dict, label: str, *, exam: int | None = None
) -> list[Prediction]:
    """Match one complete 512-image historical study by original index and SHA.

    Read-only: individual importers must validate their own frozen experiment
    receipts, allowed examinations, CSV schema, score ranges and row counts
    before calling this function. No source labels or human reviews are read.
    The domain-adapted importer has an exam-qualified two-study score map;
    older CNN and frozen-probe importers supply one-study score maps.
    """
    study = store.study(study_id)
    if study is None or study.get("synthetic") or study.get("frame_count") != 512:
        raise ValueError("Target must be an existing 512-frame real study.")
    with store.connect() as db:
        rows = list(db.execute(
            "SELECT position,source_index,source_sha256 FROM frames "
            "WHERE study_id=? ORDER BY position", (study_id,)
        ))
    if len(rows) != 512 or any(row["position"] != i for i, row in enumerate(rows)):
        raise ValueError("Expected exactly 512 ordered original source frames.")
    if len({(row["source_index"], row["source_sha256"]) for row in rows}) != 512:
        raise ValueError("Duplicate original source-frame identity.")
    predictions = []
    for row in rows:
        key = (row["source_index"], row["source_sha256"])
        if exam is not None:
            key = (exam, *key)
        if key not in scores:
            raise ValueError("Saved image hashes/source indices differ from frozen predictions.")
        predictions.append(Prediction(
            position=row["position"], image_sha256=row["source_sha256"],
            label=label, score=scores[key]
        ))
    return predictions
