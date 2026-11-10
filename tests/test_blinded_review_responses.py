import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_blinded_review_responses import FIELDS,validate_response,compare


def fixtures():
    manifest={'packet_id':'a'*24,'items':[{'item_id':'1'*24,'image':'images/'+'1'*24+'.png'},
                                          {'item_id':'2'*24,'image':'images/'+'2'*24+'.png'}]}
    values={'fresh_blood':'no','hematin':'uncertain','artifact':'no','image_quality':'adequate','needs_context':'uncertain','note':''}
    a={'schema_version':'capsule-review-blinded-response-v1','packet_id':'a'*24,'reviewer_code':'reviewer-a',
       'responses':{'1'*24:dict(values),'2'*24:dict(values)}}
    b=copy.deepcopy(a);b['reviewer_code']='reviewer-b'
    return manifest,a,b


def test_two_independent_complete_responses():
    packet,a,b=fixtures()
    b['responses']['2'*24]['fresh_blood']='yes'
    out=compare(packet,a,b)
    assert out['field_agreement']['fresh_blood']=={'agree':1,'disagree':1}
    assert out['images_with_any_disagreement']==1
    assert out['both_uncertain']['hematin']==2
    assert out['arbitration_required'] is True
    assert out['status'].endswith('NO_CLINICAL_REFERENCE_STANDARD')


def test_same_reader_rejected():
    packet,a,b=fixtures();b['reviewer_code']=a['reviewer_code']
    with pytest.raises(ValueError,match='independently'):
        compare(packet,a,b)


def test_different_packet_rejected():
    packet,a,b=fixtures();b['packet_id']='b'*24
    with pytest.raises(ValueError,match='packet mismatch'):
        compare(packet,a,b)


def test_missing_image_blocked():
    packet,a,b=fixtures();b['responses'].pop('1'*24)
    with pytest.raises(ValueError,match='Every preselected'):
        compare(packet,a,b)


def test_unknown_label_not_silently_negative():
    packet,a,b=fixtures();a['responses']['1'*24]['fresh_blood']=None
    with pytest.raises(ValueError,match='Incomplete'):
        compare(packet,a,b)


def test_extra_source_identity_refused():
    packet,a,b=fixtures();a['responses']['1'*24]['source_exam']=23
    with pytest.raises(ValueError,match='Missing or extra'):
        compare(packet,a,b)


def test_unapproved_response_refused():
    packet,a,b=fixtures();a['responses']['1'*24]['fresh_blood']='active_bleeding'
    with pytest.raises(ValueError,match='Incomplete'):
        compare(packet,a,b)


def test_patient_identifiers_not_included():
    packet,a,b=fixtures();out=compare(packet,a,b)
    assert 'patient' not in out
    assert 'source_frame' not in out
    assert len(out['disagreement_items_private'])==0
