"""Independent scalar support comparison and independent CNN reconstruction."""
import argparse
import json
import math
from pathlib import Path
import statistics
import numpy as np
import torch
from torch import nn

def quantile(a,q):
    a=sorted(a);v=q*(len(a)-1);j=math.floor(v)
    return a[j]+(a[min(j+1,len(a)-1)]-a[j])*(v-j)

def replay(manifest,bank,new_fits,legacy_fits,legacy_predictions,aggregate):
    root=Path(__file__).resolve().parents[1]
    if any(Path(p).resolve().is_relative_to(root) for p in (manifest,bank,new_fits,legacy_fits,legacy_predictions,aggregate)):
        raise ValueError('Private medical inputs must stay outside Git.')
    m=json.loads(Path(manifest).read_text());d=json.loads(Path(aggregate).read_text());a=np.load(bank,mmap_mode='r')
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True);checked=0;models=0;values=0;maxdiff=0
    for cell in d['cells']:
        e,s,arm,cohort=cell['exam'],cell['seed'],cell['arm'],cell['cohort']
        predroot=Path(new_fits) if cohort=='expanded_balanced69' else Path(legacy_predictions)
        ckroot=Path(new_fits) if cohort=='expanded_balanced69' else Path(legacy_fits)
        r=json.loads((predroot/str(e)/f'{arm}-seed{s}-logits.json').read_text());zz=dict(zip(r['endpoint_indices'],r['logits']))
        for scope in ('held_out','training'):
            pop=m['pairs'] if scope=='held_out' or cohort=='expanded_balanced69' else m['legacy_pairs']
            pp=[p for p in pop if (p['exam']==e)==(scope=='held_out')];v=[];pm=[];single=[]
            for p in pp:
                pos,neg=zz[p['positive_index']],zz[p['negative_index']];u,w=pos[1]-pos[0],neg[1]-neg[0]
                v.append(u-w);pm.append(1/(1+math.exp(-u))-1/(1+math.exp(-w)))
                if p['run_length']==1:single.append(float(u>w)+.5*float(u==w))
            out=cell[scope]
            assert out['pairs']==len(v) and out['correct']==sum(x>0 for x in v) and out['ties']==sum(x==0 for x in v)
            assert abs(out['ordering']-statistics.mean(float(x>0)+.5*float(x==0) for x in v))<1e-12
            assert abs(out['mean_margin']-statistics.mean(v))<1e-12
            assert out['singletons']==len(single)
            if single:assert abs(out['singleton_ordering']-statistics.mean(single))<1e-12
            for key,arr in [('margin_quantiles',v),('probability_margin_quantiles',pm)]:
                for q,ref in zip((0,.25,.5,.75,1),out[key]):assert abs(quantile(arr,q)-ref)<1e-12
            checked+=1
        layers=[]
        for before,after in ((3,16),(16,32),(32,64)):
            layers.extend([nn.Conv2d(before,after,3,stride=2,padding=1),nn.GroupNorm(4,after),nn.ReLU()])
        layers.append(nn.AdaptiveAvgPool2d(1));model=nn.Module();model.features=nn.Sequential(*layers);model.classifier=nn.Linear(64,2)
        model.load_state_dict(torch.load(ckroot/str(e)/f'{arm}-seed{s}.pt',weights_only=True,map_location='cpu'));model.eval()
        x=torch.from_numpy(np.array(a[r['endpoint_indices']],copy=True)).float()/255.
        with torch.inference_mode():fresh=model.classifier(model.features(x).flatten(1)).numpy()
        delta=float(np.abs(fresh-np.asarray(r['logits'])).max());assert delta<=2e-6
        maxdiff=max(maxdiff,delta);models+=1;values+=fresh.size
    for name,contrast in d['contrasts'].items():
        diffs=[]
        for row in contrast['paired']:
            e,s=row['exam'],row['seed']
            def get(c,arm):return next(v['held_out']['ordering'] for v in d['cells'] if (v['cohort'],v['arm'],v['exam'],v['seed'])==(c,arm,e,s))
            if name.startswith('data_'):
                arm=name[5:];diff=get('expanded_balanced69',arm)-get('legacy32',arm)
            else:
                c=name[8:];diff=get(c,'local_ranking')-get(c,'classification')
            assert abs(diff-row['ordering_difference'])<1e-12;diffs.append(diff)
        assert abs(statistics.mean(diffs)-contrast['mean_ordering_difference'])<1e-12
    result={'metric_cells_independently_verified':checked,'models_independently_reconstructed':models,'logit_values_verified':values,'maximum_logit_difference':maxdiff,'paired_contrast_records_verified':sum(len(x['paired']) for x in d['contrasts'].values()),'all_match':True}
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','bank','new-fits','legacy-fits','legacy-predictions','aggregate'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();replay(a.manifest,a.bank,a.new_fits,a.legacy_fits,a.legacy_predictions,a.aggregate)
