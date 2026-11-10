"""Retrospective source-safe short-event transfer / seed-consensus diagnostic.

Input paths point to PRIVATE, previously sealed Capsule Review archives. Only
non-identifying aggregates are written. Never write or print per-image logits,
source identifiers, embeddings, or pair-level outcomes to public files.

This script does not train, retune, select checkpoints, or access holdout sources.
Fitting-pair ordering is an in-sample diagnostic, not new validation.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import mean
from zipfile import ZipFile

EXAMS = (23, 25, 29, 30)
SEEDS = (17, 29, 43)
ARMS = ('classification', 'ranking')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parsed(z: ZipFile, name: str):
    return json.loads(z.read(name))


def sign_margin(logits, indices, pos, neg):
    """Return 1/0.5/0 for positive versus negative score ordering."""
    if len(indices) != len(logits) or len(set(indices)) != len(indices):
        raise ValueError('Inconsistent endpoint indices.')
    if pos not in indices or neg not in indices:
        raise ValueError('One of the source-supported pair endpoints is missing.')
    def score(i):
        x = logits[indices[i]]
        if len(x) != 2 or not all(math.isfinite(v) for v in x):
            raise ValueError('Invalid logits.')
        return float(x[1] - x[0])
    d = score(pos) - score(neg)
    return 1. if d > 0. else (0.5 if d == 0. else 0.)


def summarise_consensus(signs, singleton_mask):
    if len(signs) != len(SEEDS) or any(len(x) != len(singleton_mask) for x in signs):
        raise ValueError('Require the same distinct runs across all seeds.')
    correct = [sum(signs[k][i] == 1 for k in range(len(SEEDS))) for i in range(len(singleton_mask))]
    if any(any(x not in (0, 1) for x in row) for row in signs):
        raise ValueError('Non-binary pair score is not eligible for unanimous consensus.')
    return {'runs': len(correct), 'all_three_correct': sum(c == 3 for c in correct),
            'all_three_wrong': sum(c == 0 for c in correct),
            'mixed_seed_decisions': sum(0 < c < 3 for c in correct),
            'singleton_runs': sum(singleton_mask),
            'singleton_all_three_wrong': sum(c == 0 and singleton_mask[i] for i, c in enumerate(correct)),
            'singleton_mixed_seed_decisions': sum(0 < c < 3 and singleton_mask[i] for i, c in enumerate(correct))}


def run(foundation_archive: Path, prefit_archive: Path, prediction_archive: Path):
    with ZipFile(foundation_archive) as foundation, ZipFile(prefit_archive) as pref, ZipFile(prediction_archive) as sealed:
        lock_bytes = pref.read('PREFIT_LOCKED.json')
        lock = json.loads(lock_bytes)
        if lock != parsed(sealed, 'PREFIT_LOCKED.json') or lock['status'] != 'PREFIT_LOCKED':
            raise ValueError('Prefit lock mismatch or not sealed.')
        if tuple(lock['exams']) != EXAMS or tuple(lock['seeds']) != SEEDS or lock['runs'] != 69 or lock['singleton_runs'] != 21:
            raise ValueError('Wrong frozen cohort.')
        manifest_bytes = foundation.read('foundation/support-manifest-private.json')
        if sha(manifest_bytes) != lock['source_manifest_sha256']:
            raise ValueError('Source manifest SHA mismatch.')
        manifest = json.loads(manifest_bytes)
        pairs = manifest['pairs']
        if len(pairs) != 69 or len({(p['exam'], p['run_id']) for p in pairs}) != 69 or any(p['exam'] not in EXAMS for p in pairs):
            raise ValueError('Source-supported distinct-run cohort changed.')
        if sum(p['run_length'] == 1 for p in pairs) != 21 or len(manifest['images']) != 4412:
            raise ValueError('Singleton support or source bank count changed.')
        if any(p['run_length'] not in (1,2,3,4,5) or manifest['images'][p['positive_index']]['blood'] != 1
                or manifest['images'][p['negative_index']]['blood'] != 0 or
                manifest['images'][p['positive_index']]['exam'] != p['exam'] or
                manifest['images'][p['negative_index']]['exam'] != p['exam'] for p in pairs):
            raise ValueError('Original source pair label/identity mismatch.')
        if sha(pref.read('mobilenet-features-4412-f32.npy')) != lock['feature_sha256']:
            raise ValueError('Frozen feature bank changed.')
        receipt_bytes = sealed.read('predictions/prediction-receipt.json')
        receipt = json.loads(receipt_bytes)
        if receipt['feature_sha256'] != lock['feature_sha256'] or receipt['prefit_lock_sha256'] != sha(lock_bytes) or len(receipt['records']) != 24:
            raise ValueError('Private prediction receipt invalid.')
        by_receipt = {(r['exam'],r['seed'],r['arm']):r for r in receipt['records']}
        if len(by_receipt) != 24:
            raise ValueError('Duplicate model identities in sealed receipt.')
        prior_zip_name = 'frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip'
        prior = ZipFile(io.BytesIO(foundation.read(prior_zip_name)))
        # Historical PR72 outcomes were also sealed before evaluation; verify each exact archived file.
        prior_receipts = {e: parsed(prior, f'fits/{e}/receipts.json') for e in EXAMS}
        prior_records = {(e,r['seed'],r['arm']):r for e,rs in prior_receipts.items() for r in rs}
        if len(prior_records) != 24:
            raise ValueError('Historical PR72 control receipt identity mismatch.')
        original_endpoints = {p[k] for p in pairs for k in ('positive_index', 'negative_index')}
        if len(original_endpoints) != 137:
            raise ValueError('Unexpected source supported endpoint count.')

        heldout = {}
        train = {}
        per_cell = []
        for model in ('cnn','mobilenet'):
            for arm in ARMS:
                for e in EXAMS:
                    for seed in SEEDS:
                        if model == 'cnn':
                            older_arm = 'classification' if arm == 'classification' else 'local_ranking'
                            rec = prior_records[(e,seed,older_arm)]
                            score_path = f'fits/{e}/{rec["prediction_file"]}'
                            raw = prior.read(score_path)
                            if sha(raw) != rec['prediction_sha256'] or sha(prior.read(f'fits/{e}/{rec["checkpoint"]}')) != rec['checkpoint_sha256']:
                                raise ValueError('Historical CNN sealed checkpoint/score digest differs.')
                            data = json.loads(raw)
                        else:
                            rec = by_receipt[(e,seed,arm)]
                            score_path = f'predictions/{rec["score_file"]}'
                            raw = sealed.read(score_path)
                            if sha(raw) != rec['score_sha256'] or sha(sealed.read(f'predictions/{rec["head_file"]}')) != rec['head_sha256']:
                                raise ValueError('MobileNet checkpoint/score digest differs.')
                            data = json.loads(raw)
                        if int(data['exam'] if model == 'cnn' else data['held_out_exam']) != e or int(data['seed']) != seed:
                            raise ValueError('Wrong heldout exam/seed identity.')
                        if not original_endpoints.issubset(set(data['endpoint_indices'])):
                            raise ValueError('Missing one or more original pair endpoints.')
                        index = {int(idx): i for i,idx in enumerate(data['endpoint_indices'])}
                        signs = [sign_margin(data['logits'], index, p['positive_index'], p['negative_index']) for p in pairs]
                        hel = [signs[i] for i,p in enumerate(pairs) if p['exam'] == e]
                        tr = [signs[i] for i,p in enumerate(pairs) if p['exam'] != e]
                        heldout[(model,arm,e,seed)] = hel
                        train[(model,arm,e,seed)] = tr
                        per_cell.append({'model':model,'arm':arm,'heldout_exam':e,'seed':seed,
                                         'train_pair_count':len(tr),'training_ordered':sum(tr),
                                         'heldout_pair_count':len(hel),'heldout_ordered':sum(hel)})
        output = {'study':'Retrospective source-safe training/holdout transfer and error persistence audit',
                  'role':'Already-inspected examination-heldout development cohort; no fitting or model tuning',
                  'input_evidence':{'prefit_sha256':sha(lock_bytes), 'feature_bank_sha256':lock['feature_sha256'],
                                    'source_manifest_sha256':lock['source_manifest_sha256'],
                                    'sealed_prediction_receipt_sha256':sha(receipt_bytes),
                                    'historical_controls':'PR72 sealed predictions, SHA-verified'},
                  'support':{'distinct_short_runs':69,'singletons':21,'exam_count':4,'seeds':list(SEEDS),
                             'original_source_endpoints':len(original_endpoints), 'fits_reused':48},
                  'objective_results':{}, 'seed_consensus':{}, 'objective_decision_agreement':{},
                  'matched_model_overlap':{}, 'limitations':['No verified patient linkage; training pair accuracy is in sample, not clinical transfer.',
                  'Same 69 development runs and three fixed seeds reused; no independent test or 10% exact-K evaluation.',
                  'CNN 96px and MobileNet 160px preprocessing and architecture differ; no causal encoder-only inference.',
                  'No claims about bleeding mechanism, diagnosis, site, device or clinical benefit.'],
                  'model_promotion':False}
        for model in ('cnn','mobilenet'):
            for arm in ARMS:
                cells = [r for r in per_cell if r['model']==model and r['arm']==arm]
                train_total = sum(r['training_ordered'] for r in cells)
                train_n = sum(r['train_pair_count'] for r in cells)
                held_total = sum(r['heldout_ordered'] for r in cells)
                held_n = sum(r['heldout_pair_count'] for r in cells)
                macro_held = mean(mean(r['heldout_ordered']/r['heldout_pair_count'] for r in cells if r['heldout_exam']==e) for e in EXAMS)
                output['objective_results'][f'{model}_{arm}'] = {
                    'training_in_sample_pair_ordering_pct':100*train_total/train_n,
                    'heldout_run_weighted_ordering_pct':100*held_total/held_n,
                    'heldout_equal_exam_seed_macro_pct':100*macro_held,
                    'training_minus_heldout_run_weighted_pp':100*(train_total/train_n-held_total/held_n),
                    'observations_training_across_folds_seeds_not_independent':train_n,
                    'observations_heldout_across_seeds_not_independent':held_n,
                    'by_exam':{str(e):{'training_pct':100*sum(r['training_ordered']/r['train_pair_count'] for r in cells if r['heldout_exam']==e)/3,
                                        'heldout_pct':100*sum(r['heldout_ordered']/r['heldout_pair_count'] for r in cells if r['heldout_exam']==e)/3,
                                        'train_pairs_per_seed':next(r['train_pair_count'] for r in cells if r['heldout_exam']==e),
                                        'heldout_pairs_per_seed':next(r['heldout_pair_count'] for r in cells if r['heldout_exam']==e)} for e in EXAMS}}
                signs = []
                singletons = [p['run_length']==1 for p in pairs]
                for seed in SEEDS:
                    within_exam_cursors={e:iter(heldout[(model,arm,e,seed)]) for e in EXAMS}
                    assembled=[next(within_exam_cursors[p['exam']]) for p in pairs]
                    if len(assembled)!=len(pairs):raise ValueError('Incorrect pair order or source coverage.')
                    signs.append(assembled)
                output['seed_consensus'][f'{model}_{arm}'] = summarise_consensus(signs,singletons)
                output['seed_consensus'][f'{model}_{arm}']['by_exam'] = {}
                for ex in EXAMS:
                    loc=[i for i,pair in enumerate(pairs) if pair['exam']==ex]
                    vote=[sum(signs[seed_i][i] == 1 for seed_i in range(3)) for i in loc]
                    output['seed_consensus'][f'{model}_{arm}']['by_exam'][str(ex)]={
                        'runs':len(loc),'all_three_wrong':sum(v==0 for v in vote),
                        'all_three_correct':sum(v==3 for v in vote),'mixed':sum(v in (1,2) for v in vote),
                        'singleton_all_three_wrong':sum(v==0 and pairs[i]['run_length']==1 for i,v in zip(loc,vote))}
        for model in ('cnn','mobilenet'):
            compared = []
            for e in EXAMS:
                for seed in SEEDS:
                    a,b=heldout[(model,'classification',e,seed)],heldout[(model,'ranking',e,seed)]
                    if len(a)!=len(b):raise ValueError('Different pair sets for matched objectives.')
                    compared.extend(zip(a,b))
            output['objective_decision_agreement'][model] = {
                'identical_decisions':sum(a==b for a,b in compared),'decisions_compared':len(compared),
                'ranking_only_correct':sum(a==0 and b==1 for a,b in compared),
                'classification_only_correct':sum(a==1 and b==0 for a,b in compared)}
        for arm in ARMS:
            compared=[]
            for e in EXAMS:
                for seed in SEEDS:
                    compared.extend(zip(heldout[('cnn',arm,e,seed)], heldout[('mobilenet',arm,e,seed)]))
            output['matched_model_overlap'][arm]={
                'compared_decisions_not_independent':len(compared),
                'both_correct':sum(a==b==1 for a,b in compared),
                'cnn_only_correct':sum(a==1 and b==0 for a,b in compared),
                'mobilenet_only_correct':sum(a==0 and b==1 for a,b in compared),
                'both_wrong':sum(a==b==0 for a,b in compared)}
        expected={'cnn_classification':63.77195871761091,'cnn_ranking':72.29084321475626,
                  'mobilenet_classification':50.94038208168642,'mobilenet_ranking':49.08432147562583}
        for key, exp in expected.items():
            if abs(output['objective_results'][key]['heldout_equal_exam_seed_macro_pct']-exp)>1e-8:
                raise ValueError('Reconstructed heldout original macro does not match sealed published results.')
        return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--foundation',type=Path,required=True)
    p.add_argument('--prefit',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise FileExistsError('Do not overwrite existing diagnostic aggregate.')
    out=run(args.foundation,args.prefit,args.predictions)
    args.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('source-safe audit complete; cells',4*3*2*2)

if __name__=='__main__':main()
