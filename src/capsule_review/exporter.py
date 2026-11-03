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
        rows = db.execute(
            "SELECT f.*,r.revision,r.bookmarked,r.note,r.label,r.updated_at "
            "FROM frames f JOIN reviews r ON r.study_id=f.study_id AND r.position=f.position "
            "WHERE f.study_id=? AND (r.bookmarked=1 OR r.note<>'' OR r.label<>'') "
            "ORDER BY f.position", (study_id,)
        ).fetchall()
        if not rows:
            raise ValueError("Save a bookmark or note before exporting.")
        if len(rows) > MAX_EXPORT_FRAMES:
            raise ValueError("This version exports at most 250 saved frames at once.")
        events = [dict(x) for x in db.execute(
            "SELECT position,revision,content,created_at FROM review_events WHERE study_id=? ORDER BY id",
            (study_id,)
        )]
    images, items, cards = [], [], []
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
            "review": {"revision": row["revision"], "bookmarked": bool(row["bookmarked"]),
                       "note": row["note"], "label": row["label"], "updated_at": row["updated_at"]},
        }
        items.append(item)
        frame_number = row['position'] + 1
        source_info = f" · source frame {row['source_index']}" if row['source_index'] is not None else ""
        label = html.escape(row['label'] or 'Saved frame')
        note = html.escape(row['note'] or 'No note.').replace('\n', '<br>')
        encoded = base64.b64encode(raw).decode('ascii')
        cards.append(
            f'<article><img src="data:image/png;base64,{encoded}" alt="Selected frame {frame_number}">'
            f'<div><p class="eyebrow">Frame {frame_number}{source_info}</p>'
            f'<h2>{label}</h2><p>{note}</p>'
            f'<p class="small">{html.escape(row["filename"])} · review revision {row["revision"]}</p>'
            '</div></article>'
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
<p>{len(items)} saved frames from {study['frame_count']} imported frames. This is a reviewer-selected summary, not a complete examination or a diagnosis.</p>
<p class="small">Source: {html.escape(study['source'])}<br>Exported: {html.escape(date)}</p>
{''.join(cards)}
<footer>Notes and labels are reviewer entries. Dataset annotations and model predictions are not automatically promoted into findings. No diagnostic model is bundled with Capsule Review {__version__}. Frame numbers indicate sequence positions, not measured timestamps.</footer></body></html>'''
    manifest = {
        "schema_version": 1, "application": "capsule-review", "application_version": __version__,
        "exported_at": date, "synthetic": synthetic,
        "study": {k: study[k] for k in ('id', 'title', 'source', 'frame_count', 'manifest_sha256')},
        "selection": "Bookmarked frames and frames with reviewer notes or labels",
        "frames": items,
        "review_history": [{**e, "content": json.loads(e['content'])} for e in events],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('review.html', document)
        archive.writestr('review.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        for relative, raw in images:
            archive.writestr(relative, raw)
    return buffer.getvalue()
