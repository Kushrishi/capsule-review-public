"""A small anatomy classifier with recorded inputs and a local viewer connection.

No pretrained weights or dataset are downloaded by this module. Synthetic training
is for software tests only and cannot be installed in the normal model catalogue.
"""

import hashlib
import io
import json
import math
import random
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .baseline_data import ANATOMY_CLASSES, canonical, digest, load_manifest, read_json, safe_path
from .importer import now
from .models import PredictionImport
from .store import Store

ARCHITECTURE = 'capsule-cnn-v1'
INPUT_SIZE = 96
MAX_WEIGHTS_BYTES = 8 * 1024 * 1024


class AnatomyCNN(nn.Module):
    def __init__(self, classes: int):
        super().__init__()
        blocks, channels = [], [3, 16, 32, 64]
        for before, after in zip(channels, channels[1:]):
            blocks.extend([nn.Conv2d(before, after, 3, stride=2, padding=1),
                           nn.GroupNorm(4, after), nn.ReLU()])
        self.features = nn.Sequential(*blocks, nn.AdaptiveAvgPool2d(1))
        self.classifier = nn.Linear(64, classes)

    def forward(self, images):
        return self.classifier(self.features(images).flatten(1))


def image_tensor(path: Path) -> torch.Tensor:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im = ImageOps.pad(im, (INPUT_SIZE, INPUT_SIZE), method=Image.Resampling.BILINEAR, color=(0, 0, 0))
        pixels = np.array(im, dtype=np.float32, copy=True) / 255.0
    return torch.from_numpy(pixels.transpose(2, 0, 1).copy())


class Frames(Dataset):
    def __init__(self, root: Path, records: list[dict], classes: list[str]):
        self.root, self.records, self.classes = root, records, classes

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.records[index]
        return image_tensor(safe_path(self.root, row['path'])), self.classes.index(row['label'])


def classification_metrics(truth: list[int], predictions: list[int], exams: list[str], classes: list[str]) -> dict:
    if not truth or len(truth) != len(predictions) or len(truth) != len(exams):
        raise ValueError('Nonempty aligned labels, predictions and examination IDs are required.')
    size = len(classes)
    if any(type(x) is not int or not 0 <= x < size for x in [*truth, *predictions]):
        raise ValueError('Class index is outside the declared vocabulary.')
    matrix = np.zeros((size, size), dtype=int)
    exam_counts = defaultdict(lambda: [0, 0])
    for y, p, exam in zip(truth, predictions, exams):
        matrix[y, p] += 1
        exam_counts[exam][0] += int(y == p)
        exam_counts[exam][1] += 1
    per_class, recalls, f1s = {}, [], []
    for i, name in enumerate(classes):
        tp, support, predicted = int(matrix[i, i]), int(matrix[i, :].sum()), int(matrix[:, i].sum())
        precision, recall = (tp / predicted if predicted else None), (tp / support if support else None)
        f1 = 2 * tp / (support + predicted) if support else None
        per_class[name] = {'reference_count': support, 'prediction_count': predicted,
                           'precision': precision, 'recall': recall, 'f1': f1}
        if support:
            recalls.append(recall)
            f1s.append(f1)
    exam_accuracy = {key: val[0] / val[1] for key, val in sorted(exam_counts.items())}
    return {'frames': len(truth), 'examinations': len(exam_accuracy),
            'accuracy': float(np.trace(matrix) / matrix.sum()),
            'mean_examination_accuracy': float(np.mean(list(exam_accuracy.values()))),
            'balanced_accuracy_supported_classes': float(np.mean(recalls)),
            'macro_f1_supported_classes': float(np.mean(f1s)),
            'per_class': per_class, 'confusion_matrix': matrix.tolist(),
            'class_order': classes, 'per_examination_accuracy': exam_accuracy}


def _evaluate(model, loader, device) -> tuple[list[int], list[int], float]:
    model.eval()
    truth, predicted, total_loss = [], [], 0.0
    with torch.inference_mode():
        for x, y in loader:
            logits = model(x.to(device))
            if not torch.isfinite(logits).all():
                raise ValueError('Non-finite model outputs; no result accepted.')
            total_loss += nn.functional.cross_entropy(logits, y.to(device), reduction='sum').item()
            truth.extend(y.tolist())
            predicted.extend(logits.argmax(1).cpu().tolist())
    return truth, predicted, total_loss / len(truth)


def _save_json(path: Path, value: dict):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def train(manifest_path: Path, images: Path, output: Path, *, epochs: int = 10,
          batch_size: int = 32, learning_rate: float = 0.001, seed: int = 17,
          device: str = 'cpu', allow_synthetic_test: bool = False) -> dict:
    if not 1 <= epochs <= 1000 or not 1 <= batch_size <= 512:
        raise ValueError('Epochs must be 1–1000; batch size must be 1–512.')
    if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1 or not 0 <= seed < 2**32:
        raise ValueError('Invalid learning rate or seed.')
    if device not in {'cpu', 'cuda', 'mps'}:
        raise ValueError('Device must be cpu, cuda or mps.')
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA is not available.')
    if device == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('Apple MPS is not available.')
    if output.exists():
        raise ValueError('Output directory already exists; choose a new run directory.')
    manifest = load_manifest(manifest_path, images)
    synthetic = manifest['data_kind'] == 'synthetic-test'
    if synthetic and not allow_synthetic_test:
        raise ValueError('Synthetic training is only allowed with --allow-synthetic-test.')
    root = images.expanduser().resolve(strict=True)
    classes = manifest['classes']
    train_rows = [r for r in manifest['records'] if r['split'] == 'train']
    validation_rows = [r for r in manifest['records'] if r['split'] == 'validation']
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model = AnatomyCNN(len(classes)).to(device)
    generator = torch.Generator().manual_seed(seed)
    fitting = DataLoader(Frames(root, train_rows, classes), batch_size=batch_size, shuffle=True,
                         generator=generator, num_workers=0)
    validation = DataLoader(Frames(root, validation_rows, classes), batch_size=batch_size, shuffle=False,
                            num_workers=0)
    counts = Counter(row['label'] for row in train_rows)
    weights = torch.tensor([len(train_rows) / (len(classes) * counts[c]) for c in classes],
                           dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.0001)
    output.mkdir(parents=True, exist_ok=False)
    _save_json(output / 'status.json', {'status': 'running'})
    try:
        _save_json(output / 'dataset.json', manifest)
        best_loss, history, best_epoch = float('inf'), [], None
        for epoch in range(1, epochs + 1):
            model.train()
            total_loss, samples = 0.0, 0
            for x, y in fitting:
                optimizer.zero_grad(set_to_none=True)
                loss = loss_fn(model(x.to(device)), y.to(device))
                if not torch.isfinite(loss):
                    raise ValueError('Training produced a non-finite loss.')
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(y)
                samples += len(y)
            _, _, val_loss = _evaluate(model, validation, device)
            history.append({'epoch': epoch, 'training_loss_batch_average': total_loss / samples,
                            'validation_loss': val_loss})
            if val_loss < best_loss:
                best_loss, best_epoch = val_loss, epoch
                torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, output / 'weights.pt')
            _save_json(output / 'history.json', {'epochs': history})
        state = torch.load(output / 'weights.pt', map_location='cpu', weights_only=True)
        model.load_state_dict(state)
        truth, predicted, val_loss = _evaluate(model, validation, device)
        exams = [r['exam_id'] for r in validation_rows]
        majority = max(range(len(classes)), key=lambda i: counts[classes[i]])
        report = {'evaluation_role': 'development validation; also used for checkpoint selection',
                  'data_kind': manifest['data_kind'], 'split_unit': manifest['split_unit'],
                  'clinical_validation': False, 'best_epoch': best_epoch, 'validation_loss': val_loss,
                  'model': classification_metrics(truth, predicted, exams, classes),
                  'training_majority_baseline': classification_metrics(truth, [majority] * len(truth), exams, classes)}
        metadata = {'format': 'capsule-anatomy-model-v1', 'architecture': ARCHITECTURE,
                    'classes': classes, 'input_size': INPUT_SIZE,
                    'preprocessing': 'EXIF orientation; RGB; aspect-preserving pad to 96px; bilinear; divide by 255',
                    'data_kind': manifest['data_kind'], 'clinical_validation': False,
                    'split_unit': manifest['split_unit'], 'manifest_sha256': manifest['manifest_sha256'],
                    'weights_sha256': digest((output / 'weights.pt').read_bytes()),
                    'training': {'epochs': epochs, 'batch_size': batch_size, 'learning_rate': learning_rate,
                                 'seed': seed, 'device': device, 'class_weights': weights.cpu().tolist()},
                    'training_image_sha256': sorted({r['source_sha256'] for r in train_rows}),
                    'training_pixels_sha256': sorted({r['pixels_sha256'] for r in train_rows}),
                    'training_exams': sorted({r['exam_id'] for r in train_rows}),
                    'validation_exams': sorted({r['exam_id'] for r in validation_rows}),
                    'torch_version': str(torch.__version__), 'numpy_version': np.__version__,
                    'created_at': datetime.now(timezone.utc).isoformat()}
        # Reject a run if any selected image changed while training.
        load_manifest(manifest_path, images)
        metadata['implementation_sha256'] = {p.name: digest(p.read_bytes()) for p in [Path(__file__), Path(__file__).with_name('baseline_data.py')]}
        _save_json(output / 'metrics.json', report)
        _save_json(output / 'model.json', metadata)
        _save_json(output / 'status.json', {'status': 'complete'})
        return report
    except BaseException as exc:
        _save_json(output / 'status.json', {'status': 'failed', 'error': type(exc).__name__, 'detail': str(exc)[:500]})
        raise


def load_model(run_dir: Path, *, allow_synthetic_test: bool = False):
    run_dir = run_dir.expanduser().resolve(strict=True)
    paths = [run_dir / name for name in ['status.json', 'model.json', 'weights.pt']]
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError('Model files must be regular files.')
    if read_json(paths[0], 4096).get('status') != 'complete':
        raise ValueError('Training did not complete.')
    metadata = read_json(paths[1], 8 * 1024 * 1024)
    if metadata.get('format') != 'capsule-anatomy-model-v1' or metadata.get('architecture') != ARCHITECTURE:
        raise ValueError('Unsupported model format or architecture.')
    classes = metadata.get('classes', [])
    if len(classes) < 2 or len(classes) > 5 or len(set(classes)) != len(classes) or not set(classes) <= set(ANATOMY_CLASSES):
        raise ValueError('Invalid model vocabulary.')
    if metadata.get('input_size') != INPUT_SIZE or metadata.get('data_kind') not in {'galar', 'synthetic-test'}:
        raise ValueError('Unsupported preprocessing or data kind.')
    if metadata['data_kind'] == 'synthetic-test' and not allow_synthetic_test:
        raise ValueError('A synthetic software-test model is not an endoscopy model.')
    if not 0 < paths[2].stat().st_size <= MAX_WEIGHTS_BYTES:
        raise ValueError('Model weights exceed the supported size.')
    raw = paths[2].read_bytes()
    if digest(raw) != metadata.get('weights_sha256'):
        raise ValueError('Model weight checksum does not match.')
    try:
        state = torch.load(io.BytesIO(raw), map_location='cpu', weights_only=True)
    except Exception as exc:
        raise ValueError('Cannot read the tensor-only model checkpoint.') from exc
    model = AnatomyCNN(len(classes))
    if not isinstance(state, dict) or set(state) != set(model.state_dict()):
        raise ValueError('Unexpected model parameters.')
    expected = model.state_dict()
    for key, value in state.items():
        if not isinstance(value, torch.Tensor) or value.shape != expected[key].shape or not torch.isfinite(value).all():
            raise ValueError('Invalid or non-finite model tensor.')
    model.load_state_dict(state, strict=True)
    model.eval()
    return model, metadata


def install_model(store: Store, run_dir: Path, *, allow_synthetic_test: bool = False) -> str:
    _, metadata = load_model(run_dir, allow_synthetic_test=allow_synthetic_test)
    model_id = digest(canonical(metadata))[:24]
    root = store.root / 'models'
    root.mkdir(exist_ok=True)
    destination = root / model_id
    if destination.exists():
        raise ValueError('This exact model is already installed.')
    temporary = Path(tempfile.mkdtemp(prefix='.install-', dir=root))
    try:
        for name in ['weights.pt', 'model.json', 'status.json', 'metrics.json']:
            source = run_dir / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('Missing model artifact.')
            shutil.copyfile(source, temporary / name)
        load_model(temporary, allow_synthetic_test=allow_synthetic_test)
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return model_id


def predict_study(store: Store, study_id: str, run_dir: Path, *, allow_training_overlap: bool = False,
                  allow_synthetic_test: bool = False, batch_size: int = 32) -> PredictionImport:
    study = store.study(study_id)
    if not study:
        raise ValueError('Examination not found.')
    if not 1 <= batch_size <= 512:
        raise ValueError('Batch size must be 1–512.')
    model, metadata = load_model(run_dir, allow_synthetic_test=allow_synthetic_test)
    if study['synthetic'] and metadata['data_kind'] != 'synthetic-test':
        raise ValueError('Do not apply an endoscopy model to the synthetic demonstration.')
    if not study['synthetic'] and metadata['data_kind'] == 'synthetic-test':
        raise ValueError('A software-test model cannot run on a real examination.')
    with store.connect() as db:
        frames = [dict(r) for r in db.execute('SELECT * FROM frames WHERE study_id=? ORDER BY position', (study_id,))]
    if len(frames) > 200_000:
        raise ValueError('The local inference limit is 200000 frames per run.')
    train_hashes = set(metadata.get('training_image_sha256', []))
    train_pixels = set(metadata.get('training_pixels_sha256', []))
    overlap = False
    for frame in frames:
        path = store.images / study_id / f'{frame["position"]}.png'
        if path.is_symlink() or digest(path.read_bytes()) != frame['display_sha256']:
            raise ValueError('Stored display image was modified; no predictions saved.')
        with Image.open(path) as image:
            rgb = image.convert('RGB')
            pixel_hash = digest(f'{rgb.width}x{rgb.height}:RGB:'.encode() + rgb.tobytes())
        overlap |= frame['source_sha256'] in train_hashes or pixel_hash in train_pixels
    if overlap and not allow_training_overlap:
        raise ValueError('This examination contains training images. Refusing to present in-sample output as held-out use.')
    predictions = []
    torch.set_num_threads(2)
    with torch.inference_mode():
        for start in range(0, len(frames), batch_size):
            batch = frames[start:start + batch_size]
            inputs = torch.stack([image_tensor(store.images / study_id / f'{r["position"]}.png') for r in batch])
            scores = model(inputs).softmax(1)
            if not torch.isfinite(scores).all():
                raise ValueError('Non-finite predictions; no outputs saved.')
            for row, vector in zip(batch, scores.tolist()):
                top = max(range(len(vector)), key=vector.__getitem__)
                predictions.append({'position': row['position'], 'image_sha256': row['source_sha256'],
                                    'label': metadata['classes'][top], 'score': vector[top]})
    name = 'Software-test model — NOT MEDICAL' if metadata['data_kind'] == 'synthetic-test' else 'Anatomy baseline — research only'
    description = ('Anatomical region only, not lesion detection. Forced choice among: ' + ', '.join(metadata['classes']) +
                   '. Scores are uncalibrated. No clinical validation. ' +
                   ('Contains training images; in-sample demonstration. ' if overlap else 'No exact training-image overlap found; patient independence is not established. '))
    return PredictionImport.model_validate({'schema_version': 1, 'study_id': study_id,
        'model': {'name': name, 'version': ARCHITECTURE, 'run_id': uuid.uuid4().hex,
                  'weights_sha256': metadata['weights_sha256'], 'description': description}, 'predictions': predictions})
