"""Independently replay a completed candidate on the frozen original Galar images.

The report only verifies internal numeric identity: it is not clinical validation.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path

from PIL import Image
from capsule_review.baseline_data import image_identity, safe_path
from blood_image_pilot import validate_manifest, roc_ap
from train_domain_blood import (hash_file,validate_spec,ensure_exam_partition,
                                make_model,predict,MANIFEST_SHA256,WEIGHTS_SHA256,
                                SPEC_SHA256)


def replay(manifest:Path,images:Path,weights:Path,spec:Path,run:Path)->dict:
    import torch
    data=validate_manifest(manifest,images,check_files=False)
    validate_spec(spec)
    if data['sha256'] != MANIFEST_SHA256 or hash_file(weights)!=WEIGHTS_SHA256:
        raise ValueError('Immutable source or official pretrained weight mismatch')
    provenance=json.loads((run/'source-provenance.json').read_text())
    metrics=json.loads((run/'metrics.json').read_text())
    if (provenance.get('spec')!=SPEC_SHA256 or
        provenance.get('manifest')!=MANIFEST_SHA256 or
        provenance.get('result_sha256')!=hash_file(run/'metrics.json') or
        provenance.get('prediction_sha256')!=hash_file(run/'predictions.csv') or
        provenance.get('fine_tuned_checkpoint_sha256')!=hash_file(run/'candidate-weights.pt') or
        metrics.get('fine_tuned_checkpoint_sha256')!=hash_file(run/'candidate-weights.pt') or
        metrics.get('predictions_sha256')!=hash_file(run/'predictions.csv')):
        raise ValueError('Candidate research outputs, weights or source receipts changed')
    fit, rows=ensure_exam_partition(data['records'],metrics['mode'],metrics['heldout_exam'])
    if metrics['fit_exams']!=sorted({r['exam'] for r in fit}) or metrics['evaluated_exams']!=sorted({r['exam'] for r in rows}):
        raise ValueError('Saved evidence does not match verified examination partition')
    original_scores=[]
    with (run/'predictions.csv').open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['exam','frame','source_sha256','blood_label','domain_adapted_score']:
            raise ValueError('Unexpected prediction schema')
        for r, recorded in zip(rows,reader,strict=True):
            if (int(recorded['exam'])!=r['exam'] or int(recorded['frame'])!=r['frame'] or
                recorded['source_sha256']!=r['source_sha256'] or int(recorded['blood_label'])!=r['blood']):
                raise ValueError('Saved scores are not aligned with original images')
            v=float(recorded['domain_adapted_score'])
            if not math.isfinite(v) or not 0<=v<=1:raise ValueError('Invalid saved model score')
            original_scores.append(v)
    for r in rows:
        source,pixel=image_identity(safe_path(images,r['path']))
        if source!=r['source_sha256'] or pixel!=r['pixel_sha256']:
            raise ValueError('Original medical image differs from frozen manifest')
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    net=make_model(weights)
    checkpoint=torch.load(run/'candidate-weights.pt',map_location='cpu',weights_only=True)
    if set(checkpoint)!={'tail','head'}:
        raise ValueError('Unexpected candidate weight structure')
    net.tail.load_state_dict(checkpoint['tail'],strict=True)
    net.head.load_state_dict(checkpoint['head'],strict=True)
    fresh=predict(net,rows,images)
    deviation=max(abs(a-b) for a,b in zip(original_scores,fresh,strict=True))
    if deviation>1e-6:
        raise ValueError(f'Checkpoint cannot reproduce original predictions: error={deviation}')
    for exam in sorted(set(x['exam'] for x in rows)):
        ind=[i for i,r in enumerate(rows) if r['exam']==exam]
        y=[rows[i]['blood'] for i in ind]
        scores=[fresh[i] for i in ind]
        a=roc_ap(y,scores)
        b=metrics['fine_tuned'][str(exam)]['rank_metrics']
        for k in ('positive','negative','roc_auc','average_precision'):
            if (a[k] is None)!=(b[k] is None) or a[k] is not None and abs(a[k]-b[k])>1e-8:
                raise ValueError('Reported rank metrics cannot be replayed')
    return {'mode':metrics['mode'],'heldout':metrics['heldout_exam'],
            'status':'independent exact-source image+checkpoint replay passed; NOT clinical validation',
            'source_images_rehashed':len(rows),'max_probability_deviation':deviation,
            'official_weights_sha256':WEIGHTS_SHA256,
            'candidate_checkpoint_sha256':hash_file(run/'candidate-weights.pt'),
            'original_prediction_file_sha256':hash_file(run/'predictions.csv'),
            'model_training_exam_ids':metrics['fit_exams'],
            'model_evaluation_exam_ids':metrics['evaluated_exams']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for opt in ('manifest','images','weights','spec','run'):
        p.add_argument('--'+opt,type=Path,required=True)
    a=p.parse_args(argv)
    result=replay(a.manifest,a.images,a.weights,a.spec,a.run)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
