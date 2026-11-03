"""SQLite metadata and owned image storage; one explicit revision per frame review."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS studies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 0,
    frame_count INTEGER NOT NULL CHECK(frame_count > 0),
    manifest_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS frames (
    study_id TEXT NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    source_index INTEGER,
    filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    display_sha256 TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    reference_labels TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(study_id,position)
);
CREATE TABLE IF NOT EXISTS reviews (
    study_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    bookmarked INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    updated_at TEXT,
    PRIMARY KEY(study_id,position),
    FOREIGN KEY(study_id,position) REFERENCES frames(study_id,position) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS prediction_runs (
    id INTEGER PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    model_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(study_id,run_id)
);
CREATE TABLE IF NOT EXISTS predictions (
    run_id INTEGER NOT NULL REFERENCES prediction_runs(id) ON DELETE CASCADE,
    study_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    label TEXT NOT NULL,
    score REAL NOT NULL CHECK(score >= 0 AND score <= 1),
    PRIMARY KEY(run_id,position,label),
    FOREIGN KEY(study_id,position) REFERENCES frames(study_id,position) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS review_events (
    id INTEGER PRIMARY KEY,
    study_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Appending tables via CREATE IF NOT EXISTS upgrades existing workspaces safely.
CREATE TABLE IF NOT EXISTS review_intervals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 2000),
    created_at TEXT NOT NULL,
    CHECK(start_position < end_position),
    UNIQUE(study_id, start_position, end_position),
    FOREIGN KEY(study_id, start_position) REFERENCES frames(study_id, position),
    FOREIGN KEY(study_id, end_position) REFERENCES frames(study_id, position)
);
CREATE INDEX IF NOT EXISTS idx_review_intervals_study
    ON review_intervals(study_id, start_position, end_position);
CREATE TABLE IF NOT EXISTS review_interval_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    interval_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('created', 'deleted')),
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.images = self.root / "images"
        self.images.mkdir(exist_ok=True)
        self.db_path = self.root / "reviews.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def study(self, study_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["synthetic"] = bool(result["synthetic"])
            result["bookmark_count"] = db.execute(
                "SELECT COUNT(*) FROM reviews WHERE study_id=? AND bookmarked=1", (study_id,)
            ).fetchone()[0]
            result["runs"] = [
                {"id": x["id"], "model": json.loads(x["model_json"]), "created_at": x["created_at"]}
                for x in db.execute(
                    "SELECT * FROM prediction_runs WHERE study_id=? ORDER BY id DESC", (study_id,)
                )
            ]
            return result

    def frame(self, study_id: str, position: int) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM frames WHERE study_id=? AND position=?", (study_id, position)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["reference_labels"] = json.loads(result["reference_labels"])
            review = db.execute(
                "SELECT * FROM reviews WHERE study_id=? AND position=?", (study_id, position)
            ).fetchone()
            result["review"] = dict(review) if review else {
                "revision": 0, "bookmarked": False, "note": "", "label": "", "updated_at": None,
            }
            result["review"]["bookmarked"] = bool(result["review"]["bookmarked"])
            result["predictions"] = [
                {"label": x["label"], "score": x["score"], "model": json.loads(x["model_json"])}
                for x in db.execute(
                    "SELECT p.*,r.model_json FROM predictions p JOIN prediction_runs r "
                    "ON r.id=p.run_id WHERE p.study_id=? AND p.position=? "
                    "ORDER BY r.id DESC, p.score DESC", (study_id, position)
                )
            ]
            return result
