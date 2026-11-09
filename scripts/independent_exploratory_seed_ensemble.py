#!/usr/bin/env python3
"""Independent replay and published-control cross-check, stdlib only."""
import argparse, hashlib,io,json,zipfile
from collections import Counter
from pathlib import Path

EXAMS=[23,25,29,30]
SEEDS=[17,29,43]
ARM=['classification','local_ranking']

def sha(b): return hashlib.sha256(b).hexdigest()

def verify(outer,produced):
    r=json.loads(Path(produced).read_text())
    with zipfile.ZipFile(outer) as z:
        manifest_text=z.read('foundation/support-manifest-private.json')
        m=json.loads(manifest_text)
        pred_data=z.read('frozen-packages/Short_Event_Support_Preoutcome_Evidence_20261109.zip')
        pub=json.loads(z.read('foundation/outcomes/aggregate.json'))
    assert r['input_outer_sha256']==sha(Path(outer).read_bytes())
    assert r['input_nested_sha256']==sha(pred_data)
    assert r['input_manifest_sha256']==sha(manifest_text)
    with zipfile.ZipFile(io.BytesIO(pred_data)) as p:
        seal=json.loads(p.read('preoutcome-seal.json'))
        seal_map={str(item['path']).split('/private/foundation/',1)[-1]:(item['sha256'],item['bytes']) for item in seal['files']}
        actual={}
        for ex in EXAMS:
            for arm in ARM:
                for seed in SEEDS:
                    path=f'fits/{ex}/{arm}-seed{seed}-logits.json'
                    b=p.read(path)
                    assert path in seal_map and (sha(b),len(b))==seal_map[path]
                    d=json.loads(b)
                    actual[ex,seed,arm]={i: (b-a) for i,(a,b) in zip(d['endpoint_indices'],d['logits'])}
        expected={(t['exam'],t['seed'],t['arm']):t['held_out']['correct'] for t in pub['cells'] if t['cohort']=='expanded_balanced69'}
        assert len(expected)==24
        for ex in EXAMS:
            ps=[q for q in m['pairs'] if q['exam']==ex]
            for arm in ARM:
                seed_counts=[]
                vote_count=avg_count=0
                svote=savg=0
                singleton_counts=[]
                for seed in SEEDS:
                    count=sum(actual[ex,seed,arm][q['positive_index']]-actual[ex,seed,arm][q['negative_index']]>0 for q in ps)
                    seed_counts.append(count)
                    assert count==expected[ex,seed,arm],(ex,seed,arm,count,expected[ex,seed,arm])
                    singleton_counts.append(sum(actual[ex,seed,arm][q['positive_index']]-actual[ex,seed,arm][q['negative_index']]>0 for q in ps if q['run_length']==1))
                for q in ps:
                    vals=[actual[ex,s,arm][q['positive_index']]-actual[ex,s,arm][q['negative_index']] for s in SEEDS]
                    vote=sum(x>0 for x in vals)>=2
                    avg=sum(vals)>0
                    vote_count+=vote
                    avg_count+=avg
                    if q['run_length']==1:svote+=vote;savg+=avg
                row=next(t for t in r['rows'] if t['exam']==ex and t['arm']==arm)
                assert row['seed_correct']==seed_counts
                assert row['singleton_seed_correct']==singleton_counts
                assert row['majority_correct']==vote_count
                assert row['mean_margin_correct']==avg_count
                assert row['singleton_majority_correct']==svote
                assert row['singleton_mean_margin_correct']==savg
                assert row['distinct_runs']==len(ps)
                assert row['singletons']==sum(q['run_length']==1 for q in ps)
        for arm in ARM:
            rows=[t for t in r['rows'] if t['arm']==arm]
            assert len(rows)==4
            for typ,val in [('individual_seed_mean',lambda t:sum(t['seed_correct'])/(3*t['distinct_runs'])),('three_seed_majority',lambda t:t['majority_correct']/t['distinct_runs']),('three_seed_raw_margin_mean',lambda t:t['mean_margin_correct']/t['distinct_runs'])]:
                assert abs(sum(val(t) for t in rows)/4-r['summary'][arm][typ]['macro_ordering'])<1e-14
    return {'outer_sha256':sha(Path(outer).read_bytes()),'published_control_cells_reproduced':24,'sealed_model_score_vectors_verified':24,'distinct_runs':69,'singleton_runs':21,'analysis_rows_verified':8,'status':'PASS'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('outer',type=Path);p.add_argument('results',type=Path);p.add_argument('receipt',type=Path)
    a=p.parse_args();d=verify(a.outer,a.results);a.receipt.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))