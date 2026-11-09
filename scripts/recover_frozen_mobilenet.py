#!/usr/bin/env python3
"""Private, source-hash-checked recovery of Galar MobileNetV3 frozen features.

This code neither downloads originals nor opens benchmark outcome annotations.
Do not commit generated manifests, raw image-derived embeddings, or weights to public Git.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
import numpy as np

FEATURE_ZIP = 'galar-frozen-mobilenet-private-repro.zip'
FOUNDATION_ZIP = 'Short_Event_Foundation_Private_Final_Evidence_20261109.zip'
ORIGINAL_ZIPS = ('Local_Short_Event_New_Originals_20261109.zip',
                 'Short_Event_Foundation_New_Originals_20261109.zip')
WEIGHT_SHA = '047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f'
FEATURE_SHA = '611ac32ca3b0ada15bba65c5aba564fd2a92bdac4d60d9376af89e429181c9ae'
EXAMS = (23,25,29,30)
EXPECTED_MISSING = {23:81,25:78,29:8,30:13}


def digest(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def safe_write_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise FileExistsError(f'Refusing to replace verified result: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    try:
        with tmp.open('xb') as f:
            f.write(data)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()


def parse_sources(root: Path):
    with zipfile.ZipFile(root/FEATURE_ZIP) as z:
        rows=json.loads(z.read('original-private-source-identity/private_source_metadata.json'))
        raw=z.read('features/features-10123-float32.bin')
    if len(rows)!=10123 or len(raw)!=10123*576*4 or digest(raw)!=FEATURE_SHA:
        raise ValueError('Frozen 10,123 by 576 bank/hash mismatch')
    features=np.frombuffer(raw,dtype='<f4').reshape(10123,576)
    if not np.isfinite(features).all():raise ValueError('Non-finite cached features')
    keys=[(int(r['exam']),int(r['frame'])) for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate cached original-image identities')
    return rows,features,{key:i for i,key in enumerate(keys)}


def build(root: Path):
    source,features,lookup=parse_sources(root)
    with zipfile.ZipFile(root/FOUNDATION_ZIP) as z:
        m=json.loads(z.read('foundation/support-manifest-private.json'))
    images=m['images'];pairs=m['pairs'];core=m['core_indices']
    if len(images)!=4412 or len(core)!=4096 or len(pairs)!=69:
        raise ValueError('Unexpected PR72 support manifest size')
    keys=[(int(r['exam']),int(r['frame'])) for r in images]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate target identities')
    missing=[]; mapping=[]
    for i,(key,row) in enumerate(zip(keys,images)):
        j=lookup.get(key)
        if j is None:missing.append(i);mapping.append(None)
        else:
            if int(row['blood'])!=int(source[j]['blood']):raise ValueError('Cached feature blood-label inconsistency')
            mapping.append(j)
    if len(missing)!=180 or Counter(keys[i][0] for i in missing)!=Counter(EXPECTED_MISSING):
        raise ValueError('Unexpected missing-feature cohort')
    if len({(p['exam'],p['run_id']) for p in pairs})!=69:
        raise ValueError('Repeated run identities')
    for p in pairs:
        ip,in_=p['positive_index'],p['negative_index']
        pos,neg=images[ip],images[in_]
        if int(pos['blood'])!=1 or int(neg['blood'])!=0 or pos['exam']!=neg['exam'] or pos['exam']!=p['exam']:
            raise ValueError('Genuine opposite-label source-pair check failed')
        if abs(pos['frame']-neg['frame'])!=5 or not (1<=p['run_length']<=5):
            raise ValueError('Native-stride adjacent short-run check failed')
    if Counter(p['exam'] for p in pairs)!=Counter({23:23,25:20,29:11,30:15}):
        raise ValueError('Unexpected held-out run support')
    if {images[i]['exam'] for i in core}&set(EXAMS) and not set(EXAMS).issubset({r['exam'] for r in images}):
        raise ValueError('Source population changed')
    # Exact member paths and bytes are verified; nothing is extracted to disk here.
    image_locations={}
    for name in ORIGINAL_ZIPS:
        with zipfile.ZipFile(root/name) as z:
            for member in z.namelist():
                if not member.startswith('images/') or not member.lower().endswith('.png'):continue
                pieces=member.split('/')
                if len(pieces)!=3 or not pieces[-1].startswith('frame_'):continue
                ex=int(pieces[1]);frame=int(pieces[2].split('_')[1].split('.')[0]); key=(ex,frame)
                if key in image_locations:raise ValueError('Unexpected duplicate new original')
                image_locations[key]=(name,member)
    found=[]
    for i in missing:
        row=images[i];key=keys[i]
        if key not in image_locations:raise ValueError('Missing required original')
        name,member=image_locations[key]
        with zipfile.ZipFile(root/name) as z:raw=z.read(member)
        if len(raw)!=row['bytes'] or digest(raw)!=row['sha256']:
            raise ValueError('PNG byte-length/SHA-256 mismatch')
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        found.append({'input_index':i,'exam':key[0],'frame':key[1],
                      'original_sha256':row['sha256'],'original_bytes':row['bytes'],
                      'archive':name,'member':member})
    return images,pairs,features,mapping,found


def audit(root: Path, out: Path):
    images,pairs,features,mapping,found=build(root)
    summary={'status':'source-verified; frozen encoder weights still required for new embeddings',
        'cached_source_rows':10123,'cached_feature_dimensions':576,
        'cached_feature_sha256':FEATURE_SHA,'target_images':len(images),
        'mapped_old_features':sum(x is not None for x in mapping),
        'missing_new_embeddings':len(found),'missing_by_exam':dict(sorted(Counter(r['exam'] for r in found).items())),
        'verified_missing_pngs':len(found),'genuine_short_runs':len(pairs),
        'supported_exams':list(EXAMS),'pairs_by_exam':dict(sorted(Counter(p['exam'] for p in pairs).items())),
        'original_publisher_bytes_downloaded_in_this_audit':0,
        'full_feature_comparison_executed':False,
        'model_promoted':False}
    out.mkdir(parents=True,exist_ok=True)
    safe_write_new(out/'audit-private.json',json.dumps({'mapping':mapping,'missing':found},indent=2).encode())
    safe_write_new(out/'audit-public.json',json.dumps(summary,indent=2).encode())
    return summary



def prepare_rgb_png(raw: bytes) -> np.ndarray:
    """The original frozen-bank 160px full-field preprocessing, byte-safe."""
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'PNG':
            raise ValueError('Source canary is not an original PNG')
        image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        resized=ImageOps.exif_transpose(image).convert('RGB').resize((160,160),Image.Resampling.BICUBIC)
        return np.array(resized,dtype=np.uint8,copy=True)


def verify_cached_canaries(canary_file:Path, rows:list[dict], features:np.ndarray,
                           lookup:dict, net, bank_sha:str=FEATURE_SHA,
                           weight_sha:str=WEIGHT_SHA) -> dict:
    """Stop if exact-source canaries differ from the old 576-D frozen bank.

    Canaries are a private, outcome-blind source selection. The caller separately
    verifies the canary ZIP hash against the private prefit evidence receipt.
    """
    import torch
    with zipfile.ZipFile(canary_file) as z:
        if z.testzip() is not None:raise ValueError('Corrupt private canary ZIP')
        manifest=json.loads(z.read('canary-manifest-private.json'))
        sample=manifest['canaries']
        if len(sample)!=3 or manifest['feature_bank_sha256']!=bank_sha or manifest['backbone_weights_sha256']!=weight_sha:
            raise ValueError('Wrong private prefit canary population or weight/bank identity')
        if set(z.namelist())!={'canary-manifest-private.json',*(f'originals/canary_{j}.PNG' for j in range(3))}:
            raise ValueError('Unexpected member in private canary archive')
        arrays=[];refs=[];seen=set()
        for k,rec in enumerate(sample):
            key=(int(rec['exam']),int(rec['frame']))
            if key in seen or key[0]!=23 or key not in lookup or rec['archive_member']!=f'originals/canary_{k}.PNG':
                raise ValueError('Invalid or duplicate canary source identity')
            seen.add(key)
            index=lookup[key]
            if rec['old_bank_row_index']!=index or (int(rows[index]['exam']),int(rows[index]['frame']))!=key:
                raise ValueError('Canary mismatches source-identity bank')
            raw=z.read(rec['archive_member'])
            if len(raw)!=int(rec['source_original_bytes']) or digest(raw)!=rec['source_original_sha256']:
                raise ValueError('Canary source original SHA or size mismatch')
            px=prepare_rgb_png(raw)
            if digest(px.tobytes(order='C'))!=rec['resized_rgb_uint8_sha256']:
                raise ValueError('Historical canary resize/EXIF/RGB preprocessing mismatch')
            ref=features[index]
            if digest(ref.tobytes(order='C'))!=rec['old_feature_row_sha256']:
                raise ValueError('Historical cached canary feature-row hash mismatch')
            arrays.append(px);refs.append(ref)
    # Use the original execution's uint8 -> float32 -> /255 -> ImageNet scaling.
    x=torch.from_numpy(np.stack(arrays)).permute(0,3,1,2).contiguous().float().div_(255)
    means=x.new_tensor([.485,.456,.406]).view(1,3,1,1)
    stds=x.new_tensor([.229,.224,.225]).view(1,3,1,1)
    with torch.inference_mode():got=net((x-means)/stds).mean(dim=(2,3)).cpu().numpy()
    expected=np.stack(refs)
    if got.shape!=expected.shape or not np.isfinite(got).all():
        raise ValueError('Invalid recomputed canary features')
    delta=float(np.max(np.abs(got-expected)))
    if not np.allclose(got,expected,atol=1e-4,rtol=1e-4):
        raise ValueError(f'Exact pinned encoder failed frozen-feature canaries: max delta {delta:.9g}')
    return {'source_canaries_checked':3,'max_abs_feature_difference':delta,
            'frozen_bank_consistent':True,'canary_sha256':file_sha(canary_file)}


def extract(root: Path, out: Path, weight_file: Path, canary_file: Path, expected_canary_sha: str):
    if file_sha(weight_file)!=WEIGHT_SHA:
        raise ValueError('Backbone weights do not match pinned official SHA-256')
    if not expected_canary_sha or file_sha(canary_file)!=expected_canary_sha:
        raise ValueError('Private canary package does not match the separately pinned SHA-256')
    images,pairs,features,mapping,found=build(root)
    old_rows,_,old_lookup=parse_sources(root)
    audit_path=out/'audit-private.json'
    if not audit_path.is_file():raise ValueError('Run audit first')
    if json.loads(audit_path.read_text())['missing']!=found:
        raise ValueError('The source-verified missing-originals manifest changed')
    import torch
    from PIL import Image,ImageOps
    from torchvision.models import mobilenet_v3_small
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model=mobilenet_v3_small(weights=None).cpu().eval()
    model.load_state_dict(torch.load(weight_file,map_location='cpu',weights_only=True),strict=True)
    net=model.features
    canaries=verify_cached_canaries(canary_file,old_rows,features,old_lookup,net)
    mean=torch.tensor([.485,.456,.406],dtype=torch.float32).view(1,3,1,1)
    std=torch.tensor([.229,.224,.225],dtype=torch.float32).view(1,3,1,1)
    output=np.zeros((len(images),576),dtype='<f4')
    for i,j in enumerate(mapping):
        if j is not None:output[i]=features[j]
    # Original implementation uses PIL EXIF transpose, RGB, bicubic 160x160,
    # float32 divided by 255, ImageNet normalization, features.mean(H,W).
    for offset in range(0,len(found),12):
        batch=[]
        for entry in found[offset:offset+12]:
            with zipfile.ZipFile(root/entry['archive']) as z:raw=z.read(entry['member'])
            if digest(raw)!=entry['original_sha256']:raise ValueError('Source changed during extraction')
            batch.append(prepare_rgb_png(raw))
        x=torch.tensor(np.stack(batch),dtype=torch.float32).permute(0,3,1,2)/255.
        with torch.inference_mode(): y=net((x-mean)/std).mean(dim=(2,3)).cpu().numpy()
        if y.shape!=(len(batch),576) or not np.isfinite(y).all():raise ValueError('Feature extraction failed')
        for k,entry in enumerate(found[offset:offset+12]):output[entry['input_index']]=y[k]
    if not np.isfinite(output).all():raise ValueError('Nonfinite final features')
    save=io.BytesIO();np.save(save,output,allow_pickle=False)
    safe_write_new(out/'mobilenet-features-4412-f32.npy',save.getvalue())
    summary={'images':len(images),'dim':576,'new_embeddings':len(found),'canaries':canaries,
             'source_bank_sha256':FEATURE_SHA,'official_backbone_sha256':WEIGHT_SHA,
             'combined_npy_sha256':file_sha(out/'mobilenet-features-4412-f32.npy'),
             'model_promoted':False,'evaluation_performed':False}
    safe_write_new(out/'extraction-receipt.json',json.dumps(summary,indent=2).encode())
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('audit','extract'))
    p.add_argument('--root',type=Path,required=True,help='directory with five verified private ZIPs')
    p.add_argument('--out',type=Path,required=True,help='private output outside public git')
    p.add_argument('--weights',type=Path,help='exact SHA-verified torchvision MobileNetV3-Small checkpoint')
    p.add_argument('--canaries',type=Path,help='privately SHA-pinned source/feature canary ZIP; mandatory for extraction')
    p.add_argument('--canary-sha',type=str,help='separately recorded canary-package SHA256')
    args=p.parse_args()
    if args.action=='audit':result=audit(args.root,args.out)
    else:
        if args.weights is None or args.canaries is None or args.canary_sha is None:
            p.error('--weights, --canaries and --canary-sha required for extract')
        result=extract(args.root,args.out,args.weights,args.canaries,args.canary_sha)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
