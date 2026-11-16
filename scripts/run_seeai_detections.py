"""Produce detector suggestions using the already-preserved private SEE-AI bundle.

Synthetic studies only until checkpoint-use rights and medical-image use are
qualified. No download, conversion, unsafe deserialization or scalar scoring.
The separately licensed historical detector implementation is not redistributed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib import metadata, util
import json
from pathlib import Path
import platform
import sys
import time

from capsule_review.detections import (DetectionImport, ORIGINAL_SHA, SAFE_SHA,
                                       unletterbox_xyxy, save_detections)
from capsule_review.store import Store

QUALIFIED = {
    'SEEAI_TRUSTED_SAFE_SYNTHETIC_SMOKE.py': 'fa4bceefaa9967d4173c023b55a26f370a902bb43610335f29a20868103dfa9e',
    'seeai_576_ensemble_contract.py': 'f19448f78e6a8a6dee76c17980c6d85d45690d995238d07a37215ac18d02d070',
    'SEEAI_ARCHITECTURE_SPEC_20261110.json': '62e5ef36b302407a59ab655a81e5ce302f7788bfea02359ec427a3e10216936b',
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def require_hash(path, expected):
    if path.is_symlink() or digest(path) != expected:
        raise ValueError('Preserved source/weight identity changed: ' + path.name)


def authenticated_module(path, expected):
    require_hash(path, expected)
    name = '_detection_' + path.stem
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def run(data_dir, study_id, bundle, output, run_id):
    started = time.monotonic()
    if output.exists():
        raise FileExistsError('Never overwrite detection evidence.')
    store = Store(data_dir)
    study = store.study(study_id)
    if not study or not study['synthetic'] or study['frame_count'] > 32:
        raise ValueError('This qualification runner requires a synthetic study of at most 32 frames.')
    qualified = bundle / 'runner' / 'qualified'
    paths = {name: qualified / name for name in QUALIFIED}
    for name, expected in QUALIFIED.items():
        require_hash(paths[name], expected)
    weights = [bundle / 'weights' / f'SEEAI_best_model{i}_state_dict_only.safetensors' for i in (1, 2, 3)]
    for path, expected in zip(weights, SAFE_SHA):
        require_hash(path, expected)
    # Optional runtime is loaded only after artifact authentication.
    import cv2
    import numpy as np
    import torch
    from safetensors.torch import load_file
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.set_default_dtype(torch.float32)
    torch.set_float32_matmul_precision('highest')
    cv2.setNumThreads(1)
    graph = authenticated_module(paths['SEEAI_TRUSTED_SAFE_SYNTHETIC_SMOKE.py'], QUALIFIED['SEEAI_TRUSTED_SAFE_SYNTHETIC_SMOKE.py'])
    contract = authenticated_module(paths['seeai_576_ensemble_contract.py'], QUALIFIED['seeai_576_ensemble_contract.py'])
    blueprint = json.loads(paths['SEEAI_ARCHITECTURE_SPEC_20261110.json'].read_bytes())
    from capsule_review.detections import CLASSES
    if tuple(blueprint['spec']['class_names']) != CLASSES:
        raise ValueError('Detector category order changed.')
    models = []
    for path in weights:
        state = load_file(path, device='cpu')
        model = graph.Graph(blueprint['spec'], state)
        model.load_state_dict(state, strict=True)
        models.append(model.eval().requires_grad_(False))
    with store.connect() as db:
        sources = [dict(row) for row in db.execute('SELECT * FROM frames WHERE study_id=? ORDER BY position', (study_id,))]
    frames = []
    for source in sources:
        if time.monotonic() - started > 300:
            raise TimeoutError('Synthetic detector qualification exceeded five minutes; no output published.')
        path = store.images / study_id / f"{source['position']}.png"
        require_hash(path, source['display_sha256'])
        # Importer has already applied EXIF orientation and stripped metadata.
        bgr = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None or bgr.shape[:2] != (source['height'], source['width']):
            raise ValueError('Display decode or oriented dimensions changed.')
        tensor = contract.prepare_rgb_tensor(bgr)
        with torch.inference_mode():
            decoded = contract.concatenate_ensemble([model(tensor) for model in models])
            scores = (decoded[0, :, 4:5] * decoded[0, :, 5:]).amax(dim=0).tolist()
            detections = contract.nms_v5_semantics(decoded)[0].tolist()
        boxes = []
        for x1, y1, x2, y2, confidence, category in detections:
            try:
                xyxy = unletterbox_xyxy([x1,y1,x2,y2], (source['width'],source['height']),
                                       (tensor.shape[-1],tensor.shape[-2]))
            except ValueError:
                # Padding-only boxes have no displayed area; never fabricate one.
                continue
            boxes.append({'category': int(category), 'score': confidence, 'xyxy': xyxy})
        frames.append({key: source[key] for key in ('position','source_sha256','display_sha256','width','height')} |
                      {'category_scores': scores, 'boxes': boxes})
    implementation = {name: expected for name, expected in QUALIFIED.items()}
    implementation['run_seeai_detections.py'] = digest(Path(__file__))
    import capsule_review.detections as schema
    implementation['detections.py'] = digest(Path(schema.__file__))
    payload = DetectionImport.model_validate({
        'schema_version': 'capsule-review-detections-v1', 'run_id': run_id,
        'manifest_sha256': study['manifest_sha256'], 'frames': frames,
        'provenance': {
            'profile': 'seeai-v5-source-reviewed-v1',
            'original_checkpoint_sha256': list(ORIGINAL_SHA), 'safetensors_sha256': list(SAFE_SHA),
            'implementation_sha256': implementation,
            'runtime': {'python': platform.python_version(), 'device': 'cpu', 'precision': 'float32',
                        'fusion': 'unfused', 'batch_size': '1', 'threads': '4',
                        **{p: metadata.version(p) for p in ('torch','torchvision','numpy','opencv-python-headless','safetensors')}},
            'source_reference': 'yolov5-v5.0-f5b8f7d54c9fa69210da0177fec7ac2d9e4a627c',
            'preprocessing': 'display-rgb-exif-transposed-opencv-linear-auto-letterbox576-stride32-pad114-fp32-v1',
            'postprocessing': 'concat3-best-class-objectness-product-gt0.1-class-nms0.45-max300-v1',
            'coordinate_space': 'display-xyxy-pixels-unrounded-v1',
            'category_score_definition': 'pre-nms-float32-max-objectness-times-class-across-three-models'}})
    for name, expected in QUALIFIED.items():
        require_hash(paths[name], expected)
    for path, expected in zip(weights, SAFE_SHA):
        require_hash(path, expected)
    # Save an independently inspectable JSON first. Failed DB import leaves evidence,
    # never a successful run; duplicate IDs cannot replace previous records.
    with output.open('x') as handle:
        handle.write(payload.model_dump_json(indent=2) + '\n')
    result = save_detections(store, study_id, payload)
    print(json.dumps(result | {'elapsed_seconds': time.monotonic()-started}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--study-id', required=True)
    parser.add_argument('--bundle', type=Path, required=True, help='Preserved private assets/seeai folder')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    run(args.data_dir, args.study_id, args.bundle, args.output, args.run_id)
