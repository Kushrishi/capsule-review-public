"""Independent scalar replay; imports no production selectors or evaluator."""
import argparse,csv,hashlib,io,json,math
from pathlib import Path
import zipfile


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def replay(lock, scores_dir, source_dir, outcomes, output):
    contract=json.loads(lock.read_text());report=json.loads((outcomes/'aggregate.json').read_text())
    assert report['lock_sha256']==sha(lock)
    seal=json.loads((scores_dir/'score-seal.json').read_text())
    for s in seal:assert sha(scores_dir/s['file'])==s['sha256']
    assert sha(source_dir/'labels.zip')==contract['labels_zip_sha256']
    checked=0;queues=json.loads((outcomes/'queues-private.json').read_text())
    for e in (31,34,37):
        assert sha(source_dir/f'galar{e}-scores.json')==contract['historical_score_sha256'][str(e)]
        hist=json.loads((source_dir/f'galar{e}-scores.json').read_text())['complete_original_scores']
        with zipfile.ZipFile(source_dir/'labels.zip') as z:
            rows=list(csv.DictReader(io.StringIO(z.read(f'{e}.csv').decode('utf-8-sig'))))
        frames=[r['source_frame'] for r in hist];assert frames==[int(r['frame']) for r in rows]
        assert all(r['blood'] in ('0','1') for r in rows)
        y=[int(r['blood']) for r in rows];n=len(y);runs=[]
        for i,v in enumerate(y):
            if v:
                if i==0 or not y[i-1] or frames[i]-frames[i-1]!=5:runs.append([])
                runs[-1].append(i)
        variants=[('historical_checkpoint',None,[r['original_cnn_score'] for r in hist])]
        for arm in ('original_population','diverse_population'):
            for seed in (17,29,43):
                s=json.loads((scores_dir/f'{arm}-seed{seed}-exam{e}.json').read_text())
                assert s['lock_sha256']==sha(lock);variants.append((arm,seed,s['scores']))
        for arm,seed,v in variants:
            assert len(v)==n and all(math.isfinite(s) and 0<=s<=1 for s in v)
            for pct in (10,25):
                k=(n*pct+50)//100;ranking=sorted(range(n),key=lambda i:(-v[i],i))
                qs={'uniform':[(2*j+1)*n//(2*k) for j in range(k)],'score':ranking[:k]}
                qs['score_bin']=[max(range(j*n//k,(j+1)*n//k),key=lambda i:(v[i],-i)) for j in range(k)]
                radius=n//(2*k);blocked=set();div=[]
                for i in ranking:
                    if i not in blocked:
                        div.append(i);blocked.update(range(max(0,i-radius),min(n,i+radius+1)))
                        if len(div)==k:break
                qs['score_diverse']=div+[i for i in ranking if i not in set(div)][:k-len(div)]
                r=next(x for x in report['records'] if (x['arm'],x['seed'],x['exam'],x['percent'])==(arm,seed,e,pct))
                assert (r['n'],r['k'],r['positive_images'],r['positive_runs'])==(n,k,sum(y),len(runs))
                for method,q in qs.items():
                    assert len(q)==len(set(q))==k
                    assert set(q)==set(queues[f'{arm}:{seed}:{e}:{pct}'][method])
                    selected=set(q);hits=[bool(selected.intersection(run)) for run in runs];m=r['policies'][method]
                    assert m['positive_images']==sum(y[i] for i in q) and m['runs_reached']==sum(hits)
                    assert m['run_recall']==(sum(hits)/len(runs) if runs else None)
                    assert m['singletons_reached']==sum(h for h,run in zip(hits,runs) if len(run)==1)
                    for key,a,b in [('short_1_5',1,5),('medium_6_25',6,25),('long_26_plus',26,n)]:
                        assert m['strata'][key]['total']==sum(a<=len(run)<=b for run in runs)
                        assert m['strata'][key]['reached']==sum(h for h,run in zip(hits,runs) if a<=len(run)<=b)
                for role,ties in [('geometry_exact',False),('score_permutation_exact',True)]:
                    binid=[];prob=[]
                    for j in range(k):
                        a,b=j*n//k,(j+1)*n//k;L=b-a;m=sum(v[i]==max(v[a:b]) for i in range(a,b)) if ties else 1
                        den=math.comb(L,m)
                        for pos in range(L):
                            prob.append(math.comb(L-pos-1,m-1)/den if L-pos>=m else 0.)
                            binid.append(j)
                    expected=[]
                    for run in runs:
                        bybin={}
                        for i in run:bybin[binid[i]]=bybin.get(binid[i],0)+prob[i]
                        expected.append(1-math.prod(max(0.,1-p) for p in bybin.values()))
                    assert abs(sum(expected)-r[role]['runs_reached'])<1e-9
                    assert abs(sum(p*l for p,l in zip(prob,y))-r[role]['positive_images'])<1e-9
                checked+=1
    for pct in (10,25):
        macro=report['macro'][str(pct)];deltas=[]
        for seed in (17,29,43):
            vals={}
            for arm in ('original_population','diverse_population'):
                vals[arm]=sum(r['policies']['score_bin']['run_recall'] for r in report['records'] if r['arm']==arm and r['seed']==seed and r['percent']==pct and r['exam'] in (31,34))/2
            delta=100*(vals['diverse_population']-vals['original_population']);deltas.append(delta)
            out=next(x for x in macro['all_paired_seeds'] if x['seed']==seed)
            assert abs(delta-out['diverse_minus_matched_original_pp'])<1e-10
        assert abs(sum(deltas)/3-macro['mean_paired_change_pp'])<1e-10
        mean=sum(deltas)/3;sd=math.sqrt(sum((x-mean)**2 for x in deltas)/2)
        assert abs(sd-macro['seed_sd_pp'])<1e-10
    proof={'exam_budget_model_records':checked,'policy_sets_replayed':checked*4,
           'exact_null_expectations_replayed':checked*2,'all_seed_macro_changes_verified':True,
           'production_selector_or_evaluator_imported':False,'script_sha256':sha(__file__)}
    with output.open('x') as f:json.dump(proof,f,indent=2)
    print(json.dumps(proof))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lock','scores-dir','source-dir','outcomes','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();replay(a.lock,a.scores_dir,a.source_dir,a.outcomes,a.output)
