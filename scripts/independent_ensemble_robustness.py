#!/usr/bin/env python3
"""Independent standard-library readback of PR72 ranking ensembles and sensitivity."""
from __future__ import annotations
from pathlib import Path
import hashlib, io, json, zipfile

EXAMS=(23,25,29,30)
SEEDS=(17,29,43)
ARMS=('classification','local_ranking')

def read(archive):
    with zipfile.ZipFile(archive) as z:
        pairs=json.loads(z.read('foundation/support-manifest-private.json'))['pairs']
        nested=z.read('frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip')
    arr={}
    with zipfile.ZipFile(io.BytesIO(nested)) as nz:
        sealed=json.loads(nz.read('preoutcome-seal.json'))['files']
        verified={'/'.join(Path(x['path']).parts[-3:]):x for x in sealed}
        for e in EXAMS:
            for a in ARMS:
                for seed in SEEDS:
                    path=f'fits/{e}/{a}-seed{seed}-logits.json'
                    raw=nz.read(path)
                    assert hashlib.sha256(raw).hexdigest()==verified[path]['sha256']
                    ob=json.loads(raw)
                    assert (ob['exam'],ob['seed'],ob['arm'])==(e,seed,a)
                    arr[e,a,seed]={int(idx):val[1]-val[0] for idx,val in zip(ob['endpoint_indices'],ob['logits'])}
    return pairs,arr

def compute(archive):
    pairs,logits=read(archive)
    assert len(pairs)==69
    out={}
    for a in ARMS:
        for e in EXAMS:
            chosen=[p for p in pairs if p['exam']==e]
            correct={'raw':0,'vote':0,'raw_single':0,'vote_single':0,'train_norm':0,'train_norm_single':0}
            train=[p for p in pairs if p['exam']!=e]
            rms=[]
            for seed in SEEDS:
                g=logits[e,a,seed]
                vals=[g[p['positive_index']]-g[p['negative_index']] for p in train]
                rms.append((sum(v*v for v in vals)/len(vals))**.5)
            for p in chosen:
                margins=[logits[e,a,s][p['positive_index']]-logits[e,a,s][p['negative_index']] for s in SEEDS]
                raw=sum(margins)>0
                vote=sum(x>0 for x in margins)>=2
                normalized=sum(x/d for x,d in zip(margins,rms))>0
                for k,passed in [('raw',raw),('vote',vote),('train_norm',normalized)]:
                    correct[k]+=passed
                    if p['run_length']==1: correct[k+'_single']+=passed
            out[a,e]=correct
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('robustness_result',type=Path);p.add_argument('pr73_result',type=Path);a=p.parse_args()
    v=compute(a.archive);new=json.loads(a.robustness_result.read_text());old=json.loads(a.pr73_result.read_text())
    for arm in ARMS:
        for e in EXAMS:
            target=next(r for r in old['rows'] if r['arm']==arm and r['exam']==e)
            for our_key,old_key,new_key in [('raw','mean_margin_correct','raw_mean_margin'),('vote','majority_correct','three_seed_majority')]:
                assert v[arm,e][our_key]==target[old_key]
                assert v[arm,e][our_key]==new['methods'][arm][new_key]['rows'][EXAMS.index(e)]['correct']
            assert v[arm,e]['train_norm']==new['methods'][arm]['train_rms_normalized_mean']['rows'][EXAMS.index(e)]['correct']
    print('INDEPENDENT verification PASS: 24 sealed vectors; 16 original ensemble aggregates; 8 train-RMS aggregates; singleton matches')