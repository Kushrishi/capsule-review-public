"""Public executable for private, precommitted red-versus-green image-score pairs.

Do not publish the private input files: exact indices, source identities and image-level scores.
"""
import argparse, json, math, hashlib, zipfile
from collections import defaultdict
from pathlib import Path
EXAMS=(23,25,29,30)


def private_path(path):
    path=Path(path)
    repo=Path(__file__).resolve().parents[1]
    if path.is_symlink() or ((repo/'AGENTS.md').exists() and path.resolve().is_relative_to(repo)):
        raise ValueError('Medical inputs and outputs must remain outside the public repository')
    return path.resolve()

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def evaluate(manifest,scores):
    image_map={r['image_index']:r for r in scores['image_scores']}
    assert len(image_map)==scores['n_images']==137
    endpoint_ids={p[k] for p in manifest['pairs'] for k in ('positive_index','negative_index')}
    assert set(image_map)==endpoint_ids
    for idx,rec in image_map.items():
        if rec['sha256']!=manifest['images'][idx]['sha256'] or not math.isfinite(rec['redness']):raise ValueError('Source score validation failed')
    obs=[]
    for p in manifest['pairs']:
        assert p['exam'] in EXAMS and manifest['images'][p['positive_index']]['blood']==1 and manifest['images'][p['negative_index']]['blood']==0
        margin=image_map[p['positive_index']]['redness']-image_map[p['negative_index']]['redness']
        obs.append({'exam':p['exam'],'singleton':p['run_length']==1,'credit':1 if margin>0 else 0.5 if margin==0 else 0})
    assert len(obs)==69 and sum(x['singleton'] for x in obs)==21
    per_exam=[]
    for ex in EXAMS:
        a=[x for x in obs if x['exam']==ex];s=[x for x in a if x['singleton']]
        per_exam.append({'exam':ex,'n_runs':len(a),'correct':sum(x['credit'] for x in a),'n_singletons':len(s),'correct_singletons':sum(x['credit'] for x in s)})
    assert [x['n_runs'] for x in per_exam]==[23,20,11,15]
    assert [x['n_singletons'] for x in per_exam]==[10,6,2,3]
    macro=sum(x['correct']/x['n_runs'] for x in per_exam)/4
    singleton_macro=sum(x['correct_singletons']/x['n_singletons'] for x in per_exam)/4
    return {'method':'Fixed central-aperture redness ratio (no training)','status':'Exploratory, previously inspected development-only','n_distinct_runs':69,'n_distinct_singletons':21,'macro_ordering':macro,'pooled_correct':sum(x['correct'] for x in per_exam),'macro_singleton_ordering':singleton_macro,'pooled_correct_singletons':sum(x['correct_singletons'] for x in per_exam),'per_exam':per_exam,'clinical_model_promoted':False,'independent_patient_validation':False,'downstream_10pct_event_recall_assessed':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--manifest-zip',type=Path,required=True);ap.add_argument('--scores',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    with zipfile.ZipFile(private_path(a.manifest_zip)) as z:m=json.loads(z.read('foundation/support-manifest-private.json'))
    s=json.loads(private_path(a.scores).read_text());out=evaluate(m,s)
    a.output=private_path(a.output)
    if a.output.exists():raise FileExistsError('Never silently overwrite outcomes.')
    a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(out,indent=2))
    print('source-score-sha256',digest(a.scores))
