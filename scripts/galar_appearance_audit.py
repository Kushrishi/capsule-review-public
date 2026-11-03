"""Source-verified descriptive Galar appearance audit for already examined cases.

No training, thresholds, checkpoint selection or hidden evaluation cases. Outputs
aggregate medians/IQRs suitable for Git, and *separate private* per-frame data.
Requires only Pillow and the Python standard library, not Torch or GPU.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import fmean, median
import zipfile

from PIL import Image, ImageChops, ImageOps, ImageStat

EXPECTED_SPEC_BLOB = '60b790cc0919f2d80a2d708c77cb08d162149b32'
EXAMS = (25, 27, 29)
MODEL_COLUMNS = ('original_checkpoint', 'original_only_continued',
                 'expanded_continued', 'red_excess')
FEATURES = ('mean_luminance', 'mean_saturation', 'mean_positive_red_excess',
            'high_luminance_fraction', 'low_luminance_fraction',
            'mean_edge_difference', 'source_width_div_height',
            'padded_black_fraction')
ARCHIVES = {
    25: ('galar25-verified-source.zip', 'private-per-image-scores.csv',
         ('examination', 'source_frame', 'blood_label', 'original_image_sha256')),
    27: ('galar27-verified-source.zip', 'private-source-scores.csv',
         ('exam', 'frame', 'blood', 'source_image_sha256')),
    29: ('galar-exam29-verified-source.zip', 'private-predictions.csv',
         ('exam', 'frame', 'blood', 'source_image_sha256')),
}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha(source: bytes) -> str:
    payload = b'blob ' + str(len(source)).encode('ascii') + b'\0' + source
    return hashlib.sha1(payload).hexdigest()


def load_locked_spec(path: Path) -> dict:
    raw = path.read_bytes()
    if git_blob_sha(raw) != EXPECTED_SPEC_BLOB:
        raise ValueError('Committed appearance audit protocol blob changed.')
    doc = json.loads(raw)
    if (doc['population']['exams'] != list(EXAMS)
            or doc['population']['reference_images_per_exam'] != 512
            or set(f['name'] for f in doc['predefined_appearance_features']) != set(FEATURES)
            or set(doc['reference_model_scores']['names']) != set(MODEL_COLUMNS)
            or not doc['reporting']['no_significance_testing']
            or doc['reporting']['no_claim_of_causal_mechanism'] is not True):
        raise ValueError('Frozen appearance analysis plan changed.')
    return doc


def check_binary_label(value: str) -> int:
    if value not in ('0', '1'):
        raise ValueError('Unknown or invalid source blood label; never coerce to zero.')
    return int(value)


def scores_from_verified_repro(path: Path, exam: int, expected_sha: str) -> dict[int, dict]:
    if exam not in EXAMS:
        raise ValueError('Access to unapproved Galar examination denied.')
    csvname = ARCHIVES[exam][1]
    fields = ARCHIVES[exam][2]
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(csvname)
    if digest_bytes(raw) != expected_sha:
        raise ValueError('Private saved score CSV SHA-256 mismatch.')
    rows = {}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        study = int(row[fields[0]])
        frame = int(row[fields[1]])
        label = check_binary_label(row[fields[2]])
        sha = row[fields[3]]
        reference = int(row['reference_uniform'])
        if (study != exam or frame < 0 or frame in rows
                or reference not in (0, 1)
                or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha)):
            raise ValueError('Saved reference scores have unexpected identity or role.')
        values = {}
        for name in MODEL_COLUMNS:
            value = float(row[name])
            if not math.isfinite(value) or not (0 <= value <= 1):
                raise ValueError('Nonfinite or out-of-range frozen model score.')
            values[name] = value
        rows[frame] = {'exam': exam, 'frame': frame, 'blood': label,
                       'reference_uniform': reference,
                       'image_sha256': sha, 'scores': values}
    return rows


def original_red_excess(image: Image.Image) -> float:
    """Reproduce the existing center-crop red-excess comparator, unchanged."""
    centered = ImageOps.fit(image, (96, 96), method=Image.Resampling.BICUBIC)
    r, g, b = centered.split()
    excess = ImageChops.subtract(r, ImageChops.lighter(g, b))
    return ImageStat.Stat(excess).mean[0] / 255.0


def _appearance_features_scalar(original_rgb: Image.Image) -> dict[str, float]:
    """Dependency-free reference implementation of the eight fixed features."""
    width, height = original_rgb.size
    if min(width, height) < 1:
        raise ValueError('Invalid original PNG dimensions.')
    padded = ImageOps.pad(original_rgb, (96, 96),
                          method=Image.Resampling.BILINEAR, color=(0, 0, 0))
    raw = padded.tobytes()
    if len(raw) != 96 * 96 * 3:
        raise ValueError('Padded source image is not 96x96 RGB.')
    lum = [0.0] * (96 * 96)
    sat_total = red_total = bright = dark = black = 0.0
    for p in range(96 * 96):
        i = 3 * p
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        mx, mn = max(r, g, b), min(r, g, b)
        lum[p] = l
        sat_total += (mx - mn) / mx if mx else 0.0
        red_total += max(r - max(g, b), 0) / 255.0
        bright += l >= 0.95
        dark += l <= 0.10
        black += mx == 0
    n = 96 * 96
    horizontal = sum(abs(lum[96 * y + x] - lum[96 * y + x + 1])
                     for y in range(96) for x in range(95)) / (96 * 95)
    vertical = sum(abs(lum[96 * y + x] - lum[96 * (y + 1) + x])
                   for y in range(95) for x in range(96)) / (95 * 96)
    return {
        'mean_luminance': fmean(lum),
        'mean_saturation': sat_total / n,
        'mean_positive_red_excess': red_total / n,
        'high_luminance_fraction': bright / n,
        'low_luminance_fraction': dark / n,
        'mean_edge_difference': (horizontal + vertical) / 2.0,
        'source_width_div_height': width / height,
        'padded_black_fraction': black / n,
    }



def appearance_features(original_rgb: Image.Image) -> dict[str, float]:
    """Fast NumPy computation with mathematically equivalent Pillow-only fallback.

    NumPy is an optional acceleration, never an unrecorded feature or model change.
    """
    try:
        import numpy as np
    except ImportError:
        return _appearance_features_scalar(original_rgb)
    width, height = original_rgb.size
    if min(width, height) < 1:
        raise ValueError('Invalid original PNG dimensions.')
    padded = ImageOps.pad(original_rgb, (96, 96),
                          method=Image.Resampling.BILINEAR, color=(0, 0, 0))
    pixels = np.asarray(padded, dtype=np.float64)
    if pixels.shape != (96, 96, 3):
        raise ValueError('Padded source image is not 96x96 RGB.')
    r, g, b = (pixels[:, :, i] for i in range(3))
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = np.divide(mx - mn, mx, out=np.zeros_like(mx), where=mx != 0)
    excess = np.maximum(r - np.maximum(g, b), 0.0) / 255.0
    edge = (float(np.mean(np.abs(lum[:, 1:] - lum[:, :-1])))
            + float(np.mean(np.abs(lum[1:, :] - lum[:-1, :])))) / 2.0
    return {
        'mean_luminance': float(np.mean(lum)),
        'mean_saturation': float(np.mean(sat)),
        'mean_positive_red_excess': float(np.mean(excess)),
        'high_luminance_fraction': float(np.mean(lum >= 0.95)),
        'low_luminance_fraction': float(np.mean(lum <= 0.10)),
        'mean_edge_difference': edge,
        'source_width_div_height': width / height,
        'padded_black_fraction': float(np.mean(mx == 0)),
    }


def read_study_images(outer_path: Path, exam: int, spec: dict,
                      scores: dict[int, dict]) -> list[dict]:
    if exam not in EXAMS:
        raise ValueError('Access to unapproved Galar source examination denied.')
    item = next(x for x in spec['source']['private_images_and_scores'] if x['exam'] == exam)
    inner_name = ARCHIVES[exam][0]
    with zipfile.ZipFile(outer_path) as outer:
        # This is an original private GitHub Actions artifact; verify its inner
        # immutable original-image ZIP rather than trusting filenames alone.
        source_bytes = outer.read(inner_name)
    if digest_bytes(source_bytes) != item['inner_original_zip_sha256']:
        raise ValueError('Original medical image source ZIP SHA-256 mismatch.')
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as source:
        manifest = source.read('verified-private-manifest.json')
        if digest_bytes(manifest) != item['private_manifest_sha256']:
            raise ValueError('Source frames/labels manifest changed.')
        allrows = json.loads(manifest)
        if len(allrows) != item['union_count'] or len(scores) != item['union_count']:
            raise ValueError('Original source or score population changed.')
        refs = []
        seen = set()
        for row in allrows:
            frame = row['frame']
            if (type(frame) is not int or frame < 0 or frame in seen
                    or row['exam'] != exam or row['filename'] != f'frame_{frame:06d}.PNG'
                    or type(row['blood']) is not int or row['blood'] not in (0, 1)
                    or row['reference_uniform'] not in (0, 1)):
                raise ValueError('Medical image source identity or binary label changed.')
            seen.add(frame)
            saved = scores.get(frame)
            if (saved is None or saved['exam'] != exam
                    or saved['blood'] != row['blood']
                    or saved['reference_uniform'] != row['reference_uniform']
                    or saved['image_sha256'] != row['source_image_sha256']):
                raise ValueError('Saved prediction and original image/label identities differ.')
            if not row['reference_uniform']:
                continue
            raw_image = source.read(f'images/{exam:03d}/{row["filename"]}')
            if (len(raw_image) != row['source_bytes']
                    or digest_bytes(raw_image) != row['source_image_sha256']):
                raise ValueError('Actual selected reference PNG bytes changed.')
            with Image.open(io.BytesIO(raw_image)) as checked:
                if checked.format != 'PNG':
                    raise ValueError('Original source image is not PNG.')
                checked.verify()
            with Image.open(io.BytesIO(raw_image)) as source_im:
                oriented = ImageOps.exif_transpose(source_im).convert('RGB')
                oriented.load()
                red = original_red_excess(oriented)
                if abs(red - saved['scores']['red_excess']) > 1e-7:
                    raise ValueError('Frozen red-excess image score cannot be independently reproduced.')
                metrics = appearance_features(oriented)
            refs.append({'exam': exam, 'frame': frame, 'blood': row['blood'],
                         'source_sha256': row['source_image_sha256'],
                         **saved['scores'], **metrics})
        if len(seen) != item['union_count'] or set(seen) != set(scores):
            raise ValueError('Extra or missing original source prediction identity.')
    refs.sort(key=lambda x: x['frame'])
    expected_pos = int(spec['population']['positive_support_by_exam'][str(exam)])
    if len(refs) != 512 or sum(x['blood'] for x in refs) != expected_pos:
        raise ValueError('Frozen label-blind reference support mismatched.')
    return refs


def percentile(values: list[float], fraction: float) -> float:
    if not values or not 0 <= fraction <= 1:
        raise ValueError('Nonempty data and valid percentile required.')
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * fraction
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * (k - lo)


def describe(values: list[float]) -> dict:
    if not values or any(not math.isfinite(x) for x in values):
        raise ValueError('All observed feature values must be finite.')
    return {'n':len(values), 'median':round(median(values), 6),
            'p25':round(percentile(values, 0.25), 6),
            'p75':round(percentile(values, 0.75), 6),
            'mean':round(fmean(values), 6)}


def aggregate(studies: dict[int, list[dict]], spec: dict) -> dict:
    results = {}
    for exam in EXAMS:
        rows = studies[exam]
        if len(rows) != 512:
            raise ValueError('Partial reference cohort must not be summarized.')
        strata = {}
        for label in (0, 1):
            group = [x for x in rows if x['blood'] == label]
            strata[str(label)] = {name:describe([x[name] for x in group])
                                  for name in (*FEATURES, *MODEL_COLUMNS)}
        counts = {str(label): sum(x['blood'] == label for x in rows) for label in (0, 1)}
        ten = {}
        for name in MODEL_COLUMNS:
            ranked = sorted(rows, key=lambda x:(-x[name], x['frame']))[:51]
            ten[name] = sum(x['blood'] for x in ranked)
        results[str(exam)] = {
            'reference_images':512,
            'label_counts':counts,
            'prespecified_feature_descriptives_by_label':strata,
            'frozen_model_reference_hits_at_10pct':ten,
            'frozen_model_score_positive_minus_negative_median':{
                name:round(strata['1'][name]['median']-strata['0'][name]['median'], 6)
                for name in MODEL_COLUMNS
            },
        }
    return {
        'study':'Capsule Review descriptive post-hoc Galar appearance failure audit',
        'protocol_blob_sha': EXPECTED_SPEC_BLOB,
        'examinations':list(EXAMS),
        'reference_scope':'Only previously selected label-blind 512-image samples; no enriched-only frames',
        'features':list(FEATURES),
        'frozen_model_scores':list(MODEL_COLUMNS),
        'by_examination':results,
        'no_training_or_model_selection':True,
        'independent_clinical_validation':False,
        'patient_independence_confirmed':False,
        'interpretation_limits':spec['limits'] + [
            'This is explicitly post-hoc descriptive error characterization after seeing model outcomes.',
            'Reported medians/IQRs cannot establish causality, clinical pathology or model improvement.',
            'Blood-positive frames may be serially correlated within a few annotation runs; do not treat them as independent lesions.'
        ],
        'per_image_identifiers_or_pixels_committed':False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    for exam in EXAMS:
        parser.add_argument(f'--source-{exam}',type=Path,required=True)
        parser.add_argument(f'--scores-{exam}',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,
                        help='New private output folder; do not reuse.')
    a = parser.parse_args(argv)
    if not a.output.parent.is_dir():
        parser.error('Output parent must exist; never create implicit parent path.')
    if a.output.exists():
        parser.error('Research output directory exists; refuse to overwrite.')
    spec = load_locked_spec(a.spec)
    studies = {}
    for exam in EXAMS:
        cfg = next(x for x in spec['source']['private_images_and_scores'] if x['exam']==exam)
        scores = scores_from_verified_repro(getattr(a, f'scores_{exam}'), exam,
                                            cfg['private_scores_sha256'])
        studies[exam] = read_study_images(getattr(a, f'source_{exam}'), exam, spec, scores)
        print(f'Exam {exam}: verified {len(studies[exam])} label-blind source PNGs',flush=True)
    results = aggregate(studies, spec)
    a.output.mkdir(parents=True, exist_ok=False)
    private = a.output / 'private-per-image-features.csv'
    with private.open('x', encoding='utf8', newline='') as stream:
        fields = ('exam','frame','source_sha256','blood',*MODEL_COLUMNS,*FEATURES)
        writer = csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        for exam in EXAMS:
            for row in studies[exam]:
                writer.writerow(row)
    (a.output/'aggregate.json').write_text(
        json.dumps(results, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf8')
    receipt = {'protocol_blob_sha': EXPECTED_SPEC_BLOB,
               'private_individual_feature_csv_sha256':file_sha256(private),
               'aggregate_sha256':file_sha256(a.output/'aggregate.json'),
               'source_examinations':list(EXAMS),
               'verified_reference_pngs':sum(len(x) for x in studies.values()),
               'clinical_validation':False,
               'original_images_and_per_frame_data_must_remain_private':True}
    (a.output/'private-reproduction-receipt.json').write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'source_examinations':list(EXAMS),'aggregate_sha256':receipt['aggregate_sha256'],
                      'private_individual_csv_sha256':receipt['private_individual_feature_csv_sha256']},indent=2))


if __name__ == '__main__':
    main()
