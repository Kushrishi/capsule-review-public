"""Build a frozen development manifest from local Galar images and annotations."""

import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

from .importer import FRAME_RE, MAX_FILE_BYTES, MAX_PIXELS, read_galar_labels

ANATOMY_CLASSES = ('mouth', 'esophagus', 'stomach', 'small intestine', 'colon')
MANIFEST_FORMAT = 'capsule-development-v1'
HEX = re.compile(r'^[a-f0-9]{64}$')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_json(path: Path, limit: int = 32 * 1024 * 1024) -> dict:
    if path.stat().st_size > limit:
        raise ValueError(f'JSON exceeds the {limit}-byte limit: {path.name}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    return data


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise ValueError('Manifest image paths must be relative and inside the image root.')
    candidate = root / path
    if any(p.is_symlink() for p in [candidate, *candidate.parents] if p != root.parent):
        raise ValueError('Symlinked dataset paths are not supported.')
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError('Manifest path is not an image within the image root.')
    return resolved


def image_identity(path: Path) -> tuple[str, str]:
    if not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError(f'Invalid image size: {path.name}')
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        if im.format not in {'PNG', 'JPEG', 'WEBP'} or getattr(im, 'n_frames', 1) != 1:
            raise ValueError('Only static PNG, JPEG and WebP images are supported.')
        if im.width * im.height > MAX_PIXELS:
            raise ValueError('Image exceeds the pixel limit.')
        im = ImageOps.exif_transpose(im).convert('RGB')
        pixels = f'{im.width}x{im.height}:RGB:'.encode() + im.tobytes()
    return digest(raw), digest(pixels)


def _annotation_class(labels: dict, classes: tuple[str, ...]) -> tuple[str | None, str]:
    # Require all five columns. Missing values do not mean "not diseased".
    bits = []
    for name in ANATOMY_CLASSES:
        value = labels.get(name)
        if value is None:
            return None, 'unknown_annotation'
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Invalid binary anatomy annotation: {name}={value!r}') from exc
        if not math.isfinite(number) or number not in {0.0, 1.0}:
            raise ValueError(f'Anatomy annotations must be 0 or 1: {name}={value!r}')
        bits.append(number)
    positives = [name for name, value in zip(ANATOMY_CLASSES, bits) if value == 1]
    if len(positives) > 1:
        raise ValueError('A frame has multiple positive anatomy labels; resolve the annotation first.')
    if not positives:
        return None, 'no_anatomy_label'
    label = positives[0]
    return (label, '') if label in classes else (None, 'outside_selected_classes')


def prepare_manifest(images: Path, annotations: Path, output: Path, *, validation_exams: list[int],
                     max_frames_per_exam: int = 512, classes: tuple[str, ...] = ANATOMY_CLASSES,
                     data_kind: str = 'galar', patient_groups: dict[str, str] | None = None) -> dict:
    """Reserve Galar examinations 61+; no test labels or pixels are opened.

    An explicit validation examination list is required. Sampling is uniform in
    source-frame order *before* reading class values, never balanced using validation
    labels. Exact decoded-image duplicates across train/validation cause failure.
    """
    if data_kind not in {'galar', 'synthetic-test'}:
        raise ValueError('Choose galar or synthetic-test data explicitly.')
    if len(classes) < 2 or len(set(classes)) != len(classes) or not set(classes) <= set(ANATOMY_CLASSES):
        raise ValueError('Select at least two unique supported anatomy classes.')
    if not 2 <= max_frames_per_exam <= 100_000:
        raise ValueError('Frames per examination must be between 2 and 100000.')
    validation = {int(x) for x in validation_exams}
    if not validation or not validation <= set(range(1, 61)):
        raise ValueError('Validation IDs must be explicit Galar development examinations 1–60.')
    if output.exists():
        raise ValueError('Manifest already exists; use a new path instead of overwriting a split.')
    images, annotations = images.expanduser().resolve(strict=True), annotations.expanduser().resolve(strict=True)
    folders: dict[int, Path] = {}
    for p in images.iterdir():
        if not p.is_dir() or not p.name.isdecimal():
            continue
        number = int(p.name)
        if number < 1 or number > 60:
            continue
        if number in folders or p.is_symlink():
            raise ValueError('Duplicate examination ID or symlinked examination folder.')
        folders[number] = p
    if not validation <= folders.keys() or not (folders.keys() - validation):
        raise ValueError('Provide at least one training and one validation examination; check the IDs.')
    if patient_groups is not None:
        if any(str(k) not in patient_groups or not patient_groups[str(k)] for k in folders):
            raise ValueError('Patient grouping must cover every included examination.')
        group_roles: dict[str, set] = {}
        for n in folders:
            group_roles.setdefault(str(patient_groups[str(n)]), set()).add('validation' if n in validation else 'train')
        if any(len(roles) != 1 for roles in group_roles.values()):
            raise ValueError('A provided patient group occurs in both training and validation.')
    rows, exam_reports, pixel_roles = [], [], {}
    for number, folder in sorted(folders.items()):
        annotation_options = {annotations / f'{number}.csv', annotations / f'{number:03d}.csv'}
        existing = [p for p in annotation_options if p.is_file()]
        if len(existing) != 1:
            raise ValueError(f'Expected one annotation CSV for examination {number}.')
        label_path = existing[0]
        if label_path.is_symlink():
            raise ValueError('Symlinked annotations are not supported.')
        labels = read_galar_labels(label_path)
        candidates: dict[int, Path] = {}
        for path in folder.iterdir():
            match = FRAME_RE.fullmatch(path.name)
            if not match:
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError('Image paths must be regular files.')
            idx = int(match.group(1))
            if idx in candidates:
                raise ValueError(f'Duplicate source frame index: examination {number}, frame {idx}.')
            if idx not in labels:
                raise ValueError(f'No annotation row for examination {number}, frame {idx}.')
            candidates[idx] = path
        ordered = sorted(candidates)
        if not ordered:
            raise ValueError(f'No numbered image files in examination {number}.')
        count = min(len(ordered), max_frames_per_exam)
        # Evenly spaced positions include both endpoints. No labels used to sample.
        selected = [ordered[(i * (len(ordered) - 1)) // (count - 1)] for i in range(count)] if count > 1 else ordered
        split = 'validation' if number in validation else 'train'
        skipped, kept = Counter(), Counter()
        for idx in selected:
            label, reason = _annotation_class(labels[idx], classes)
            if label is None:
                skipped[reason] += 1
                continue
            path = candidates[idx]
            raw_hash, pixel_hash = image_identity(path)
            if pixel_hash in pixel_roles and pixel_roles[pixel_hash] != split:
                raise ValueError('Identical decoded image content occurs across train/validation; split rejected.')
            pixel_roles[pixel_hash] = split
            row = {'path': path.relative_to(images).as_posix(), 'exam_id': str(number),
                   'frame': idx, 'split': split, 'label': label,
                   'source_sha256': raw_hash, 'pixels_sha256': pixel_hash}
            if patient_groups is not None:
                row['group_id'] = digest(str(patient_groups[str(number)]).encode())
            rows.append(row)
            kept[label] += 1
        exam_reports.append({'exam_id': str(number), 'split': split, 'available_frames': len(ordered),
                             'annotation_rows': len(labels), 'sampled_frames': len(selected),
                             'included_class_counts': dict(kept), 'excluded_counts': dict(skipped),
                             'annotation_sha256': digest(label_path.read_bytes())})
    if not rows or {r['split'] for r in rows} != {'train', 'validation'}:
        raise ValueError('Both splits need eligible labelled frames.')
    counts = {part: {label: sum(r['split'] == part and r['label'] == label for r in rows)
                     for label in classes} for part in ['train', 'validation']}
    missing = [label for label in classes if counts['train'][label] == 0]
    if missing:
        raise ValueError(f'Training data have no examples of {missing}. Increase the sample or explicitly select fewer classes.')
    result = {'format': MANIFEST_FORMAT, 'data_kind': data_kind, 'classes': list(classes),
              'split_unit': 'provided_patient_group' if patient_groups is not None else 'examination',
              'validation_exams': sorted(validation), 'reserved_test_exams': '61–80: not opened',
              'sampling': {'method': 'uniform-by-position-before-label-filter', 'max_frames_per_exam': max_frames_per_exam},
              'counts': counts, 'examinations': exam_reports, 'records': rows}
    result['manifest_sha256'] = digest(canonical(result))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    return result


def load_manifest(path: Path, images: Path) -> dict:
    result = read_json(path)
    expected = result.get('manifest_sha256')
    content = {k: v for k, v in result.items() if k != 'manifest_sha256'}
    if expected != digest(canonical(content)) or result.get('format') != MANIFEST_FORMAT:
        raise ValueError('Manifest hash or format is invalid.')
    if result.get('data_kind') not in {'galar', 'synthetic-test'}:
        raise ValueError('Invalid manifest data kind.')
    if result.get('split_unit') not in {'examination', 'provided_patient_group'}:
        raise ValueError('Invalid split unit.')
    classes = result.get('classes', [])
    if len(classes) < 2 or len(set(classes)) != len(classes) or not set(classes) <= set(ANATOMY_CLASSES):
        raise ValueError('Invalid manifest classes.')
    records = result.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('Manifest has no records.')
    identity, exam_roles, group_roles, pixel_roles = set(), {}, {}, {}
    root = images.expanduser().resolve(strict=True)
    for row in records:
        if not isinstance(row, dict) or type(row.get('frame')) is not int or row['frame'] < 0:
            raise ValueError('Invalid record or source frame index.')
        if not isinstance(row.get('path'), str):
            raise ValueError('Invalid image path.')
        split, label = row.get('split'), row.get('label')
        if split not in {'train', 'validation'} or label not in classes:
            raise ValueError('Unexpected split or class in manifest.')
        if not str(row.get('exam_id', '')).isdecimal() or not 1 <= int(row['exam_id']) <= 60:
            raise ValueError('Only development examinations 1–60 are accepted.')
        key = (row['exam_id'], row['frame'])
        if key in identity:
            raise ValueError('Duplicate frame identity in manifest.')
        identity.add(key)
        exam_roles.setdefault(row['exam_id'], set()).add(split)
        if result['split_unit'] == 'provided_patient_group':
            if not HEX.fullmatch(row.get('group_id', '')):
                raise ValueError('Missing patient-group identity.')
            group_roles.setdefault(row['group_id'], set()).add(split)
        raw_hash, pixel_hash = image_identity(safe_path(root, row['path']))
        if raw_hash != row.get('source_sha256') or pixel_hash != row.get('pixels_sha256'):
            raise ValueError(f'Image changed since manifest preparation: {row["path"]}')
        pixel_roles.setdefault(pixel_hash, set()).add(split)
    if any(len(v) > 1 for d in [exam_roles, group_roles, pixel_roles] for v in d.values()):
        raise ValueError('Train/validation overlap detected.')
    for part in ['train', 'validation']:
        if not any(r['split'] == part for r in records):
            raise ValueError('Both train and validation records are required.')
    if any(not any(r['split'] == 'train' and r['label'] == c for r in records) for c in classes):
        raise ValueError('Every selected class needs training examples.')
    return result
