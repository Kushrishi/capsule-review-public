"""Import real sparse blood-visibility scores as *model suggestions* in a local study.

Never writes Galar reference annotations or human reviewer notes. The caller must
first import the permitted examination into Capsule Review, then supply its ID.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from capsule_review.models import ModelInfo, PredictionImport
from capsule_review.prediction_service import align_fixed_development_scores, save_predictions
from capsule_review.store import Store

LABEL = 'Blood visual cue (research only)'


def import_scores(data_dir: Path, study_id: str, exam: int, run_dir: Path) -> dict:
    if exam not in (9, 10):
        raise ValueError('Only the historical development examinations 9 or 10 may be imported.')
    metrics=json.loads((run_dir/'metrics.json').read_text(encoding='utf-8'))
    weights_sha=hashlib.sha256((run_dir/'weights.pt').read_bytes()).hexdigest()
    if metrics.get('weights_sha256')!=weights_sha or metrics.get('development_examinations')!=[9,10]:
        raise ValueError('Unverified model weights or unexpected experiment split.')
    scores={}
    with (run_dir/'predictions.csv').open(newline='',encoding='utf-8') as fp:
        reader=csv.DictReader(fp)
        if not {'exam','frame','source_sha256','cnn_score'}.issubset(reader.fieldnames or []):
            raise ValueError('Unexpected prediction CSV schema.')
        for row in reader:
            if int(row['exam']) not in (9,10):
                raise ValueError('Scores contain an unapproved examination.')
            if int(row['exam'])!=exam:
                continue
            key=(int(row['frame']),row['source_sha256'])
            p=float(row['cnn_score'])
            if key in scores or not math.isfinite(p) or not 0<=p<=1:
                raise ValueError('Duplicate frame or invalid model score.')
            scores[key]=p
    if len(scores)!=512:
        raise ValueError('Expected exactly 512 predictions and 512 real study frames.')
    store=Store(data_dir)
    predictions=align_fixed_development_scores(store,study_id,scores,LABEL)
    model=ModelInfo(name='Galar sparse blood-visibility baseline (research)',
                    version='blood-sparse-v1',run_id=f'blood-sparse-{weights_sha[:24]}',
                    weights_sha256=weights_sha,
                    description='Uncalibrated blood-label image score; 1–8 fit, 9–10 historical dev. Not active bleeding detection or clinical triage.')
    payload=PredictionImport(schema_version=1,study_id=study_id,model=model,predictions=predictions)
    return save_predictions(store,study_id,payload)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--study-id',required=True)
    parser.add_argument('--examination',type=int,choices=(9,10),required=True)
    parser.add_argument('--run-dir',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(import_scores(args.data_dir,args.study_id,args.examination,args.run_dir),indent=2))
if __name__=='__main__': main()
