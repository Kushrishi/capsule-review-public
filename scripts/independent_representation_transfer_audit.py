"""Independent, no-training replay of existing MobileNet-vs-CNN transfer aggregates.

Reads private sealed evidence only; returns aggregate verification status and never
writes source-level results. Distinct from diagnose_representation_transfer.py.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def extract_rows(foundation_path, prediction_path):
    """Replay per-score ordering in a separate implementation using sorted source pairs."""
    with ZipFile(foundation_path) as primary:
        manifest = json.loads(primary.read('foundation/support-manifest-private.json'))
        foundation = ZipFile(io.BytesIO(primary.read('frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip')))
        pairs = sorted(manifest['pairs'], key=lambda p: (p['exam'],p['run_id']))
        with ZipFile(prediction_path) as modern:
            rows = []
            for model,z in (('cnn',foundation),('mobilenet',modern)):
                for exam in (23,25,29,30):
                    for seed in (17,29,43):
                        for arm in ('classification','ranking'):
                            fname = f'fits/{exam}/{"local_ranking" if arm=="ranking" else arm}-seed{seed}-logits.json' if model=='cnn' else f'predictions/fold{exam}-seed{seed}-{arm}-scores.json'
                            payload=json.loads(z.read(fname))
                            # Independent score calculation: positive class raw logit minus negative class.
                            lookup={i: x[1]-x[0] for i,x in zip(payload['endpoint_indices'],payload['logits'])}
                            if len(lookup)!=len(payload['endpoint_indices']):raise ValueError('Duplicate score index')
                            for row in pairs:
                                delta=lookup[row['positive_index']]-lookup[row['negative_index']]
                                if delta==0:raise ValueError('Unexpected exact tie; diagnostic consensus requires strict signs')
                                rows.append({'model':model,'exam':exam,'seed':seed,'arm':arm,
                                             'pair_exam':row['exam'], 'singleton':row['run_length']==1,
                                             'run_key':(row['exam'],row['run_id']), 'success':delta>0})
            return rows


def verify(records, published):
    from collections import defaultdict
    # Independently aggregate using model/arm and exam filtering; no reuse of the production audit.
    groups=defaultdict(list)
    signs=defaultdict(dict)
    for r in records:
        groups[(r['model'],r['arm'],r['exam'],r['pair_exam']==r['exam'])].append(r['success'])
        if r['pair_exam']==r['exam']:
            key=(r['model'],r['arm'],r['seed'],r['run_key'])
            if key in signs:raise ValueError('Duplicate heldout source run')
            signs[key]=r['success']
    summary={}
    for model in ('cnn','mobilenet'):
        for arm in ('classification','ranking'):
            tag=f'{model}_{arm}'
            train=[];test=[];macro=[]
            for e in (23,25,29,30):
                a=[]
                for s in (17,29,43):
                    grp=[r for r in records if r['model']==model and r['arm']==arm and r['exam']==e and r['seed']==s]
                    tr=[r['success'] for r in grp if r['pair_exam']!=e]
                    ho=[r['success'] for r in grp if r['pair_exam']==e]
                    if not tr or not ho:raise ValueError('Missing fit or heldout pair')
                    train.extend(tr);test.extend(ho);a.append(sum(ho)/len(ho))
                macro.append(sum(a)/3.)
            expected=published['objective_results'][tag]
            assert abs(100*sum(train)/len(train)-expected['training_in_sample_pair_ordering_pct'])<1e-9
            assert abs(100*sum(test)/len(test)-expected['heldout_run_weighted_ordering_pct'])<1e-9
            assert abs(100*sum(macro)/4.-expected['heldout_equal_exam_seed_macro_pct'])<1e-9
            run_keys=sorted({r['run_key'] for r in records if r['model']==model and r['arm']==arm and r['exam']==r['pair_exam']})
            vote_counts=[sum(int(signs[(model,arm,s,rk)]) for s in (17,29,43)) for rk in run_keys]
            consensus=published['seed_consensus'][tag]
            assert (sum(x==3 for x in vote_counts),sum(x==0 for x in vote_counts),sum(x in (1,2) for x in vote_counts)) == (consensus['all_three_correct'],consensus['all_three_wrong'],consensus['mixed_seed_decisions'])
            summary[tag]={'training_pct':100*sum(train)/len(train),'heldout_pct':100*sum(test)/len(test),'macro_pct':100*sum(macro)/4,
                          'all_seeds_wrong':sum(x==0 for x in vote_counts)}
    for model in ('cnn','mobilenet'):
        agree=0;plus=0;minus=0;n=0
        for s in (17,29,43):
            for run_key in {r['run_key'] for r in records if r['model']==model and r['arm']=='classification' and r['exam']==r['pair_exam']}:
                a=signs[(model,'classification',s,run_key)]
                b=signs[(model,'ranking',s,run_key)]
                n+=1;agree+=a==b;plus+=(not a and b);minus+=(a and not b)
        tgt=published['objective_decision_agreement'][model]
        assert (agree,plus,minus,n)==(tgt['identical_decisions'],tgt['ranking_only_correct'],tgt['classification_only_correct'],tgt['decisions_compared'])
    return {'verified':True,'replayed_model_pair_cells':48,'distinct_short_runs':69,'results':summary,
            'source_level_rows_written':False,'new_training_or_evaluation':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--foundation',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--aggregate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError('Do not overwrite verification receipt')
    report=verify(extract_rows(a.foundation,a.predictions),json.loads(a.aggregate.read_text()))
    a.out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('independent replay passed',report['replayed_model_pair_cells'],'model cells')

if __name__=='__main__':main()
