"""End-to-end synthetic Capsule Review export -> source-run evidence audit.

Only local generated geometric PNGs and mock source annotations are used.
This does not access original Galar pixels or reserved evaluation cases.
"""
from __future__ import annotations

import io
import json
import zipfile

from PIL import Image

from capsule_review.importer import import_sources
from capsule_review.interval_evidence import evaluate_interval_evidence, read_review_export


def synthetic_image(number: int) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (48, 40), (number * 3 % 255, number * 7 % 255, 31)).save(buffer, format='PNG')
    return buffer.getvalue()


def test_local_app_review_interval_export_can_be_audited_without_inventing_span_hits(
        app, client, headers, tmp_path):
    imported_indices = (5, 10, 20, 30, 40, 50, 60, 65)
    study = import_sources(
        app.state.store,
        ((f'frame_{frame:06d}.PNG', synthetic_image(frame)) for frame in imported_indices),
        title='Synthetic interval-evidence audit fixture',
        source='Synthetic images, not original Galar data',
    )
    base = f"/api/studies/{study['id']}"
    note = client.put(f'{base}/frames/2/review', headers=headers,
                      json={'revision': 0, 'bookmarked': True, 'note': 'Synthetic evidence check'})
    assert note.status_code == 200, note.text
    interval = client.post(f'{base}/intervals', headers=headers,
                           json={'start_position': 1, 'end_position': 6,
                                 'note': 'Only synthetic boundaries were marked'})
    assert interval.status_code == 201, interval.text

    response = client.get(base + '/export')
    assert response.status_code == 200, response.text
    zip_path = tmp_path / 'synthetic-review.zip'
    zip_path.write_bytes(response.content)
    review = read_review_export(zip_path)
    manifest = client.get(base + '/manifest').json()
    assert manifest['synthetic'] is False  # Local fixture, not a diagnostic dataset.
    labels = {5: 0, 10: 0, 15: 1, 20: 1, 25: 0, 30: 0,
              35: 1, 40: 0, 45: 1, 50: 1, 55: 1, 60: 0, 65: 0}
    original_rows = [{'frame': frame, 'blood': str(label)} for frame, label in labels.items()]
    receipt = [
        {'exam': 23, 'frame': item['source_index'], 'filename': item['filename'],
         'source_image_sha256': item['source_sha256'], 'source_bytes': len(synthetic_image(item['source_index'])),
         'blood': labels[item['source_index']], 'reference_uniform': 1, 'fit_enriched': 0}
        for item in manifest['frames']
    ]
    result = evaluate_interval_evidence(review, manifest, receipt, original_rows, exam=23)
    assert result['source_positive_annotation_runs'] == 3
    assert result['imported_representable_positive_runs'] == 2
    assert result['selected_export_images'] == 3
    assert result['selected_export_positive_images'] == 1
    assert result['direct_selected_positive_annotation_runs'] == 1
    assert result['span_overlapped_source_positive_runs'] == 3
    assert result['span_overlapped_without_direct_selected_evidence'] == 2
    with zipfile.ZipFile(zip_path) as archive:
        assert 'images/frame_000001.png' in archive.namelist()
        assert 'images/frame_000002.png' in archive.namelist()
        assert 'images/frame_000006.png' in archive.namelist()
        assert 'images/frame_000003.png' not in archive.namelist()
    assert 'Synthetic evidence check' not in json.dumps(result)
    assert 'Only synthetic boundaries' not in json.dumps(result)
