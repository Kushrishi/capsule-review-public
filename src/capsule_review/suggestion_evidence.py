"""Bounded, read-only export of imported suggestions, separate from human findings."""
import json

MAX_SUGGESTION_BYTES = 8 * 1024 * 1024


def snapshot_suggestions(db, study_id, positions):
    """Use the caller's SQLite read transaction and only its exported positions.

    Provenance is preserved as imported claims, not verified model execution.
    The original complete detection-payload digest is not a digest of this subset.
    """
    selected = json.dumps(sorted(positions))
    result = {'schema_version': 'capsule-review-model-suggestions-v1',
              'status': 'MODEL_SUGGESTIONS_ONLY', 'scope': 'exported_frames_only',
              'execution_verification': 'IMPORTED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED',
              'prediction_runs': [], 'detection_runs': []}
    used = 0
    def account(value):
        nonlocal used
        used += len(value.encode('utf-8'))
        if used > MAX_SUGGESTION_BYTES:
            raise ValueError('Exported model suggestions exceed the 8-MiB metadata limit. Select fewer frames.')

    previous = None
    for row in db.execute(
        'SELECT r.id,r.run_id,r.model_json,r.created_at,p.position,p.label,p.score,f.source_sha256 '
        'FROM prediction_runs r JOIN predictions p ON p.run_id=r.id '
        'JOIN frames f ON f.study_id=r.study_id AND f.position=p.position '
        'WHERE r.study_id=? AND p.position IN (SELECT value FROM json_each(?)) '
        'ORDER BY r.id,p.position,p.label', (study_id, selected)):
        if row['id'] != previous:
            account(row['model_json'])
            run = {'run_id': row['run_id'], 'model': json.loads(row['model_json']),
                   'created_at': row['created_at'], 'predictions': []}
            result['prediction_runs'].append(run)
            previous = row['id']
        prediction = {'position': row['position'], 'image_sha256': row['source_sha256'],
                      'label': row['label'], 'score': row['score']}
        account(json.dumps(prediction))
        run['predictions'].append(prediction)

    previous = None
    for row in db.execute(
        'SELECT r.id,r.run_id,r.provenance,r.created_at,r.payload_sha256,f.record '
        'FROM detection_runs r JOIN detection_frames f ON f.run_id=r.id '
        'WHERE r.study_id=? AND f.position IN (SELECT value FROM json_each(?)) '
        'ORDER BY r.id,f.position', (study_id, selected)):
        if row['id'] != previous:
            account(row['provenance'])
            run = {'run_id': row['run_id'], 'provenance': json.loads(row['provenance']),
                   'created_at': row['created_at'], 'payload_sha256': row['payload_sha256'],
                   'payload_digest_scope': 'original_complete_imported_run', 'frames': []}
            result['detection_runs'].append(run)
            previous = row['id']
        account(row['record'])
        run['frames'].append(json.loads(row['record']))
    return result
