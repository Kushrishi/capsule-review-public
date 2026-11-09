#!/usr/bin/env python3
"""Exploratory scale and seed-omission robustness on PR72's ALREADY-inspected fitting exams.
Never write raw logits, pair identities, or protected medical labels to public paths.
Requires privately retained source evidence archive. This is NOT a confirmatory test.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, zipfile
from pathlib import Path
import numpy as np

EXAMS=(23,25,29,30)
SEEDS=(17,29,43)
ARMS=('classification','local_ranking')

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load(outer: Path):
    with zipfile.ZipFile(outer) as f:
        raw_manifest=f.read('foundation/support-manifest-private.json')
        data=f.read('frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip')
        m=json.loads(raw_manifest)
    assert len(m['pairs'])==69
    assert tuple(sorted(set(x['exam'] for x in m['pairs']))) == EXAMS
    assert all(x['run_length']>=1 for x in m['pairs'])
    scores={}
    with zipfile.ZipFile(io.BytesIO(data)) as f:
        seal=json.loads(f.read('preoutcome-seal.json'))
        expected={'/'.join(Path(x['path']).parts[-3:]): (x['sha256'],x['bytes']) for x in seal['files']}
        for ex in EXAMS:
            for arm in ARMS:
                for seed in SEEDS:
                    key=f'fits/{ex}/{arm}-seed{seed}-logits.json'
                    blob=f.read(key)
                    assert key in expected and (sha(blob),len(blob))==expected[key],key
                    d=json.loads(blob)
                    assert (d['exam'],d['seed'],d['arm'])==(ex,seed,arm)
                    idx=d['endpoint_indices']; logits=d['logits']
                    assert len(idx)==len(set(idx))==len(logits)
                    vals={int(k):float(l[1])-float(l[0]) for k,l in zip(idx,logits)}
                    assert all(math.isfinite(v) for v in vals.values())
                    scores[ex,arm,seed]=vals
    assert len(scores)==24
    return m,scores,{'source_sha256':sha(outer.read_bytes()),'manifest_sha256':sha(raw_manifest),'nested_sha256':sha(data)}

def correct_margin(z):
    return float(z>0)+.5*float(z==0)

def calc(x):
    return float(np.mean([correct_margin(v) for v in x]))

def fold_arrays(m,scores,ex,arm):
    held=[p for p in m['pairs'] if p['exam']==ex]
    train=[p for p in m['pairs'] if p['exam']!=ex]
    def mat(pairs):
        return np.asarray([[scores[ex,arm,seed][p['positive_index']]-scores[ex,arm,seed][p['negative_index']] for seed in SEEDS] for p in pairs],dtype=np.float64)
    hold,fit=mat(held),mat(train)
    assert hold.shape==(len(held),3) and fit.shape==(69-len(held),3)
    assert np.isfinite(hold).all() and np.isfinite(fit).all()
    sing=np.array([p['run_length']==1 for p in held],dtype=bool)
    assert 1 <= sing.sum() <= len(held)
    return hold,fit,sing

def results(outer):
    m,scores,provenance=load(outer)
    folded={}
    for arm in ARMS:
      for ex in EXAMS:
        h,t,s=fold_arrays(m,scores,ex,arm)
        # Training-only per-model scaling, no held-out labels used to choose scales.
        rms=np.sqrt(np.mean(t*t,axis=0)); assert (rms>0).all()
        # Probe sensitivity to arbitrary seed-scale ratios rather than optimize weights.
        methods={'individual_seed_mean': np.mean(h>0,axis=1),
                 'three_seed_majority':(np.sum(h>0,axis=1)>=2).astype(float),
                 'raw_mean_margin': (np.mean(h,axis=1)>0).astype(float),
                 'train_rms_normalized_mean':(np.mean(h/rms[None,:],axis=1)>0).astype(float)}
        for i,seed in enumerate(SEEDS):
            keep=[j for j in range(3) if i!=j]
            methods[f'omit_seed_{seed}']= (np.mean(h[:,keep],axis=1)>0).astype(float)
        for i,seed in enumerate(SEEDS):
          for factor in (0.25, 0.5, 2,4):
            adjusted=h.copy();adjusted[:,i]*=factor
            methods[f'rescale_{seed}_x{factor}']=(np.mean(adjusted,axis=1)>0).astype(float)
        folded[arm,ex]={'counts':(len(h),int(s.sum())),'rms':rms.tolist(),
                       'outcomes':{key:(float(v.sum()),float(v[s].sum())) for key,v in methods.items()}}
    method_names=list(folded['local_ranking',23]['outcomes'])
    assert all(set(folded[a,e]['outcomes'])==set(method_names) for a in ARMS for e in EXAMS)
    public={'status':'posthoc_previously_inspected_development_only_no_model_promotion',
            'source_proofs':provenance,'exams':list(EXAMS),
            'seed_ids':list(SEEDS),'counts':{str(e):list(folded['local_ranking',e]['counts']) for e in EXAMS},
            'methods':{},'sensitivity':{}}
    for arm in ARMS:
        public['methods'][arm]={}
        for method in method_names:
            rows=[]
            for e in EXAMS:
                n,ns=folded[arm,e]['counts'];ok,os=folded[arm,e]['outcomes'][method]
                rows.append({'exam':e,'runs':n,'correct':ok,'singletons':ns,'singleton_correct':os,
                             'ordering':ok/n,'singleton_ordering':os/ns})
            public['methods'][arm][method]={'macro':sum(r['ordering'] for r in rows)/4,
                                    'pooled':sum(r['correct'] for r in rows)/69,
                                    'singleton_macro':sum(r['singleton_ordering'] for r in rows)/4,
                                    'singleton_pooled':sum(r['singleton_correct'] for r in rows)/21,
                                    'rows':rows}
        eligible=[k for k in method_names if k.startswith('rescale_')]
        public['sensitivity'][arm]={
          'seed_rescaling_macro_range':[min(public['methods'][arm][k]['macro'] for k in eligible),max(public['methods'][arm][k]['macro'] for k in eligible)],
          'seed_rescaling_singleton_macro_range':[min(public['methods'][arm][k]['singleton_macro'] for k in eligible),max(public['methods'][arm][k]['singleton_macro'] for k in eligible)],
          'training_rms_scales_by_exam':{str(e):folded[arm,e]['rms'] for e in EXAMS},
        }
    return public

def main():
    p=argparse.ArgumentParser();p.add_argument('private_archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    data=results(a.private_archive)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print('VALIDATED 24 previously-sealed PR72 logit files (private source retained)')
    for arm in ARMS:
        for method in ['individual_seed_mean','three_seed_majority','raw_mean_margin','train_rms_normalized_mean']:
            v=data['methods'][arm][method]
            print(arm,method,'macro',round(v['macro']*100,3),'singleton_macro',round(v['singleton_macro']*100,3),'singleton_pooled',round(v['singleton_pooled']*100,3))
        v=data['sensitivity'][arm]
        print('rescaling range',arm, [round(x*100,3) for x in v['seed_rescaling_macro_range']])

if __name__=='__main__':main()