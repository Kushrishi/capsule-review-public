import csv
import io
import json

import random
import pytest
from PIL import Image, PngImagePlugin

from capsule_review.baseline_data import ANATOMY_CLASSES, canonical, digest, load_manifest, prepare_manifest


def make_dataset(root, exams=(1, 2, 3), classes=('stomach', 'colon'), frames_per_class=4):
    images, annotations = root / 'images', root / 'labels'
    images.mkdir(parents=True); annotations.mkdir()
    for exam in exams:
        folder = images / f'{exam:03d}'; folder.mkdir()
        rows = []
        for frame in range(len(classes) * frames_per_class):
            label = classes[frame % len(classes)]
            rng = random.Random(exam * 1000 + frame)
            pixels = bytes(rng.randrange(25) + (180 if channel == frame % len(classes) else 0)
                           for _ in range(36 * 48) for channel in range(3))
            Image.frombytes('RGB', (48, 36), pixels).save(folder / f'frame_{frame:06d}.PNG')
            rows.append({'frame': frame, **{c: int(c == label) for c in ANATOMY_CLASSES}})
        with (annotations / f'{exam}.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['frame', *ANATOMY_CLASSES]); writer.writeheader(); writer.writerows(rows)
    return images, annotations


@pytest.fixture
def local_data(tmp_path):
    return make_dataset(tmp_path / 'data')


def prepared(tmp_path, local_data, **kwargs):
    images, annotations = local_data
    output = tmp_path / 'manifest.json'
    result = prepare_manifest(images, annotations, output, validation_exams=[3],
                              classes=('stomach', 'colon'), data_kind='synthetic-test', **kwargs)
    return images, output, result


def test_examination_split_and_test_holdout(tmp_path, local_data):
    images, labels = local_data
    (images / '061').mkdir(); (images / '061' / 'frame_000000.PNG').write_bytes(b'NOT AN IMAGE')
    (labels / '61.csv').write_text('deliberately invalid reserved annotations')
    _, path, result = prepared(tmp_path, local_data)
    assert {r['exam_id'] for r in result['records'] if r['split'] == 'train'} == {'1', '2'}
    assert {r['exam_id'] for r in result['records'] if r['split'] == 'validation'} == {'3'}
    assert len(result['records']) == 24
    assert result['counts']['train'] == {'stomach': 8, 'colon': 8}
    assert load_manifest(path, images) == result


def test_duplicate_pixels_even_with_different_png_metadata(tmp_path, local_data):
    images, _ = local_data
    with Image.open(images/'001/frame_000000.PNG') as im:
        meta = PngImagePlugin.PngInfo(); meta.add_text('different', 'encoding')
        im.save(images/'003/frame_000000.PNG', pnginfo=meta)
    with pytest.raises(ValueError, match='Identical decoded'):
        prepared(tmp_path, local_data)
    assert not (tmp_path/'manifest.json').exists()


def test_patient_overlap_rejected(tmp_path, local_data):
    with pytest.raises(ValueError, match='patient group'):
        prepared(tmp_path, local_data, patient_groups={'1': 'person-a', '2': 'person-b', '3': 'person-a'})


def test_patient_groups_not_exposed_as_raw_ids(tmp_path, local_data):
    _, _, manifest = prepared(tmp_path, local_data, patient_groups={'1':'person-a','2':'person-b','3':'person-c'})
    assert manifest['split_unit'] == 'provided_patient_group'
    assert 'person-a' not in json.dumps(manifest)


def test_missing_training_class_is_not_silently_removed(tmp_path, local_data):
    images, labels = local_data
    with pytest.raises(ValueError, match='no examples'):
        prepare_manifest(images, labels, tmp_path/'missing.json', validation_exams=[3], data_kind='synthetic-test')


def test_single_exam_is_not_randomly_frame_split(tmp_path):
    images, labels = make_dataset(tmp_path/'single', exams=(1,))
    with pytest.raises(ValueError, match='training and one validation'):
        prepare_manifest(images, labels, tmp_path/'one.json', validation_exams=[1], classes=('stomach','colon'))


def test_unknown_and_unlabelled_rows_are_reported(tmp_path, local_data):
    images, labels = local_data
    path = labels/'1.csv'
    rows = list(csv.DictReader(path.open()))
    rows[0]['stomach']=''
    for key in ANATOMY_CLASSES: rows[1][key]='0'
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['frame',*ANATOMY_CLASSES]);writer.writeheader();writer.writerows(rows)
    _, _, result = prepared(tmp_path, local_data)
    assert result['examinations'][0]['excluded_counts'] == {'unknown_annotation':1, 'no_anatomy_label':1}
    assert len(result['records']) == 22


@pytest.mark.parametrize('value', ['NaN','-1','2','text'])
def test_invalid_one_hot_values_rejected(tmp_path, local_data, value):
    _, labels = local_data
    path=labels/'1.csv'; rows=list(csv.DictReader(path.open()));rows[0]['stomach']=value
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['frame',*ANATOMY_CLASSES]);w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError): prepared(tmp_path,local_data)


def test_image_change_detected(tmp_path,local_data):
    images,path,result=prepared(tmp_path,local_data)
    Image.new('RGB',(48,36),'blue').save(images/result['records'][0]['path'])
    with pytest.raises(ValueError,match='Image changed'):load_manifest(path,images)


def test_manifest_tamper_detected(tmp_path,local_data):
    images,path,result=prepared(tmp_path,local_data);result['records'][0]['split']='validation'
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError,match='hash'):load_manifest(path,images)


def test_path_traversal_rejected_even_if_rehashed(tmp_path,local_data):
    images,path,result=prepared(tmp_path,local_data);result['records'][0]['path']='../outside.png'
    result['manifest_sha256']=digest(canonical({k:v for k,v in result.items() if k!='manifest_sha256'}))
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError,match='inside'):load_manifest(path,images)


def test_duplicate_frame_index_rejected(tmp_path,local_data):
    images,_=local_data
    (images/'001/frame_0.png').write_bytes((images/'001/frame_000000.PNG').read_bytes())
    with pytest.raises(ValueError,match='Duplicate source frame'):prepared(tmp_path,local_data)


def test_uniform_sampling_has_explicit_counts(tmp_path,local_data):
    _,_,result=prepared(tmp_path,local_data,max_frames_per_exam=4)
    assert [r['frame'] for r in result['records'] if r['exam_id']=='3'] == [0,2,4,7]
    assert result['examinations'][0]['sampled_frames'] == 4


def test_manifest_no_overwrite(tmp_path,local_data):
    prepared(tmp_path,local_data)
    with pytest.raises(ValueError,match='already exists'):prepared(tmp_path,local_data)
