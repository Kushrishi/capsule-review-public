"""Separate, immutable detector suggestions bound to imported source and display bytes.

No detector code, weights, scalar ranking or clinical labels are bundled here.
Hashes authenticate correspondence, not the truth of a model's suggestions.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re
import sqlite3
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .importer import now

CLASSES = ('angiodysplasia', 'erosion', 'stenosis', 'lymphangiectasis',
           'lymph follicle', 'SMT', 'polyp like', 'bleeding', 'diverticula',
           'redness', 'foreign body', 'venous')
ORIGINAL_SHA = (
    '204287f67fce0bbc91302ddb236f600ba2b92a91fb7d9113090ebf7970998471',
    '2811e8298993821a213ecdaede3e5f1abebfec0b9cb4f83d3be371b2923f85f4',
    '22c1ada26ea493987f9ffdb5019735b1a9ea3284d0dd8d334c4afd2441a78bf1')
SAFE_SHA = (
    'f1f9f2de9f6caeae9fb9531cfd7afc907103e5a3229bc0b6dda98c87c122ccf7',
    '9a5e7203d2c5dce6abb592637509bd0fb52b18c4b8590ede8420fa4d99984ea7',
    '4b713943346416ac6023eae7f2a2313554ee1843da04ae7deaa7cbc6c32992fe')
Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Provenance(Record):
    profile: Literal['seeai-v5-source-reviewed-v1', 'synthetic-fixture-v1']
    original_checkpoint_sha256: list[Digest] = Field(min_length=3, max_length=3)
    safetensors_sha256: list[Digest] = Field(min_length=3, max_length=3)
    implementation_sha256: dict[str, Digest] = Field(min_length=1, max_length=20)
    runtime: dict[str, str] = Field(min_length=1, max_length=20)
    source_reference: Literal['yolov5-v5.0-f5b8f7d54c9fa69210da0177fec7ac2d9e4a627c']
    preprocessing: Literal['display-rgb-exif-transposed-opencv-linear-auto-letterbox576-stride32-pad114-fp32-v1']
    postprocessing: Literal['concat3-best-class-objectness-product-gt0.1-class-nms0.45-max300-v1']
    coordinate_space: Literal['display-xyxy-pixels-unrounded-v1']
    category_score_definition: Literal['pre-nms-float32-max-objectness-times-class-across-three-models']

    @model_validator(mode='after')
    def identities(self):
        if self.profile == 'seeai-v5-source-reviewed-v1' and (
                tuple(self.original_checkpoint_sha256) != ORIGINAL_SHA or
                tuple(self.safetensors_sha256) != SAFE_SHA):
            raise ValueError('SEE-AI checkpoint roster differs from preserved assets.')
        return self


class Box(Record):
    category: Annotated[StrictInt, Field(ge=0, lt=12)]
    score: Score
    xyxy: list[Annotated[float, Field(strict=True, allow_inf_nan=False)]] = Field(min_length=4, max_length=4)


class Frame(Record):
    position: Annotated[StrictInt, Field(ge=0)]
    source_sha256: Digest
    display_sha256: Digest
    width: Annotated[StrictInt, Field(gt=0, le=24000000)]
    height: Annotated[StrictInt, Field(gt=0, le=24000000)]
    category_scores: list[Score] = Field(min_length=12, max_length=12)
    boxes: list[Box] = Field(max_length=300)

    @model_validator(mode='after')
    def geometry(self):
        for box in self.boxes:
            x1, y1, x2, y2 = box.xyxy
            if not (0 <= x1 < x2 <= self.width and 0 <= y1 < y2 <= self.height):
                raise ValueError('Box is outside the oriented display image or degenerate.')
            if box.score <= .1 or box.score > self.category_scores[box.category] + 1e-7:
                raise ValueError('Box confidence conflicts with detector category scores.')
        return self


class DetectionImport(Record):
    schema_version: Literal['capsule-review-detections-v1']
    run_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')]
    manifest_sha256: Digest
    provenance: Provenance
    frames: list[Frame] = Field(min_length=1, max_length=200000)


def unletterbox_xyxy(box, display_size, tensor_size):
    """Invert historical scale_coords using actual tensor shape, then clip.

    Input must be inferred from the EXIF-corrected display RGB pixels. Raw-camera
    coordinates are deliberately unsupported. No integer rounding is applied.
    """
    width, height = display_size
    tw, th = tensor_size
    if (min(width, height, tw, th) <= 0 or tw % 32 or th % 32 or
            len(box) != 4 or not all(math.isfinite(float(x)) for x in box)):
        raise ValueError('Invalid letterbox geometry.')
    gain = min(th / height, tw / width)
    px, py = (tw - width * gain) / 2, (th - height * gain) / 2
    x1, y1, x2, y2 = box
    result = [max(0., min(float(width), (x1-px)/gain)),
              max(0., min(float(height), (y1-py)/gain)),
              max(0., min(float(width), (x2-px)/gain)),
              max(0., min(float(height), (y2-py)/gain))]
    if result[0] >= result[2] or result[1] >= result[3]:
        raise ValueError('Detector box has no area in the display image.')
    return result


def save_detections(store, study_id, payload: DetectionImport):
    # Whole-run validation and insertion are atomic; never edit notes/predictions.
    raw = payload.model_dump_json()
    if len(raw.encode()) > 64 * 1024 * 1024:
        raise ValueError('Detection records exceed 64 MiB.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        study = db.execute('SELECT * FROM studies WHERE id=?', (study_id,)).fetchone()
        if not study or payload.manifest_sha256 != study['manifest_sha256']:
            raise ValueError('Imported source manifest does not match.')
        if payload.provenance.profile == 'synthetic-fixture-v1' and not study['synthetic']:
            raise ValueError('Synthetic detector fixtures require a synthetic study.')
        rows = db.execute('SELECT * FROM frames WHERE study_id=? ORDER BY position', (study_id,)).fetchall()
        if [f.position for f in payload.frames] != list(range(study['frame_count'])):
            raise ValueError('Exactly one ordered record per imported frame is required; missing is not negative.')
        for frame, row in zip(payload.frames, rows):
            for key in ('source_sha256', 'display_sha256', 'width', 'height'):
                if getattr(frame, key) != row[key]:
                    raise ValueError('Frame identity or oriented geometry differs.')
            image = store.images / study_id / f'{frame.position}.png'
            if sha256(image.read_bytes()).hexdigest() != frame.display_sha256:
                raise ValueError('Stored display bytes changed.')
        try:
            cursor = db.execute('INSERT INTO detection_runs(study_id,run_id,provenance,created_at,payload_sha256) VALUES(?,?,?,?,?)',
                                (study_id, payload.run_id, payload.provenance.model_dump_json(), now(), sha256(raw.encode()).hexdigest()))
        except sqlite3.IntegrityError as exc:
            raise ValueError('Detection run already exists; use a new run ID.') from exc
        db.executemany('INSERT INTO detection_frames(run_id,position,record) VALUES(?,?,?)',
                       [(cursor.lastrowid, f.position, f.model_dump_json()) for f in payload.frames])
        db.executemany('INSERT INTO detection_category_frames VALUES(?,?,?)',
                       [(cursor.lastrowid, category, f.position) for f in payload.frames
                        for category in ({-1} | {b.category for b in f.boxes} if f.boxes else set())])
        db.execute('INSERT INTO detection_indexed_runs VALUES(?)', (cursor.lastrowid,))
    return {'run_id': payload.run_id, 'frames': len(payload.frames), 'status': 'MODEL_SUGGESTIONS_ONLY'}


def detection_runs(store, study_id):
    with store.connect() as db:
        return [{**dict(row), 'provenance': json.loads(row['provenance']),
                 'execution_verification': 'IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED'} for row in db.execute(
            'SELECT run_id,provenance,created_at,payload_sha256 FROM detection_runs WHERE study_id=? ORDER BY id DESC', (study_id,))]


def detection_frames(store, study_id, run_id, category=None, position=None, *, after=-1, limit=200):
    """Keyset lookup; decode only the requested page, never the full recording."""
    if not 1 <= limit <= 200:
        raise ValueError('Detection page size must be in 1..200.')
    with store.connect() as db:
        run = db.execute('SELECT id FROM detection_runs WHERE study_id=? AND run_id=?', (study_id, run_id)).fetchone()
        if not run:
            raise ValueError('Detection run not found.')
        if position is not None:
            sql = 'SELECT record FROM detection_frames WHERE run_id=? AND position=? AND position>? LIMIT ?'
            args = [run['id'], position, after, limit]
        else:
            sql = ('SELECT f.record FROM detection_category_frames i JOIN detection_frames f '
                   'ON f.run_id=i.run_id AND f.position=i.position '
                   'WHERE i.run_id=? AND i.category=? AND i.position>? ORDER BY i.position LIMIT ?')
            args = [run['id'], -1 if category is None else category, after, limit]
        result = []
        for row in db.execute(sql, args):
            frame = json.loads(row['record'])
            if category is not None:
                frame['boxes'] = [b for b in frame['boxes'] if b['category'] == category]
            if position is not None or frame['boxes']:
                result.append(frame)
        return result
