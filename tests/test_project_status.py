"""Current science summary must derive from canonical, not manually edited claims."""
from __future__ import annotations
from copy import deepcopy
import pytest

from scripts.project_status import DEVELOPMENT, EXAM_BALANCED, LOCKED, load, summarize


def test_status_is_derived_from_frozen_public_aggregates():
    result = summarize(load(LOCKED), load(DEVELOPMENT))
    locked = result["locked_study"]
    assert locked["source_images"] == 163161
    assert locked["defined_positive_run_examinations"] == 6
    assert locked["primary_workload_percent"] == 10
    assert locked["primary_paired_difference_pp"] == pytest.approx(-1.2668765)
    assert locked["secondary_25_percent_difference_pp"] == pytest.approx(9.5106442)
    assert locked["primary_demonstrated_benefit"] is False
    development = result["latest_development"]
    assert development["original_cnn_positive_hits_at_51_total"] == 22
    assert development["pretrained_probe_positive_hits_at_51_total"] == 15
    assert development["model_promoted"] is False
    recent = result["latest_examination_balancing"]
    assert recent["examinations"] == 16
    assert recent["paired_primary_difference_pp"] == pytest.approx(-0.129877, abs=1e-6)
    assert recent["pooled_top51_positive_images"] == 151
    assert recent["tempered_top51_positive_images"] == 148
    assert recent["signal_threshold_met"] is False
    assert recent["model_promoted"] is False
    assert result["reserved_galar_61_80"] == "unopened"


@pytest.mark.parametrize("mutate", [
    lambda g, d: g.update(source_images=163160),
    lambda g, d: g.update(clinical_validation=True),
    lambda g, d: g.update(model_tuned_on_evaluation_outcomes=True),
    lambda g, d: g["budget_summary"]["10"]["policies"]["score_bin"].update(
        mean_defined_examination_run_recall=0.70),
    lambda g, d: d.update(model_promoted=True),
    lambda g, d: d.update(galar_reserved_61_80_opened=True),
    lambda g, d: d["aggregate"]["frozen_mobilenet_v3_linear_probe"][
        "total_positive_images_hit"].update({"51": 26}),
])
def test_unfavorable_science_cannot_be_silently_rewritten(mutate):
    g, d = deepcopy(load(LOCKED)), deepcopy(load(DEVELOPMENT))
    mutate(g, d)
    with pytest.raises(ValueError):
        summarize(g, d)


def test_latest_candidate_failure_cannot_be_hidden_from_status():
    g, d, b = load(LOCKED), load(DEVELOPMENT), load(EXAM_BALANCED)
    changed = deepcopy(b)
    changed["aggregate"]["tempered_examination_balanced"]["pooled_positive_reference_hits_at_k"]["51"] = 166
    with pytest.raises(ValueError):
        summarize(g, d, changed)
    changed = deepcopy(b)
    changed["data_boundary"]["model_promoted"] = True
    with pytest.raises(ValueError):
        summarize(g, d, changed)
