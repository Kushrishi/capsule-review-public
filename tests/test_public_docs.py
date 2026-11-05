"""Regression checks for the public research handoff and local documentation links.

These tests use public source text only: never load private medical-image data.
"""
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "GALAR_UNSEEN_EVALUATION_PLAN.md",
    ROOT / "docs" / "GALAR_NEGATIVE_22_24_RESULTS.md",
    ROOT / "docs" / "GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md",
    ROOT / "docs" / "PUBLIC_RELEASE_SAFETY.md",
    ROOT / "docs" / "PROJECT_MATURITY_AUDIT_20261104.md",
    ROOT / "docs" / "SUPERVISOR_DEMO.md",
    ROOT / "docs" / "RESEARCH_COLLABORATION_BRIEF.md",
    ROOT / "docs" / "EXPERIMENTAL_GAP_GUARDED_SELECTION.md",
    ROOT / "docs" / "ORIGINAL_BLOOD_PHOTOMETRIC_ROBUSTNESS_20261104.md",
    ROOT / "docs" / "GALAR_EXAM_EXCLUDED_ADAPTATION_RESULTS.md",
    ROOT / "docs" / "MATCHED_PRETRAINED_PROBE_LOCK_20261104.md",
    ROOT / "docs" / "GALAR_MATCHED_PRETRAINED_PROBE_20261104.md",
    ROOT / "docs" / "PROJECT_STATUS.md",
    ROOT / "docs" / "ROADMAP.md",
)


def test_critical_public_document_links_resolve():
    for document in DOCS:
        assert document.is_file(), f"Missing public document: {document.relative_to(ROOT)}"
        body = document.read_text(encoding="utf-8")
        for raw in re.findall(r"\]\(([^)]+)\)", body):
            target = unquote(raw.split("#", 1)[0].split(" ?", 1)[0].strip())
            if not target or re.match(r"^(https?://|mailto:|data:|#)", target, re.I):
                continue
            resolved = (document.parent / target).resolve()
            assert resolved.is_relative_to(ROOT.resolve()), (
                f"Unexpected external local path in {document.relative_to(ROOT)}: {raw}"
            )
            assert resolved.is_file(), (
                f"Broken public link in {document.relative_to(ROOT)}: {target}"
            )


def test_current_science_is_linked_not_manually_copied_into_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    status = (ROOT / "docs" / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    provenance = (ROOT / "docs" / "GALAR_NEGATIVE_22_24_RESULTS.md").read_text(encoding="utf-8")
    results = (ROOT / "docs" / "GALAR_NEGATIVE_EXPANSION_CV_RESULTS.md").read_text(encoding="utf-8")
    for record in (provenance, results):
        assert "11,147" in record and "512" in record
    assert "11,147" in roadmap
    assert "16-examination" in roadmap
    assert "docs/PROJECT_STATUS.md" in readme
    assert "docs/ROADMAP.md" in readme
    assert "No clinical model was promoted." in readme
    assert "10% primary" in status and "−1.2668765" in status
    assert "blood=0" in provenance
    assert "61–80" in readme


def test_public_research_docs_do_not_claim_model_promotion():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    provenance = (ROOT / "docs" / "GALAR_NEGATIVE_22_24_RESULTS.md").read_text(encoding="utf-8")
    assert "not a clinical decision-support device" in readme
    assert "not a model or clinical validation" in provenance
    assert (ROOT / "docs" / "PUBLIC_RELEASE_SAFETY.md").exists()


def test_public_entrypoints_stay_concise_without_escaped_newlines():
    """Keep the landing page readable; put experiment chronology in research reports."""
    for filename, max_words in (("README.md", 800), ("AGENTS.md", 800)):
        content = (ROOT / filename).read_text(encoding="utf-8")
        assert len(content.split()) <= max_words, f"{filename} is becoming a running lab notebook"
        assert "\\n\\n" not in content, f"{filename} contains literal escaped line breaks"


def test_interval_export_copy_distinguishes_boundary_and_full_span_exports():
    html = (ROOT / "src" / "capsule_review" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Export review keeps interval endpoints and saved frames." in html
    assert "Export full spans includes every imported image within marked intervals" in html
    assert "not unimported video frames" in html
    assert "never unseen interior images" not in html
