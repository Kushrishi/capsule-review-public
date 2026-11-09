"""Evaluate sealed support intervention on the same held-out run population."""
import argparse
import json
from pathlib import Path
import numpy as np
from exam_heldout_pair_transfer import private, sha
from evaluate_exam_pair_transfer import pair_metrics
from short_event_support_comparison import EXAMS, SEEDS

COHORTS=('legacy32','expanded_balanced69')
ARMS=('classification','local_ranking')

def contrast(cells,kind):
    def find(cohort,arm,e,s):
        return next(r['held_out'] for r in cells if (r['cohort'],r['arm'],r['exam'],r['seed'])==(cohort,arm,e,s))
    if kind.startswith('data_'):
        arm=kind.removeprefix('data_');left=('legacy32',arm);right=('expanded_balanced69',arm)
    else:
        cohort=kind.removeprefix('ranking_');left=(cohort,'classification');right=(cohort,'local_ranking')
    paired=[]
    for e in EXAMS:
        for s in SEEDS:
            a,b=find(*left,e,s),find(*right,e,s)
            paired.append({'exam':e,'seed':s,'ordering_difference':b['ordering']-a['ordering'],
                           'singleton_difference':b['singleton_ordering']-a['singleton_ordering'],
                           'mean_margin_difference':b['mean_margin']-a['mean_margin']})
    seeds=[float(np.mean([r['ordering_difference'] for r in paired if r['seed']==s])) for s in SEEDS]
    exams={str(e):float(np.mean([r['ordering_difference'] for r in paired if r['exam']==e])) for e in EXAMS}
    single=float(np.mean([r['singleton_difference'] for r in paired]))
    return {'paired':paired,'mean_ordering_difference':float(np.mean(seeds)),'seed_macro_differences':seeds,
            'seed_sd':float(np.std(seeds,ddof=1)),'per_exam_seed_mean_difference':exams,'singleton_macro_difference':single,
            'consistency_passed':all(x>0 for x in seeds) and all(x>=0 for x in exams.values()) and single>=0,
            'leave_one_exam_out_effect_range':[float(min(np.mean([v for e,v in exams.items() if e!=str(drop)]) for drop in EXAMS)),float(max(np.mean([v for e,v in exams.items() if e!=str(drop)]) for drop in EXAMS))]}

def evaluate(manifest,fits,legacy_predictions,seal,output):
    output=private(output)
    if output.exists():raise FileExistsError('Never overwrite outcomes.')
    m=json.loads(private(manifest).read_text());fits=private(fits);legacy_predictions=private(legacy_predictions)
    sealed=json.loads(private(seal).read_text())
    if sealed['new_fits']!=24 or sealed['legacy_checkpoints_reused']!=24:raise ValueError('Incomplete prespecified comparison.')
    for r in sealed['files']:
        if sha(Path(r['path']))!=r['sha256']:raise ValueError('Pre-outcome seal changed.')
    cells=[]
    for cohort in COHORTS:
        base=fits if cohort=='expanded_balanced69' else legacy_predictions
        for e in EXAMS:
            held=[p for p in m['pairs'] if p['exam']==e]
            train=[p for p in (m['pairs'] if cohort=='expanded_balanced69' else m['legacy_pairs']) if p['exam']!=e]
            for s in SEEDS:
                for arm in ARMS:
                    d=json.loads((base/str(e)/f'{arm}-seed{s}-logits.json').read_text())
                    z={i:v[1]-v[0] for i,v in zip(d['endpoint_indices'],d['logits'])}
                    if any(p['positive_index'] not in z or p['negative_index'] not in z for p in train):raise ValueError('Training diagnostic endpoint missing.')
                    out={'cohort':cohort,'exam':e,'seed':s,'arm':arm}
                    for name,pairs in [('held_out',held),('training',train)]:
                        margins=[z[p['positive_index']]-z[p['negative_index']] for p in pairs]
                        out[name]=pair_metrics(margins,[p['run_length'] for p in pairs])
                        prob=lambda v:1/(1+np.exp(-v))
                        pm=[prob(z[p['positive_index']])-prob(z[p['negative_index']]) for p in pairs]
                        out[name]['probability_margin_quantiles']=np.quantile(pm,[0,.25,.5,.75,1]).tolist()
                    cells.append(out)
    contrasts={k:contrast(cells,k) for k in ('data_classification','data_local_ranking','ranking_legacy32','ranking_expanded_balanced69')}
    macro={c:{a:float(np.mean([r['held_out']['ordering'] for r in cells if r['cohort']==c and r['arm']==a])) for a in ARMS} for c in COHORTS}
    out={'cells':cells,'contrasts':contrasts,'macro_ordering':macro,'distinct_heldout_runs':69,'supported_examinations':4,
         'patient_independence_verified':False,'clinical_model_promoted':False,'intervention':'joint increased run support and equal examination exposure;not a sample-count-only causal estimate',
         'downstream_10pct_endpoint_unchanged':True,'benchmark_eligibility':{'classification':contrasts['data_classification']['consistency_passed'],
             'local_ranking':contrasts['data_local_ranking']['consistency_passed'] and contrasts['ranking_expanded_balanced69']['consistency_passed']}}
    output.mkdir();(output/'aggregate.json').write_text(json.dumps(out,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in out.items() if k!='cells'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','fits','legacy-predictions','seal','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();evaluate(a.manifest,a.fits,a.legacy_predictions,a.seal,a.output)
