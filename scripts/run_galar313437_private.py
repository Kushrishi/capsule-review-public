"""PRIVATE frozen Galar31/34/37 original-CNN scoring and separate outcome audit.

No acquisition or training. Outputs and all inputs must remain outside public Git.
Run scoring without any labels. Audit requires a remote-readback retention seal
for all original packages and snapshots; that seal must be independently verified.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import zipfile

from capsule_review.geometry_control import analyze, annotation_runs, metrics
from capsule_review.interval_evidence import parse_corrected_source_rows
from capsule_review.priority import select_positions, ordinal_coverage, largest_unselected_span
from capsule_review.temporal_baseline import temporal_max_scores
from capsule_review.unseen_evaluation import freeze_queues
from run_galar35_full_sequence_private import load_original_model, WEIGHTS_SHA, sha256_file

ROOT = Path(__file__).resolve().parents[1]
COHORT = {31: (24919,3310,162), 34: (10867,49,9), 37: (18125,0,0)}
LABEL_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
LOCK_COMMIT = 'bd59b4936770d8d782df0e29df5cf8a9df1af15d'


def private_path(value: Path) -> Path:
    if value.is_symlink() or value.resolve().is_relative_to(ROOT):
        raise ValueError('Private input/output cannot be a symlink or enter public Git.')
    return value.resolve()


def source_members(z: zipfile.ZipFile, exam: int) -> list:
    if exam not in COHORT: raise ValueError('Only the frozen cohort is permitted.')
    pattern = re.compile(rf'images/{exam:03}/frame_(\d+)\.PNG\Z')
    members=[]; names=set()
    for v in z.infolist():
        if v.filename in names or v.is_dir() or (v.external_attr>>16)&0o170000==0o120000:
            raise ValueError('Duplicate, directory or symlink original member.')
        names.add(v.filename)
        m=pattern.fullmatch(v.filename)
        if m is None or not 0<v.file_size<=16*1024*1024:
            raise ValueError('Unexpected original image path/size; no manifests or labels in scoring ZIP.')
        members.append((int(m.group(1)),v))
    members.sort(key=lambda x:x[0])
    if len(members)!=COHORT[exam][0] or any(b[0]-a[0]!=5 for a,b in zip(members,members[1:])):
        raise ValueError('Complete pinned native-stride source grid required.')
    return members


def queues(frames, hashes, scores):
    frozen=freeze_queues(frames,hashes,scores)
    temporal=temporal_max_scores(scores,frames,window=3,source_stride=5)
    return frozen,[{'review_percent':p,'k':k,
                    'policies':{m:list(q) for m,q in methods},
                    'temporal_window3_score_bin':list(select_positions(temporal,k,'score_bin'))}
                   for p,k,methods in frozen.selection_by_percent]


def score(exam, originals, expected_sha, model_zip):
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    if sha256_file(originals,16*1024**3)!=expected_sha: raise ValueError('Original package hash mismatch.')
    model=load_original_model(model_zip); entries=[];pending=[]
    def flush():
        if not pending:return
        scores=torch.softmax(model(torch.stack([x[2] for x in pending])),dim=1)[:,1].cpu().tolist()
        for (frame,h,_),s in zip(pending,scores):
            if not 0<=s<=1:raise ValueError('Invalid CNN score.')
            entries.append({'source_frame':frame,'original_png_sha256':h,'original_cnn_score':float(s)})
        pending.clear()
    with zipfile.ZipFile(originals) as z,torch.inference_mode():
        for i,(frame,v) in enumerate(source_members(z,exam),1):
            raw=z.read(v)
            with Image.open(io.BytesIO(raw)) as im:
                if im.format!='PNG':raise ValueError('Non-PNG source.')
                image=ImageOps.pad(ImageOps.exif_transpose(im).convert('RGB'),(96,96),method=Image.Resampling.BILINEAR,color=(0,0,0))
                pixels=np.asarray(image,dtype=np.float32)/255.0
            pending.append((frame,hashlib.sha256(raw).hexdigest(),torch.from_numpy(pixels.transpose(2,0,1).copy())))
            if len(pending)==32:flush()
            if i%2000==0:print(f'{exam}: {i} original images scored',flush=True)
        flush()
    frozen,q=queues([x['source_frame'] for x in entries],[x['original_png_sha256'] for x in entries],[x['original_cnn_score'] for x in entries])
    return {'schema_version':1,'record_type':'private-galar313437-frozen-original-scores-v1','exam':exam,
            'development_only':True,'lock_commit':LOCK_COMMIT,'weights_sha256':WEIGHTS_SHA,
            'original_package_sha256':expected_sha,'native_source_stride':5,
            'labels_accessed_during_scoring':False,'complete_original_scores':entries,'frozen_queues':q,
            'input_commitment_sha256':frozen.input_commitment_sha256,
            'runtime':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__}}


def verify_retention(seal, base):
    if seal.get('lock_commit')!=LOCK_COMMIT or seal.get('all_remote_bytes_readback_verified') is not True:
        raise ValueError('Independent remote readback seal required before outcome access.')
    for exam in COHORT:
        for role in ('originals','scores'):
            record=seal.get('examinations',{}).get(str(exam),{}).get(role,{})
            path=base/f'galar{exam}-{role}.{ "zip" if role=="originals" else "json"}'
            if record.get('remote_sha256')!=sha256_file(path,16*1024**3) or record.get('remote_bytes')!=path.stat().st_size:
                raise ValueError('Missing or mismatched remote retention record.')


def audit(base, labels_path, seal):
    verify_retention(seal,base)
    if sha256_file(labels_path,32*1024**2)!=LABEL_SHA:raise ValueError('Corrected label archive changed.')
    result={'record_type':'galar313437-complete-source-development-v1','lock_commit':LOCK_COMMIT,
            'development_only':True,'model_promoted':False,'patient_independence_verified':False,
            'authors61_80_opened':False,'examinations':{},'macro':{}}
    draws={}
    for exam,(n,positive,total_runs) in COHORT.items():
        s=json.loads((base/f'galar{exam}-scores.json').read_text())
        if (s.get('exam')!=exam or s.get('weights_sha256')!=WEIGHTS_SHA or s.get('lock_commit')!=LOCK_COMMIT
                or s.get('labels_accessed_during_scoring') is not False):raise ValueError('Untrusted score snapshot.')
        entries=s['complete_original_scores'];frames=[x['source_frame'] for x in entries];hashes=[x['original_png_sha256'] for x in entries];scores=[x['original_cnn_score'] for x in entries]
        frozen,q=queues(frames,hashes,scores)
        if s.get('original_package_sha256')!=seal['examinations'][str(exam)]['originals']['remote_sha256'] or len(frames)!=n or q!=s['frozen_queues'] or frozen.input_commitment_sha256!=s['input_commitment_sha256']:
            raise ValueError('Frozen source/queue commitment changed.')
        with zipfile.ZipFile(base/f'galar{exam}-originals.zip') as z:
            members=source_members(z,exam)
            if [f for f,v in members]!=frames:raise ValueError('Original/scored source mismatch.')
            for (_,v),h in zip(members,hashes):
                if hashlib.sha256(z.read(v)).hexdigest()!=h:raise ValueError('Original PNG changed after score freeze.')
        with zipfile.ZipFile(labels_path) as z:rows=parse_corrected_source_rows(z.read(f'{exam}.csv'))
        if [x['frame'] for x in rows]!=frames or any(x['blood'] not in ('0','1') for x in rows):raise ValueError('Incomplete one-to-one explicit label join.')
        y=[int(x['blood']) for x in rows];runs=annotation_runs(y,frames,5)
        if sum(y)!=positive or len(runs)!=total_runs:raise ValueError('Pinned label support changed.')
        # Outcome joins remain private, separate from public aggregate.
        with (base/f'galar{exam}-outcome-join.json').open('x') as f:
            json.dump([dict(e,blood_label=v) for e,v in zip(entries,y)],f)
        result['examinations'][str(exam)]={};draws[str(exam)]={}
        for percent in (10,25):
            report,repetitions=analyze(scores,y,frames,stride=5,percent=percent,exam=exam)
            frozen_q=next(v for v in q if v['review_percent']==percent)
            selected={**frozen_q['policies'],'temporal_window3_score_bin':frozen_q['temporal_window3_score_bin']}
            report['policies']['temporal_window3_score_bin']=metrics(y,runs,selected['temporal_window3_score_bin'])
            for name,positions in selected.items():
                chosen=set(positions);m=report['policies'][name]
                m['singletons_total']=sum(len(r)==1 for r in runs)
                m['singletons_reached']=sum(len(r)==1 and bool(chosen.intersection(r)) for r in runs)
                m['short_runs_missed']=sum(len(r)<=5 and not chosen.intersection(r) for r in runs)
                m['source_position_coverage']=ordinal_coverage(n,positions)
                m['largest_unselected_span_images']=(largest_unselected_span(n,positions) or {}).get('imported_images_not_in_queue',0)
            result['examinations'][str(exam)][str(percent)]=report;draws[str(exam)][str(percent)]=repetitions
            print(f'{exam} {percent}% outcome controls completed',flush=True)
    import numpy as np
    for percent in ('10','25'):
        reports=[result['examinations'][str(e)][percent] for e in (31,34)]
        real=[r['policies']['score_bin']['run_recall'] for r in reports]
        uniform=[r['policies']['uniform']['run_recall'] for r in reports]
        exact=[r['controls']['within_bin_permuted_scores']['analytic_expected_counts']['runs_reached']/r['positive_runs'] for r in reports]
        conditional=np.mean([np.array(draws[str(e)][percent]['permutation'])[:,1]/r['positive_runs'] for e,r in zip((31,34),reports)],axis=0)
        effect=[a-b for a,b in zip(real,exact)]
        result['macro'][percent]={'positive_examinations':2,'score_bin_run_recall':float(np.mean(real)),
            'uniform_run_recall':float(np.mean(uniform)),'score_bin_minus_uniform':float(np.mean(real)-np.mean(uniform)),
            'score_bin_minus_geometry_exact':float(np.mean(effect)),'per_exam_score_information_contrasts':effect,
            'conditional_reference_95':np.quantile(np.mean(real)-conditional,[.025,.975]).tolist(),
            'null_mean_mc_se':float(conditional.std(ddof=1)/100),
            'upper_tail_plus_one':float((1+(conditional>=np.mean(real)).sum())/10001),
            'two_exam_resampling_support_not_population_ci':[min(effect),float(np.mean(effect)),max(effect)]}
    return result,draws


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['score','audit'])
    p.add_argument('--private-dir',type=Path,required=True);p.add_argument('--exam',type=int,choices=COHORT)
    p.add_argument('--originals-sha256');p.add_argument('--model-zip',type=Path);p.add_argument('--labels-zip',type=Path);p.add_argument('--retention-seal',type=Path)
    a=p.parse_args();base=private_path(a.private_dir)
    if a.mode=='score':
        if a.exam is None or a.labels_zip or a.retention_seal or not a.model_zip or not a.originals_sha256:p.error('Scoring requires exam/model/hash and forbids outcome inputs.')
        output=base/f'galar{a.exam}-scores.json'
        if output.exists():raise FileExistsError('Refuse score overwrite.')
        report=score(a.exam,base/f'galar{a.exam}-originals.zip',a.originals_sha256,private_path(a.model_zip))
        with output.open('x') as f:json.dump(report,f,allow_nan=False)
        print(json.dumps({'exam':a.exam,'images_scored':len(report['complete_original_scores']),'snapshot_sha256':sha256_file(output,20*1024**2)}))
    else:
        if a.exam or a.model_zip or not a.labels_zip or not a.retention_seal:p.error('Audit requires labels and independently verified retention seal.')
        if (base/'aggregate.json').exists():raise FileExistsError('Refuse audit overwrite.')
        report,draws=audit(base,private_path(a.labels_zip),json.loads(private_path(a.retention_seal).read_text()))
        for name,data in [('aggregate.json',report),('repetitions-private.json',draws)]:
            with (base/name).open('x') as f:json.dump(data,f,indent=2 if name=='aggregate.json' else None,allow_nan=False)

if __name__=='__main__':main()
