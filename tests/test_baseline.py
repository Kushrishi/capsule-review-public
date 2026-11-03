import json
from pathlib import Path

import pytest

torch = pytest.importorskip('torch', reason='Install the optional ml extra to test training/inference')
pytest.importorskip('numpy')
from fastapi.testclient import TestClient
from capsule_review.app import create_app
from capsule_review.baseline import classification_metrics, install_model, load_model, predict_study, train
from capsule_review.baseline_data import digest, prepare_manifest
from capsule_review.importer import import_sources
from capsule_review.prediction_service import save_predictions
from capsule_review.store import Store
from test_baseline_data import make_dataset


@pytest.fixture(scope='module')
def run_bundle(tmp_path_factory):
    root=tmp_path_factory.mktemp('training')
    images,labels=make_dataset(root/'data')
    manifest=root/'manifest.json'
    prepare_manifest(images,labels,manifest,validation_exams=[3],classes=('stomach','colon'),data_kind='synthetic-test')
    output=root/'run'
    report=train(manifest,images,output,epochs=3,batch_size=8,seed=17,allow_synthetic_test=True)
    return images,labels,manifest,output,report


def import_exam(store,images,exam=3,synthetic=True):
    folder=images/f'{exam:03d}'
    return import_sources(store,((p.name,p.read_bytes()) for p in sorted(folder.glob('*.PNG'))),
                          title='Software test — NOT MEDICAL',source='Generated test patterns',synthetic=synthetic)


def test_training_runs_and_keeps_validation_separate(run_bundle):
    _,_,_,run,report=run_bundle
    assert report['data_kind']=='synthetic-test' and report['clinical_validation'] is False
    assert report['model']['frames']==8 and report['model']['examinations']==1
    history=json.loads((run/'history.json').read_text())['epochs']
    assert len(history)==3
    assert history[-1]['training_loss_batch_average'] < history[0]['training_loss_batch_average']
    model,meta=load_model(run,allow_synthetic_test=True)
    assert meta['training_exams']==['1','2'] and meta['validation_exams']==['3']
    assert set(meta['implementation_sha256'])=={'baseline.py','baseline_data.py'}
    assert len(list(model.parameters()))>0


def test_synthetic_model_requires_explicit_test_flag(run_bundle,tmp_path):
    _,_,manifest,run,_=run_bundle
    with pytest.raises(ValueError,match='software-test'):load_model(run)
    with pytest.raises(ValueError,match='software-test'):install_model(Store(tmp_path/'workspace'),run)
    with pytest.raises(ValueError,match='Synthetic training'):
        train(manifest,run_bundle[0],tmp_path/'not-run',epochs=1)
    assert not (tmp_path/'not-run').exists()


def test_reproducible_cpu_weights(run_bundle,tmp_path):
    images,_,manifest,run,_=run_bundle
    second=tmp_path/'repeat'
    train(manifest,images,second,epochs=3,batch_size=8,seed=17,allow_synthetic_test=True)
    first,_=load_model(run,allow_synthetic_test=True);repeat,_=load_model(second,allow_synthetic_test=True)
    for key,value in first.state_dict().items():assert torch.equal(value,repeat.state_dict()[key])


def test_inference_ignores_reference_labels_and_preserves_notes(run_bundle,tmp_path):
    images,_,_,run,_=run_bundle;store=Store(tmp_path/'workspace');study=import_exam(store,images)
    with store.connect() as db:
        db.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?)',(study['id'],0,1,1,'My independent note','reviewer label','now'))
    a=predict_study(store,study['id'],run,allow_synthetic_test=True)
    with store.connect() as db:db.execute('UPDATE frames SET reference_labels=? WHERE study_id=?',(json.dumps({'colon':999}),study['id']))
    b=predict_study(store,study['id'],run,allow_synthetic_test=True)
    assert [p.model_dump() for p in a.predictions]==[p.model_dump() for p in b.predictions]
    result=save_predictions(store,study['id'],a)
    assert result['count']==8
    frame=store.frame(study['id'],0)
    assert frame['review']['note']=='My independent note' and frame['review']['revision']==1
    assert frame['reference_labels']=={'colon':999}
    assert frame['predictions'][0]['model']['name']=='Software-test model — NOT MEDICAL'


def test_training_overlap_refused(run_bundle,tmp_path):
    images,_,_,run,_=run_bundle;store=Store(tmp_path/'workspace');study=import_exam(store,images,exam=1)
    with pytest.raises(ValueError,match='training images'):predict_study(store,study['id'],run,allow_synthetic_test=True)
    payload=predict_study(store,study['id'],run,allow_synthetic_test=True,allow_training_overlap=True)
    assert 'in-sample' in payload.model.description


def test_synthetic_model_cannot_process_real_exam(run_bundle,tmp_path):
    images,_,_,run,_=run_bundle;store=Store(tmp_path/'workspace');study=import_exam(store,images,synthetic=False)
    with pytest.raises(ValueError,match='real examination'):predict_study(store,study['id'],run,allow_synthetic_test=True)


def test_display_tampering_refused(run_bundle,tmp_path):
    images,_,_,run,_=run_bundle;store=Store(tmp_path/'workspace');study=import_exam(store,images)
    (store.images/study['id']/'0.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='modified'):predict_study(store,study['id'],run,allow_synthetic_test=True)


def test_model_install_and_browser_api(run_bundle,tmp_path):
    images,_,_,run,_=run_bundle;app=create_app(tmp_path/'workspace');store=app.state.store
    study=import_exam(store,images);model_id=install_model(store,run,allow_synthetic_test=True)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        models=client.get('/api/models').json();assert models[0]['id']==model_id and models[0]['synthetic_test']
        token=client.get('/api/config').json()['token']
        response=client.post(f'/api/studies/{study["id"]}/predict',headers={'x-review-token':token},json={'model_id':model_id})
        assert response.status_code==201,response.text
        assert response.json()['count']==8
        assert len(store.frame(study['id'],0)['predictions'])==1
        assert client.post(f'/api/studies/{study["id"]}/predict',headers={'x-review-token':token},json={'model_id':'../escape'}).status_code==422
    with pytest.raises(ValueError,match='already installed'):install_model(store,run,allow_synthetic_test=True)


def test_no_model_files_overwritten(run_bundle):
    images,_,manifest,run,_=run_bundle
    with pytest.raises(ValueError,match='already exists'):train(manifest,images,run,allow_synthetic_test=True)


def test_corrupted_weights_rejected(run_bundle,tmp_path):
    import shutil
    target=tmp_path/'copy';shutil.copytree(run_bundle[3],target)
    (target/'weights.pt').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):load_model(target,allow_synthetic_test=True)


def test_nonfinite_model_weights_rejected(run_bundle,tmp_path):
    import shutil
    target=tmp_path/'copy';shutil.copytree(run_bundle[3],target)
    state=torch.load(target/'weights.pt',weights_only=True)
    state[next(iter(state))].fill_(float('nan'));torch.save(state,target/'weights.pt')
    meta=json.loads((target/'model.json').read_text());meta['weights_sha256']=digest((target/'weights.pt').read_bytes())
    (target/'model.json').write_text(json.dumps(meta))
    with pytest.raises(ValueError,match='non-finite'):load_model(target,allow_synthetic_test=True)


def test_metrics_show_denominators_and_missing_support():
    r=classification_metrics([0,0,1],[0,1,1],['a','a','b'],['stomach','colon','mouth'])
    assert r['confusion_matrix']==[[1,1,0],[0,1,0],[0,0,0]]
    assert r['accuracy']==pytest.approx(2/3)
    assert r['mean_examination_accuracy']==.75
    assert r['per_class']['mouth']['recall'] is None
    assert r['per_class']['mouth']['f1'] is None
