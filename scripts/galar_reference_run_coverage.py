"""Audit full-annotation blood runs reachable by historically selected sparse Galar frames.

Post-hoc exploratory research only. This script uses *only* the original corrected
source annotations and previously verified, private per-image prediction archives.
Source-frame identities and prediction rows are NEVER emitted in public results.
An annotation-positive run is not a physician-adjudicated lesion or video event.
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
import statistics
import zipfile

SOURCE_SHA = '2f5ba84c47d343d51952e78bf22183b9d04ba8c105f625af3cf9ffb20412e52f'
EXAMS = (9, 10, 21, 23, 25, 27, 29, 30)
EXPECTED_REFERENCE_POSITIVE = {9:0, 10:213, 21:1, 23:4, 25:14, 27:26, 29:122, 30:120}
EXPECTED_CSV = {
    'pilot': ('private-development-predictions/predictions.csv', 1024, 'f921194639a99e206c9b24e3e896f25ff1a409669024f87c4b8b42767c70b36b', (9,10)),
    'new': ('private/source-scores.csv', 3000, 'caa85f950ac0912a3a89a3a93aad6c4e24ba1dc186a52e51456bf843e8111812', (21,23,30)),
    'exam25': ('private-per-image-scores.csv', 1013, '285d3b14ab0f9e2cf45f4a7ca51205623e5694a17db0d55b9ba421e3023029c7', (25,)),
    'exam27': ('private-source-scores.csv', 1005, '4bd6bb1f605c10c1e1749f3c9d69238951de866c0b72009326923644ca927fe8', (27,)),
    'exam29': ('private-predictions.csv', 1009, 'f27a410a75cdf51bc726b181083fee3f89e9f71f0bed567c04223c1aebf51e79', (29,)),
}
MODEL_NAMES = ('original_checkpoint', 'red_excess', 'original_only_continued', 'expanded_continued')
BUDGETS = (5,10,25,50,75,100)
STRATA = ('1-5','6-25','26+')
THRESHOLDS = (0.1,0.5,0.9)


def sha(data:bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path:Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for blob in iter(lambda:f.read(1<<20),b''):
            h.update(blob)
    return h.hexdigest()


def parse_binary(value:str) -> int:
    if value not in ('0','1'):
        raise ValueError('Unknown, malformed or nonbinary blood/role annotation: cannot coerce to negative.')
    return int(value)


def positive_runs(rows:list[dict], *, step:int=5) -> tuple[list[dict],dict[int,int]]:
    """Contiguous full original positive annotation rows, split at source gaps."""
    if step != 5:
        raise ValueError('Unapproved source stride.')
    runs=[]
    reference={}
    previous=None
    current=[]
    for row in rows:
        frame=row['frame']; blood=row['blood']
        if type(frame) is not int or frame < 0 or blood not in ('0','1',''):
            raise ValueError('Invalid corrected source frame or label.')
        if previous is not None and frame <= previous:
            raise ValueError('Source frame order is corrupted.')
        if current and (blood!='1' or frame-previous!=step):
            runs.append({'length_annotated_rows':len(current),'stratum':stratum(len(current))})
            run_id=len(runs)-1
            for v in current:
                reference[v]=run_id
            current=[]
        if blood=='1':
            current.append(frame)
        previous=frame
    if current:
        runs.append({'length_annotated_rows':len(current),'stratum':stratum(len(current))})
        run_id=len(runs)-1
        for v in current:
            reference[v]=run_id
    if sum(run['length_annotated_rows'] for run in runs)!=len(reference):
        raise ValueError('Annotation runs are not disjoint.')
    return runs,reference


def stratum(length:int) -> str:
    if length<=0:raise ValueError('Empty positive run.')
    if length<=5:return '1-5'
    if length<=25:return '6-25'
    return '26+'


def open_labels(path:Path) -> dict[int,dict]:
    if sha_file(path)!=SOURCE_SHA:
        raise ValueError('Official corrected annotation ZIP SHA-256 changed.')
    result={}
    with zipfile.ZipFile(path) as z:
        # The full outer ZIP SHA-256 is already checked. Do NOT call testzip():
        # that traverses every member, including reserved 11–20 and 61–80.
        # z.read() validates CRC only for the explicitly permitted CSV members.
        for exam in EXAMS:  # NEVER read heldout 11–20 or 61–80.
            blob=z.read(f'{exam}.csv')
            if len(blob)>20*1024*1024:
                raise ValueError('Unbounded annotation CSV.')
            reader=csv.DictReader(io.StringIO(blob.decode('utf-8-sig'),newline=''))
            if len(reader.fieldnames or ())!=len(set(reader.fieldnames or ())) or not {'frame','blood'}<=set(reader.fieldnames or ()):
                raise ValueError('Unexpected corrected annotation schema.')
            rows=[]
            for row in reader:
                if None in row or not row['frame'].isdigit() or row['blood'] not in ('0','1',''):
                    raise ValueError('Malformed original corrected annotation.')
                rows.append({'frame':int(row['frame']),'blood':row['blood']})
            if len(rows)<512:
                raise ValueError('Fewer source annotations than the reference cohort.')
            diffs=Counter(rows[i]['frame']-rows[i-1]['frame'] for i in range(1,len(rows)))
            if diffs[5]/(len(rows)-1)<0.95 or max(diffs,key=diffs.get)!=5:
                raise ValueError('Source-frame stride not supported by the locked protocol.')
            runs,mapping=positive_runs(rows)
            result[exam]={'source_rows':len(rows), 'source_positive_rows':len(mapping),
                          'labels':{r['frame']:r['blood'] for r in rows},
                          'runs':runs,'frame_to_run':mapping,
                          'source_csv_sha256':sha(blob)}
    return result


def normalize_row(raw:dict,kind:str,allowed_exams:tuple[int,...]) -> dict:
    if kind=='pilot':
        exam_str,frame_str,label_str,role='exam','frame','blood_label',None
        score_keys={'original_checkpoint':'cnn_score','red_excess':'red_excess_score'}
        img_key='source_sha256'
    elif kind=='new':
        exam_str,frame_str,label_str,role='exam','frame','blood','reference_uniform'
        score_keys={'original_checkpoint':'cnn_score','red_excess':'red_excess_score'}
        img_key='source_image_sha256'
    elif kind=='exam25':
        exam_str,frame_str,label_str,role='examination','source_frame','blood_label','reference_uniform'
        score_keys={x:x for x in MODEL_NAMES}
        img_key='original_image_sha256'
    else:
        exam_str,frame_str,label_str,role='exam','frame','blood','reference_uniform'
        score_keys={x:x for x in MODEL_NAMES}
        img_key='source_image_sha256'
    if not raw[exam_str].isdigit() or int(raw[exam_str]) not in allowed_exams or not raw[frame_str].isdigit():
        raise ValueError('Unapproved/reserved examination or malformed source frame identity.')
    exam=int(raw[exam_str]);frame=int(raw[frame_str]);label=parse_binary(raw[label_str]);
    is_reference=1 if role is None else parse_binary(raw[role])
    raw_image_sha=raw[img_key]
    if len(raw_image_sha)!=64 or any(d not in '0123456789abcdef' for d in raw_image_sha):
        raise ValueError('Missing or altered verified source image SHA-256.')
    scores={}
    for name,col in score_keys.items():
        v=float(raw[col])
        if not math.isfinite(v) or not 0<=v<=1:
            raise ValueError('Invalid saved uncalibrated model ranking score.')
        scores[name]=v
    return {'exam':exam,'frame':frame,'blood':label,'reference_uniform':is_reference,
            'source_image_sha256':raw_image_sha,'scores':scores}


def open_scores(inputs:dict[str,Path],source:dict[int,dict]) -> dict[int,list[dict]]:
    all_rows={e:[] for e in EXAMS}
    for name,(csv_name,expected_n,expected_sha,allowed_exams) in EXPECTED_CSV.items():
        p=inputs[name]
        with zipfile.ZipFile(p) as z:
            if z.testzip() is not None:
                raise ValueError('Previously verified private prediction ZIP CRC error.')
            info=z.getinfo(csv_name)
            if info.file_size>2*1024*1024:
                raise ValueError('Unexpectedly large private per-image predictions.')
            blob=z.read(info)
        if sha(blob)!=expected_sha:
            raise ValueError('Private original image ranking source identity SHA mismatch.')
        reader=csv.DictReader(io.StringIO(blob.decode('utf-8-sig'),newline=''))
        rows=list(reader)
        if len(rows)!=expected_n or len(reader.fieldnames or ())!=len(set(reader.fieldnames or ())):
            raise ValueError('Saved source-score CSV schema/size changed.')
        seen=set()
        for raw in rows:
            if None in raw:raise ValueError('Malformed private prediction record.')
            row=normalize_row(raw,name,allowed_exams)
            key=(row['exam'],row['frame'])
            if key in seen:
                raise ValueError('Repeated original source frame within saved score archive.')
            seen.add(key)
            correct=source[row['exam']]['labels'].get(row['frame'])
            if correct is None or correct=='' or correct!=str(row['blood']):
                raise ValueError('Original corrected blood label does not match saved image prediction.')
            all_rows[row['exam']].append(row)
    for exam,rows in all_rows.items():
        rows.sort(key=lambda r:r['frame'])
        if sum(r['reference_uniform'] for r in rows)!=512:
            raise ValueError('Exactly 512 previously uniform-selected reference frames required.')
        if sum(r['blood']*r['reference_uniform'] for r in rows)!=EXPECTED_REFERENCE_POSITIVE[exam]:
            raise ValueError('Saved reference blood support changed.')
        for r in rows:
            if r['blood'] and r['frame'] not in source[exam]['frame_to_run']:
                raise ValueError('Saved blood-positive image outside original corrected run inventory.')
    return {exam:[r for r in rows if r['reference_uniform']] for exam,rows in all_rows.items()}


def analyze(exam:int,refs:list[dict],full:dict) -> dict:
    if len(refs)!=512:
        raise ValueError('Reference sample changed.')
    frame_to_run=full['frame_to_run'];runs=full['runs'];total=len(runs)
    available={frame_to_run[r['frame']] for r in refs if r['blood']}
    assert len(available)<=total
    counts=Counter(x['stratum'] for x in runs)
    ceiling_by_size=Counter(runs[j]['stratum'] for j in available)
    methods=[m for m in MODEL_NAMES if all(m in r['scores'] for r in refs)]
    if 'original_checkpoint' not in methods or 'red_excess' not in methods:
        raise ValueError('Original CNN and redness comparator must be present on every examination.')
    source_output={
        'source_annotated_rows':full['source_rows'],
        'source_blood_positive_annotated_rows':full['source_positive_rows'],
        'source_blood_annotation_runs':total,
        'source_run_length_categories':{k:counts[k] for k in STRATA},
        'reference_count':512,
        'reference_blood_positive':sum(r['blood'] for r in refs),
        'reference_run_ceiling_hits':len(available),
        'reference_run_ceiling_recall':(len(available)/total if total else None),
        'reference_ceiling_by_length':{k:ceiling_by_size[k] for k in STRATA},
        'budgets':{},
    }
    if exam==9:
        scores=[r['scores']['original_checkpoint'] for r in refs]
        source_output['negative_source_examination_fixed_score_thresholds']={
            f'{p:.1f}':{'selected_scored_images':sum(v>=p for v in scores),
                       'blood_annotation_negative_selected':sum(v>=p for v in scores)}
            for p in THRESHOLDS
        }
        source_output['negative_source_examination_score_summary']={
            'median':statistics.median(scores),
            'max':max(scores),
            'mean':statistics.fmean(scores)
        }
    for pct in BUDGETS:
        k=512*pct//100
        if k<1:raise ValueError('Zero sampling budget.')
        candidates={name:sorted(range(512),key=lambda i:(-refs[i]['scores'][name],i))[:k] for name in methods}
        candidates['uniform']=[(2*i+1)*512//(2*k) for i in range(k)]
        stats={}
        for name,idxs in candidates.items():
            if len(idxs)!=k or len(set(idxs))!=k:
                raise ValueError('Sampling budget or uniqueness changed.')
            selected=[refs[i] for i in idxs]
            hits={frame_to_run[x['frame']] for x in selected if x['blood']}
            strat=Counter(runs[j]['stratum'] for j in hits)
            p_hits=sum(r['blood'] for r in selected)
            stats[name]={
                'blood_positive_reference_images_found':p_hits,
                'blood_annotation_negative_images_selected':k-p_hits,
                'source_annotation_runs_hit':len(hits),
                'source_annotation_run_recall':len(hits)/total if total else None,
                'fraction_of_reference_accessible_runs_hit':len(hits)/len(available) if available else None,
                'by_run_length_category':{s:strat[s] for s in STRATA}
            }
        source_output['budgets'][str(pct)]={'selected_reference_images':k,'methods':stats}
    # All reference images are selected at 100%; an identical ceiling across methods is mandatory.
    if any(row['source_annotation_runs_hit']!=len(available) for row in source_output['budgets']['100']['methods'].values()):
        raise ValueError('Methods disagree on 100% available source runs.')
    return source_output


def run(labels_zip:Path,inputs:dict[str,Path],destination:Path)->dict:
    if destination.exists():
        raise FileExistsError('Refuse to overwrite previously frozen results.')
    source=open_labels(labels_zip)
    scores=open_scores(inputs,source)
    result={
        'study':'Galar original annotation-run coverage for sparse, previously scored reference images',
        'status':'post-hoc exploratory reference sampling and image-ranking audit; NOT lesion sensitivity',
        'source_corrected_release_sha256':SOURCE_SHA,
        'score_sources_csv_sha256':{k:v[2] for k,v in EXPECTED_CSV.items()},
        'exam_roles':{'historical_development':[9,10], 'previously_inspected_fitting_candidates':[21,23,25,27,29,30],
                      'future_unopened_evaluation':'11–20', 'authors_unopened_holdout':'61–80'},
        'reference_per_exam':512,
        'review_budgets_percent':list(BUDGETS),
        'run_definition':'consecutive original corrected source rows with blood=1 and source frame stride exactly 5, split on nonpositive/unknown rows or frame gap; NOT individual lesions',
        'run_length_categories':list(STRATA),
        'examinations':{str(e):analyze(e,scores[e],source[e]) for e in EXAMS},
        'limitations':[
            'This is a post-hoc audit of previously examined cases and scores, never a blinded clinical validation.',
            'Run coverage is annotation-run intersection at original corrected sampled annotation positions, NOT lesion or video-event sensitivity.',
            'All methods are restricted to 512 previously selected reference images per exam: even 100% here is not a whole-video review.',
            'Study IDs do not establish patient independence. Several exams have very few positive images.',
            'Previously inspected Galar 9–10 were used in original CNN checkpoint selection and are not independent testing.',
            'Uncalibrated score thresholds are illustrations, not clinical decision thresholds; blood=0 does not prove clinical normality.',
            'No new source pixel data, model fitting, checkpoint selection or use of reserved evaluation examinations occurred.'
        ],
        'medical_images_or_frame_scores_committed':False,
        'clinical_validation':False
    }
    # Descriptive totals across the already examined studies. These are pooled
    # image/annotation counts, NOT independent lesion or patient outcomes.
    all_exam=list(result['examinations'].values())
    total_runs=sum(x['source_blood_annotation_runs'] for x in all_exam)
    accessible=sum(x['reference_run_ceiling_hits'] for x in all_exam)
    total_by_stratum={k:sum(x['source_run_length_categories'][k] for x in all_exam) for k in STRATA}
    accessible_by_stratum={k:sum(x['reference_ceiling_by_length'][k] for x in all_exam) for k in STRATA}
    if total_runs < accessible or sum(total_by_stratum.values())!=total_runs or sum(accessible_by_stratum.values())!=accessible:
        raise ValueError('Cross-examination original source run aggregation inconsistent.')
    aggregated_budgets={}
    for pct in BUDGETS:
        aggregated_budgets[str(pct)]={}
        for method in ('original_checkpoint','red_excess','uniform'):
            records=[x['budgets'][str(pct)]['methods'][method] for x in all_exam]
            aggregated_budgets[str(pct)][method]={
                'source_annotated_runs_hit':sum(x['source_annotation_runs_hit'] for x in records),
                'blood_positive_reference_images_found':sum(x['blood_positive_reference_images_found'] for x in records),
                'blood_annotation_negative_images_selected':sum(x['blood_annotation_negative_images_selected'] for x in records),
            }
    result['cross_examination_descriptive_totals']={
        'examination_count':len(all_exam),
        'source_positive_run_count':total_runs,
        'reachable_by_all_reference_images':accessible,
        'reachable_fraction_of_full_source_annotation_runs':accessible/total_runs if total_runs else None,
        'source_run_counts_by_length':total_by_stratum,
        'reference_reachable_run_counts_by_length':accessible_by_stratum,
        'budgets':aggregated_budgets,
        'interpretation':'Descriptive sums across preselected studies. NOT distinct lesions, study-independent estimates or full-video sensitivity.',
    }
    destination.mkdir(parents=True)
    (destination/'aggregate.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf8')
    return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('labels-zip','pilot','new','exam25','exam27','exam29','output-dir'):
        p.add_argument('--'+arg,type=Path,required=True)
    args=p.parse_args()
    paths={k:getattr(args,k) for k in EXPECTED_CSV}
    result=run(args.labels_zip,paths,args.output_dir)
    print(json.dumps({'source_studies':len(result['examinations']),
                      'total_source_runs':sum(x['source_blood_annotation_runs'] for x in result['examinations'].values()),
                      'full_reference_ceiling_runs':sum(x['reference_run_ceiling_hits'] for x in result['examinations'].values()),
                      'exam9_illustrative_thresholds':result['examinations']['9']['negative_source_examination_fixed_score_thresholds']},indent=2))


if __name__=='__main__':
    main()
