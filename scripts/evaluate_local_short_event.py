"""Evaluate sealed ablation scores on the already-inspected development sources.

No fitting, seed selection or model promotion. Existing historical evaluation
files are read-only. Per-image inputs and queue positions remain private.
"""
from __future__ import annotations
import argparse,csv,io,json,math
from pathlib import Path
import zipfile
import numpy as np
from capsule_review.geometry_control import annotation_runs,metrics,expected_metrics
from capsule_review.priority import select_positions
from local_short_event_ranking import private,sha,SEEDS


def evaluate(lock_path, scores_dir, source_dir, output):
    lock=json.loads(lock_path.read_text());scores_dir=private(scores_dir);source_dir=private(source_dir);output=private(output)
    if output.exists():raise FileExistsError('Do not replace outcomes.')
    seal=json.loads((scores_dir/'score-seal.json').read_text())
    assert len(seal)==18
    for r in seal:assert sha(scores_dir/r['file'])==r['sha256']
    labels=source_dir/'labels.zip'
    assert sha(labels)==lock['labels_zip_sha256']
    assert sha(source_dir/'repetitions-private.json')==lock['historical_repetitions_sha256']
    repetitions=json.loads((source_dir/'repetitions-private.json').read_text())
    result={'development_only':True,'model_promoted':False,'patient_independence_verified':False,
            'reserved61_80_opened':False,'lock_sha256':sha(lock_path),'records':[],'paired_seed_effects':{}}
    queue_record={}
    for exam in (31,34,37):
        old=json.loads((source_dir/f'galar{exam}-scores.json').read_text())
        assert sha(source_dir/f'galar{exam}-scores.json')==lock['historical_score_sha256'][str(exam)]
        entries=old['complete_original_scores'];frames=[x['source_frame'] for x in entries]
        with zipfile.ZipFile(labels) as z:
            rows=list(csv.DictReader(io.StringIO(z.read(f'{exam}.csv').decode('utf-8-sig'))))
        assert frames==[int(x['frame']) for x in rows] and all(x['blood'] in ('0','1') for x in rows)
        y=[int(x['blood']) for x in rows];runs=annotation_runs(y,frames,5)
        vectors=[('historical_checkpoint',None,[x['original_cnn_score'] for x in entries])]
        for arm in ('classification','local_ranking'):
            for seed in SEEDS:
                name=f'{arm}-seed{seed}-exam{exam}.json';s=json.loads((scores_dir/name).read_text())
                assert s['lock_sha256']==sha(lock_path) and s['arm']==arm and s['seed']==seed and s['exam']==exam
                vectors.append((arm,seed,s['scores']))
        for arm,seed,v in vectors:
            assert len(v)==len(y) and all(math.isfinite(s) and 0<=s<=1 for s in v)
            for pct in (10,25):
                k=(len(y)*pct+50)//100
                qs={m:list(select_positions(v,k,m)) for m in ('uniform','score_bin','score','score_diverse')}
                policies={m:metrics(y,runs,q) for m,q in qs.items()}
                for m,q in qs.items():
                    chosen=set(q)
                    policies[m]['singletons_reached']=sum(len(r)==1 and bool(chosen.intersection(r)) for r in runs)
                    policies[m]['singletons_total']=sum(len(r)==1 for r in runs)
                geom=expected_metrics(y,runs,v,k,permuted_scores=False)
                perm=expected_metrics(y,runs,v,k,permuted_scores=True)
                result['records'].append({'arm':arm,'seed':seed,'exam':exam,'percent':pct,'n':len(y),'k':k,
                    'positive_images':sum(y),'positive_runs':len(runs),'policies':policies,
                    'geometry_exact':geom,'score_permutation_exact':perm,
                    'score_effect_pp':100*(policies['score_bin']['runs_reached']-geom['runs_reached'])/len(runs) if runs else None,
                    'raw_minus_uniform_pp':100*(policies['score_bin']['run_recall']-policies['uniform']['run_recall']) if runs else None})
                rr=result['records'][-1]
                cuts=[(j*len(y)//k,(j+1)*len(y)//k) for j in range(k)]
                rr['bins_with_tied_maximum']=sum(sum(s==max(v[a:b]) for s in v[a:b])>1 for a,b in cuts)
                rr['reused_geometry_and_phase_reference']={}
                for key in ('geometry','phases'):
                    arr=np.asarray(repetitions[str(exam)][str(pct)][key],dtype=float)[:,1]
                    rr['reused_geometry_and_phase_reference'][key]={'mean_runs':float(arr.mean()),
                        'run_reference_95':np.quantile(arr,[.025,.975]).tolist(),'draws':len(arr)}
                queue_record[f'{arm}:{seed}:{exam}:{pct}']=qs
    def record(arm,seed,exam,pct):
        return next(r for r in result['records'] if (r['arm'],r['seed'],r['exam'],r['percent'])==(arm,seed,exam,pct))
    def macro(arm,seed,pct):
        rr=[record(arm,seed,e,pct) for e in (31,34)]
        return {'raw_run_recall':sum(r['policies']['score_bin']['run_recall'] for r in rr)/2,
                'score_effect_pp':sum(r['score_effect_pp'] for r in rr)/2,
                'raw_minus_uniform_pp':sum(r['raw_minus_uniform_pp'] for r in rr)/2}
    result['macro']={}
    for pct in (10,25):
        hist=macro('historical_checkpoint',None,pct);perseed=[]
        for seed in SEEDS:
            orig=macro('classification',seed,pct);div=macro('local_ranking',seed,pct)
            perseed.append({'seed':seed,'classification':orig,'local_ranking':div,
                'ranking_minus_classification_pp':100*(div['raw_run_recall']-orig['raw_run_recall']),
                'ranking_minus_historical_pp':100*(div['raw_run_recall']-hist['raw_run_recall'])})
        effects=[r['ranking_minus_classification_pp'] for r in perseed]
        result['macro'][str(pct)]={'historical_checkpoint':hist,'all_paired_seeds':perseed,
            'mean_paired_change_pp':float(np.mean(effects)),'seed_sd_pp':float(np.std(effects,ddof=1)),
            'seed_range_pp':[min(effects),max(effects)],
            'positive_paired_seeds':sum(x>0 for x in effects)}
        geo=(np.array(repetitions['31'][str(pct)]['geometry'])[:,1]/162+
             np.array(repetitions['34'][str(pct)]['geometry'])[:,1]/9)/2
        for item in perseed:
            for arm in ('classification','local_ranking'):
                contrast=100*(item[arm]['raw_run_recall']-geo)
                item[arm]['conditional_geometry_reference_95_pp']=np.quantile(contrast,[.025,.975]).tolist()
        per_exam=[]
        for e in (31,34):
            per_exam.append(sum(100*(record('local_ranking',seed,e,pct)['policies']['score_bin']['run_recall']-
                                    record('classification',seed,e,pct)['policies']['score_bin']['run_recall']) for seed in SEEDS)/3)
        result['macro'][str(pct)]['per_exam_seed_mean_changes_pp']=dict(zip(('31','34'),per_exam))
        result['macro'][str(pct)]['two_exam_resampling_support_pp']=sorted([per_exam[0],sum(per_exam)/2,per_exam[1]])
    output.mkdir();(output/'aggregate.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    (output/'queues-private.json').write_text(json.dumps(queue_record,separators=(',',':')))
    print(json.dumps(result['macro'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lock','scores-dir','source-dir','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();evaluate(a.lock,a.scores_dir,a.source_dir,a.output)
