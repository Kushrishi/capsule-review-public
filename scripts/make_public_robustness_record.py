#!/usr/bin/env python3
"""Only non-identifying aggregates from the PRIVATE exploratory robustness record."""
import json,sys
from pathlib import Path

def main(source, destination):
    private=json.loads(Path(source).read_text())
    out={'status':'retrospective_posthoc_development_only_no_model_promotion',
         'unit':'original annotated short run; examinations not verified patient-independent',
         'source_proofs':private['source_proofs'],
         'cohort':{'exams':[23,25,29,30],'distinct_short_runs':69,'distinct_singleton_runs':21,
                   'seed_models_per_objective':3},
         'summary':{},'rescaling_probe_factors':[0.25,0.5,2.0,4.0],
         'warnings':['All policies examined after PR72 outcomes already known.',
                     'Two-seed omission and rescaling are sensitivity probes; no selection or tuning.',
                     'Training-RMS scales use only fitting-pair margins, no held-out outcomes.',
                     'Ensemble result is NOT complete-source exact-K event recall or clinical validation.']}
    for arm in ['classification','local_ranking']:
        r=private['methods'][arm]
        out['summary'][arm]={}
        for name in ['individual_seed_mean','three_seed_majority','raw_mean_margin','train_rms_normalized_mean',
                     'omit_seed_17','omit_seed_29','omit_seed_43']:
            row=r[name]
            out['summary'][arm][name]={k:row[k] for k in ('macro','pooled','singleton_macro','singleton_pooled')}
        out['summary'][arm]['seed_scale_probe_envelope']={k:v for k,v in private['sensitivity'][arm].items() if k!='training_rms_scales_by_exam'}
        out['summary'][arm]['per_examination']=[{'exam':x['exam'],
                  'runs':x['runs'],'correct':x['correct'],
                  'singletons':x['singletons'],'singleton_correct':x['singleton_correct']}
                 for x in r['raw_mean_margin']['rows']]
    assert sum(x['runs'] for x in out['summary']['local_ranking']['per_examination'])==69
    assert sum(x['singletons'] for x in out['summary']['local_ranking']['per_examination'])==21
    Path(destination).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main(sys.argv[1],sys.argv[2])