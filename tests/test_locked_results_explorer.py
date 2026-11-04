"""Public-aggregate-only research explorer: no source images, outcomes or weights."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "src" / "capsule_review" / "static" / "locked-results.html"
AGGREGATE = ROOT / "experiments" / "galar-unseen-11-20-20261104" / "aggregate.json"
INDEX = ROOT / "src" / "capsule_review" / "static" / "index.html"
POLICIES = ("uniform", "score", "score_diverse", "score_bin")
WORKLOADS = ("5", "10", "25", "50", "100")


def _projection():
    content = HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="locked-results-data" type="application/json">([^<]*)</script>',
        content,
    )
    assert match, "Results must be self-contained and available without network access."
    return json.loads(match.group(1))


def test_explorer_uses_only_existing_locked_aggregate():
    view = _projection()
    source = json.loads(AGGREGATE.read_text(encoding="utf-8"))
    assert view["source"] == "experiments/galar-unseen-11-20-20261104/aggregate.json"
    assert view["merge_commit"] == "6c22b5c2030f1a41dc63948b9b996da18f4e8407"
    assert view["total_images"] == source["source_images"] == 163161
    assert view["annotated_runs"] == 154
    assert view["positive_images"] == 1742
    assert view["defined_examinations"] == source["defined_primary_examinations"] == 6
    assert set(view["budgets"]) == set(WORKLOADS)
    for percent in WORKLOADS:
        display = view["budgets"][percent]
        original = source["budget_summary"][percent]
        assert display["reviewed"] == original["selected_images_all_examinations"]
        assert set(display["policies"]) == set(POLICIES)
        for policy in POLICIES:
            got, expected = display["policies"][policy], original["policies"][policy]
            assert got == {
                "macro": expected["mean_defined_examination_run_recall"],
                "runs": expected["pooled_annotation_runs_hit"],
                "images": expected["positive_annotated_images_hit"],
                "gap": expected["maximum_largest_unselected_imported_span"],
            }


def test_every_examination_and_all_200_fixed_policy_results_reconcile():
    view = _projection()
    source = json.loads(AGGREGATE.read_text(encoding="utf-8"))
    assert [e["id"] for e in view["exams"]] == list(range(11, 21))
    comparisons = 0
    for e in view["exams"]:
        original = source["per_examination"][str(e["id"])]
        assert e["eligible"] == original["imported_annotated_images"]
        assert e["positive_images"] == original["positive_annotated_images"]
        assert e["runs"] == original["positive_annotation_runs"]
        original_budgets = {str(b["review_percent"]): b for b in original["review_results"]}
        assert set(map(str, e["budgets"])) == set(WORKLOADS)
        for percent in WORKLOADS:
            x, y = e["budgets"][percent], original_budgets[percent]
            assert x["k"] == y["review_images"]
            for policy in POLICIES:
                assert x["policies"][policy] == {
                    "recall": y["policies"][policy]["annotation_run_recall"],
                    "runs": y["policies"][policy]["distinct_positive_annotation_runs_hit"],
                    "images": y["policies"][policy]["positive_annotated_images_hit"],
                    "gap": y["policies"][policy]["largest_unselected_imported_span"],
                }
                if e["runs"] == 0:
                    assert x["policies"][policy]["recall"] is None
                comparisons += 1
    assert comparisons == 200


def test_primary_failure_preserved_and_secondary_labeled():
    view = _projection()
    ten = view["budgets"]["10"]["policies"]
    twenty_five = view["budgets"]["25"]["policies"]
    assert abs((ten["score_bin"]["macro"] - ten["uniform"]["macro"]) * 100
               - (-1.2668765)) < 1e-6
    assert abs((twenty_five["score_bin"]["macro"] - twenty_five["uniform"]["macro"]) * 100
               - 9.5106442) < 1e-6
    assert (ten["score"]["images"], ten["score"]["runs"]) == (305, 28)
    assert (ten["uniform"]["images"], ten["uniform"]["runs"]) == (170, 63)
    html = HTML.read_text(encoding="utf-8")
    assert "10% · primary" in html and "25% · secondary" in html
    assert "not clinical validation" in html.lower()
    assert "undefined" in html.lower()
    assert "not proven unique clinical lesions" in html.lower()
    assert "data:" not in html.lower().split("<script id=", 1)[0]


def test_local_app_links_to_self_contained_aggregate_explorer(client):
    index = INDEX.read_text(encoding="utf-8")
    assert 'href="/static/locked-results.html"' in index
    response = client.get("/static/locked-results.html")
    assert response.status_code == 200
    assert "application/json" in response.text
    assert '<script id="locked-results-data"' in response.text
    assert "<img " not in response.text
    assert '<script src=' not in response.text
