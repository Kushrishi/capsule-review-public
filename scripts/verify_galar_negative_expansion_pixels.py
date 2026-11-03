"""Independent sampled original-PNG -> 96px tensor check across all 16 fitting exams.

Run with private materialized original source archives, never commit frame identities
or private source pixels. This does not re-verify *all* images; that was done by
source ingest. Here we independently validate the cached input tensor transform.
"""
from __future__ import annotations
import hashlib, io, json, tempfile, zipfile, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

ROOT=Path(os.environ.get('CAPSULE_CV_DATA_ROOT', '/mnt/data/capsule_next'))
DATA=ROOT/'negative_expansion_outputs'
EXAMS=(1,2,3,4,5,6,7,8,21,22,23,24,25,27,29,30)
NEW={e:ROOT/'inputs'/f'galar-exam{e}-verified-frames-private.zip' for e in (21,23,25,27,29,30)}
OLD={1:'001-002',2:'001-002',3:'003-004',4:'003-004',5:'005-006',6:'005-006',7:'007-008',8:'007-008'}

def sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def get_raw(exam:int, frame:int):
    name=f'images/{exam:03d}/frame_{frame:06d}.PNG'
    if exam in OLD:
        path=ROOT/'inputs'/f'galar-pilot-images-{OLD[exam]}.zip'
        with zipfile.ZipFile(path) as z:
            return z.read(name)
    if exam in (22,24):
        with zipfile.ZipFile(ROOT/'private_negative_verified_originals.zip') as z:return z.read(name)
    with zipfile.ZipFile(NEW[exam]) as outer:
        innername=next(s for s in outer.namelist() if s.endswith('.zip'))
        # Using a bounded single-archive temp file avoids holding all PNG source bytes in memory.
        with tempfile.TemporaryFile() as temp:
            with outer.open(innername) as source:
                while data:=source.read(1<<20):temp.write(data)
            temp.seek(0)
            with zipfile.ZipFile(temp) as inner:return inner.read(name)

def independent_transform(raw):
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format=='PNG'
        normalized=ImageOps.exif_transpose(image).convert('RGB')
        resized=ImageOps.pad(normalized,(96,96),method=Image.Resampling.BILINEAR,color=(0,0,0))
        return np.asarray(resized,dtype=np.uint8)

def main():
    metadatafile=DATA/'private_source_metadata.json'
    meta=json.loads(metadatafile.read_text())
    assert len(meta)==11147
    bank=np.memmap(DATA/'bank_96_rgb_uint8.dat',dtype=np.uint8,mode='r',shape=(len(meta),96,96,3))
    total=0
    count_by_exam={}
    for exam in EXAMS:
        examined=[(i,row) for i,row in enumerate(meta) if row['exam']==exam]
        assert examined
        neg=next((i,row) for i,row in examined if row['blood']==0)
        positives=[(i,row) for i,row in examined if row['blood']==1]
        firstpositive=positives[len(positives)//2] if positives else examined[-1]
        choices={neg[0]:neg,firstpositive[0]:firstpositive}
        if exam in NEW:
            # Copy an outer ZIP's nested source ZIP only once per examination.
            with zipfile.ZipFile(NEW[exam]) as outer:
                innername=next(s for s in outer.namelist() if s.endswith('.zip'))
                with tempfile.TemporaryFile() as temp:
                    with outer.open(innername) as source:
                        while data:=source.read(1<<20):temp.write(data)
                    temp.seek(0)
                    with zipfile.ZipFile(temp) as inner:
                        for i,r in choices.values():
                            raw=inner.read(f"images/{exam:03d}/frame_{r['frame']:06d}.PNG")
                            if not np.array_equal(independent_transform(raw),bank[i]):
                                raise AssertionError('Source-PNG transform mismatch')
                            total+=1
        else:
            for i,r in choices.values():
                original=get_raw(exam,r['frame'])
                if not np.array_equal(independent_transform(original),bank[i]):
                    raise AssertionError('Source-PNG transform mismatch')
                total+=1
        count_by_exam[str(exam)]=len(choices)
        print('Matched original PNG tensor transformation for examination',exam, 'count',len(choices),flush=True)
    report={
        'source_images_original_sha256_manifest_sha256':sha(metadatafile),
        'input_tensor_bank_sha256':sha(DATA/'bank_96_rgb_uint8.dat'),
        'examination_count':len(EXAMS),
        'independently_reloaded_original_pngs':total,
        'sampled_images_per_examination':count_by_exam,
        'max_absolute_pixel_difference':0,
        'clinical_validity':False,
        'individual_source_image_ids_excluded':True,
        'source_unaltered':True,
    }
    output=DATA/'source_pixel_spotcheck.json'
    if output.exists():raise FileExistsError('Refuse overwrite prior source-image verification.')
    output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('Independent source image spotcheck',json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
