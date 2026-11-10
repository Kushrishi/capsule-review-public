"""Display a fixed domain-adapted blood research candidate in existing Capsule Review.

Only the previously explored Galar examination-9/10 images may be imported. This
adds model suggestions; it must not edit original annotations or reviewer notes.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path

from capsule_review.models import ModelInfo, PredictionImport
from capsule_review.prediction_service import align_fixed_development_scores, save_predictions
from capsule_review.store import Store
from train_domain_blood import MANIFEST_SHA256, SPEC_SHA256, WEIGHTS_SHA256,hash_file

LABEL='Blood visual cue (fine-tuned research candidate)'


def import_scores(data_dir:Path, study_id:str, exam:int, run_dir:Path)->dict:
    if exam not in (9,10):raise ValueError('Only historical development examinations 9-10 allowed.')
    metrics=json.loads((run_dir/'metrics.json').read_text())
    provenance=json.loads((run_dir/'source-provenance.json').read_text())
    if (metrics.get('mode')!='final' or metrics.get('fit_exams')!=list(range(1,9)) or
        metrics.get('evaluated_exams')!=[9,10] or
        metrics.get('frozen_spec_sha256')!=SPEC_SHA256 or
        metrics.get('frozen_manifest_sha256')!=MANIFEST_SHA256 or
        metrics.get('official_imagenet_weights_sha256')!=WEIGHTS_SHA256 or
        provenance.get('result_sha256')!=hash_file(run_dir/'metrics.json') or
        provenance.get('fine_tuned_checkpoint_sha256')!=hash_file(run_dir/'candidate-weights.pt') or
        provenance.get('prediction_sha256')!=hash_file(run_dir/'predictions.csv') or
        provenance.get('prediction_sha256')!=metrics.get('predictions_sha256')):
        raise ValueError('Research experiment receipts or original data identity changed.')
    found={}
    with (run_dir/'predictions.csv').open(newline='',encoding='utf8') as file:
        reader=csv.DictReader(file)
        if reader.fieldnames!=['exam','frame','source_sha256','blood_label','domain_adapted_score']:
            raise ValueError('Unexpected saved prediction schema.')
        for r in reader:
            e=int(r['exam']);frame=int(r['frame']);score=float(r['domain_adapted_score'])
            if e not in (9,10) or not math.isfinite(score) or not 0<=score<=1:
                raise ValueError('Invalid source or model score.')
            key=(e,frame,r['source_sha256'])
            if key in found:raise ValueError('Duplicated original image prediction.')
            found[key]=score
    if len(found)!=1024:raise ValueError('Expected exact original 1,024 historical development predictions.')
    store=Store(data_dir)
    predictions=align_fixed_development_scores(store,study_id,found,LABEL,exam=exam)
    ckpt=provenance['fine_tuned_checkpoint_sha256']
    model=ModelInfo(name='Full-field MobileNet domain-adapted research candidate',
                    version='domain-blood-fixed-3epoch-v1',
                    run_id=f'domain-galar-blood-{ckpt[:24]}',
                    weights_sha256=ckpt,
                    description='Frozen ImageNet MobileNetV3-small early features, 3-epoch Galar supervised tail adaptation on exams 1-8. Scores are uncalibrated; prior examinations 9-10 were explored and this is NOT clinical or independent diagnostic validation.')
    return save_predictions(store,study_id,PredictionImport(schema_version=1,study_id=study_id,
                                                             model=model,predictions=predictions))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--study-id',required=True)
    p.add_argument('--exam',type=int,choices=(9,10),required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(import_scores(a.data_dir,a.study_id,a.exam,a.run_dir),indent=2))

if __name__=='__main__':main()
