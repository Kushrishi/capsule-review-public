"""Private-only two-reader consistency analysis for blinded Capsule Review packets.

Requires complete responses with distinct reviewer codes. Outputs private
opaque-ID disagreement and review-required registers. Codes cannot establish
reviewer independence or qualifications. No clinical truth, diagnoses, patient
independence or model sensitivity is inferred. No web requests.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse, json, re, zipfile

FIELDS={
 'fresh_blood':{'yes','no','uncertain'},
 'hematin':{'yes','no','uncertain'},
 'artifact':{'yes','no','uncertain'},
 'image_quality':{'adequate','limited','uninterpretable'},
 'needs_context':{'yes','no','uncertain'},
}


def validate_response(response:object,packet:dict)->dict:
    if type(response) is not dict or response.get('schema_version')!='capsule-review-blinded-response-v1':
        raise ValueError('Unrecognized blinded reviewer response format.')
    if response.get('packet_id')!=packet['packet_id']:
        raise ValueError('Response packet mismatch.')
    code=response.get('reviewer_code')
    if not isinstance(code,str) or re.fullmatch('[A-Za-z0-9_-]{2,40}',code) is None:
        raise ValueError('Expected a valid pseudonymous independent reviewer code.')
    required={item['item_id'] for item in packet['items']}
    if len(required)!=len(packet['items']) or set(response.get('responses',{}))!=required:
        raise ValueError('Every preselected image must have exactly one complete reviewer response.')
    out={}
    for itemid,record in response['responses'].items():
        if type(record) is not dict or set(record)!=(set(FIELDS)|{'note'}):
            raise ValueError('Missing or extra reviewer fields.')
        for k,choices in FIELDS.items():
            if record[k] not in choices:
                raise ValueError('Incomplete or invalid category; uncertain is a valid response.')
        note=record['note']
        if not isinstance(note,str) or len(note)>240:
            raise ValueError('Invalid reviewer note.')
        out[itemid]=record
    return {'reviewer_code':code,'responses':out}


def compare(packet:dict,a:object,b:object)->dict:
    a=validate_response(a,packet);b=validate_response(b,packet)
    if a['reviewer_code']==b['reviewer_code']:
        raise ValueError('Two independently coded reviewers are required.')
    stats={f:Counter() for f in FIELDS};disagreements=[];review_required=[]
    both_uncertain={f:0 for f in FIELDS}
    for item in packet['items']:
        itemid=item['item_id'];one=a['responses'][itemid];two=b['responses'][itemid]
        diff={};flagged_fields={}
        for f in FIELDS:
            stats[f]['agree' if one[f]==two[f] else 'disagree']+=1
            if f in ('fresh_blood','hematin','artifact','needs_context') and one[f]=='uncertain' and two[f]=='uncertain':both_uncertain[f]+=1
            if one[f]!=two[f]:diff[f]=[one[f],two[f]]
            answers=[one[f],two[f]]
            reasons=[]
            if one[f]!=two[f]:reasons.append('disagreement')
            if 'uncertain' in answers:reasons.append('uncertain')
            if f=='image_quality' and any(value!='adequate' for value in answers):
                reasons.append('quality_not_adequate')
            if f=='needs_context' and 'yes' in answers:
                reasons.append('context_requested')
            if reasons:flagged_fields[f]={'answers':answers,'reasons':reasons}
        if diff:disagreements.append({'item_id':itemid,'disputed_fields':diff})
        if flagged_fields:review_required.append({'item_id':itemid,'fields':flagged_fields})
    return {'schema_version':'capsule-review-blinded-dual-review-v1','packet_id':packet['packet_id'],
            'status':'DUAL_REVIEW_AGREEMENT_ONLY_NO_CLINICAL_REFERENCE_STANDARD',
            'n_source_selected_images':len(packet['items']),
            'reviewer_codes':[a['reviewer_code'],b['reviewer_code']],
            'field_agreement':{f:dict(s) for f,s in stats.items()},
            'both_uncertain':both_uncertain,
            'images_with_any_disagreement':len(disagreements),
            'arbitration_required':True,
            'disagreement_items_private':disagreements,
            'images_requiring_review':len(review_required),
            'review_required_items_private':review_required,
            'constraints':['Preselected, previously labelled source-neighbour comparison images: not a prevalence sample.',
                           'Reviewer agreement and unresolved ambiguity are not a validated clinical truth standard.',
                           'Distinct reviewer codes do not verify independent review or clinical qualifications.',
                           'Flagged disagreements, uncertainty, quality limits and context requests require qualified human review; no answer is resolved automatically.',
                           'An empty review-required register does not establish clinical truth or distinct event identity.',
                           'No medical model outcome, patient-independence or event-detection claim is generated.']}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviewer-zip',type=Path,required=True)
    p.add_argument('--reader-a',type=Path,required=True)
    p.add_argument('--reader-b',type=Path,required=True)
    p.add_argument('--output-private',type=Path,required=True)
    a=p.parse_args()
    if a.output_private.exists():raise FileExistsError('Never overwrite an existing clinical review result.')
    with zipfile.ZipFile(a.reviewer_zip) as z:packet=json.loads(z.read('manifest.json'))
    result=compare(packet,json.loads(a.reader_a.read_text()),json.loads(a.reader_b.read_text()))
    a.output_private.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Complete dual-reader comparison and review-required register generated locally. No clinical answers resolved or event/clinical accuracy computed.')


if __name__=='__main__':main()
