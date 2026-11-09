"""Independent scalar outcome replay and separately constructed CNN canary.

Does not import the production transfer/evaluation scripts or model class.
Private inputs, checkpoints and raw predictions stay outside public Git.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
import torch
from torch import nn


def replay(manifest, bank, fits, aggregate):
    root=Path(__file__).resolve().parents[1]
    for p in (manifest,bank,fits,aggregate):
        if Path(p).resolve().is_relative_to(root):raise ValueError('Private data must stay outside Git.')
    m=json.loads(Path(manifest).read_text());out=json.loads(Path(aggregate).read_text())
    a=np.load(bank,mmap_mode='r');torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    maxdiff=0.;checked=0;effects=[]
    for cell in out['cells']:
        e,s,arm=cell['exam'],cell['seed'],cell['arm']
        folder=Path(fits)/str(e);d=json.loads((folder/f'{arm}-seed{s}-logits.json').read_text())
        logits=dict(zip(d['endpoint_indices'],d['logits']))
        for name in ('held_out','training'):
            pairs=[p for p in m['pairs'] if (p['exam']==e)==(name=='held_out')]
            margins=[];single=[]
            for p in pairs:
                pos,neg=logits[p['positive_index']],logits[p['negative_index']]
                v=(pos[1]-pos[0])-(neg[1]-neg[0]);margins.append(v)
                if p['run_length']==1:single.append(float(v>0)+.5*float(v==0))
            ref=cell[name]
            assert ref['pairs']==len(pairs) and ref['correct']==sum(v>0 for v in margins) and ref['ties']==sum(v==0 for v in margins)
            assert abs(ref['ordering']-statistics.mean(float(v>0)+.5*float(v==0) for v in margins))<1e-12
            assert abs(ref['mean_margin']-statistics.mean(margins))<1e-12
            assert ref['singletons']==len(single)
            if single:assert abs(ref['singleton_ordering']-statistics.mean(single))<1e-12
            assert np.allclose(ref['margin_quantiles'],np.quantile(margins,[0,.25,.5,.75,1]),atol=1e-12,rtol=0)
            checked+=1
        # Independently assemble the published architecture with matching state keys.
        blocks=[]
        for before,after in ((3,16),(16,32),(32,64)):
            blocks.extend([nn.Conv2d(before,after,3,stride=2,padding=1),nn.GroupNorm(4,after),nn.ReLU()])
        blocks.append(nn.AdaptiveAvgPool2d(1))
        model=nn.Module();model.features=nn.Sequential(*blocks);model.classifier=nn.Linear(64,2)
        state=torch.load(folder/f'{arm}-seed{s}.pt',map_location='cpu',weights_only=True)
        model.load_state_dict(state);model.eval()
        x=torch.from_numpy(np.array(a[d['endpoint_indices']],copy=True)).to(torch.float32)/255
        with torch.inference_mode():fresh=model.classifier(model.features(x).flatten(1)).numpy()
        diff=float(np.max(np.abs(fresh-np.asarray(d['logits']))));maxdiff=max(maxdiff,diff);assert diff<=2e-6
    for e in (21,23,25,29,30):
        for s in (17,29,43):
            c,r=[next(x['held_out']['ordering'] for x in out['cells'] if (x['exam'],x['seed'],x['arm'])==(e,s,arm)) for arm in ('classification','local_ranking')]
            saved=next(x['ordering_difference'] for x in out['paired'] if (x['exam'],x['seed'])==(e,s))
            assert abs(saved-(r-c))<1e-12;effects.append(r-c)
    assert abs(statistics.mean(effects)-out['primary_mean_paired_difference'])<1e-12
    result={'independent_metric_cells_verified':checked,'paired_effects_verified':len(effects),
            'independent_models_verified':len(out['cells']),'logit_values_verified':len(out['cells'])*len(d['endpoint_indices'])*2,
            'maximum_logit_difference':maxdiff,'all_match':True}
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','bank','fits','aggregate'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();replay(a.manifest,a.bank,a.fits,a.aggregate)
