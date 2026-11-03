import io

import pytest
from PIL import Image

from capsule_review.importer import (
    create_demo, import_folder, import_sources, natural_key, normalize_image,
    read_galar_labels, validate_filename,
)
from capsule_review.store import Store


def test_natural_order():
    assert sorted(['frame_10.PNG', 'frame_2.PNG', 'frame_1.PNG'], key=natural_key) == [
        'frame_1.PNG', 'frame_2.PNG', 'frame_10.PNG']


@pytest.mark.parametrize('name', ['../frame.png', '/a.png', 'a\\b.png', '.hidden.png',
                                  'x.svg', 'x.html', 'x.gif', '', 'a\x00.png'])
def test_reject_unsafe_filenames(name):
    with pytest.raises(ValueError):
        validate_filename(name)


def test_import_identity(app, study, image_bytes):
    from hashlib import sha256
    frame = app.state.store.frame(study['id'], 0)
    assert frame['source_sha256'] == sha256(image_bytes).hexdigest()
    assert frame['source_index'] == 2
    assert frame['position'] == 0
    assert frame['predictions'] == []
    assert frame['reference_labels'] == {}
    assert frame['review']['revision'] == 0


def test_folder_natural_order_and_reference(tmp_path, image_bytes):
    folder = tmp_path / '001'
    folder.mkdir()
    for n in [10, 2, 1]:
        (folder / f'frame_{n}.PNG').write_bytes(image_bytes)
    labels = tmp_path / '1.csv'
    labels.write_text('frame,stomach,blood,unknown\n1,1,0,\n2,,1,1\n10,0,0,0\n')
    store = Store(tmp_path / 'state')
    study = import_folder(store, folder, title='Galar schema fixture', source='Synthetic test fixture', labels=labels)
    assert store.frame(study['id'], 0)['source_index'] == 1
    second = store.frame(study['id'], 1)
    assert second['source_index'] == 2
    assert second['reference_labels']['stomach'] is None
    assert second['reference_labels']['blood'] == '1'
    assert not second['predictions']


@pytest.mark.parametrize('csv', [
    'wrong,blood\n1,1\n', 'frame,blood\n1,0\n1,1\n', 'frame,blood\n-1,0\n',
    'frame,blood\none,0\n', 'frame,blood\n1,0,extra\n', 'frame,blood,blood\n1,0,1\n',
])
def test_bad_csv_rejected(tmp_path, csv):
    p = tmp_path / 'bad.csv'
    p.write_text(csv)
    with pytest.raises(ValueError):
        read_galar_labels(p)


def test_empty_csv_is_allowed(tmp_path):
    p = tmp_path / 'empty.csv'
    p.write_text('frame,blood\n')
    assert read_galar_labels(p) == {}


def test_failed_import_rolls_back(app, image_bytes):
    store = app.state.store
    with pytest.raises(ValueError):
        import_sources(store, [('frame_1.png', image_bytes), ('bad.png', b'not an image')], title='Bad')
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM studies').fetchone()[0] == 0
    assert list(store.images.iterdir()) == []
    assert not list(store.root.glob('.import-*'))


def test_duplicate_names_rejected(app, image_bytes):
    with pytest.raises(ValueError, match='Duplicate'):
        import_sources(app.state.store, [('frame.png', image_bytes), ('FRAME.PNG', image_bytes)], title='Bad')


def test_duplicate_source_indices_rejected(app, image_bytes):
    with pytest.raises(ValueError, match='Duplicate numbered'):
        import_sources(app.state.store, [('frame_1.png', image_bytes), ('frame_01.png', image_bytes)], title='Bad')


def test_zero_frames_rejected(app):
    with pytest.raises(ValueError, match='No supported'):
        import_sources(app.state.store, [], title='Empty')


def test_symlink_rejected(tmp_path, image_bytes):
    p = tmp_path / 'images'
    p.mkdir()
    original = tmp_path / 'original.png'
    original.write_bytes(image_bytes)
    (p / 'frame.png').symlink_to(original)
    with pytest.raises(ValueError, match='symlink'):
        import_folder(Store(tmp_path / 'db'), p, title='Bad', source='Test')


def test_decoded_pixels_preserved(image_bytes):
    display, thumb, w, h = normalize_image(image_bytes)
    assert (w, h) == (64, 48)
    assert Image.open(io.BytesIO(display)).convert('RGB').tobytes() == Image.open(io.BytesIO(image_bytes)).convert('RGB').tobytes()
    assert Image.open(io.BytesIO(thumb)).format == 'JPEG'


def test_demo_is_explicitly_synthetic(app):
    study = create_demo(app.state.store)
    assert study['synthetic'] is True
    assert study['frame_count'] == 24
    assert study['runs'] == []
    assert not app.state.store.frame(study['id'], 0)['reference_labels']


def test_import_manifest_is_reproducible(app, image_bytes):
    one = import_sources(app.state.store, [('frame_1.png', image_bytes)], title='One')
    two = import_sources(app.state.store, [('frame_1.png', image_bytes)], title='Two')
    assert one['manifest_sha256'] == two['manifest_sha256']
    assert one['id'] != two['id']


def test_published_image_export_numbering_is_preserved(app, image_bytes):
    from capsule_review.source_coverage import summarize_source_spacing
    study = import_sources(app.state.store, [
        ('image-00007.png', image_bytes), ('image-00008.png', image_bytes),
        ('image-00012.png', image_bytes),
    ], title='Rhode-style source index test', source='Synthetic image data', synthetic=True)
    with app.state.store.connect() as db:
        numbered = [row[0] for row in db.execute(
            'SELECT source_index FROM frames WHERE study_id=? ORDER BY position',
            (study['id'],))]
    assert numbered == [7, 8, 12]
    audit = summarize_source_spacing(numbered)
    assert audit['adjacent_index_jumps'] == 1
    assert audit['maximum_forward_index_step'] == 4
    assert audit['complete_original_sequence_verified'] is False


def test_unrecognized_numbered_names_stay_unverified(app, image_bytes):
    study = import_sources(app.state.store, [
        ('camera_0007.png', image_bytes), ('unrelated_0008.png', image_bytes),
    ], title='Unrecognized numbering', source='Synthetic data')
    assert app.state.store.frame(study['id'], 0)['source_index'] is None
    assert app.state.store.frame(study['id'], 1)['source_index'] is None


def test_mixed_numbering_cannot_reuse_a_source_id(app, image_bytes):
    with pytest.raises(ValueError, match='Duplicate numbered'):
        import_sources(app.state.store, [
            ('frame_7.png', image_bytes), ('image-00007.png', image_bytes),
        ], title='Duplicate frame identity')


def test_rhode_style_names_cannot_inherit_galar_reference_labels(app, image_bytes):
    with pytest.raises(ValueError, match='Galar reference'):
        import_sources(app.state.store, [
            ('image-00007.png', image_bytes),
        ], title='Invalid cross-dataset labels', reference={7: {'blood': '1'}})
