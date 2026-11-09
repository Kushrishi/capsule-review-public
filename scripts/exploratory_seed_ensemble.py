#!/usr/bin/env python3
"""Retrospective seeded-ensemble diagnostic. Raw PR72 data stays private."""
from __future__ import annotations
import argparse,hashlib,io,json,zipfile
from pathlib import Path

EXAMS=(23,25,29,30);SEEDS=(17,29,43);ARMS=('classification','local_ranking')


def ensemble_outcomes(margins):
    """Three paired seed margins; return majority-vote and mean-margin credits."""
    assert len(margins)==3 and all(abs(x)<1e12 for x in margins)
    positives=sum(x>0 for x in margins)
    negatives=sum(x<0 for x in margins)
    vote=1.0 if positives>=2 else 0.0 if negatives>=2 else 0.5
    mean=sum(margins)
    raw=1.0 if mean>0 else 0.0 if mean<0 else 0.5
    return vote,raw


def digest(raw):return hashlib.sha256(raw).hexdigest()

def main(archive:Path, out:Path):
    with zipfile.ZipFile(archive) as z:
        manifest_bytes=z.read('foundation/support-manifest-private.json')
        manifest=json.loads(manifest_bytes)
        raw_nested=z.read('frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip')
    pairs=manifest['pairs'];assert len(pairs)==69
    assert sorted(set(p['exam'] for p in pairs))==list(EXAMS)
    assert sorted(set((p['exam'],p['run_id']) for p in pairs))==sorted((p['exam'],p['run_id']) for p in pairs)
    with zipfile.ZipFile(io.BytesIO(raw_nested)) as f:
        seal=json.loads(f.read('preoutcome-seal.json'))
        hashmap={'/'.join(Path(x['path']).parts[-3:]):(x['sha256'],x['bytes']) for x in seal['files']}
        scores={}
        for ex in EXAMS:
            for arm in ARMS:
                for seed in SEEDS:
                    name=f'{arm}-seed{seed}-logits.json'
                    key=f'fits/{ex}/{name}'
                    b=f.read(key)
                    assert key in hashmap and (digest(b),len(b))==hashmap[key], ('sealed hash mismatch',key)
                    d=json.loads(b)
                    assert (d['exam'],d['seed'],d['arm'])==(ex,seed,arm)
                    assert len(d['endpoint_indices'])==len(d['logits'])
                    assert len(d['endpoint_indices'])==len(set(d['endpoint_indices']))
                    vals={int(idx):float(log[1])-float(log[0]) for idx,log in zip(d['endpoint_indices'],d['logits'])}
                    assert all(abs(v)<1e12 for v in vals.values())
                    scores[ex,arm,seed]=vals
    result=[]
    for ex in EXAMS:
        this=[p for p in pairs if p['exam']==ex]
        for arm in ARMS:
            indiv=[0.0]*3
            voted=0.0;meaned=0.0
            indiv_single=[0.0]*3
            vote_single=mean_single=0.0
            single_count=0
            for p in this:
                z=[]
                for seed in SEEDS:
                    x=scores[ex,arm,seed]
                    z.append(x[p['positive_index']]-x[p['negative_index']])
                indicators=[float(v>0)+0.5*float(v==0) for v in z]
                vote,mean=ensemble_outcomes(z)
                for k,v in enumerate(indicators):indiv[k]+=v
                voted+=vote;meaned+=mean
                if p['run_length']==1:
                    single_count+=1
                    for k,v in enumerate(indicators):indiv_single[k]+=v
                    vote_single+=vote;mean_single+=mean
            result.append({'exam':ex,'arm':arm,'distinct_runs':len(this),'singletons':single_count,
                           'seed_correct':indiv,'majority_correct':voted,'mean_margin_correct':meaned,
                           'singleton_seed_correct':indiv_single,'singleton_majority_correct':vote_single,
                           'singleton_mean_margin_correct':mean_single})
    out.parent.mkdir(parents=True,exist_ok=True)
    public={'status':'exploratory_posthoc_no_promotion','input_outer_sha256':digest(archive.read_bytes()),
            'input_nested_sha256':digest(raw_nested),'input_manifest_sha256':digest(manifest_bytes),
            'rows':result,'summary':{}}
    for arm in ARMS:
        rows=[x for x in result if x['arm']==arm]
        summary={}
        for key in ('individual_seed_mean','three_seed_majority','three_seed_raw_margin_mean'):
            def fractions(r):
                if key=='individual_seed_mean':return sum(r['seed_correct'])/(3*r['distinct_runs'])
                if key=='three_seed_majority':return r['majority_correct']/r['distinct_runs']
                return r['mean_margin_correct']/r['distinct_runs']
            def sing(r):
                if key=='individual_seed_mean':return sum(r['singleton_seed_correct'])/(3*r['singletons'])
                if key=='three_seed_majority':return r['singleton_majority_correct']/r['singletons']
                return r['singleton_mean_margin_correct']/r['singletons']
            summary[key]={'macro_ordering':sum(map(fractions,rows))/len(rows),
                          'macro_singleton':sum(map(sing,rows))/len(rows),
                          'pooled_runs_correct_or_mean':sum((r['majority_correct'] if key=='three_seed_majority' else r['mean_margin_correct'] if key=='three_seed_raw_margin_mean' else sum(r['seed_correct'])/3) for r in rows),
                          'distinct_runs_total':69}
        public['summary'][arm]=summary
    out.write_text(json.dumps(public,indent=2,allow_nan=False)+'\n')
    print('VERIFIED 24 sealed prediction files and evaluated 69 distinct runs')
    for arm in ARMS:
        for k,x in public['summary'][arm].items():print(arm,k,'ordering',f"{100*x['macro_ordering']:.3f}%",'singleton',f"{100*x['macro_singleton']:.3f}%")

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();main(a.archive,a.output)