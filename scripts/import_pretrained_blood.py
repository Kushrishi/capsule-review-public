"""Add a frozen exploratory pretrained blood-score run to an existing research viewer.

Never edits dataset reference labels, previous model runs, or reviewer annotations.
Only historical, previously evaluated examinations 9 and 10 are supported.
"""
from __future__ import annotations
import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path

from capsule_review.models import ModelInfo, Prediction, PredictionImport
from capsule_review.prediction_service import save_predictions
from capsule_review.store import Store
from pretrained_blood_probe import MANIFEST_SHA256, SPEC_SHA256, WEIGHTS_SHA256, hash_file

LABEL='Blood visual cue (pretrained research baseline)'


def import_scores(data_dir:Path,study_id:str,exam:int,run_dir:Path)->dict:
    if exam not in (9,10):
        raise ValueError('Only prior Galar development examinations 9/10 are supported.')
    provenance=json.loads((run_dir/'provenance.json').read_text())
    metrics=json.loads((run_dir/'metrics.json').read_text())
    if (metrics['frozen_manifest_sha256']!=MANIFEST_SHA256 or
        metrics['frozen_spec_sha256']!=SPEC_SHA256 or
        metrics['historical_development_examinations']!=[9,10] or
        provenance['official_weight_sha256']!=WEIGHTS_SHA256 or
        provenance['head_sha256']!=hash_file(run_dir/'probe-head.json') or
        provenance['predictions_sha256']!=hash_file(run_dir/'predictions.csv') or
        provenance['metrics_sha256']!=hash_file(run_dir/'metrics.json')):
        raise ValueError('Research model or original image-score records changed.')
    scores={}
    with (run_dir/'predictions.csv').open(newline='',encoding='utf-8') as fp:
        reader=csv.DictReader(fp)
        if set(reader.fieldnames or []) != {'exam','frame','source_sha256','blood_label','mobilenet_score'}:
            raise ValueError('Unexpected prediction columns.')
        for row in reader:
            ex=int(row['exam']);frame=int(row['frame'])
            if ex not in (9,10):raise ValueError('Unexpected examination in saved predictions.')
            score=float(row['mobilenet_score'])
            if not math.isfinite(score) or not 0<=score<=1:
                raise ValueError('Nonfinite/out-of-range saved score.')
            if ex!=exam:continue
            key=(frame,row['source_sha256'])
            if key in scores:raise ValueError('Repeated source frame.')
            scores[key]=score
    store=Store(data_dir)
    study=store.study(study_id)
    if study is None or study.get('synthetic') or study['frame_count']!=512:
        raise ValueError('Real previously imported Galar development study required.')
    with store.connect() as db:
        rows=list(db.execute('SELECT position,source_index,source_sha256 FROM frames WHERE study_id=? ORDER BY position',(study_id,)))
    if len(rows)!=512 or len(scores)!=512:
        raise ValueError('Missing or surplus original source frames.')
    predictions=[]
    for r in rows:
        key=(r['source_index'],r['source_sha256'])
        if key not in scores:
            raise ValueError('Image SHA-256/frame number mismatch; refusing save.')
        predictions.append(Prediction(position=r['position'],image_sha256=r['source_sha256'],
                                      label=LABEL,score=scores[key]))
    head_hash=provenance['head_sha256']
    model=ModelInfo(name='ImageNet MobileNet feature probe (exploratory)',
                    version='mobilenet-blood-probe-v1',
                    run_id=f'mobilenet-blood-{head_hash[:24]}',
                    weights_sha256=head_hash,
                    description='Frozen ImageNet MobileNetV3-small features + train-only linear probe. Development examples 9-10 already inspected. Uncalibrated blood annotation ranking, NOT diagnostic or clinically validated; original CNN had stronger historical development results.')
    return save_predictions(store,study_id,PredictionImport(schema_version=1,study_id=study_id,model=model,predictions=predictions))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--study-id',required=True)
    p.add_argument('--exam',type=int,choices=(9,10),required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(import_scores(a.data_dir,a.study_id,a.exam,a.run_dir),indent=2))

if __name__=='__main__':main()
