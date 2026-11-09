"""Fixed, research-only red-versus-green image score on private verified PNGs.

All runtime inputs (manifests, PNGs) and per-image outputs MUST be kept outside public Git.
Zero new training, publisher downloads or model weights. No clinical interpretation.
"""
from __future__ import annotations
import argparse, hashlib, io, json, zipfile
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np

EXAMS=(23,25,29,30)


def private_path(path):
    path=Path(path)
    repo=Path(__file__).resolve().parents[1]
    if path.is_symlink() or ((repo/'AGENTS.md').exists() and path.resolve().is_relative_to(repo)):
        raise ValueError('Medical inputs and outputs must remain outside the public repository')
    return path.resolve()
CIRCLE=np.fromfunction(lambda y,x: ((x-79.5)**2 + (y-79.5)**2) <= 70.0**2,(160,160),dtype=int)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def fixed_score(raw):
    with Image.open(io.BytesIO(raw)) as im:
        if im.format!='PNG': raise ValueError('Not an original PNG')
        img=ImageOps.exif_transpose(im).convert('RGB').resize((160,160),Image.Resampling.BICUBIC)
        rgb=np.asarray(img,dtype=np.float64)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    keep=CIRCLE & ((r+g+b)>=45.)
    if not keep.any():raise ValueError('No non-border pixels; stop rather than impute')
    val=np.clip((r-g)/(r+g+20.),-1.,1.)
    return float(val[keep].mean())

def extract_endpoints(manifest, root, output, archive_dir):
    # Never publish the source-associated outputs from this function.
    root=private_path(root); output=private_path(output); archive_dir=private_path(archive_dir)
    pairs=manifest['pairs']; assert len(pairs)==69
    indices={p[k] for p in pairs for k in ('positive_index','negative_index')}
    req={}
    for i in indices:
        row=manifest['images'][i]
        assert row['exam'] in EXAMS
        req[(row['exam'],row['frame'])]=(i,row)
    found={}; origins={}
    for name in ('Short_Event_Foundation_New_Originals_20261109.zip','Local_Short_Event_New_Originals_20261109.zip'):
        with zipfile.ZipFile(root/name) as z:
            for f in z.namelist():
                if not f.endswith('.PNG'):continue
                seg=f.split('/');ex=int(seg[-2]);frame=int(seg[-1].split('_')[1].split('.')[0]);key=(ex,frame)
                if key not in req or key in found:continue
                b=z.read(f);index,row=req[key]
                if len(b)!=row['bytes'] or sha(b)!=row['sha256']:raise ValueError('Stored image failed source identity check')
                found[key]=fixed_score(b);origins[key]=name
    # Previous real original data archives, not newly acquired publisher data.
    for ex in EXAMS:
        name=f'galar-exam{ex}-verified-frames-private.zip'
        path=archive_dir/name
        with zipfile.ZipFile(path) as outer:
            inner_name=[x for x in outer.namelist() if x.endswith('.zip')][0]
            with zipfile.ZipFile(io.BytesIO(outer.read(inner_name))) as inner:
                for (e,frame),(idx,row) in req.items():
                    if e!=ex or (e,frame) in found:continue
                    f=f'images/{ex:03d}/frame_{frame:06d}.PNG'
                    if f not in inner.namelist():continue
                    b=inner.read(f)
                    if len(b)!=row['bytes'] or sha(b)!=row['sha256']:raise ValueError('Original source verification mismatch')
                    found[(e,frame)]=fixed_score(b);origins[(e,frame)]=name
    missing=set(req)-set(found)
    if missing: raise ValueError(f'Missing {len(missing)} verified image endpoints; no approximation allowed')
    assert len(req)==len(found)==137
    records=[{'image_index':i,'sha256':row['sha256'],'redness':found[(row['exam'],row['frame'])]} for (e,frame),(i,row) in sorted(req.items())]
    data={'source':'Frozen PR72 69-run 137-endpoint source-matched originals','method':'central-circle mean clipped normalized red-minus-green','n_images':137,'image_scores':records,'recovered_from_archives':{name:list(origins.values()).count(name) for name in sorted(set(origins.values()))}}
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(data,indent=2,allow_nan=False))
    print(json.dumps({'all_original_sha_verified':True,'n_images':len(records),'n_pairs':len(pairs),'source_archive_counts':data['recovered_from_archives'],'private_scores_sha256':sha(output.read_bytes())},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--manifest-zip',type=Path,required=True);ap.add_argument('--original-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--archive-dir',type=Path,required=True);a=ap.parse_args()
    with zipfile.ZipFile(a.manifest_zip) as z:manifest=json.loads(z.read('foundation/support-manifest-private.json'))
    extract_endpoints(manifest,a.original_root,a.output,a.archive_dir)
