"""Independent image-level replay of the frozen MobileNet Galar development output."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

from pretrained_blood_probe import (WEIGHTS_SHA256, SPEC_SHA256, MANIFEST_SHA256,
                                    hash_file, extract_features, score_probe)
from blood_image_pilot import validate_manifest
from capsule_review.baseline_data import image_identity, safe_path
from blood_image_pilot import evaluate


def verify(manifest:Path, images:Path, weights:Path, spec:Path, run:Path) -> dict:
    if hash_file(weights)!=WEIGHTS_SHA256 or hash_file(spec)!=SPEC_SHA256:
        raise ValueError('Official weights or frozen research specification changed.')
    data=validate_manifest(manifest, images, check_files=False)
    if data['sha256']!=MANIFEST_SHA256:
        raise ValueError('Frozen Galar manifest changed.')
    prov=json.loads((run/'provenance.json').read_text())
    if not all((prov['official_weight_sha256']==WEIGHTS_SHA256,
                prov['frozen_spec_sha256']==SPEC_SHA256,
                prov['frozen_manifest_sha256']==MANIFEST_SHA256,
                prov['head_sha256']==hash_file(run/'probe-head.json'),
                prov['metrics_sha256']==hash_file(run/'metrics.json'),
                prov['predictions_sha256']==hash_file(run/'predictions.csv'))):
        raise ValueError('Frozen recorded experiment identity mismatch.')
    head=json.loads((run/'probe-head.json').read_text())
    metrics=json.loads((run/'metrics.json').read_text())
    if metrics['official_backbone_sha256']!=WEIGHTS_SHA256 or metrics['frozen_spec_sha256']!=SPEC_SHA256:
        raise ValueError('Backbone or protocol mismatch.')
    rows=[r for r in data['records'] if r['split']=='development']
    for row in rows:
        actual_hashes=image_identity(safe_path(images,row['path']))
        if actual_hashes != (row['source_sha256'],row['pixel_sha256']):
            raise ValueError('Original image bytes or decoded pixels changed.')
    actual=score_probe(extract_features(rows,images,weights),head)
    with (run/'predictions.csv').open(newline='',encoding='utf-8') as fp:
        saved=list(csv.DictReader(fp))
    if len(saved)!=1024 or len(actual)!=1024:
        raise ValueError('Unexpected number of development predictions.')
    largest=0
    for row,s,z in zip(rows,actual,saved):
        if ((row['exam'],row['frame'],row['source_sha256'],row['blood']) !=
                (int(z['exam']),int(z['frame']),z['source_sha256'],int(z['blood_label']))):
            raise ValueError('Changed source identity or annotation alignment.')
        diff=abs(s-float(z['mobilenet_score']))
        largest=max(largest,diff)
        if diff>1e-8:
            raise ValueError('Independent pretrained replay changed a score.')
    reevaluated=evaluate(rows,actual)
    for scope in ['aggregate']:
        for field in ('roc_auc','average_precision','positive','negative'):
            if abs(reevaluated[scope][field]-metrics['evaluation'][scope][field])>1e-8:
                raise ValueError('Mismatch in frozen aggregate metric.')
    for exam in ('9','10'):
        for field in ('roc_auc','average_precision','positive','negative'):
            old=metrics['evaluation']['by_examination'][exam][field]
            now=reevaluated['by_examination'][exam][field]
            if old is None or now is None:
                if old is not now:raise ValueError('Null-class handling changed.')
            elif abs(old-now)>1e-8:raise ValueError('Per-examination metric changed.')
    return {'status':'independent replay passed',
            'data_kind':'real Galar historical development',
            'frames_sha256_and_labels_checked':1024,
            'all_saved_scores_reproduced':True,
            'max_score_absolute_difference':largest,
            'frozen_source_manifest_sha256':MANIFEST_SHA256,
            'official_pretrained_weights_sha256':WEIGHTS_SHA256,
            'probe_sha256':prov['head_sha256'],
            'clinical_validation':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for field in ('manifest','images','weights','spec','run'):
        p.add_argument('--'+field,type=Path,required=True)
    a=p.parse_args()
    out=verify(a.manifest,a.images,a.weights,a.spec,a.run)
    (a.run/'independent-verification.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
