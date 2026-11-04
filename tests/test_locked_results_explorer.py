"""Public-aggregate-only research explorer: no source images, outcomes or weights."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "src" / "capsule_review" / "static" / "locked-results.html"
JS = ROOT / "src" / "capsule_review" / "static" / "locked-results.js"
CSS = ROOT / "src" / "capsule_review" / "static" / "locked-results.css"
AGGREGATE = ROOT / "experiments" / "galar-unseen-11-20-20261104" / "aggregate.json"
INDEX = ROOT / "src" / "capsule_review" / "static" / "index.html"
POLICIES = ("uniform", "score", "score_diverse", "score_bin")
WORKLOADS = ("5", "10", "25", "50", "100")


def _projection():
    script = JS.read_text(encoding="utf-8")
    match = re.search(r"(?m)^const d=(\\{[^\\n]*\\});$", script)
    assert match, "Aggregate projection must be bundled in an executable same-origin script."
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
    assert '<script src="/static/locked-results.js" defer></script>' in html
    assert '<link rel="stylesheet" href="/static/locked-results.css">' in html
    assert "<style>" not in html and "<script>" not in html and 'style="' not in html


def test_local_app_serves_csp_compatible_aggregate_explorer(client):
    index = INDEX.read_text(encoding="utf-8")
    assert 'href="/static/locked-results.html"' in index
    response = client.get("/static/locked-results.html")
    assert response.status_code == 200
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert '<script src="/static/locked-results.js" defer></script>' in response.text
    assert '<link rel="stylesheet" href="/static/locked-results.css">' in response.text
    assert '<script id="locked-results-data"' not in response.text
    assert "<img " not in response.text
    assert 'style="' not in response.text and "<style>" not in response.text
    for path in ("/static/locked-results.js", "/static/locked-results.css"):
        asset = client.get(path)
        assert asset.status_code == 200
        assert asset.content
