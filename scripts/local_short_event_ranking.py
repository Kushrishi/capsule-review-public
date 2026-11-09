"""Single matched CE versus CE+local-ranking experiment; private medical inputs.

Both arms see the same 16 reference images and eight real adjacent +/- pairs
per batch. No acquisition, validation-label access, checkpoint or seed selection.
"""
from __future__ import annotations
import argparse,hashlib,json,random
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from capsule_review.baseline import AnatomyCNN

ROOT=Path(__file__).resolve().parents[1]
SEEDS=(17,29,43)
ARMS=('classification','local_ranking')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def private(path):
    p=Path(path)
    if p.is_symlink() or p.resolve().is_relative_to(ROOT):raise ValueError('Private inputs/outputs must stay outside Git.')
    return p.resolve()

def schedule(seed):
    c=torch.Generator().manual_seed(seed)
    p=torch.Generator().manual_seed(seed+100003)
    core=torch.cat([torch.randperm(4096,generator=c) for _ in range(4)]).reshape(1024,16)
    pairs=torch.cat([torch.randperm(32,generator=p) for _ in range(256)]).reshape(1024,8)
    return core,pairs

def objective(logits,labels,weights,ranking_weight):
    if logits.shape!=(32,2) or labels.shape!=(32,) or ranking_weight not in (0.,.5):raise ValueError('Frozen batch/objective mismatch.')
    if not torch.all(labels[16:24]==1) or not torch.all(labels[24:]==0):raise ValueError('Local pairs must contain explicit positive/negative endpoints.')
    ce=F.cross_entropy(logits,labels,weight=weights)
    blood_logit=logits[:,1]-logits[:,0]
    ranking=F.softplus(blood_logit[24:]-blood_logit[16:24]).mean()
    return ce+ranking_weight*ranking,ce,ranking

def validate(lock_path,manifest_path,bank_path):
    lock=json.loads(Path(lock_path).read_text());m=json.loads(Path(manifest_path).read_text())
    if lock['training_code_sha256']!=sha(__file__) or lock['private_manifest_sha256']!=sha(manifest_path) or lock['fitting_bank_sha256']!=sha(bank_path):raise ValueError('Frozen source/code mismatch.')
    if lock['seeds']!=list(SEEDS) or lock['ranking_weight']!=.5 or lock['updates']!=1024:raise ValueError('Frozen design changed.')
    if len(m['core_indices'])!=4096 or len(m['pairs'])!=32:raise ValueError('Fixed population support required.')
    rows=m['images'];allowed=set(range(1,9))|{21,23,25,27,29,30}
    if any(r['exam'] not in allowed or r['blood'] not in (0,1) for r in rows):raise ValueError('Forbidden source or unknown label.')
    if len({(r['exam'],r['frame']) for r in rows})!=len(rows) or len({r['sha256'] for r in rows})!=len(rows):raise ValueError('Duplicated source input.')
    core=m['core_indices']
    if len(set(core))!=4096 or sum(rows[i]['blood'] for i in core)!=239:raise ValueError('Historical reference membership/class counts changed.')
    runs=set();byexam={}
    for pair in m['pairs']:
        a,b=rows[pair['positive_index']],rows[pair['negative_index']]
        if a['exam']!=b['exam'] or abs(a['frame']-b['frame'])!=5 or (a['blood'],b['blood'])!=(1,0) or not 1<=pair['run_length']<=5:raise ValueError('A genuine adjacent short-event pair is required.')
        key=(a['exam'],pair['run_id']);runs.add(key);byexam[a['exam']]=byexam.get(a['exam'],0)+1
    if len(runs)!=32 or len(byexam)<4 or max(byexam.values())>16:raise ValueError('Run diversity gate failed.')
    return lock,m

def fit(lock_path,manifest_path,bank_path,output):
    output=private(output)
    if output.exists():raise FileExistsError('Never replace completed fits.')
    lock,m=validate(lock_path,private(manifest_path),private(bank_path));a=np.load(bank_path,mmap_mode='r')
    if a.dtype!=np.uint8 or a.shape!=(len(m['images']),3,96,96):raise ValueError('Wrong preprocessing bank.')
    x=torch.from_numpy(np.array(a,copy=True)).float()/255.;y=torch.tensor([r['blood'] for r in m['images']])
    core=torch.tensor(m['core_indices']);pos=torch.tensor([r['positive_index'] for r in m['pairs']]);neg=torch.tensor([r['negative_index'] for r in m['pairs']])
    weights=torch.tensor([32768/(2*23620),32768/(2*9148)],dtype=torch.float32)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True);output.mkdir();receipts=[]
    for seed in SEEDS:
        co,po=schedule(seed);schedule_sha=hashlib.sha256(co.numpy().tobytes()+po.numpy().tobytes()).hexdigest()
        for arm in ARMS:
            torch.manual_seed(seed);np.random.seed(seed);random.seed(seed);model=AnatomyCNN(2)
            initial=hashlib.sha256(b''.join(v.detach().numpy().tobytes() for v in model.state_dict().values())).hexdigest()
            opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001);logs=[];losses=[];label_counts=[0,0]
            for step in range(1024):
                ix=torch.cat([core[co[step]],pos[po[step]],neg[po[step]]]);bx=x[ix];by=y[ix]
                opt.zero_grad(set_to_none=True);loss,ce,rank=objective(model(bx),by,weights,0. if arm=='classification' else .5)
                if not torch.isfinite(loss):raise ValueError('Nonfinite training objective.')
                loss.backward();opt.step();losses.append([float(v.detach()) for v in (loss,ce,rank)])
                label_counts[1]+=int(by.sum());label_counts[0]+=32-int(by.sum())
                if (step+1)%128==0:
                    logs.append({'updates':step+1,'mean_total_ce_rank_losses':np.mean(losses,axis=0).tolist()});losses=[]
                    print(arm,seed,'updates',step+1,logs[-1]['mean_total_ce_rank_losses'],flush=True)
            assert label_counts==[23620,9148]
            f=output/f'{arm}-seed{seed}.pt';torch.save(model.state_dict(),f)
            receipts.append({'arm':arm,'seed':seed,'checkpoint_file':f.name,'checkpoint_sha256':sha(f),'initial_tensor_sha256':initial,'schedule_sha256':schedule_sha,'updates':1024,'negative_positive_exposures':label_counts,'lock_sha256':sha(lock_path),'logs':logs})
    for seed in SEEDS:
        for key in ('initial_tensor_sha256','schedule_sha256'):assert len({r[key] for r in receipts if r['seed']==seed})==1
    (output/'training-receipts.json').write_text(json.dumps(receipts,indent=2))

def score(lock_path,checkpoints,benchmark_dir,output):
    output=private(output);checkpoints=private(checkpoints);benchmark_dir=private(benchmark_dir)
    if output.exists():raise FileExistsError('Never replace scores.')
    lock=json.loads(Path(lock_path).read_text());assert lock['training_code_sha256']==sha(__file__)
    rows=json.loads((checkpoints/'training-receipts.json').read_text());assert len(rows)==6
    output.mkdir();torch.set_num_threads(2);torch.use_deterministic_algorithms(True);proof=[]
    for exam,n in [(31,24919),(34,10867),(37,18125)]:
        bank=benchmark_dir/f'benchmark{exam}.npy';a=np.load(bank,mmap_mode='r');assert a.shape==(n,3,96,96) and a.dtype==np.uint8
        source=json.loads((benchmark_dir/f'benchmark{exam}-ready.json').read_text());assert source['all_png_sha256_verified'] is True and source['tensor_sha256']==sha(bank)==lock['benchmark_tensor_sha256'][str(exam)]
        for r in rows:
            ck=checkpoints/r['checkpoint_file'];assert sha(ck)==r['checkpoint_sha256'] and r['lock_sha256']==sha(lock_path)
            model=AnatomyCNN(2);model.load_state_dict(torch.load(ck,weights_only=True,map_location='cpu'));model.eval();scores=[]
            with torch.inference_mode():
                for j in range(0,n,32):scores.extend(torch.softmax(model(torch.from_numpy(np.array(a[j:j+32],copy=True)).float()/255.),1)[:,1].tolist())
            assert len(scores)==n and all(0<=v<=1 for v in scores)
            f=output/f"{r['arm']}-seed{r['seed']}-exam{exam}.json";f.write_text(json.dumps({'arm':r['arm'],'seed':r['seed'],'exam':exam,'lock_sha256':sha(lock_path),'checkpoint_sha256':r['checkpoint_sha256'],'source_tensor_sha256':sha(bank),'scores':scores},separators=(',',':')))
            proof.append({'file':f.name,'images':n,'sha256':sha(f)});print(r['arm'],r['seed'],exam,'scored',n,flush=True)
    (output/'score-seal.json').write_text(json.dumps(proof,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['fit','score']);p.add_argument('--lock',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path);p.add_argument('--bank',type=Path);p.add_argument('--checkpoints',type=Path);p.add_argument('--benchmark-dir',type=Path);args=p.parse_args()
    if args.mode=='fit':fit(args.lock,args.manifest,args.bank,args.output)
    else:score(args.lock,args.checkpoints,args.benchmark_dir,args.output)
