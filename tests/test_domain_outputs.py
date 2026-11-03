"""Generated, no-medical-image tests for candidate-result integrity and viewer guards."""
from pathlib import Path
import csv
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import summarize_domain_blood as agg
import import_domain_blood as viewer
from train_domain_blood import MANIFEST_SHA256,SPEC_SHA256,WEIGHTS_SHA256


def fake_run(tmp_path,exam=1):
    run=tmp_path/'run';run.mkdir()
    (run/'candidate-weights.pt').write_bytes(b'generated fake checkpoint')
    labels=[1 if i < (22 if exam==1 else 208) else 0 for i in range(512)]
    scores=[0.95 if y else 0.05 for y in labels]
    with (run/'predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['exam','frame','source_sha256','blood_label','domain_adapted_score'])
        for i,(y,s) in enumerate(zip(labels,scores)):
            w.writerow([exam,i*5,f'{i:064x}',y,s])
    from blood_image_pilot import roc_ap
    record=roc_ap(labels,scores)
    m={'mode':'fold','heldout_exam':exam,'fit_exams':[x for x in range(1,9) if x!=exam],
       'evaluated_exams':[exam],'frozen_spec_sha256':SPEC_SHA256,
       'frozen_manifest_sha256':MANIFEST_SHA256,
       'official_imagenet_weights_sha256':WEIGHTS_SHA256,
       'fine_tuned':{str(exam):{'rank_metrics':record}},
       'predictions_sha256':agg.hash_file(run/'predictions.csv'),
       'fine_tuned_checkpoint_sha256':agg.hash_file(run/'candidate-weights.pt')}
    (run/'metrics.json').write_text(json.dumps(m))
    receipt={'spec':SPEC_SHA256,'manifest':MANIFEST_SHA256,
             'result_sha256':agg.hash_file(run/'metrics.json'),
             'prediction_sha256':m['predictions_sha256'],
             'fine_tuned_checkpoint_sha256':m['fine_tuned_checkpoint_sha256']}
    (run/'source-provenance.json').write_text(json.dumps(receipt))
    return run


def test_reads_complete_fixed_fold_arithmetic(tmp_path):
    run=fake_run(tmp_path,exam=1)
    result=agg.read_run(run,'fold',1)
    assert result['aggregate']['roc_auc']==1.0
    assert result['aggregate']['positive']==22


def test_receipt_must_match_evaluated_predictions(tmp_path):
    run=fake_run(tmp_path)
    with (run/'predictions.csv').open('a') as f:f.write('1,999,abcd,1,0.9\n')
    with pytest.raises(ValueError,match='receipt mismatch'):
        agg.read_run(run,'fold',1)


def test_metric_corruption_detected_against_receipt(tmp_path):
    run=fake_run(tmp_path)
    (run/'metrics.json').write_text('{}')
    with pytest.raises(ValueError):agg.read_run(run,'fold',1)


def test_wrong_fold_never_accepted(tmp_path):
    run=fake_run(tmp_path)
    with pytest.raises(ValueError,match='Unexpected role'):
        agg.read_run(run,'fold',7)


def test_viewer_rejects_training_exams_without_touching_database(tmp_path):
    with pytest.raises(ValueError,match='Only historical'):
        viewer.import_scores(tmp_path,'study',7,tmp_path/'nonexistent')
