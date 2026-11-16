"""Independent stdlib replay of fixed CR-MA-01 logits, counts and selections.

Does not import the execution implementation, torch or numpy. Never fits or
runs a model. Inputs remain private; output contains private video identities.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path


def read(p):return json.loads(p.read_text())
def digest(p):return sha256(p.read_bytes()).hexdigest()


def calculate(logits,records,classes):
    matrix=[[0]*3 for _ in range(3)];cells=defaultdict(lambda:[0,0]);video=defaultdict(lambda:[0,0]);losses=[]
    assert len(logits)==len(records)
    for scores,r in zip(logits,records):
        assert len(scores)==3 and all(math.isfinite(s) for s in scores)
        actual=classes.index(r['label']);chosen=max(range(3),key=lambda k:scores[k]);correct=int(chosen==actual)
        matrix[actual][chosen]+=1;cells[actual,r['video']][0]+=correct;cells[actual,r['video']][1]+=1
        video[r['video']][0]+=correct;video[r['video']][1]+=1
        largest=max(scores);losses.append(largest+math.log(math.fsum(math.exp(s-largest) for s in scores))-scores[actual])
    exact={}
    for c,name in enumerate(classes):
        fractions=[Fraction(a,b) for (k,v),(a,b) in cells.items() if k==c]
        exact[name]=sum(fractions,Fraction())/len(fractions)
    f1=[]
    for c in range(3):
        den=sum(matrix[c])+sum(row[c] for row in matrix);f1.append(2*matrix[c][c]/den if den else 0.)
    return {'primary':sum(exact.values(),Fraction())/3,'exact':exact,'confusion':matrix,
        'loss':math.fsum(losses)/len(losses),'f1':math.fsum(f1)/3,
        'videos':{v:{'accuracy':a/b,'categories':{classes[c]:x/y for (c,w),(x,y) in cells.items() if w==v}} for v,(a,b) in video.items()}}


def verify(args):
    root=args.output;folder=args.frozen/'qualified'
    assert digest(folder/'COMMITMENT.json')=='ac9b6615c69d7f31a9f26ea8d114188fbc681885e0c74e7495ffec138f8e8a18'
    for name,item in read(folder/'COMMITMENT.json')['files'].items():assert digest(folder/name)==item['sha256']
    for seal in ('FIT_SELECTION_SEAL.json','PRE_EVALUATION_SEAL.json'):
        assert digest(root/seal)==(root/(seal+'.sha256')).read_text().strip()
        for name,item in read(root/seal)['files'].items():assert digest(root/name)==item['sha256']
    records=read(folder/'IMAGE_BACKED_CANDIDATE_SPLIT.json')['records_private'];classes=read(folder/'FINAL_PROTOCOL_PRIVATE.json')['class_order']
    batches=read(folder/'SHARED_TRAINING_ORDER_PRIVATE.json')['batches'];test=[i for i,r in enumerate(records) if r['split']=='test'];validation=[i for i,r in enumerate(records) if r['split']=='validation']
    published=read(root/'TEST_RESULTS_PRIVATE.json');computed={};selected={}
    for arm in ('scratch','mobilenet'):
        path=root/arm;trace=[json.loads(line) for line in (path/'TRAINING_TRACE.jsonl').read_text().splitlines()]
        assert len(trace)==512
        for step,(line,batch) in enumerate(zip(trace,batches),1):
            assert line['step']==step and math.isfinite(line['loss'])
            assert line['batch_sha256']==sha256(json.dumps(batch,separators=(',',':')).encode()).hexdigest()
            assert line['resources']['wall_seconds']<=3600 and line['resources']['peak_RSS_bytes']<=4*1024**3
        candidates=[]
        for step in (128,256,384,512):
            values=read(path/f'validation-{step}.json');assert values['indices']==validation
            m=calculate(values['logits'],[records[i] for i in validation],classes)
            measured=read(path/f'validation-measurement-{step}.json')
            compare(m,measured['metrics']);assert digest(path/measured['checkpoint'])==measured['checkpoint_sha256']
            candidates.append((-m['primary'],m['loss'],step))
        selected[arm]=min(candidates)[2];fit=read(path/'FIT_COMPLETE.json')
        assert fit['updates']==512 and fit['selected_step']==selected[arm]
        assert digest(path/fit['selected_checkpoint'])==fit['selected_checkpoint_sha256']
        values=read(root/f'{arm}-test-logits.json');assert values['indices']==test and values['model_sha256']==fit['selected_checkpoint_sha256']
        computed[arm]=calculate(values['logits'],[records[i] for i in test],classes);compare(computed[arm],published[arm])
    difference=computed['mobilenet']['primary']-computed['scratch']['primary']
    advance=difference>0 and all(computed['mobilenet']['exact'][c]>=computed['scratch']['exact'][c] for c in classes[:2])
    expected='ADVANCE_EXPLORATORY_SYSTEM' if advance else 'DO_NOT_ADVANCE_FIXED_CONFIGURATION'
    assert published['advancement']['decision']==expected
    assert published['advancement']['exact_macro_recall_difference']==[difference.numerator,difference.denominator]
    for v,base in computed['scratch']['videos'].items():
        delta=published['per_video_differences_private'][v];challenger=computed['mobilenet']['videos'][v]
        assert abs(delta['accuracy_difference']-(challenger['accuracy']-base['accuracy']))<1e-12
        for c,value in base['categories'].items():assert abs(delta['category_recall_differences'][c]-(challenger['categories'][c]-value))<1e-12
    result={'status':'PASS','implementation':'stdlib math/Fraction; no primary metric imports or inference','selected_steps':selected,
        'verified':['512 shared batches each','four validation measurements and checkpoint selection','checkpoint and pre-evaluation seals','test indices and model identities','confusion, recalls, macro-F1, log loss, video differences','exact advancement decision'],
        'numerical_tolerance':1e-10,'test_results_sha256':digest(root/'TEST_RESULTS_PRIVATE.json'),'decision':expected}
    with (root/'INDEPENDENT_VERIFICATION.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))


def compare(independent,reported):
    assert independent['confusion']==reported['confusion_matrix']
    for key,value in [('class_then_video_macro_recall',float(independent['primary'])),('macro_F1',independent['f1']),('multiclass_log_loss',independent['loss'])]:assert abs(value-reported[key])<1e-10
    for c,value in independent['exact'].items():
        assert reported['exact_recalls'][c]==[value.numerator,value.denominator]
        assert abs(float(value)-reported['category_video_macro_recalls'][c])<1e-12
    for v,item in independent['videos'].items():
        assert abs(item['accuracy']-reported['videos_private'][v]['accuracy'])<1e-12
        for c,value in item['categories'].items():assert abs(value-reported['videos_private'][v]['category_recalls'][c])<1e-12


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--frozen',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args())
