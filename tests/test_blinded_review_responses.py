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


def test_agreed_uncertainty_still_has_an_item_level_handoff():
    packet,a,b=fixtures()
    out=compare(packet,a,b)
    assert out['images_with_any_disagreement']==0
    assert out['both_uncertain']['hematin']==2
    assert out['images_requiring_review']==2
    assert out['review_required_items_private']==[
        {'item_id':item['item_id'],'fields':{
            'hematin':{'answers':['uncertain','uncertain'],'reasons':['uncertain']},
            'needs_context':{'answers':['uncertain','uncertain'],'reasons':['uncertain']},
        }} for item in packet['items']
    ]


def unambiguous_responses():
    packet,a,b=fixtures()
    for response in (a,b):
        for record in response['responses'].values():
            record.update(hematin='no',needs_context='no')
    return packet,a,b


def test_concordant_answers_have_no_flags_but_are_not_clinical_truth():
    packet,a,b=unambiguous_responses()
    # Agreement on a visible finding is as unambiguous as agreement on absence;
    # neither establishes a diagnosis or a unique event.
    for response in (a,b):
        response['responses']['1'*24]['fresh_blood']='yes'
    out=compare(packet,a,b)
    assert out['images_requiring_review']==0
    assert out['review_required_items_private']==[]
    assert out['arbitration_required'] is True
    assert out['status'].endswith('NO_CLINICAL_REFERENCE_STANDARD')


@pytest.mark.parametrize('field',['fresh_blood','hematin','artifact','needs_context'])
def test_one_uncertain_reader_is_preserved_with_disagreement(field):
    packet,a,b=unambiguous_responses()
    b['responses']['1'*24][field]='uncertain'
    out=compare(packet,a,b)
    assert out['images_requiring_review']==1
    assert out['review_required_items_private']==[{
        'item_id':'1'*24,'fields':{
            field:{'answers':['no','uncertain'],'reasons':['disagreement','uncertain']}
        }
    }]
    assert out['disagreement_items_private']==[{
        'item_id':'1'*24,'disputed_fields':{field:['no','uncertain']}
    }]
    assert out['both_uncertain'][field]==0


@pytest.mark.parametrize('field,value,reason',[
    ('needs_context','yes','context_requested'),
    ('image_quality','limited','quality_not_adequate'),
    ('image_quality','uninterpretable','quality_not_adequate'),
])
def test_agreed_context_or_quality_limit_is_not_lost(field,value,reason):
    packet,a,b=unambiguous_responses()
    for response in (a,b):
        response['responses']['1'*24][field]=value
    out=compare(packet,a,b)
    assert out['images_with_any_disagreement']==0
    assert out['images_requiring_review']==1
    assert out['review_required_items_private']==[{
        'item_id':'1'*24,'fields':{
            field:{'answers':[value,value],'reasons':[reason]}
        }
    }]


def test_multiple_reasons_share_one_item_and_preserve_source_order():
    packet,a,b=unambiguous_responses()
    for response in (a,b):
        response['responses']['1'*24].update(
            fresh_blood='uncertain',image_quality='limited',needs_context='yes')
    b['responses']['1'*24]['fresh_blood']='yes'
    b['responses']['2'*24]['artifact']='yes'
    # Response-map insertion order must not change the manifest-ordered handoff.
    b['responses']=dict(reversed(list(b['responses'].items())))
    before=copy.deepcopy((packet,a,b))
    out=compare(packet,a,b)
    assert (packet,a,b)==before
    assert out['images_requiring_review']==2
    assert [item['item_id'] for item in out['review_required_items_private']]==['1'*24,'2'*24]
    assert out['review_required_items_private'][0]['fields']=={
        'fresh_blood':{'answers':['uncertain','yes'],'reasons':['disagreement','uncertain']},
        'image_quality':{'answers':['limited','limited'],'reasons':['quality_not_adequate']},
        'needs_context':{'answers':['yes','yes'],'reasons':['context_requested']},
    }
    assert out['review_required_items_private'][1]['fields']=={
        'artifact':{'answers':['no','yes'],'reasons':['disagreement']}
    }


def test_swapped_readers_change_answer_order_only():
    packet,a,b=unambiguous_responses()
    a['responses']['1'*24].update(fresh_blood='uncertain',needs_context='yes')
    b['responses']['1'*24]['image_quality']='uninterpretable'
    one=compare(packet,a,b);two=compare(packet,b,a)
    for field in ('field_agreement','both_uncertain','images_with_any_disagreement',
                  'images_requiring_review','status','arbitration_required'):
        assert one[field]==two[field]
    assert one['reviewer_codes']==list(reversed(two['reviewer_codes']))
    first=one['review_required_items_private'][0]
    second=two['review_required_items_private'][0]
    assert first['item_id']==second['item_id']
    assert first['fields'].keys()==second['fields'].keys()
    for field,value in first['fields'].items():
        assert value['reasons']==second['fields'][field]['reasons']
        assert value['answers']==list(reversed(second['fields'][field]['answers']))


def test_handoff_contains_only_opaque_ids_and_categorical_answers():
    packet,a,b=fixtures()
    for response in (a,b):
        response['responses']['1'*24]['note']='PRIVATE NOTE NOT NEEDED IN HANDOFF'
    out=compare(packet,a,b)
    assert 'PRIVATE NOTE' not in str(out)
    for item in out['review_required_items_private']:
        assert set(item)=={'item_id','fields'}
        assert item['item_id'] in a['responses']
        for field,record in item['fields'].items():
            assert field in FIELDS
            assert set(record)=={'answers','reasons'}
            assert all(answer in FIELDS[field] for answer in record['answers'])
