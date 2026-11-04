"""Generated PNGs/CSV only: preserve an ineligible source gap through evaluation."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image

from capsule_review import private_source_gate as gate


def test_explicit_eligible_population_keeps_gap_and_primary_workload(tmp_path, monkeypatch):
    images = tmp_path / 'generated'
    images.mkdir()
    # A nonexistent annotation row is not a missing eligible image.
    frames = [f for f in range(0, 155, 5) if f != 10]
    records = []
    for i, frame in enumerate(frames):
        name = f'synthetic-{frame}.png'
        Image.new('RGB', (4, 5), (i, 40, 80)).save(images / name)
        records.append({'frame': frame, 'name': name,
                        'sha256': hashlib.sha256((images / name).read_bytes()).hexdigest()})
    content = io.StringIO(newline='')
    writer = csv.writer(content)
    writer.writerow(['frame', 'blood'])
    writer.writerows((f, '1') for f in frames)
    labels = tmp_path / 'synthetic.zip'
    with zipfile.ZipFile(labels, 'w') as z:
        z.writestr('11.csv', content.getvalue())
        z.writestr('61.csv', 'SYNTHETIC RESERVED MEMBER MUST NOT OPEN')
    original = Path(__file__).resolve().parents[1] / 'docs/GALAR_UNSEEN_11_20_EVALUATION_LOCK.json'
    spec = json.loads(original.read_text())
    spec['publisher']['expected_sha256'] = hashlib.sha256(labels.read_bytes()).hexdigest()
    protocol = tmp_path / 'synthetic-protocol.json'
    protocol.write_text(json.dumps(spec))
    snapshot = tmp_path / 'private-synthetic-snapshot.json'
    digest = gate.freeze_private_queues(
        image_root=images, image_records=records, scores=[i / len(frames) for i in range(len(frames))],
        examination_id=11, expected_first=frames[0], expected_last=frames[-1],
        expected_count=len(frames), expected_source_frames=frames,
        weights_sha256=spec['original_model']['weights_sha256'], protocol_path=protocol,
        destination=snapshot,
    )
    visited = []
    read = zipfile.ZipFile.read

    def tracked(self, member, *args, **kwargs):
        visited.append(member.filename if hasattr(member, 'filename') else member)
        return read(self, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, 'read', tracked)
    outcome = gate.evaluate_private_snapshot(
        destination=snapshot, expected_snapshot_sha256=digest, image_root=images,
        protocol_path=protocol, labels_zip=labels, exam=11,
    )
    assert visited == ['11.csv']
    assert outcome['imported_annotated_images'] == 30  # No invented 31st candidate.
    assert outcome['positive_annotation_runs'] == 2  # Positive on both sides, still split.
    assert outcome['primary_workload_percent'] == 10
    primary = next(row for row in outcome['review_results'] if row['review_percent'] == 10)
    assert primary['review_images'] == 3
    full = next(row for row in outcome['review_results'] if row['review_percent'] == 100)
    assert all(result['distinct_positive_annotation_runs_hit'] == 2 for result in full['policies'].values())
    assert all(result['positive_annotated_images_hit'] == 30 for result in full['policies'].values())
