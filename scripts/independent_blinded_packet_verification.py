"""Independent, read-only verification of a private blinded image-review handoff.

Do not commit reviewer ZIP or key, patient/source mappings or verification
receipt to public Git. Run only in an access-controlled local environment.
"""
from __future__ import annotations
import hashlib, io, json, re, zipfile
from collections import Counter
from pathlib import Path
from PIL import Image


def sha(b):return hashlib.sha256(b).hexdigest()


def verify(review_zip:Path,key_zip:Path,originals:list[Path])->dict:
    rb=review_zip.read_bytes();kb=key_zip.read_bytes()
    with zipfile.ZipFile(io.BytesIO(rb)) as review, zipfile.ZipFile(io.BytesIO(kb)) as escrow:
        manifest=json.loads(review.read('manifest.json'))
        private=json.loads(escrow.read('PRIVATE_KEY.json'))
        if private['reviewer_zip_sha256']!=sha(rb) or manifest['packet_id']!=private['packet_id']:
            raise ValueError('The reviewer package and unblinding key do not agree.')
        items=manifest['items'];mapping=private['images'];pairs=private['pairs']
        if len(items)!=137 or len(mapping)!=137 or len(pairs)!=69:
            raise ValueError('Changed original study size.')
        exposed={x['item_id'] for x in items}
        mapping_ids={x['item_id'] for x in mapping}
        if len(exposed)!=137 or exposed!=mapping_ids:
            raise ValueError('Missing/duplicate opaque reviewer identity.')
        if len([n for n in review.namelist() if n.endswith('.png')])!=137:
            raise ValueError('Wrong number of blinded clinical images.')
        visible=review.read('manifest.json')+review.read('packet-data.js')+review.read('index.html')
        forbidden=(b'positive_index',b'negative_index',b'published_blood_label',b'source_exam',b'source_frame',b'Galar 23',b'Galar 25',b'Galar 29',b'Galar 30')
        if any(x in visible for x in forbidden):
            raise ValueError('The blinded reviewer ZIP includes hidden source/role metadata.')
        if b"connect-src 'none'" not in review.read('index.html'):
            raise ValueError('Offline browser privacy policy missing.')
        observed={}
        for entry in mapping:
            itemid=entry['item_id']
            if not re.fullmatch(r'[a-f0-9]{24}',itemid):raise ValueError('Nonopaque source identity.')
            name='images/'+itemid+'.png';raw=review.read(name)
            if sha(raw)!=entry['review_png_sha256']:
                raise ValueError('Blinded image bytes differ from saved escrow.')
            with Image.open(io.BytesIO(raw)) as image:
                if image.size!=(512,512) or image.mode!='RGB':
                    raise ValueError('Altered native image geometry.')
                pixels=sha(image.tobytes())
            if pixels!=entry['retained_pixel_sha256']:
                raise ValueError('Source RGB pixel bytes altered.')
            observed[(entry['source_exam'],entry['source_frame'])]=entry
        if len(observed)!=137:raise ValueError('Repeated original source key.')
        for p in pairs:
            a=next(x for x in mapping if x['item_id']==p['published_positive_item_id'])
            b=next(x for x in mapping if x['item_id']==p['published_negative_item_id'])
            if a['source_exam']!=p['source_exam'] or b['source_exam']!=p['source_exam'] or a['published_blood_label']!=1 or b['published_blood_label']!=0:
                raise ValueError('Published-label source role/key mismatch.')
            if abs(a['source_frame']-b['source_frame'])!=5:
                raise ValueError('Not native source adjacent.')
        if Counter(p['source_exam'] for p in pairs)!={23:23,25:20,29:11,30:15}:
            raise ValueError('Different examination/run population.')
        if sum(p['run_length']==1 for p in pairs)!=21:
            raise ValueError('Wrong singleton count.')
        # Read actual publisher images independently; never accept a derived pixel summary alone.
        nmatch=0
        for outerpath in originals:
            with zipfile.ZipFile(outerpath) as outer:
                nests=[n for n in outer.namelist() if n.endswith('.zip')]
                if len(nests)>1:raise ValueError('Ambiguous source nested archives.')
                inner=zipfile.ZipFile(io.BytesIO(outer.read(nests[0]))) if nests else outer
                try:
                    for info in inner.infolist():
                        m=re.fullmatch(r'images/(0?\d{2,3})/frame_(\d{6})\.PNG',info.filename)
                        if m is None:continue
                        k=(int(m.group(1)),int(m.group(2)))
                        if k not in observed:continue
                        raw=inner.read(info)
                        orig=observed[k]
                        if sha(raw)!=orig['original_png_sha256'] or len(raw)!=orig['original_png_bytes']:
                            raise ValueError('Publisher image original SHA changed.')
                        with Image.open(io.BytesIO(raw)) as i:
                            if sha(i.convert('RGB').tobytes())!=orig['retained_pixel_sha256']:
                                raise ValueError('Reviewed image differs from publisher RGB pixels.')
                        nmatch+=1
                finally:
                    if inner is not outer:inner.close()
        if nmatch<137:
            raise ValueError('At least one reviewer source was not independently reverified.')
        return {'status':'VERIFIED_REVIEW_PREPARATION_ONLY','images':len(items),'source_adjacent_pairs':len(pairs),
                'singleton_runs':21,'source_bytes_rechecked_at_least':nmatch,
                'pixel_identity_rechecked':len(items),'reader_responses_present':False,
                'clinical_adjudication_completed':False,'patient_independence_verified':False,
                'reviewer_sha256':sha(rb),'escrow_sha256':sha(kb),
                'privacy':'All real source identities and labels remain in the separate private escrow.'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('reviewer_zip',type=Path);p.add_argument('escrow_zip',type=Path);p.add_argument('source_archives',nargs='+',type=Path)
    x=p.parse_args();print(json.dumps(verify(x.reviewer_zip,x.escrow_zip,x.source_archives),indent=2))
