"""Safety and arithmetic checks for the fixed real-Galar domain-adaptation design."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import train_domain_blood as m


def fixture_records():
    return [{'exam': exam, 'frame': i*5, 'blood': int(exam in (1,7) and i< (22 if exam==1 else 208)),
             'path': f'{exam:03}/frame_{i*5:06}.PNG',
             'split': 'train' if exam<=8 else 'development'}
            for exam in range(1,11) for i in range(512)]


def test_fixed_spec_matches_commit_hash():
    spec=Path(__file__).resolve().parents[1]/'docs/DOMAIN_ADAPTATION_SPEC.json'
    data=m.validate_spec(spec)
    assert data['training']['epochs']==3
    assert data['held_out_training_fold_examinations']==[1,7]


def test_spec_tamper_is_rejected(tmp_path):
    spec=Path(__file__).resolve().parents[1]/'docs/DOMAIN_ADAPTATION_SPEC.json'
    altered=tmp_path/'altered.json'
    altered.write_bytes(spec.read_bytes().replace(b'0.00015',b'0.10000'))
    with pytest.raises(ValueError,match='specification changed'):
        m.validate_spec(altered)


@pytest.mark.parametrize('heldout', [1,7])
def test_training_only_validation_excludes_entire_heldout_examination(heldout):
    train,hold=m.ensure_exam_partition(fixture_records(),'fold',heldout)
    assert len(train)==3584 and len(hold)==512
    assert {r['exam'] for r in hold}=={heldout}
    assert {r['exam'] for r in train}==set(range(1,9))-{heldout}
    assert all(r['split']=='train' for r in train+hold)


def test_final_training_cannot_include_9_10_even_if_current_development_was_explored():
    train,dev=m.ensure_exam_partition(fixture_records(),'final',None)
    assert len(train)==4096 and len(dev)==1024
    assert {r['exam'] for r in train}==set(range(1,9))
    assert {r['exam'] for r in dev}=={9,10}


@pytest.mark.parametrize('mode,heldout',[('fold',2),('fold',9),('final',7),('incorrect',None)])
def test_unapproved_folds_or_test_evaluation_refused(mode,heldout):
    with pytest.raises(ValueError,match='Only internal folds'):
        m.ensure_exam_partition(fixture_records(),mode,heldout)


def test_conflicting_labels_or_missing_image_rejected():
    rows=fixture_records()
    rows[0]['blood']=None
    with pytest.raises(ValueError,match='Cross-examination leakage'):
        m.ensure_exam_partition(rows,'fold',7)
    rows=fixture_records()[1:]
    with pytest.raises(ValueError,match='Cross-examination leakage'):
        m.ensure_exam_partition(rows,'fold',7)


def test_reserved_patient_examination_cannot_be_silently_added():
    rows=fixture_records()
    rows[20]['exam']=61
    with pytest.raises(ValueError,match='Cross-examination leakage'):
        m.ensure_exam_partition(rows,'final',None)


def test_duplicate_source_frame_rejected():
    rows=fixture_records()
    rows[1]['frame']=rows[0]['frame']
    with pytest.raises(ValueError,match='Cross-examination leakage'):
        m.ensure_exam_partition(rows,'fold',7)


def test_budget_metrics_multiple_review_budgets_and_no_claim_for_negative_only_exam():
    y=fixture_records()
    first=[r for r in y if r['exam']==1]
    scores=[0.9 if r['blood']==1 else 0.1 for r in first]
    out=m.budget_metrics(first,scores)['1']
    assert out['support']['positive']==22
    assert out['rank_metrics']['roc_auc']==1.0
    assert out['budgets']['10']['reviewed']==51
    assert out['budgets']['10']['positive_frames_found']==22
    assert out['budgets']['100']['reviewed']==512
    negative=[r for r in y if r['exam']==8]
    out2=m.budget_metrics(negative,[0.1]*512)['8']
    assert out2['rank_metrics']['roc_auc'] is None
    assert out2['rank_metrics']['average_precision'] is None
    assert out2['budgets']['100']['positive_frames_found']==0


def test_scores_must_align():
    rows=[r for r in fixture_records() if r['exam']==1]
    with pytest.raises(ValueError,match='Scores misaligned'):
        m.budget_metrics(rows,[0.5]*511)
    with pytest.raises(ValueError,match='Scores misaligned'):
        m.budget_metrics(rows,[float('nan')]*512)


def test_existing_output_guard_precedes_pretrained_imports(tmp_path):
    present=tmp_path/'output'
    present.mkdir()
    with pytest.raises(FileExistsError,match='Refusing to overwrite'):
        m.atomic_run(tmp_path/'missing',tmp_path/'images',tmp_path/'weights',tmp_path/'spec',present,'final')
