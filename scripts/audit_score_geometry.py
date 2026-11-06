#!/usr/bin/env python3
"""Private-only frozen-score reuse. No acquisition, training or CNN inference.

Requires NumPy (existing ml extra). Publishes no individual data automatically.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import zipfile
import numpy as np
from capsule_review.geometry_control import analyze, annotation_runs, metrics
from capsule_review.unseen_evaluation import freeze_queues
from capsule_review.interval_evidence import parse_corrected_source_rows
from capsule_review.temporal_baseline import temporal_max_scores
from capsule_review.priority import select_positions

ROOT = Path(__file__).resolve().parents[1]
PINS = {35: ('b22bd37ffa08bdace73a4cb8b3f785772f9565cdcf7b0303632ebb1ad10ef4e7',9643,1534,29),
        36: ('a636cb9c74f5019a58bc03414a6e428298eb833bb5cf69066dc4a78cf4d6dd90',13326,209,59)}
LABEL_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
WEIGHTS = 'f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def private_path(path):
    path = path.resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('Private inputs/outputs must be outside public repository.')
    return path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-dir',type=Path,required=True)
    p.add_argument('--private-output',type=Path,required=True)
    a=p.parse_args(); base=private_path(a.private_dir); out=private_path(a.private_output)
    if out.exists() or out.with_suffix('.repetitions.json').exists():
        p.error('Refuse overwriting research outputs.')
    label_path=base/'labels.zip'
    if digest(label_path)!=LABEL_SHA:raise ValueError('Corrected label archive changed.')
    result={'schema_version':1,'record_type':'frozen-score-geometry-control-development-v1',
            'contract_commit':'74d8586ebc4e626068669ee688a9dfe36f3ca4a6',
            'contract_sha256':digest(ROOT/'docs/SCORE_GEOMETRY_CONTROL_PLAN_20261106.md'),
            'development_only':True,'new_training':False,'new_inference':False,
            'authors_61_80_opened':False,'galar_11_20_reopened':False,
            'pixel_bytes_reverified_this_analysis':False,
            'repetitions':10000,'coarse_shift_repetitions':1000,'seed':20261106,
            'runtime':{'python':platform.python_version(),'numpy':np.__version__},
            'examinations':{},'macro':{}}
    private={}
    for exam,(pin,n,positives,total_runs) in PINS.items():
        source=base/f'galar{exam}-scores.json'
        if digest(source)!=pin:raise ValueError('Frozen score hash changed.')
        snapshot=json.loads(source.read_text())
        if snapshot['exam']!=exam or not snapshot['development_only'] or snapshot['native_source_stride']!=5:
            raise ValueError('Invalid snapshot role/stride.')
        if snapshot.get('original_model_weights_sha256',snapshot.get('unchanged_original_checkpoint_sha256'))!=WEIGHTS:
            raise ValueError('Wrong original checkpoint.')
        entries=snapshot['complete_original_scores']
        frames=[r['source_frame'] for r in entries]; hashes=[r['original_png_sha256'] for r in entries]
        scores=[r['original_cnn_score'] for r in entries]
        if len(scores)!=n or any(b-a!=5 for a,b in zip(frames,frames[1:])):
            raise ValueError('Incomplete native source chronology.')
        frozen=freeze_queues(frames,hashes,scores)
        if frozen.input_commitment_sha256!=snapshot['prelabel_original_queues_commitment_sha256']:
            raise ValueError('Frozen input commitment mismatch.')
        smooth=temporal_max_scores(scores,frames,window=3,source_stride=5)
        expected=[{'review_percent':percent,'k':k,'policies':{name:list(q) for name,q in methods},
                   'temporal_window3_score_bin':list(select_positions(smooth,k,'score_bin'))}
                  for percent,k,methods in frozen.selection_by_percent]
        if snapshot['frozen_queues']!=expected:raise ValueError('Frozen exact-K queue mismatch.')
        # Only explicitly permitted existing development members; no archive-wide traversal.
        with zipfile.ZipFile(label_path) as z:
            rows=parse_corrected_source_rows(z.read(f'{exam}.csv'))
        if [r['frame'] for r in rows]!=frames or any(r['blood'] not in ('0','1') for r in rows):
            raise ValueError('Incomplete source/label join.')
        labels=[int(r['blood']) for r in rows];runs=annotation_runs(labels,frames,5)
        if sum(labels)!=positives or len(runs)!=total_runs:raise ValueError('Historical denominator mismatch.')
        historical=json.loads((ROOT/'experiments'/f'galar{exam}-full-source-2026110{5 if exam==35 else 6}'/'aggregate.json').read_text())
        for old,frozen_q in zip(historical['review_results'],expected):
            if old['review_images']!=frozen_q['k'] or old['review_percent']!=frozen_q['review_percent']:
                raise ValueError('Historical budget mismatch.')
            for name,q in {**frozen_q['policies'],'temporal_window3_score_bin':frozen_q['temporal_window3_score_bin']}.items():
                m=metrics(labels,runs,q);h=old['policies'][name]
                if (m['positive_images']!=h['positive_annotated_images_hit']
                        or m['runs_reached']!=h['distinct_positive_annotation_runs_hit']):
                    raise ValueError('Historical outcome replay mismatch.')
        result['examinations'][str(exam)]={};private[str(exam)]={}
        for percent in (10,25):
            report,draws=analyze(scores,labels,frames,stride=5,percent=percent,exam=exam)
            k=report['k'];report['policies']['temporal_window3_score_bin']=metrics(labels,runs,select_positions(smooth,k,'score_bin'))
            result['examinations'][str(exam)][str(percent)]=report
            private[str(exam)][str(percent)]=draws
            print(f'completed {exam} {percent}%',flush=True)
    for percent in ('10','25'):
        reports=[result['examinations'][str(e)][percent] for e in PINS]
        differences=[r['policies']['score_bin']['run_recall']-r['policies']['uniform']['run_recall'] for r in reports]
        exact=[(r['policies']['score_bin']['runs_reached']-r['controls']['within_bin_permuted_scores']['analytic_expected_counts']['runs_reached'])/r['positive_runs'] for r in reports]
        observed=float(np.mean([r['policies']['score_bin']['run_recall'] for r in reports]))
        arrays=[np.array(private[str(e)][percent]['permutation'])[:,1]/r['positive_runs'] for e,r in zip(PINS,reports)]
        null=(arrays[0]+arrays[1])/2
        result['macro'][percent]={'positive_examinations':2,'equal_examination_weight':True,
            'score_bin_run_recall':observed,
            'uniform_run_recall':float(np.mean([r['policies']['uniform']['run_recall'] for r in reports])),
            'score_bin_minus_uniform':float(np.mean(differences)),
            'score_bin_minus_exact_permutation_expectation':float(np.mean(exact)),
            'per_exam_score_information_contrasts':exact,
            'between_exam_contrast_range':float(max(exact)-min(exact)),
            'paired_mc_score_information_reference_95':np.quantile(observed-null,[.025,.975]).tolist(),
            'paired_mc_upper_tail_plus_one':float((1+(null>=observed).sum())/(len(null)+1)),
            'null_mean_mc_se':float(null.std(ddof=1)/np.sqrt(len(null))),
            'two_exam_bootstrap_support_not_population_ci':{
                'values':[min(exact),float(np.mean(exact)),max(exact)],'weights':[.25,.5,.25]},
            'population_generalization_uncertainty':'Not estimable reliably from two outcome-inspected examinations.'}
    result['all_50_historical_policy_budget_count_replays_passed']=True
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with out.with_suffix('.repetitions.json').open('x') as f:json.dump(private,f,allow_nan=False)

if __name__=='__main__':main()
