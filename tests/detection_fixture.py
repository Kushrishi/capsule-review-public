"""Generated nonmedical suggestions; no detector or clinical labels involved."""
from capsule_review.detections import ORIGINAL_SHA, SAFE_SHA


def fixture(store, study_id):
    study = store.study(study_id)
    with store.connect() as db:
        sources = [dict(row) for row in db.execute('SELECT * FROM frames WHERE study_id=? ORDER BY position', (study_id,))]
    frames = []
    for source in sources:
        boxes = []
        scores = [0.01] * 12
        if source['position'] in (0, 2):
            category = 7 if source['position'] == 0 else 0
            scores[category] = .9
            boxes.append({'category': category, 'score': .8,
                          'xyxy': [source['width']*.1, source['height']*.2,
                                   source['width']*.7, source['height']*.8]})
        frames.append({key: source[key] for key in ('position','source_sha256','display_sha256','width','height')} |
                      {'category_scores': scores, 'boxes': boxes})
    return {'schema_version': 'capsule-review-detections-v1', 'run_id': 'generated-boxes',
            'manifest_sha256': study['manifest_sha256'], 'frames': frames,
            'provenance': {
                'profile': 'synthetic-fixture-v1',
                'original_checkpoint_sha256': ['0'*64]*3, 'safetensors_sha256': ['0'*64]*3,
                'implementation_sha256': {'generated-fixture': '0'*64}, 'runtime': {'kind': 'generated-no-model'},
                'source_reference': 'yolov5-v5.0-f5b8f7d54c9fa69210da0177fec7ac2d9e4a627c',
                'preprocessing': 'display-rgb-exif-transposed-opencv-linear-auto-letterbox576-stride32-pad114-fp32-v1',
                'postprocessing': 'concat3-best-class-objectness-product-gt0.1-class-nms0.45-max300-v1',
                'coordinate_space': 'display-xyxy-pixels-unrounded-v1',
                'category_score_definition': 'pre-nms-float32-max-objectness-times-class-across-three-models'}}
