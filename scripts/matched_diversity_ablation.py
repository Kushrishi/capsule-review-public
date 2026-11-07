"""Fixed-budget fitting-examination diversity ablation; private inputs/outputs only.

No source download, label access during fitting/scoring, or benchmark selection.
Source verification and a committed lock must precede execution. Checkpoints and
scores stay outside public Git. Evaluation is a separate sealed-score operation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (17, 29, 43)
FIT_EXAMS = tuple(range(1, 9)) + (21, 23, 25, 27, 29, 30)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def private(path):
    path = Path(path)
    if path.is_symlink() or path.resolve().is_relative_to(ROOT):
        raise ValueError('Research inputs/outputs must remain outside public Git.')
    return path.resolve()


def balanced_sample(rows, count, label):
    """Capacity-constrained round-robin over exams; hash order within exams.

    One fixed sample, shared by all optimizer seeds. Only fitting labels and
    source identities enter the sampler. No benchmark-derived quantities.
    """
    groups = {}
    for r in rows:
        if r['blood'] == label:
            groups.setdefault(r['exam'], []).append(r)
    if sum(map(len, groups.values())) < count:
        raise ValueError('Insufficient distinct class support; amendment required.')
    for e in groups:
        groups[e].sort(key=lambda r: hashlib.sha256(
            f"20261107:{e}:{r['frame']}:{r['sha256']}".encode()).hexdigest())
    taken = {e: 0 for e in groups}
    result = []
    while len(result) < count:
        for e in sorted(groups):
            if taken[e] < len(groups[e]):
                result.append(groups[e][taken[e]])
                taken[e] += 1
                if len(result) == count: break
    return result


def select_arms(rows):
    if ({r['exam'] for r in rows} != set(FIT_EXAMS)
            or len(rows) != 7168
            or any(r['blood'] not in (0, 1) for r in rows)
            or len({(r['exam'], r['frame']) for r in rows}) != len(rows)
            or len({r['sha256'] for r in rows}) != len(rows)
            or any(sum(r['exam'] == e for r in rows) != 512 for e in FIT_EXAMS)):
        raise ValueError('Reference population, labels or identities changed.')
    original = [r for r in rows if r['exam'] in range(1, 9)]
    diverse = balanced_sample(rows, 239, 1) + balanced_sample(rows, 3857, 0)
    arms = {}
    for name, arm in [('original_population', original), ('diverse_population', diverse)]:
        if len(arm) != 4096 or sum(r['blood'] for r in arm) != 239:
            raise ValueError('Exact matched class counts required.')
        # Identical label sequence makes every paired shuffled batch class matched.
        arms[name] = sorted(arm, key=lambda r: (r['blood'], r['exam'], r['frame']))
    if [r['blood'] for r in arms['original_population']] != [r['blood'] for r in arms['diverse_population']]:
        raise ValueError('Paired batch class labels differ.')
    return arms


def validate(lock_path, manifest_path, tensor_path):
    lock = json.loads(Path(lock_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    if (lock['harness_sha256'] != sha(__file__)
            or lock['private_manifest_sha256'] != sha(manifest_path)
            or lock['fitting_tensor_sha256'] != sha(tensor_path)
            or lock['seeds'] != list(SEEDS)
            or lock['training'] != {'epochs': 8, 'updates': 1024, 'batch': 32,
                                   'lr': 0.001, 'weight_decay': 0.0001,
                                   'positive': 239, 'other': 3857}):
        raise ValueError('Frozen contract/input identity mismatch.')
    return lock, manifest


def fit(lock_path, manifest_path, tensor_path, output):
    import numpy as np
    import torch
    from capsule_review.baseline import AnatomyCNN
    from torch.utils.data import DataLoader, TensorDataset
    output = private(output)
    if output.exists(): raise FileExistsError('Never overwrite research outputs.')
    lock, manifest = validate(lock_path, private(manifest_path), private(tensor_path))
    a = np.load(tensor_path, mmap_mode='r')
    if a.dtype != np.uint8 or a.shape != (7168, 3, 96, 96): raise ValueError('Wrong tensor bank.')
    arms = select_arms(manifest['pool'])
    output.mkdir()
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    receipts = []
    for seed in SEEDS:
        for name, rows in arms.items():
            torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
            model = AnatomyCNN(2).cpu()
            initial = {k: v.detach().clone() for k, v in model.state_dict().items()}
            x = torch.from_numpy(np.array(a[[r['tensor_index'] for r in rows]], copy=True)).float() / 255.
            y = torch.tensor([r['blood'] for r in rows], dtype=torch.long)
            loader = DataLoader(TensorDataset(x, y), batch_size=32, shuffle=True,
                                generator=torch.Generator().manual_seed(seed), num_workers=0)
            opt = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
            weights = torch.tensor([4096/(2*3857), 4096/(2*239)], dtype=torch.float32)
            history=[]; updates=0
            for epoch in range(1,9):
                model.train(); losses=[]
                for bx,by in loader:
                    opt.zero_grad(set_to_none=True)
                    loss=torch.nn.functional.cross_entropy(model(bx),by,weight=weights)
                    if not torch.isfinite(loss): raise ValueError('Nonfinite loss.')
                    loss.backward(); opt.step(); updates+=1; losses.append(float(loss.detach()))
                history.append({'epoch':epoch,'mean_weighted_batch_loss':sum(losses)/len(losses)})
                print(name,seed,'epoch',epoch,'updates',updates,'loss',history[-1]['mean_weighted_batch_loss'],flush=True)
            assert updates==1024
            path=output/f'{name}-seed{seed}.pt'
            torch.save(model.state_dict(),path)
            # Canonical tensor digest avoids torch ZIP filename/serialization effects.
            initial_sha=hashlib.sha256(b''.join(v.numpy().tobytes() for v in initial.values())).hexdigest()
            receipts.append({'arm':name,'seed':seed,'updates':updates,'initial_tensor_sha256':initial_sha,
                             'checkpoint_file':path.name,'checkpoint_sha256':sha(path),
                             'history':history,'lock_sha256':sha(lock_path)})
            del model,x,y,loader,opt
    for seed in SEEDS:
        assert len({r['initial_tensor_sha256'] for r in receipts if r['seed']==seed})==1
    (output/'training-receipts.json').write_text(json.dumps(receipts,indent=2))


def score(lock_path, manifest_path, tensor_path, checkpoints, benchmark_dir, output):
    import numpy as np
    import torch
    from capsule_review.baseline import AnatomyCNN
    lock,_=validate(lock_path,private(manifest_path),private(tensor_path))
    checkpoints=private(checkpoints);benchmark_dir=private(benchmark_dir);output=private(output)
    if output.exists():raise FileExistsError('Never replace frozen scores.')
    output.mkdir();torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    receipts=json.loads((checkpoints/'training-receipts.json').read_text());proof=[]
    if len(receipts)!=6:raise ValueError('All six fixed fits are required.')
    for exam in (31,34,37):
        bank=benchmark_dir/f'benchmark{exam}.npy'
        if sha(bank)!=lock['benchmark_tensor_sha256'][str(exam)]:raise ValueError('Benchmark source changed.')
        a=np.load(bank,mmap_mode='r')
        for r in receipts:
            ck=checkpoints/r['checkpoint_file'];assert sha(ck)==r['checkpoint_sha256']
            model=AnatomyCNN(2);model.load_state_dict(torch.load(ck,weights_only=True,map_location='cpu'));model.eval()
            scores=[]
            with torch.inference_mode():
                for j in range(0,len(a),32):
                    x=torch.from_numpy(np.array(a[j:j+32],copy=True)).float()/255.
                    scores.extend(torch.softmax(model(x),dim=1)[:,1].tolist())
            assert len(scores)==len(a) and all(0<=s<=1 for s in scores)
            dest=output/f"{r['arm']}-seed{r['seed']}-exam{exam}.json"
            dest.write_text(json.dumps({'arm':r['arm'],'seed':r['seed'],'exam':exam,
                'checkpoint_sha256':r['checkpoint_sha256'],'lock_sha256':sha(lock_path),
                'tensor_sha256':sha(bank),'scores':scores},separators=(',',':')))
            proof.append({'file':dest.name,'sha256':sha(dest),'images':len(a)})
            print(r['arm'],r['seed'],'exam',exam,'scored',len(a),flush=True)
    (output/'score-seal.json').write_text(json.dumps(proof,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['fit','score']);p.add_argument('--lock',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--tensor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--checkpoints',type=Path)
    p.add_argument('--benchmark-dir',type=Path)
    args=p.parse_args()
    if args.mode=='fit':fit(args.lock,args.manifest,args.tensor,args.output)
    else:score(args.lock,args.manifest,args.tensor,args.checkpoints,args.benchmark_dir,args.output)
