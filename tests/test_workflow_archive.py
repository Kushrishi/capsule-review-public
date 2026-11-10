"""Ensure retirement of one-off research Actions preserves the exact original Git blobs.

No medical sources or private artifacts are loaded; these YAML files are
historical execution recipes, not automatic scientific reproduction.
"""
from __future__ import annotations

from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = frozenset({"tests.yml", "public-source-privacy.yml",
                    "galar-frozen-mobilenet.yml", "galar-negative-expansion-cv.yml"})
ORIGINAL_ARCHIVE_BLOBS = {
    "galar-21-29-index.yml": "9ca3b6648153a8f55251ceebf8ab478fa88e335a",
    "galar-31-40-index-only.yml": "762f71dc6150eb9cf0d1652a90ff80e7204c021f",
    "galar-block0-acquisition.yml": "fd26783f78e215f8eee7a94121bc816132af814b",
    "galar-block1-exam23.yml": "68359d21229aa82b72299f1b30279de0918fc0db",
    "galar-density-ceiling.yml": "2071570cb2657f62e3babca5f86df13b214dde59",
    "galar-exam29-acquisition.yml": "4386b4ffbac33bfb3a9255c04355cb42bd381723",
    "galar-multiblock-exam30.yml": "cc0260fb3b0e54d82166f840163ac1637e857ab4",
    "galar-negative-22-24.yml": "632e564f6ea2eed0b14d65f0ef913fa82f4d9fea",
    "galar23-pixel-density.yml": "03e47000f46e3d96191c4e6b1b7c8bd8193fc468",
    "galar25-streamed-acquisition.yml": "98823a86977f7c57e46221461f51491aa059078a",
    "galar27-streamed-acquisition.yml": "b8293e8b164c2c2a066756fba7fa48e5916a9630",
    "pretrained-weights.yml": "c544fd825c858bcc56bff18fedaba1c0b948e825",
    "red-lesion-gate.yml": "1dc7bcc488e06847698eac5b7da58206c0b00fdb",
    "rhode-replication.yml": "30cd2575ff0a4d9f2430a0d0d2694f1dbb8a27a4",
}


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def test_only_active_ci_and_targeted_pr_checks_remain_in_actions_directory():
    live = ROOT / ".github" / "workflows"
    assert {x.name for x in live.glob("*.yml")} == ACTIVE
    assert not list(live.glob("*.yaml"))


def test_archived_workflows_are_byte_identical_to_the_original_git_blobs():
    archive = ROOT / "archive" / "research-workflows"
    assert {x.name for x in archive.glob("*.yml")} == set(ORIGINAL_ARCHIVE_BLOBS)
    for name, sha in ORIGINAL_ARCHIVE_BLOBS.items():
        p = archive / name
        assert p.is_file() and _git_blob_sha(p.read_bytes()) == sha, name


def test_historical_acquisition_document_links_to_preserved_workflow():
    doc = (ROOT / "docs" / "GALAR_21_30_ACQUISITION.md").read_text(encoding="utf-8")
    assert "../archive/research-workflows/galar-block0-acquisition.yml" in doc
    assert "../.github/workflows/galar-block0-acquisition.yml" not in doc
