#!/usr/bin/env python3
"""Offline qualification: existing Galar31–40 labels/index, never image/model access.

Input annotations stay private. Only counts and source-cost aggregates are emitted.
This is reference-standard assessment, not a new CNN-performance experiment.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import zipfile
from plan_galar31_40_development_blocks import validate_index

ROOT = Path(__file__).resolve().parents[1]
LABEL_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
EXAMS = tuple(range(31,41))
NEW = (31,32,33,34,37,38,39,40)


def assess_rows(raw: bytes, *, stride: int) -> dict:
    if type(stride) is not int or stride not in (1,5) or len(raw)>32*1024*1024:
        raise ValueError('Unsupported source stride or annotation size.')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    names=reader.fieldnames or []
    if len(set(names))!=len(names) or not {'frame','blood','active bleeding','hematin'}<=set(names):
        raise ValueError('Missing or duplicated target columns.')
    rows=list(reader)
    if not rows:raise ValueError('Missing annotation rows.')
    previous=-1;source_gaps=0;positives=[];runs=[];overlap=Counter()
    for position,row in enumerate(rows):
        if (None in row or not isinstance(row['frame'],str) or not row['frame'].isdigit()
                or any(row[k] not in ('0','1') for k in ('blood','active bleeding','hematin'))):
            raise ValueError('Invalid source identity or unknown target annotation; refuse inference.')
        frame=int(row['frame'])
        if frame<=previous:raise ValueError('Duplicate or reordered source identity.')
        contiguous=previous<0 or frame-previous==stride
        if previous>=0 and not contiguous:source_gaps+=1
        blood=int(row['blood']);active=int(row['active bleeding']);hematin=int(row['hematin'])
        overlap['active_bleeding_positive']+=active;overlap['hematin_positive']+=hematin
        overlap['blood_and_active_bleeding']+=blood*active
        overlap['active_bleeding_without_blood_label']+=active*(1-blood)
        overlap['blood_without_active_bleeding_label']+=blood*(1-active)
        overlap['blood_and_hematin']+=blood*hematin
        if blood:
            if not positives or positives[-1]!=position-1 or not contiguous:runs.append([])
            runs[-1].append(position);positives.append(position)
        previous=frame
    lengths=[len(r) for r in runs]
    gaps=Counter()
    # Only count separation where the entire source interval is native-contiguous.
    frames=[int(r['frame']) for r in rows]
    for left,right in zip(runs,runs[1:]):
        a,b=left[-1],right[0]
        if frames[b]-frames[a]!=(b-a)*stride:
            gaps['source_discontinuity']+=1;continue
        negatives=b-a-1
        gaps['one_negative' if negatives==1 else 'two_negative' if negatives==2
             else 'three_to_five_negative' if negatives<=5 else 'six_plus_negative']+=1
    return {'annotation_rows':len(rows),'positive_images':len(positives),'positive_runs':len(runs),
            'unknown_target_rows':0,'native_stride':stride,'internal_source_gaps':source_gaps,
            'run_lengths':{'1-5':sum(n<=5 for n in lengths),'6-25':sum(6<=n<=25 for n in lengths),
                           '26+':sum(n>=26 for n in lengths),'singleton':lengths.count(1)},
            'between_run_negative_gap_counts':dict(gaps),'label_relationship_counts':dict(overlap),
            'clinical_events_adjudicated':False,'patient_grouping_authenticated':False}


def enumerate_costs(index: dict, budget: int=8*1024**3) -> dict:
    if type(budget) is not int or budget<1:raise ValueError('Invalid acquisition budget.')
    _,studies=validate_index(index)
    records=[]
    for size in range(1,len(NEW)+1):
        for selected in itertools.combinations(NEW,size):
            blocks=set(b for e in selected for b in index['studies'][str(e)]['required_block_ids_for_complete_export'])
            incremental=blocks-{5,6}
            cost=sum(index['blocks'][i]['compressed_bytes'] for i in incremental)
            positive=sum(studies[e]['previously_inspected_positive_annotation_runs']>0 for e in selected)
            records.append({'examinations':list(selected),'new_positive_examinations':positive,
                            'new_zero_blood_examinations':len(selected)-positive,
                            'new_blocks':sorted(incremental),'incremental_bytes':cost})
    qualifying=[r for r in records if r['new_positive_examinations']>=2 and r['new_zero_blood_examinations']>=1]
    minimum=min(qualifying,key=lambda r:(r['incremental_bytes'],r['examinations']))
    return {'all_nonempty_new_case_subsets_evaluated':len(records),'budget_bytes':budget,
            'support_floor_not_power_calculation':{'new_positive_examinations':2,'new_zero_blood_examinations':1},
            'minimum_support_floor_cohort':minimum,
            'support_floor_subsets_within_budget':sum(r['incremental_bytes']<=budget for r in qualifying),
            'full_expansion':next(r for r in records if len(r['examinations'])==len(NEW)),
            'cost_is_shared_block_union_not_sum_of_per_exam_costs':True,
            'retained_5_6_credit_uses_prior_verified_receipts_not_new_source_access':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-labels',type=Path,required=True)
    p.add_argument('--private-output',type=Path,required=True)
    a=p.parse_args()
    for path in (a.private_labels,a.private_output):
        if path.resolve().is_relative_to(ROOT):p.error('Private files must stay outside public Git.')
    if a.private_output.exists():p.error('Refuse overwriting assessment.')
    if hashlib.sha256(a.private_labels.read_bytes()).hexdigest()!=LABEL_SHA:p.error('Wrong official corrected archive.')
    index=json.loads((ROOT/'experiments/galar-31-40-index-20261105/aggregate.json').read_text())
    output={'schema_version':1,'assessment_type':'reference_standard_and_cost_not_CNN_evaluation',
            'contract_commit':'5204205f61582c6f78c562e633a1c2a82a6ced30',
            'new_images_acquired':0,'new_model_inference':False,'new_performance_estimate':False,
            'reserved_outcomes_opened':False,'examinations':{}}
    with zipfile.ZipFile(a.private_labels) as z:
        for exam in EXAMS:
            info=z.getinfo(f'{exam}.csv')
            if info.file_size>32*1024**2:p.error('Oversized selected member.')
            report=assess_rows(z.read(info),stride=index['studies'][str(exam)]['native_source_stride'])
            expected=index['studies'][str(exam)]
            if (report['annotation_rows']!=expected['image_members']
                    or report['positive_images']!=expected['previous_label_positive_rows']
                    or report['positive_runs']!=expected['previous_label_positive_runs']
                    or report['internal_source_gaps']):
                p.error('Source index/annotation support mismatch.')
            output['examinations'][str(exam)]=report
    output['cost_feasibility']=enumerate_costs(index)
    a.private_output.parent.mkdir(parents=True,exist_ok=True)
    with a.private_output.open('x') as f:json.dump(output,f,indent=2);f.write('\n')
    print('Assessed10 existing development label members and255 case subsets; no image or CNN access.')

if __name__=='__main__':main()
