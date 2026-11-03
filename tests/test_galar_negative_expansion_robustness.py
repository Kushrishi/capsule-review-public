"""Synthetic integrity/edge-case tests plus locked public aggregate replay.

No original medical images, source annotations, patient identifiers or weights.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.analyze_galar_negative_expansion_robustness import (
    DEFAULT_INPUT, HIGH_SUPPORT, _percentile, analyze,
)


def public_pair():
    return json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))


def test_public_exam_bootstrap_exhaustive_and_reproduced():
    result = analyze(public_pair())
    assert result["high_support_examinations"] == list(HIGH_SUPPORT)
    assert result["examinations_improved"] == 5
    assert result["mean_auc_difference"] == pytest.approx(0.02121296538756401)
    assert result["bootstrap_descriptive"]["enumerated_draws"] == 6 ** 6
    assert result["bootstrap_descriptive"]["lower_2_5_percent"] == pytest.approx(-0.002686368335843551)
    assert result["bootstrap_descriptive"]["upper_97_5_percent"] == pytest.approx(0.044152529170588546)
    assert result["top_51_all_14_exams"] == {
        "old_positive_labelled_images": 151,
        "expanded_positive_labelled_images": 153,
        "difference": 2,
    }
    assert result["unresolved_hard_examinations"] == {
        "23": {"old_top_51_positive_images": 0, "expanded_top_51_positive_images": 0},
        "25": {"old_top_51_positive_images": 0, "expanded_top_51_positive_images": 0},
    }
    assert result["clinical_validity"] is False
    assert result["model_promotion_authorized"] is False
    assert all(v > 0 for v in result["leave_one_examination_out_mean_auc_difference"].values())


def test_percentile_interpolation_not_nearest_rank():
    assert _percentile([0, 1, 2, 3], 0.25) == pytest.approx(0.75)
    assert _percentile([0, 1, 2, 3], 0.975) == pytest.approx(2.925)


@pytest.mark.parametrize("change", [
    lambda d: d["per_exam"].update({"22": deepcopy(d["per_exam"]["23"])}),
    lambda d: d["heldout_examinations_exactly_the_original_14"].append(22),
    lambda d: d.update({"model_promotion_authorized": True}),
    lambda d: d.update({"no_reserved_exams_accessed": False}),
    lambda d: d["per_exam"]["25"].update({"auc_difference": 0.2}),
    lambda d: d["per_exam"]["7"].update({"blood_positive_reference_images": 9}),
    lambda d: d["per_exam"]["3"].update({"baseline_roc_auc": 0.5}),
    lambda d: d["per_exam"]["29"]["expanded_topk_positive"].update({"51": 80}),
    lambda d: d["all_14_exam_positive_image_hits_by_k"]["51"].update({"new": 900}),
    lambda d: d["macro_roc_auc_high_support_6"].update({"delta": 0.5}),
])
def test_refuse_changed_heldouts_invalid_metadata_or_metric_inconsistency(change):
    data = public_pair()
    change(data)
    with pytest.raises(ValueError):
        analyze(data)


def test_public_cli_writes_aggregate_only_and_never_overwrites(tmp_path):
    path = tmp_path / "replay.json"
    command = [sys.executable, str(Path(__file__).resolve().parents[1] /
                "scripts/analyze_galar_negative_expansion_robustness.py"),
               "--output", str(path)]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.returncode == 0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["no_private_source_rows_or_model_records_read"] is True
    assert data["bootstrap_descriptive"]["enumerated_draws"] == 46656
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0
    assert path.exists()
