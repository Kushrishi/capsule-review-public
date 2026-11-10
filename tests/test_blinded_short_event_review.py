"""Synthetic-only source safety / blinding / export smoke tests."""
from io import BytesIO
from pathlib import Path
import json
import sys
import zipfile

import pytest
PIL = pytest.importorskip('PIL')
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_blinded_short_event_review import (verify_cohort, fetch_verified_sources,
    build_packet, pixel_identical_deidentified_png, sha)


def png(color):
    image=Image.new('RGB',(512,512),color)
    out=BytesIO();image.save(out,format='PNG')
    return out.getvalue()


def fixture(tmp_path):
    keys=[(23,10,1),(23,15,0),(25,30,1),(25,35,0)]
    raw={(e,f):png((r*90+5,35,f)) for e,f,r in keys}
    manifest={'images':[{'exam':e,'frame':f,'blood':r,'sha256':sha(raw[(e,f)]),'bytes':len(raw[(e,f)])}
                         for e,f,r in keys],
              'pairs':[{'exam':23,'run_id':0,'run_length':1,'positive_index':0,'negative_index':1},
                       {'exam':25,'run_id':1,'run_length':2,'positive_index':2,'negative_index':3}]}
    source=tmp_path/'private-originals.zip'
    with zipfile.ZipFile(source,'w') as z:
        for (e,f),b in raw.items():z.writestr(f'images/{e}/frame_{f:06d}.PNG',b)
    return manifest,raw,source


def build(tmp_path):
    m,raw,p=fixture(tmp_path)
    pairs,records=verify_cohort(m,expected_pairs=2)
    images,archives=fetch_verified_sources(records,[p],{p.name:sha(p.read_bytes())})
    rv,key,receipt=build_packet(m,images,archives,manifest_sha=sha(b'fixture'),expected_pairs=2,
                                 deterministic_ids={i:format(i+1,'024x') for i in records},packet_id='e'*24)
    return rv,key,receipt


def test_exact_mapping_and_no_label_leakage(tmp_path):
    rv,key,receipt=build(tmp_path)
    with zipfile.ZipFile(BytesIO(rv)) as z:
        data=json.loads(z.read('manifest.json'))
        assert len(data['items'])==4
        assert all(set(i)=={'item_id','image'} for i in data['items'])
        assert 'published_blood_label' not in z.read('manifest.json').decode()
        assert 'source_exam' not in z.read('packet-data.js').decode()
        assert 'positive_index' not in z.read('index.html').decode()
        assert 'http:' not in z.read('review.js').decode().lower()
        assert 'fetch(' not in z.read('review.js').decode()
        assert "connect-src 'none'" in z.read('index.html').decode()
        assert '<script src="packet-data.js"></script>' in z.read('index.html').decode()
        for n in z.namelist():
            if n.endswith('.png'):
                with Image.open(BytesIO(z.read(n))) as img:
                    assert img.size==(512,512)
    with zipfile.ZipFile(BytesIO(key)) as z:
        m=json.loads(z.read('PRIVATE_KEY.json'))
        assert len(m['pairs'])==2
        assert len(m['images'])==4
        assert {i['published_blood_label'] for i in m['images']}=={0,1}
        assert m['reviewer_zip_sha256']==sha(rv)
    assert receipt['status']=='PREPARED_NOT_CLINICALLY_REVIEWED'
    assert receipt['model_training_performed'] is False


def test_managed_and_original_pixels_identical(tmp_path):
    raw=png((32,64,90));out,pix_sha=pixel_identical_deidentified_png(raw)
    with Image.open(BytesIO(raw)) as a, Image.open(BytesIO(out)) as b:
        assert a.tobytes()==b.tobytes()
        assert pix_sha==sha(a.tobytes())


def test_tampered_original_rejected(tmp_path):
    m,raw,p=fixture(tmp_path)
    _,records=verify_cohort(m,expected_pairs=2)
    with zipfile.ZipFile(p,'w') as z:
        for (e,f),b in raw.items():z.writestr(f'images/{e}/frame_{f:06d}.PNG',b+b'bad' if e==23 and f==10 else b)
    with pytest.raises(ValueError,match='byte/identity mismatch'):
        fetch_verified_sources(records,[p])


def test_source_archive_sha_gate(tmp_path):
    m,raw,p=fixture(tmp_path)
    _,records=verify_cohort(m,expected_pairs=2)
    with pytest.raises(ValueError,match='pinned expected SHA'):
        fetch_verified_sources(records,[p],{p.name:'0'*64})


def test_frozen_pair_count(tmp_path):
    m,_,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='pair count changed'):
        verify_cohort(m)


def test_duplicate_run_rejected(tmp_path):
    m,_,_=fixture(tmp_path);m['pairs'][1]['exam']=23;m['pairs'][1]['run_id']=0
    with pytest.raises(ValueError,match='Duplicate original source event run'):
        verify_cohort(m,expected_pairs=2)


def test_disjoint_run_missing_source_rejected(tmp_path):
    m,_,p=fixture(tmp_path)
    _,records=verify_cohort(m,expected_pairs=2)
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('images/23/frame_000010.PNG',png((1,2,3)))
    with pytest.raises(ValueError,match='Not all original-source endpoints'):
        fetch_verified_sources(records,[p])


def test_fake_adjacent_step_rejected(tmp_path):
    m,_,_=fixture(tmp_path);m['images'][1]['frame']=25
    with pytest.raises(ValueError,match='stride-five'):
        verify_cohort(m,expected_pairs=2)


def test_role_mismatch_rejected(tmp_path):
    m,_,_=fixture(tmp_path);m['images'][0]['blood']=0
    with pytest.raises(ValueError,match='source role'):
        verify_cohort(m,expected_pairs=2)


def test_source_identity_duplicate_rejected(tmp_path):
    m,_,_=fixture(tmp_path);m['images'][2]['frame']=m['images'][0]['frame'];m['images'][2]['exam']=23
    with pytest.raises(ValueError):
        verify_cohort(m,expected_pairs=2)


def test_output_id_collision_rejected(tmp_path):
    m,raw,p=fixture(tmp_path)
    _,records=verify_cohort(m,expected_pairs=2)
    images,archives=fetch_verified_sources(records,[p])
    with pytest.raises(ValueError,match='duplicated opaque'):
        build_packet(m,images,archives,manifest_sha=sha(b'fixture'),expected_pairs=2,
                     deterministic_ids={i:'c'*24 for i in records})


def test_nested_source_package_reads(tmp_path):
    m,raw,_=fixture(tmp_path)
    inner=BytesIO()
    with zipfile.ZipFile(inner,'w') as z:
        for (e,f),b in raw.items():z.writestr(f'images/{e:03d}/frame_{f:06d}.PNG',b)
    outer=tmp_path/'nested.zip'
    with zipfile.ZipFile(outer,'w') as z:z.writestr('originals.zip',inner.getvalue())
    _,records=verify_cohort(m,expected_pairs=2)
    images,_=fetch_verified_sources(records,[outer])
    assert len(images)==4
