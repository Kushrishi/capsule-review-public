"""Deterministic score *fixtures* for the built-in, nonmedical 24-frame demo.

These values do not come from a model, class labels, source pathology, or any
clinical inference. They exercise the real read-only selection and review UI.
"""
from __future__ import annotations

from .importer import create_demo
from .models import ModelInfo, Prediction, PredictionImport
from .prediction_service import DuplicateRunError, save_predictions
from .store import Store

DEMO_RUN_ID = "capsule-review-synthetic-demo-v1"
DEMO_LABEL = "synthetic-pattern"
DEMO_MODEL_NAME = "Generated ranking example (not AI)"
DEMO_SOURCE = "Generated software-test images"
DEMO_FRAMES = 24


def _example_score(position: int) -> float:
    """Concentrate generated high values in one span to illustrate omission."""
    if 6 <= position <= 12:
        return round(0.81 + 0.01 * ((position * 3) % 10), 3)
    return round(0.06 + 0.02 * ((position * 5) % 9), 3)


def ensure_demo_scores(store: Store, study_id: str) -> dict:
    """Add one complete, deterministic example-score stream to the built-in demo.

    An older demo from a previous release is upgraded in-place without
    overwriting reviewer notes, bookmarks, intervals or other prediction runs.
    Arbitrary imported studies (including other synthetic studies) are
    deliberately ineligible.
    """
    study = store.study(study_id)
    if not study or not (study["synthetic"] and study["title"] == "Test sequence"
                         and study["source"] == DEMO_SOURCE
                         and study["frame_count"] == DEMO_FRAMES):
        raise ValueError("Only the built-in nonmedical test sequence can receive generated demo scores.")

    with store.connect() as db:
        existing = db.execute(
            "SELECT id FROM prediction_runs WHERE study_id=? AND run_id=?",
            (study_id, DEMO_RUN_ID),
        ).fetchone()
        if existing:
            return store.study(study_id)
        identities = list(db.execute(
            "SELECT position,source_sha256 FROM frames WHERE study_id=? ORDER BY position",
            (study_id,),
        ))
    if len(identities) != DEMO_FRAMES or any(
        frame["position"] != i for i, frame in enumerate(identities)
    ):
        raise ValueError("The built-in synthetic demo has an incomplete frame identity stream.")

    payload = PredictionImport(
        schema_version=1,
        study_id=study_id,
        model=ModelInfo(
            name=DEMO_MODEL_NAME,
            version="1",
            run_id=DEMO_RUN_ID,
            description=(
                "Deterministic, generated numbers for demonstration only. "
                "Not trained AI, pathology inference, a reference annotation "
                "or a clinical probability."
            ),
        ),
        predictions=[
            Prediction(position=i, image_sha256=frame["source_sha256"],
                       label=DEMO_LABEL, score=_example_score(i))
            for i, frame in enumerate(identities)
        ],
    )
    try:
        save_predictions(store, study_id, payload)
    except DuplicateRunError:
        # Concurrent demo requests may have inserted the identical run.
        pass
    return store.study(study_id)


def open_or_create_demo(store: Store, study_id: str | None = None) -> dict:
    """Open the existing built-in fixture or create it once, then seed demo scores.

    CLI and HTTP use the same path. The optional explicit study_id is validated
    by ensure_demo_scores, so a clinical or unrelated study cannot be modified.
    Only metadata for the generated 24-frame fixture are used for discovery.
    """
    if study_id is None:
        with store.connect() as db:
            row = db.execute(
                "SELECT id FROM studies WHERE synthetic=1 AND title='Test sequence' "
                "AND source=? AND frame_count=? ORDER BY created_at, id LIMIT 1",
                (DEMO_SOURCE, DEMO_FRAMES),
            ).fetchone()
            study_id = row["id"] if row else None
        if study_id is None:
            study_id = create_demo(store)["id"]
    return ensure_demo_scores(store, study_id)
