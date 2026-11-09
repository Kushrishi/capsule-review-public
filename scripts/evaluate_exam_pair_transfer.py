"""Outcome calculation after all thirty private held-out fits are sealed."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from exam_heldout_pair_transfer import EXAMS, SEEDS, fold_indices, private, sha

def pair_metrics(margins, lengths):
    a = np.asarray(margins, dtype=float)
    if len(a) == 0 or not np.isfinite(a).all():
        raise ValueError('Finite nonempty margins required.')
    order = (a > 0).astype(float) + .5*(a == 0)
    single = np.asarray(lengths) == 1
    return {'pairs': len(a), 'correct': int((a > 0).sum()),
            'ties': int((a == 0).sum()), 'ordering': float(order.mean()),
            'mean_margin': float(a.mean()), 'margin_quantiles': np.quantile(a, [0,.25,.5,.75,1]).tolist(),
            'singletons': int(single.sum()),
            'singleton_ordering': float(order[single].mean()) if single.any() else None}

def evaluate(manifest, fits, seal_path, output):
    output = private(output)
    if output.exists():
        raise FileExistsError('Never replace outcomes.')
    m = json.loads(private(manifest).read_text())
    fits = private(fits)
    seal = json.loads(private(seal_path).read_text())
    if len(seal['predictions']) != 30:
        raise ValueError('All30 fits required before outcomes.')
    for r in seal['files']:
        if sha(fits/r['file']) != r['sha256']:
            raise ValueError('Pre-outcome seal mismatch.')
    cells = []
    for e in EXAMS:
        _, train, held = fold_indices(m, e)
        for seed in SEEDS:
            for arm in ('classification','local_ranking'):
                d = json.loads((fits/str(e)/f'{arm}-seed{seed}-logits.json').read_text())
                z = {i: row[1]-row[0] for i,row in zip(d['endpoint_indices'], d['logits'])}
                prob = {i: 1/(1+np.exp(-v)) for i,v in z.items()}
                out = {'exam': e, 'seed': seed, 'arm': arm}
                for name, pairs in [('held_out',held), ('training',train)]:
                    margins = [z[p['positive_index']]-z[p['negative_index']] for p in pairs]
                    out[name] = pair_metrics(margins, [p['run_length'] for p in pairs])
                    pm = [prob[p['positive_index']]-prob[p['negative_index']] for p in pairs]
                    out[name]['probability_margin_quantiles'] = np.quantile(pm,[0,.25,.5,.75,1]).tolist()
                cells.append(out)
    paired = []
    for e in EXAMS:
        for seed in SEEDS:
            c,r = [next(x for x in cells if x['exam']==e and x['seed']==seed and x['arm']==arm)
                   for arm in ('classification','local_ranking')]
            paired.append({'exam':e,'seed':seed,'ordering_difference':r['held_out']['ordering']-c['held_out']['ordering'],
                           'mean_logit_margin_difference':r['held_out']['mean_margin']-c['held_out']['mean_margin']})
    per_exam = [{'exam':e, 'mean_ordering_difference':float(np.mean([x['ordering_difference'] for x in paired if x['exam']==e]))}
                for e in EXAMS]
    seed_effect = [float(np.mean([x['ordering_difference'] for x in paired if x['seed']==s])) for s in SEEDS]
    macro = {arm:float(np.mean([x['held_out']['ordering'] for x in cells if x['arm']==arm])) for arm in ('classification','local_ranking')}
    support_sensitivity = {arm:float(np.mean([x['held_out']['ordering'] for x in cells if x['arm']==arm and x['exam'] in (29,30)])) for arm in macro}
    mean_effect = float(np.mean(seed_effect))
    consistency = all(v>0 for v in seed_effect) and all(x['mean_ordering_difference']>=0 for x in per_exam)
    summary = {'cells':cells,'paired':paired,'per_exam':per_exam,'primary_macro_ordering':macro,
               'primary_mean_paired_difference':mean_effect,'seed_macro_differences':seed_effect,
               'seed_difference_sd':float(np.std(seed_effect,ddof=1)),
               'higher_support_29_30_sensitivity':support_sensitivity,
               'leave_one_exam_out_effect_range':[float(min(np.mean([x['mean_ordering_difference'] for x in per_exam if x['exam']!=e]) for e in EXAMS)),float(max(np.mean([x['mean_ordering_difference'] for x in per_exam if x['exam']!=e]) for e in EXAMS))],
               'consistency_passed':consistency,'promotion':False,
               'unit':'five examinations;32 annotation runs;seeds are repeated algorithmic fits, not patients',
               'patient_independence_verified':False}
    output.mkdir()
    (output/'aggregate.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('cells','paired')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','fits','seal','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();evaluate(a.manifest,a.fits,a.seal,a.output)
