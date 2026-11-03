"""Self-contained illustrated exports containing reviewer-selected material only."""

import base64
import html
import io
import json
import zipfile

from . import __version__
from .importer import now
from .store import Store

MAX_EXPORT_FRAMES = 250
MAX_EXPORT_BYTES = 128 * 1024 * 1024


def export_review(store: Store, study_id: str) -> bytes:
    with store.connect() as db:
        study = db.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
        if study is None:
            raise KeyError("Examination not found.")
        intervals = [dict(x) for x in db.execute(
            "SELECT i.id,i.start_position,i.end_position,i.note,i.created_at,"
            "a.source_index AS start_source_index,b.source_index AS end_source_index "
            "FROM review_intervals i "
            "JOIN frames a ON a.study_id=i.study_id AND a.position=i.start_position "
            "JOIN frames b ON b.study_id=i.study_id AND b.position=i.end_position "
            "WHERE i.study_id=? ORDER BY i.start_position,i.end_position,i.id",
            (study_id,)
        )]
        endpoints = sorted({
            position
            for interval in intervals
            for position in (interval['start_position'], interval['end_position'])
        })
        # Include only the two selected boundary images, never every image
        # between them. This bounds exports and does not imply a reviewed video.
        endpoint_clause = (
            " OR f.position IN (" + ",".join("?" for _ in endpoints) + ")"
            if endpoints else ""
        )
        rows = db.execute(
            "SELECT f.*,COALESCE(r.revision,0) AS revision,"
            "COALESCE(r.bookmarked,0) AS bookmarked,COALESCE(r.note,'') AS note,"
            "COALESCE(r.label,'') AS label,r.updated_at "
            "FROM frames f LEFT JOIN reviews r ON r.study_id=f.study_id AND r.position=f.position "
            "WHERE f.study_id=? AND (COALESCE(r.bookmarked,0)=1 "
            "OR COALESCE(r.note,'')<>'' OR COALESCE(r.label,'')<>''"
            + endpoint_clause + ") ORDER BY f.position",
            (study_id, *endpoints),
        ).fetchall()
        if not rows:
            raise ValueError("Save a bookmark, note, or reviewer-marked image interval before exporting.")
        if len(rows) > MAX_EXPORT_FRAMES:
            raise ValueError("This version exports at most 250 selected boundary/saved frames at once.")
        events = [dict(x) for x in db.execute(
            "SELECT position,revision,content,created_at FROM review_events WHERE study_id=? ORDER BY id",
            (study_id,)
        )]
        interval_events = [dict(x) for x in db.execute(
            "SELECT interval_id,action,start_position,end_position,note,created_at "
            "FROM review_interval_events WHERE study_id=? ORDER BY id",
            (study_id,)
        )]
    images, items, cards = [], [], []
    endpoint_set = set(endpoints)
    byte_total = 0
    for row in rows:
        image = store.images / study_id / f"{row['position']}.png"
        raw = image.read_bytes()
        byte_total += len(raw)
        if byte_total > MAX_EXPORT_BYTES:
            raise ValueError("Selected images exceed the 128-MiB export limit.")
        relative = f"images/frame_{row['position']:06d}.png"
        images.append((relative, raw))
        item = {
            "position": row["position"], "source_index": row["source_index"],
            "source_filename": row["filename"], "source_sha256": row["source_sha256"],
            "display_sha256": row["display_sha256"], "image": relative,
            "interval_boundary": row["position"] in endpoint_set,
            "review": {"revision": row["revision"], "bookmarked": bool(row["bookmarked"]),
                       "note": row["note"], "label": row["label"], "updated_at": row["updated_at"]},
        }
        items.append(item)
        frame_number = row['position'] + 1
        source_info = f" · source frame {row['source_index']}" if row['source_index'] is not None else ""
        label = html.escape(row['label'] or ('Interval boundary' if row['position'] in endpoint_set else 'Saved frame'))
        note = html.escape(row['note'] or 'No note.').replace('\n', '<br>')
        encoded = base64.b64encode(raw).decode('ascii')
        cards.append(
            f'<article><img src="data:image/png;base64,{encoded}" alt="Selected frame {frame_number}">'
            f'<div><p class="eyebrow">Frame {frame_number}{source_info}</p>'
            f'<h2>{label}</h2><p>{note}</p>'
            f'<p class="small">{html.escape(row["filename"])} · review revision {row["revision"]}</p>'
            '</div></article>'
        )
    interval_cards = []
    for interval in intervals:
        start = interval['start_position'] + 1
        end = interval['end_position'] + 1
        source_start = interval['start_source_index']
        source_end = interval['end_source_index']
        source_span = (
            f" · observed source IDs #{source_start}–#{source_end}"
            if source_start is not None and source_end is not None else ""
        )
        note = html.escape(interval['note'] or 'No interval note.').replace('\n', '<br>')
        interval_cards.append(
            f'<li><strong>Imported frames {start}–{end}</strong>'
            f'{html.escape(source_span)}. {note}</li>'
        )
    interval_section = (
        '<section><h2>Reviewer-marked image intervals</h2>'
        '<p>Only start and end image boundaries are included below. '
        'Interior images were not automatically reviewed or exported. '
        'Imported positions and source IDs are not capture timestamps or diagnosed lesions.</p>'
        '<ol>' + ''.join(interval_cards) + '</ol></section>'
        if intervals else ''
    )
    synthetic = bool(study['synthetic'])
    warning = '<p class="warning">SYNTHETIC TEST SEQUENCE — NOT CLINICAL DATA</p>' if synthetic else ''
    date = now()
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{html.escape(study['title'])} — review</title>
<style>
body{{font:16px/1.6 system-ui,sans-serif;color:#20343e;background:#f5f7f6;max-width:1050px;margin:40px auto;padding:0 24px}}
h1{{font-size:36px;line-height:1.15}}h2{{font-size:20px;margin:8px 0}}article{{display:flex;gap:24px;padding:24px;background:white;border:1px solid #d5dfdf;border-radius:12px;margin:20px 0;break-inside:avoid}}article img{{width:42%;object-fit:contain;align-self:start}}article div{{flex:1;min-width:0;overflow-wrap:anywhere}}.eyebrow,.small{{font-size:12px;color:#536974}}.warning{{padding:12px;background:#fff1c9;font-weight:700}}footer{{border-top:1px solid #ccd8da;margin-top:32px;padding-top:16px;font-size:12px}}@media(max-width:650px){{article{{display:block}}article img{{width:100%}}}}@media print{{body{{background:white;margin:0}}article{{border-radius:0}}}}
</style></head><body><p class="eyebrow">CAPSULE REVIEW · RESEARCH RECORD</p>
<h1>{html.escape(study['title'])}</h1>{warning}
<p>{len(items)} selected boundary/saved frames and {len(intervals)} marked image intervals from {study['frame_count']} imported frames. This is a reviewer-selected summary, not a complete examination or a diagnosis.</p>
<p class="small">Source: {html.escape(study['source'])}<br>Exported: {html.escape(date)}</p>
{interval_section}
{''.join(cards)}
<footer>Notes and labels are reviewer entries. Dataset annotations and model predictions are not automatically promoted into findings. No diagnostic model is bundled with Capsule Review {__version__}. Frame numbers indicate sequence positions, not measured timestamps.</footer></body></html>'''
    manifest = {
        "schema_version": 1, "application": "capsule-review", "application_version": __version__,
        "exported_at": date, "synthetic": synthetic,
        "study": {k: study[k] for k in ('id', 'title', 'source', 'frame_count', 'manifest_sha256')},
        "selection": "Bookmarked/noted frames plus interval boundary images only",
        "frames": items,
        "intervals": intervals,
        "review_history": [{**e, "content": json.loads(e['content'])} for e in events],
        "interval_history": interval_events,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('review.html', document)
        archive.writestr('review.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        for relative, raw in images:
            archive.writestr(relative, raw)
    return buffer.getvalue()
