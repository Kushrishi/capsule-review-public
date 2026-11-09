"""Fixed examination-held-out objective diagnostic; authorized private inputs only.

No acquisition or benchmark access. One complete examination is excluded from
references and pairs. Outputs are private checkpoint and pair-level records.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import numpy as np
import torch
from capsule_review.baseline import AnatomyCNN
from local_short_event_ranking import objective

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (17, 29, 43)
EXAMS = (21, 23, 25, 29, 30)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def private(path):
    p = Path(path)
    if p.is_symlink() or p.resolve().is_relative_to(ROOT):
        raise ValueError('Medical input/output must be outside public Git.')
    return p.resolve()

def shuffled_cycles(n, count, seed):
    if n < 1 or count < 1:
        raise ValueError('Nonempty population/exposure count required.')
    g = torch.Generator().manual_seed(seed)
    return torch.cat([torch.randperm(n, generator=g)
                      for _ in range(math.ceil(count / n))])[:count]

def fold_indices(m, exam):
    rows = m['images']
    if exam not in EXAMS:
        raise ValueError('Unspecified fold.')
    core = [i for i in m['core_indices'] if rows[i]['exam'] != exam]
    train = [p for p in m['pairs'] if p['exam'] != exam]
    held = [p for p in m['pairs'] if p['exam'] == exam]
    used = set(core) | {p[k] for p in train for k in ('positive_index', 'negative_index')}
    test = {p[k] for p in held for k in ('positive_index', 'negative_index')}
    if not core or not train or not held or used & test:
        raise ValueError('Invalid fold support or source overlap.')
    if any(rows[i]['exam'] == exam for i in used):
        raise ValueError('Held-out examination leaked into fitting.')
    if {rows[i]['sha256'] for i in used} & {rows[i]['sha256'] for i in test}:
        raise ValueError('Held-out byte identity overlaps fitting.')
    if len({(p['exam'], p['run_id']) for p in held}) != len(held):
        raise ValueError('Repeated runs are not independent support.')
    return core, train, held

def fit_fold(lock_path, manifest_path, bank_path, output, exam):
    output = private(output)
    if output.exists():
        raise FileExistsError('Never overwrite completed fits.')
    lock = json.loads(Path(lock_path).read_text())
    for path, key in [(manifest_path, 'manifest_sha256'), (bank_path, 'bank_sha256'),
                      (__file__, 'training_code_sha256'),
                      (ROOT/'scripts/local_short_event_ranking.py', 'original_objective_code_sha256'),
                      (ROOT/'src/capsule_review/baseline.py', 'architecture_code_sha256')]:
        if sha(path) != lock[key]:
            raise ValueError('Frozen input/code changed: ' + key)
    if lock['seeds'] != list(SEEDS) or lock['exams'] != list(EXAMS) or lock['updates'] != 1024 or lock['ranking_weight'] != .5:
        raise ValueError('Frozen design changed.')
    m = json.loads(private(manifest_path).read_text())
    bank = np.load(private(bank_path), mmap_mode='r')
    if bank.dtype != np.uint8 or bank.shape != (len(m['images']), 3, 96, 96):
        raise ValueError('Wrong input tensor bank.')
    core, train, held = fold_indices(m, exam)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    x = torch.from_numpy(np.array(bank, copy=True)).float()/255.
    y = torch.tensor([r['blood'] for r in m['images']])
    core = torch.tensor(core)
    pos = torch.tensor([p['positive_index'] for p in train])
    neg = torch.tensor([p['negative_index'] for p in train])
    output.mkdir(parents=True)
    receipts = []
    # Predictions are recorded for all fitting and held-out pairs, without
    # calculating ordering outcomes until the entire experiment is sealed.
    endpoint = sorted({p[k] for p in m['pairs'] for k in ('positive_index', 'negative_index')})
    for seed in SEEDS:
        co = shuffled_cycles(len(core), 16384, seed).reshape(1024, 16)
        po = shuffled_cycles(len(train), 8192, seed+100003).reshape(1024, 8)
        exposure_positive = 8192 + int(y[core[co]].sum())
        counts = [32768-exposure_positive, exposure_positive]
        weights = torch.tensor([32768/(2*n) for n in counts])
        schedule_sha = hashlib.sha256(co.numpy().tobytes()+po.numpy().tobytes()).hexdigest()
        for arm in ('classification', 'local_ranking'):
            torch.manual_seed(seed)
            np.random.seed(seed)
            random.seed(seed)
            model = AnatomyCNN(2)
            initial = hashlib.sha256(b''.join(v.detach().numpy().tobytes() for v in model.state_dict().values())).hexdigest()
            opt = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
            for step in range(1024):
                ix = torch.cat([core[co[step]], pos[po[step]], neg[po[step]]])
                opt.zero_grad(set_to_none=True)
                loss, _, _ = objective(model(x[ix]), y[ix], weights, 0. if arm == 'classification' else .5)
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite loss.')
                loss.backward()
                opt.step()
            ck = output/f'{arm}-seed{seed}.pt'
            torch.save(model.state_dict(), ck)
            model.eval()
            with torch.inference_mode():
                logits = model(x[endpoint]).tolist()
            record = {'held_out_exam': exam, 'seed': seed, 'arm': arm,
                      'endpoint_indices': endpoint, 'logits': logits,
                      'checkpoint_sha256': sha(ck), 'lock_sha256': sha(lock_path)}
            pred = output/f'{arm}-seed{seed}-logits.json'
            pred.write_text(json.dumps(record, allow_nan=False))
            receipts.append({'exam': exam, 'seed': seed, 'arm': arm,
                             'initial_tensor_sha256': initial, 'schedule_sha256': schedule_sha,
                             'negative_positive_exposures': counts, 'updates': 1024,
                             'training_core': len(core), 'training_pairs': len(train),
                             'held_out_pairs': len(held), 'class_weights': weights.tolist(),
                             'checkpoint': ck.name, 'checkpoint_sha256': sha(ck),
                             'predictions': pred.name, 'predictions_sha256': sha(pred)})
            print('completed', exam, seed, arm, flush=True)
    for seed in SEEDS:
        for key in ('initial_tensor_sha256', 'schedule_sha256', 'negative_positive_exposures'):
            assert len({json.dumps(r[key]) for r in receipts if r['seed'] == seed}) == 1
    (output/'receipts.json').write_text(json.dumps(receipts, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('lock', 'manifest', 'bank', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--exam', type=int, choices=EXAMS, required=True)
    a = p.parse_args()
    fit_fold(a.lock, a.manifest, a.bank, a.output, a.exam)
