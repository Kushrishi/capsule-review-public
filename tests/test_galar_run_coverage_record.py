"""Check the saved nonidentifying real Galar run-coverage result algebraically.

No private source frames, labels or per-image predictions are loaded in CI.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'experiments/galar-run-coverage-2026-11-02/aggregate.json'
SPEC = ROOT / 'docs/GALAR_RUN_COVERAGE_AUDIT_SPEC.json'
EXPECTED_AGGREGATE_SHA = '8065f166f2f807b0703d4ef6c28a71d4c452d445db85d8fdd7a4c5313860eb07'
EXP_POSITIVE_SUPPORT = {9:0,10:213,21:1,23:4,25:14,27:26,29:122,30:120}
EXP_ORIGINAL_SOURCE_RUNS = {9:0,10:41,21:3,23:28,25:53,27:4,29:107,30:47}
EXP_SAMPLE_CEILINGS = {9:0,10:31,21:1,23:4,25:3,27:4,29:47,30:20}
BUDGETS=(5,10,25,50,75,100)
STRATA=('1-5','6-25','26+')


def load():
    blob=REPORT.read_bytes()
    assert hashlib.sha256(blob).hexdigest()==EXPECTED_AGGREGATE_SHA
    return json.loads(blob)


def test_protocol_source_roles_immutable_and_holdouts_absent():
    frozen=json.loads(SPEC.read_text())
    result=load()
    assert frozen['version']=='1.0'
    assert frozen['data_source']['sha256']==result['source_corrected_release_sha256']
    assert frozen['data_source']['examinations']==[9,10,21,23,25,27,29,30]
    assert result['review_budgets_percent']==list(BUDGETS)
    assert set(result['examinations'])=={str(x) for x in EXP_POSITIVE_SUPPORT}
    assert result['clinical_validation'] is False
    assert result['medical_images_or_frame_scores_committed'] is False
    assert result['exam_roles']['future_unopened_evaluation']=='11–20'
    assert result['exam_roles']['authors_unopened_holdout']=='61–80'
    assert result['score_sources_csv_sha256']=={
        'pilot':frozen['data_source']['reference_image_score_sources'][0]['saved_csv_sha256'],
        'new':frozen['data_source']['reference_image_score_sources'][1]['saved_csv_sha256'],
        'exam29':frozen['data_source']['reference_image_score_sources'][2]['saved_csv_sha256'],
        'exam25':frozen['data_source']['reference_image_score_sources'][3]['saved_csv_sha256'],
        'exam27':frozen['data_source']['reference_image_score_sources'][4]['saved_csv_sha256'],
    }


def test_per_examination_sample_ceiling_original_annotated_runs_and_100_percent():
    result=load()
    for exam,pos in EXP_POSITIVE_SUPPORT.items():
        d=result['examinations'][str(exam)]
        assert d['reference_count']==512
        assert d['reference_blood_positive']==pos
        assert d['source_blood_annotation_runs']==EXP_ORIGINAL_SOURCE_RUNS[exam]
        assert d['reference_run_ceiling_hits']==EXP_SAMPLE_CEILINGS[exam]
        assert sum(d['source_run_length_categories'].values())==d['source_blood_annotation_runs']
        assert sum(d['reference_ceiling_by_length'].values())==d['reference_run_ceiling_hits']
        if d['source_blood_annotation_runs']:
            assert d['reference_run_ceiling_recall']==d['reference_run_ceiling_hits']/d['source_blood_annotation_runs']
        else:
            assert d['reference_run_ceiling_recall'] is None
        assert set(d['budgets'])=={str(x) for x in BUDGETS}
        for pct in BUDGETS:
            k=512*pct//100
            budget=d['budgets'][str(pct)]
            assert budget['selected_reference_images']==k
            methods=budget['methods']
            assert {'original_checkpoint','red_excess','uniform'} <= set(methods)
            if exam in (25,27,29):
                assert set(methods)=={'original_checkpoint','red_excess','uniform','original_only_continued','expanded_continued'}
            else:
                assert set(methods)=={'original_checkpoint','red_excess','uniform'}
            for m in methods.values():
                assert (m['blood_positive_reference_images_found'] +
                        m['blood_annotation_negative_images_selected'])==k
                assert m['blood_positive_reference_images_found']<=pos
                assert m['source_annotation_runs_hit']<=d['reference_run_ceiling_hits']
                assert sum(m['by_run_length_category'].values())==m['source_annotation_runs_hit']
                if d['source_blood_annotation_runs']==0:
                    assert m['source_annotation_run_recall'] is None
                else:
                    assert m['source_annotation_run_recall']==m['source_annotation_runs_hit']/d['source_blood_annotation_runs']
                if pct==100:
                    assert m['source_annotation_runs_hit']==d['reference_run_ceiling_hits']
                    assert m['blood_positive_reference_images_found']==pos


def test_fundamental_frame_hits_vs_run_coverage_counterexample():
    d=load()['examinations']['10']
    method=d['budgets']['10']['methods']
    assert method['original_checkpoint']['blood_positive_reference_images_found']==47
    assert method['uniform']['blood_positive_reference_images_found']==21
    assert method['original_checkpoint']['source_annotation_runs_hit']==3
    assert method['uniform']['source_annotation_runs_hit']==10
    assert d['source_blood_annotation_runs']==41
    assert d['reference_run_ceiling_hits']==31


def test_total_sparse_source_ceiling_and_short_run_prevalence():
    x=load()['cross_examination_descriptive_totals']
    assert x['examination_count']==8
    assert x['source_positive_run_count']==283
    assert x['reachable_by_all_reference_images']==110
    assert x['reachable_fraction_of_full_source_annotation_runs']==110/283
    assert x['source_run_counts_by_length']=={'1-5':124,'6-25':85,'26+':74}
    assert x['reference_reachable_run_counts_by_length']=={'1-5':13,'6-25':25,'26+':72}
    assert x['budgets']['10']['original_checkpoint']=={
        'blood_annotation_negative_images_selected':8*51-142,
        'blood_positive_reference_images_found':142,
        'source_annotated_runs_hit':28}
    assert x['budgets']['10']['uniform']=={
        'blood_annotation_negative_images_selected':8*51-48,
        'blood_positive_reference_images_found':48,
        'source_annotated_runs_hit':31}


def test_source_blood_negative_exam_counts_and_undefined_recall():
    x=load()['examinations']['9']
    assert x['source_blood_positive_annotated_rows']==0
    assert x['source_blood_annotation_runs']==0
    assert x['reference_run_ceiling_recall'] is None
    assert x['negative_source_examination_fixed_score_thresholds']['0.1']['selected_scored_images']==149
    assert x['negative_source_examination_fixed_score_thresholds']['0.5']['selected_scored_images']==1
    assert x['negative_source_examination_fixed_score_thresholds']['0.9']['selected_scored_images']==0
    assert x['budgets']['10']['methods']['original_checkpoint']['blood_annotation_negative_images_selected']==51


def test_public_results_contain_no_individual_source_frame_identity_or_saved_score():
    data=load()
    forbidden={'frame','filename','source_frame','source_image_sha256','private_path',
               'pixel_sha256','cnn_score','blood_label','source_sha256','records'}
    def check(x):
        if isinstance(x,dict):
            assert not (forbidden & set(x))
            for v in x.values():check(v)
        elif isinstance(x,list):
            for v in x:check(v)
    check(data)
    assert not any(p.suffix.lower() in {'.png','.jpg','.jpeg','.zip','.7z','.pt','.csv'}
                   for p in REPORT.parent.rglob('*') if p.is_file())


def test_separate_original_source_replay_receipt_is_consistent():
    receipt=json.loads((REPORT.parent/'verification.json').read_text())
    assert receipt['verification']=='independent real-data run segmentation and all-budget replay passed'
    assert receipt['examinations_checked']==8
    assert receipt['source_reference_images_checked']==4096
    assert receipt['method_budget_comparisons_recomputed']==8*6*3==144
    assert receipt['original_source_positive_runs_checked']==283
    assert receipt['unreachable_source_runs_under_complete_512_reference']==173
    assert receipt['source_original_sha256']==load()['source_corrected_release_sha256']
    assert receipt['source_aggregate_sha256']==EXPECTED_AGGREGATE_SHA
    assert receipt['reserved_exams_11_20_and_61_80_opened'] is False
    assert receipt['individual_source_frame_identity_exported'] is False
    assert receipt['clinical_validation'] is False
