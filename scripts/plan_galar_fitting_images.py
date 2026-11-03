"""Create Galar 21–30 fitting-only image requests from corrected source labels.

Prespecification *before new image acquisition/training*, not a clinical study.
The private plan contains exact frame IDs and binary blood annotations: NEVER Git.
Public output has aggregate support and SHA-256 only. No held-out reads.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

SOURCE_SHA256 = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
SOURCE_NAME = '20251215_Labels_Updated.zip'
SOURCE_FILE_ID = 60383963
TRAIN_POOL = tuple(range(21, 31))
HELD_OUT = tuple(range(11, 21)) + tuple(range(61, 81))
EXPECTED_IMAGE_FILE_ID = 45258019
EXPECTED_STRIDE = 5


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def read_exam(z: zipfile.ZipFile, exam: int) -> tuple[list[dict], str, int]:
    if exam not in TRAIN_POOL:
        raise ValueError('Evaluation or other non-fitting examination access denied.')
    name = f'{exam}.csv'
    info = z.getinfo(name)
    if info.file_size == 0 or info.file_size > 64 * 1024 * 1024:
        raise ValueError('Invalid annotation source size.')
    raw = z.read(info)
    source_sha = hashlib.sha256(raw).hexdigest()
    with io.StringIO(raw.decode('utf-8-sig'), newline='') as f:
        reader = csv.DictReader(f)
        if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])) or not {'frame', 'blood'} <= set(reader.fieldnames or []):
            raise ValueError('Missing or ambiguous blood annotation schema.')
        rows = []
        previous = None
        for row in reader:
            if None in row or row.get('blood') not in ('0', '1', '') or not (row.get('frame') or '').isdigit():
                raise ValueError('Malformed or missing source annotation; unknown cannot be treated negative.')
            frame = int(row['frame'])
            if previous is not None and frame <= previous:
                raise ValueError('Unexpected or unordered frame-index spacing; examine source before planning.')
            previous=frame
            rows.append({'frame':frame,'blood':row['blood']})
    if len(rows)<2:
        raise ValueError('Too few source annotations.')
    gaps=Counter(rows[i]['frame']-rows[i-1]['frame'] for i in range(1,len(rows)))
    modal, support=gaps.most_common(1)[0]
    if ((len(gaps)>1 and gaps.most_common(2)[1][1]==support)
        or support/(len(rows)-1)<.95 or modal not in (1,5)
        or modal != 5):
        raise ValueError('Unstable or unexpected label-blind source-frame stride.')
    return rows, source_sha, modal


def uniform_indices(n: int, k: int) -> list[int]:
    if not (0 <= k <= n):
        raise ValueError('Invalid deterministic uniform selection size.')
    return [((2*j+1)*n)//(2*k) for j in range(k)] if k else []


def positive_runs(rows: list[dict], step: int = EXPECTED_STRIDE) -> list[list[int]]:
    runs=[]
    current=[]
    for i,row in enumerate(rows):
        if row['blood']=='1':
            if current and rows[i]['frame']-rows[i-1]['frame']!=step:
                runs.append(current);current=[]
            current.append(i)
        elif current:
            runs.append(current);current=[]
    if current:runs.append(current)
    return runs


def ordered_spread(indices: list[int]) -> list[int]:
    """Coverage-first order within a run; deterministic midpoint then interval bisect."""
    if not indices: return []
    taken=[]
    intervals=[(0,len(indices)-1)]
    while intervals:
        intervals.sort(key=lambda x:(-(x[1]-x[0]),x[0]))
        lo,hi=intervals.pop(0)
        if lo>hi:continue
        mid=(lo+hi)//2
        taken.append(indices[mid])
        if lo<=mid-1:intervals.append((lo,mid-1))
        if mid+1<=hi:intervals.append((mid+1,hi))
    return taken


def choose_enriched(rows: list[dict], n: int, positive_fraction: float = 0.5, *, step: int = EXPECTED_STRIDE) -> set[int]:
    """Training only: cover all observed runs once before spreading remaining positives."""
    if not 0 < positive_fraction < 1:
        raise ValueError('Require a positive and negative fraction target.')
    n=min(n, len(rows))
    runs=positive_runs(rows,step=step)
    positives=min(sum(len(run) for run in runs), math.floor(n*positive_fraction))
    # Phase 1 selects one representative from each run (when budget permits).
    sequences=[ordered_spread(run) for run in runs]
    if len(sequences)>positives:
        preferred=uniform_indices(len(sequences), positives)
        sequences=[sequences[i] for i in preferred]
    result=set()
    while len(result)<positives:
        progressed=False
        for seq in sequences:
            if seq and len(result)<positives:
                result.add(seq.pop(0));progressed=True
        if not progressed:break
    if len(result)!=positives:
        raise ValueError('Failed to allocate positive training images.')
    negative=[i for i,row in enumerate(rows) if row['blood']=='0']
    k=n-len(result)
    if k > len(negative):
        # Never coerce unknown rows; available explicit negatives are the only pool.
        k=len(negative)
    result.update(negative[j] for j in uniform_indices(len(negative), k))
    if any(rows[i]['blood'] not in ('0','1') for i in result):
        raise ValueError('Unknown blood label entered training sample.')
    return result


def plan(labels_zip: Path, output_dir: Path, *, per_exam: int = 512, positive_fraction: float = 0.5) -> dict:
    if per_exam < 2 or per_exam > 4096:
        raise ValueError('Engineering selection target must be 2..4096 images/examination.')
    if not 0<positive_fraction<1:
        raise ValueError('positive_fraction must be between zero and one.')
    if output_dir.exists():
        raise FileExistsError('Private sampling output exists; refuse overwrite.')
    if hash_file(labels_zip) != SOURCE_SHA256:
        raise ValueError('Official corrected-source SHA-256 mismatch.')
    output_dir.mkdir(parents=True)
    requests=[];by_exam={}
    with zipfile.ZipFile(labels_zip) as archive:
        for exam in TRAIN_POOL:
            rows, label_sha, stride=read_exam(archive,exam)
            labelled=[i for i,x in enumerate(rows) if x['blood'] in ('0','1')]
            if len(labelled)<per_exam:
                raise ValueError('Insufficient explicitly labelled candidate frames.')
            reference={labelled[j] for j in uniform_indices(len(labelled),per_exam)}
            enriched=choose_enriched(rows,per_exam,positive_fraction,step=stride)
            union=reference|enriched
            runs=positive_runs(rows,step=stride)
            covered=sum(bool(set(run)&enriched) for run in runs)
            by_exam[str(exam)]={
                'annotation_rows':len(rows),
                'source_frame_stride':stride,
                'blood_positive_source_rows':sum(r['blood']=='1' for r in rows),
                'annotated_positive_runs':len(runs),
                'enriched_positive_runs_represented':covered,
                'enriched_training_candidates':len(enriched),
                'enriched_positive_candidates':sum(rows[i]['blood']=='1' for i in enriched),
                'label_blind_reference_candidates':len(reference),
                'reference_positive_candidates':sum(rows[i]['blood']=='1' for i in reference),
                'unique_requested_images':len(union),
                'dual_purpose_overlap':len(enriched&reference),
                'annotation_csv_sha256':label_sha,
            }
            for i in sorted(union):
                record=rows[i]
                requests.append({
                    'exam':exam,'frame':record['frame'],
                    'filename':f'frame_{record["frame"]:06d}.PNG',
                    'blood':record['blood'],
                    'fit_enriched':int(i in enriched),
                    'reference_uniform':int(i in reference),
                    'source_csv_sha256':label_sha,
                })
    private=output_dir/'requested_frames.csv'
    with private.open('x',newline='',encoding='utf8') as file:
        writer=csv.DictWriter(file,fieldnames=['exam','frame','filename','blood','fit_enriched','reference_uniform','source_csv_sha256'],lineterminator='\n')
        writer.writeheader();writer.writerows(requests)
    summary={
        'analysis':'Galar 21–30 fitting-only pre-image-acquisition selection; not a model result',
        'data_source_name':SOURCE_NAME,
        'official_corrected_labels_sha256':SOURCE_SHA256,
        'source_frame_archive_file_id':EXPECTED_IMAGE_FILE_ID,
        'exam_roles':{'new_fitting':[21,30],'previous_fitting':[1,8],
                      'unopened_future_evaluation':[11,20],'author_unopened_holdout':[61,80]},
        'sampling':{'operational_images_per_exam_per_method':per_exam,
                    'enriched_positive_fraction_max':positive_fraction,
                    'evaluation_sample_rule':'source-chronological uniform, label-blind',
                    'fit_candidate_rule':'run-diverse positive enrichment + uniformly spaced explicitly blood-negative frames',
                    'no_holdout_access':True},
        'overall':{
            'examinations':len(by_exam),'unique_frames_requested':len(requests),
            'training_enriched_candidates':sum(r['enriched_training_candidates'] for r in by_exam.values()),
            'positive_enriched_candidates':sum(r['enriched_positive_candidates'] for r in by_exam.values()),
            'uniform_reference_candidates':sum(r['label_blind_reference_candidates'] for r in by_exam.values()),
            'positive_uniform_reference_candidates':sum(r['reference_positive_candidates'] for r in by_exam.values()),
            'positive_examinations':sum(r['blood_positive_source_rows']>0 for r in by_exam.values()),
            'annotated_positive_runs_covered_in_enriched':sum(r['enriched_positive_runs_represented'] for r in by_exam.values()),
            'annotated_positive_runs':sum(r['annotated_positive_runs'] for r in by_exam.values()),
        },
        'per_examination':{k:{key:v for key,v in r.items() if key!='annotation_csv_sha256'} for k,r in by_exam.items()},
        'private_request_sha256':hash_file(private),
        'private_request_rows':len(requests),
        'private_original_frame_identifiers_committed':False,
        'clinical_validity':False,
        'known_limits':['New fitting sample uses pathology labels for enrichment, so its observed prevalence is not population prevalence.',
                        'Never use pathology-enriched sample as clinical validation.',
                        'Uniform reference positions support only internal exam-held-out comparison when entire exam withheld from fitting.',
                        'No patient IDs available; distinct exams do not prove distinct patients.',
                        'Frame IDs/labels in private manifest must be exactly matched to original verified image bytes before training.',
                        'No source images have been acquired. Source archive layout and exact member filenames still need validation.'],
    }
    (output_dir/'aggregate.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--labels-zip',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--images-per-exam',type=int,default=512)
    p.add_argument('--positive-fraction',type=float,default=0.5)
    a=p.parse_args()
    s=plan(a.labels_zip,a.output_dir,per_exam=a.images_per_exam,positive_fraction=a.positive_fraction)
    print('Fitting-only image request count:',s['overall']['unique_frames_requested'],
          'across',s['overall']['examinations'],'exams; reference positions label-blind.')


if __name__=='__main__':
    main()