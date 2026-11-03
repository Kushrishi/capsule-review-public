"""Independent arithmetic/provenance checks for the frozen real s288 pilot."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = json.loads((ROOT / 'experiments/rhode-s288/sequence_selection_results.json').read_text())
SPEC = json.loads((ROOT / 'docs/SEQUENCE_SELECTION_SPEC.json').read_text())


def test_real_results_identity_and_scope():
    assert RESULT['study'] == 's288'
    assert RESULT['source_zip_sha256'] == '145dad913880a155c7ac5942742e1941cb85c9508dd835e8a444ee66a7b0828e'
    assert RESULT['role'] == 'exploratory / previously inspected'
    assert RESULT['image_count'] == 4189
    assert RESULT['source_indices_complete'] is True
    assert RESULT['anatomy_boundary_count'] == 3
    assert sum(RESULT['anatomy_counts'].values()) == 4189
    assert RESULT['capture_timestamps'] is None
    assert RESULT['pathology_labels'] is None
    assert RESULT['patient_independence_known'] is False
    assert RESULT['clinical_claims_supported'] is False


def test_budgets_and_transition_metrics_are_consistent():
    assert [x['budget'] for x in RESULT['budget_results']] == SPEC['budgets']
    for result in RESULT['budget_results']:
        k = math.ceil(result['budget'] * RESULT['image_count'])
        assert result['k'] == k
        assert set(result['methods']) == {'uniform','global_change','stratified_change','random_anchored'}
        for name in ['uniform','global_change','stratified_change']:
            metrics = result['methods'][name]
            assert metrics['selected_count'] == k
            assert metrics['boundary_count'] == 3
            assert len(metrics['boundary_distances']) == 3
            for tolerance in SPEC['boundary_tolerances_frames']:
                expected=sum(d<=tolerance for d in metrics['boundary_distances'])
                assert metrics['boundary_hits'][str(tolerance)] == expected
            assert metrics['max_nearest_position_distance'] <= metrics['max_selected_position_gap']
            assert metrics['regions_represented'] <= 4
        assert result['methods']['random_anchored']['draws'] == 100


def test_future_members_are_frozen_before_access():
    selected=SPEC['future_studies_selected_without_examining_images_or_labels']
    assert [x['study'] for x in selected] == ['s280','s284']
    assert [x['source_member_bytes'] for x in selected] == [103418092,115960292]
    assert sum(x['source_member_bytes'] for x in selected) < 512*1024*1024
