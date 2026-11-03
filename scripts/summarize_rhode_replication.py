"""Summarize the preregistered two-study replication without model selection.

The three labelled anatomy boundaries per study are not clinical pathology labels.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

SPEC_HASH = 'c92500af677a12323ea5b8ebf43feb1b17f41bcf44ccfa80e94f28a19289399e'
METHODS = ('uniform', 'global_change', 'stratified_change', 'random_anchored')
BUDGETS=(0.05,0.10,0.25)
EXPECTED = {'s280':103418092, 's284':115960292, 's288':79873437}


def summarize(sources:dict) -> dict:
    if set(sources)!=set(EXPECTED):
        raise ValueError('Study set must be the original s288 and prespecified s280/s284')
    records={}
    for study,obj in sources.items():
        if (obj.get('study') != study or obj.get('source_zip_bytes') != EXPECTED[study] or
                obj.get('spec_sha256') != SPEC_HASH or obj.get('anatomy_boundary_count')!=3 or
                len(obj.get('budget_results',[]))!=3 or
                not obj.get('source_indices_complete',False)):
            raise ValueError(f'Invalid study identity, protocol or anatomy labels: {study}')
        metrics=[]
        for budget, record in zip(BUDGETS,obj['budget_results']):
            if record['budget']!=budget or set(record['methods'])!=set(METHODS):
                raise ValueError('Inconsistent fixed budget/method set')
            row={'budget':budget,'selected':record['k']}
            for method in METHODS:
                item=record['methods'][method]
                hit=item.get('boundary_hits',item.get('boundary_hits_mean'))
                if not hit or '5' not in hit:
                    raise ValueError('Missing prespecified ±5 boundary metric')
                row[method]={
                    'boundary_hits_5':hit['5'],
                    'max_nearest_position_distance':item['max_nearest_position_distance'],
                    'mean_nearest_position_distance':item['mean_nearest_position_distance'],
                }
            metrics.append(row)
        records[study]={
            'image_count':obj['image_count'],
            'anatomy_boundary_count':obj['anatomy_boundary_count'],
            'source_zip_sha256':obj['source_zip_sha256'],
            'role':obj['role'],
            'results':metrics,
        }
    result={'study_count':3,'new_studies':['s280','s284'],'historical_study':'s288',
            'source':'Rhode Island GI VCE, Charoen et al. (2022), original published article',
            'spec_sha256':SPEC_HASH,
            'outcome':'anatomical folder transition reach and source-index coverage; NOT pathology sensitivity',
            'independent_patient_groups_confirmed':False,
            'capture_timestamps_available':False,
            'clinical_validation':False,
            'per_study':records,
            'study_macro':{}}
    for group,subset in [('new_two',['s280','s284']),('all_three',['s280','s284','s288'])]:
        stats=[]
        for bi,budget in enumerate(BUDGETS):
            d={'budget':budget,'studies':len(subset),'methods':{}}
            for m in METHODS:
                vals=[records[s]['results'][bi][m] for s in subset]
                d['methods'][m]={
                    'mean_anatomy_boundaries_hit_5_of_3':round(mean(v['boundary_hits_5'] for v in vals),5),
                    'mean_max_nearest_frame_distance':round(mean(v['max_nearest_position_distance'] for v in vals),5),
                    'mean_nearest_frame_distance':round(mean(v['mean_nearest_position_distance'] for v in vals),5)
                }
            stats.append(d)
        result['study_macro'][group]=stats
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('s288','s280','s284'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        p.error('Refusing to overwrite result')
    sources={k:json.loads(getattr(args,k).read_text()) for k in EXPECTED}
    result=summarize(sources)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Summarized 2 prespecified studies + 1 previously explored study',flush=True)

if __name__=='__main__': main()
