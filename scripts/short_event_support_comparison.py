"""Matched support/balance intervention; reuse PR71 fits, train only new cohort.

All medical inputs and outputs must be outside Git. The joint intervention
changes independent pair support and examination exposure balance, not the CNN,
loss weight, image count, optimizer budget, initialization or stopping rule.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import numpy as np
import torch
from capsule_review.baseline import AnatomyCNN
from local_short_event_ranking import objective
from exam_heldout_pair_transfer import private, sha, shuffled_cycles

EXAMS=(23,25,29,30)
SEEDS=(17,29,43)
ROOT=Path(__file__).resolve().parents[1]

def balanced_pair_schedule(pairs, held_out, seed, count=8192):
    groups={e:[i for i,p in enumerate(pairs) if p['exam']==e] for e in EXAMS if e!=held_out}
    if held_out not in EXAMS or len(groups)!=3 or any(len(v)<10 for v in groups.values()):
        raise ValueError('Four supported examination folds required.')
    exams=sorted(groups);slots=shuffled_cycles(3,count,seed+100003);out=torch.empty(count,dtype=torch.long)
    for j,e in enumerate(exams):
        at=torch.nonzero(slots==j).flatten();ix=shuffled_cycles(len(groups[e]),len(at),seed+200003+e)
        out[at]=torch.tensor(groups[e])[ix]
    if any(pairs[i]['exam']==held_out for i in out.tolist()):raise ValueError('Held-out pair leaked.')
    return out

def verify(lock_path,manifest_path,bank_path):
    lock=json.loads(Path(lock_path).read_text())
    for path,key in [(manifest_path,'manifest_sha256'),(bank_path,'bank_sha256'),(__file__,'training_code_sha256'),(ROOT/'scripts/local_short_event_ranking.py','objective_code_sha256'),(ROOT/'src/capsule_review/baseline.py','architecture_code_sha256')]:
        if sha(path)!=lock[key]:raise ValueError('Frozen source mismatch: '+key)
    if lock['exams']!=list(EXAMS) or lock['seeds']!=list(SEEDS) or lock['updates']!=1024 or lock['ranking_weight']!=.5:
        raise ValueError('Frozen design changed.')
    m=json.loads(private(manifest_path).read_text());a=np.load(private(bank_path),mmap_mode='r')
    if a.dtype!=np.uint8 or a.shape!=(len(m['images']),3,96,96):raise ValueError('Wrong preprocessing bank.')
    if len(m['pairs'])!=69 or len({(p['exam'],p['run_id']) for p in m['pairs']})!=69:
        raise ValueError('Fixed distinct-run population required.')
    return lock,m,a

def fit(lock_path,manifest_path,bank_path,legacy_fits,output,held_out):
    output=private(output);legacy_fits=private(legacy_fits)
    if output.exists():raise FileExistsError('Never overwrite completed fits.')
    _,m,bank=verify(lock_path,manifest_path,bank_path)
    core=[i for i in m['core_indices'] if m['images'][i]['exam']!=held_out]
    train=[p for p in m['pairs'] if p['exam']!=held_out]
    used=set(core)|{p[k] for p in train for k in ('positive_index','negative_index')}
    test={p[k] for p in m['pairs'] if p['exam']==held_out for k in ('positive_index','negative_index')}
    if used&test or any(m['images'][i]['exam']==held_out for i in used):raise ValueError('Examination/source leakage.')
    if {m['images'][i]['sha256'] for i in used}&{m['images'][i]['sha256'] for i in test}:raise ValueError('Byte leakage.')
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    x=torch.from_numpy(np.array(bank,copy=True)).float()/255.;y=torch.tensor([r['blood'] for r in m['images']]);core=torch.tensor(core)
    pos=torch.tensor([p['positive_index'] for p in m['pairs']]);neg=torch.tensor([p['negative_index'] for p in m['pairs']])
    endpoints=sorted(set(pos.tolist()+neg.tolist())|{p[k] for p in m['legacy_pairs'] for k in ('positive_index','negative_index')});old=json.loads((legacy_fits/str(held_out)/'receipts.json').read_text())
    output.mkdir(parents=True);receipts=[]
    for seed in SEEDS:
        co=shuffled_cycles(len(core),16384,seed).reshape(1024,16)
        po=balanced_pair_schedule(m['pairs'],held_out,seed).reshape(1024,8)
        positive=8192+int(y[core[co]].sum());counts=[32768-positive,positive]
        weights=torch.tensor([32768/(2*n) for n in counts])
        # Reconstruct legacy schedule to verify reference ordering/budget; no legacy fit.
        legacy_n=sum(p['exam']!=held_out for p in m['legacy_pairs'])
        old_po=shuffled_cycles(legacy_n,8192,seed+100003).reshape(1024,8)
        old_sha=hashlib.sha256(co.numpy().tobytes()+old_po.numpy().tobytes()).hexdigest()
        old_receipts=[r for r in old if r['seed']==seed]
        if any(r['schedule_sha256']!=old_sha or r['negative_positive_exposures']!=counts for r in old_receipts):raise ValueError('Legacy budget/reference schedule mismatch.')
        exposure={str(e):sum(m['pairs'][i]['exam']==e for i in po.flatten().tolist()) for e in EXAMS if e!=held_out}
        for arm in ('classification','local_ranking'):
            torch.manual_seed(seed);np.random.seed(seed);random.seed(seed);model=AnatomyCNN(2)
            initial=hashlib.sha256(b''.join(v.detach().numpy().tobytes() for v in model.state_dict().values())).hexdigest()
            if any(r['initial_tensor_sha256']!=initial for r in old_receipts):raise ValueError('Legacy initialization mismatch.')
            opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
            for step in range(1024):
                ix=torch.cat([core[co[step]],pos[po[step]],neg[po[step]]]);opt.zero_grad(set_to_none=True)
                loss,_,_=objective(model(x[ix]),y[ix],weights,0. if arm=='classification' else .5)
                if not torch.isfinite(loss):raise ValueError('Nonfinite fit.')
                loss.backward();opt.step()
            ck=output/f'{arm}-seed{seed}.pt';torch.save(model.state_dict(),ck);model.eval()
            with torch.inference_mode():logits=model(x[endpoints]).tolist()
            pred=output/f'{arm}-seed{seed}-logits.json';pred.write_text(json.dumps({'cohort':'expanded_balanced69','exam':held_out,'seed':seed,'arm':arm,'endpoint_indices':endpoints,'logits':logits,'checkpoint_sha256':sha(ck),'lock_sha256':sha(lock_path)},allow_nan=False))
            receipts.append({'cohort':'expanded_balanced69','exam':held_out,'seed':seed,'arm':arm,'initial_tensor_sha256':initial,'schedule_sha256':hashlib.sha256(co.numpy().tobytes()+po.numpy().tobytes()).hexdigest(),'legacy_schedule_verified':True,'negative_positive_exposures':counts,'pair_presentations_by_exam':exposure,'training_distinct_runs':len(train),'heldout_distinct_runs':sum(p['exam']==held_out for p in m['pairs']),'updates':1024,'checkpoint':ck.name,'checkpoint_sha256':sha(ck),'prediction_file':pred.name,'prediction_sha256':sha(pred)})
            print('completed',held_out,seed,arm,flush=True)
    (output/'receipts.json').write_text(json.dumps(receipts,indent=2))

def reuse_legacy(lock_path,manifest_path,bank_path,legacy_fits,output):
    output=private(output);legacy_fits=private(legacy_fits)
    if output.exists():raise FileExistsError('Never replace sealed predictions.')
    _,m,bank=verify(lock_path,manifest_path,bank_path);endpoint=sorted({p[k] for p in m['pairs']+m['legacy_pairs'] for k in ('positive_index','negative_index')})
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True);output.mkdir();receipts=[]
    for e in EXAMS:
        old=json.loads((legacy_fits/str(e)/'receipts.json').read_text());(output/str(e)).mkdir()
        for r in old:
            ck=legacy_fits/str(e)/r['checkpoint'];pred=legacy_fits/str(e)/r['predictions']
            if sha(ck)!=r['checkpoint_sha256'] or sha(pred)!=r['predictions_sha256']:raise ValueError('Retained legacy artifact changed.')
            d=json.loads(pred.read_text());cache=dict(zip(d['endpoint_indices'],d['logits']));missing=[i for i in endpoint if i not in cache]
            if missing:
                model=AnatomyCNN(2);model.load_state_dict(torch.load(ck,weights_only=True,map_location='cpu'));model.eval()
                with torch.inference_mode():fresh=model(torch.from_numpy(np.array(bank[missing],copy=True)).float()/255.).tolist()
                cache.update(zip(missing,fresh))
            dest=output/str(e)/f"{r['arm']}-seed{r['seed']}-logits.json"
            dest.write_text(json.dumps({'cohort':'legacy32','exam':e,'seed':r['seed'],'arm':r['arm'],'endpoint_indices':endpoint,'logits':[cache[i] for i in endpoint],'checkpoint_sha256':sha(ck),'lock_sha256':sha(lock_path),'existing_logits_reused':len(endpoint)-len(missing),'new_endpoint_images_scored':len(missing)},allow_nan=False))
            receipts.append({'exam':e,'seed':r['seed'],'arm':r['arm'],'file':str(dest.relative_to(output)),'sha256':sha(dest),'checkpoint_sha256':sha(ck),'existing_logits_reused':len(endpoint)-len(missing),'new_endpoint_images_scored':len(missing)})
    (output/'reuse-receipts.json').write_text(json.dumps(receipts,indent=2));print('Reused24 PR71 checkpoints;only newly required endpoint logits inferred.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['fit','reuse'])
    for n in ('lock','manifest','bank','legacy-fits','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--exam',type=int,choices=EXAMS);a=p.parse_args()
    if a.mode=='fit':fit(a.lock,a.manifest,a.bank,a.legacy_fits,a.output,a.exam)
    else:reuse_legacy(a.lock,a.manifest,a.bank,a.legacy_fits,a.output)
