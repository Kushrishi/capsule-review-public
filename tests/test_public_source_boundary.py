"""Synthetic-only tests for accidental-publication source boundary checks."""
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.verify_public_source_boundary import (
    MAX_TRACKED_FILE_BYTES, PublicSourceBoundaryError,
    check_repository, check_tracked_file, git_tracked_paths,
)


def test_normal_public_source_allowed(tmp_path: Path):
    path = tmp_path / "src" / "model.py"
    path.parent.mkdir()
    path.write_text("print('synthetic example')\n", encoding="utf-8")
    assert check_tracked_file(tmp_path, "src/model.py") == []


@pytest.mark.parametrize("relative,reason", [
    ("images/source_1.json", "private research directory"),
    ("private/predictions.json", "private research directory"),
    ("weights/parameters.json", "private research directory"),
    ("experiments/medical_frames.zip", "blocked research"),
    ("synthetic/fake_source.PNG", "blocked research"),
    ("data/predictions.csv", "blocked research"),
    ("src/.env", "environment credential"),
    ("config/.env.production", "environment credential"),
    ("experiments/checkpoint.PTH", "blocked research"),
])
def test_sensitive_paths_rejected_without_reading_contents(tmp_path: Path, relative: str, reason: str):
    path = tmp_path.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic fixture")
    errors = check_tracked_file(tmp_path, relative)
    assert any(reason in error for error in errors)


@pytest.mark.parametrize("payload", [
    b"\x89PNG\r\n\x1a\n" + b"not an image",
    b"PK\x03\x04" + b"not a zip",
    b"SQLite format 3\x00" + b"not a database",
    b"plain text\x00embedded binary",
])
def test_renamed_binary_content_is_rejected(tmp_path: Path, payload: bytes):
    (tmp_path / "apparently-safe.json").write_bytes(payload)
    assert check_tracked_file(tmp_path, "apparently-safe.json")


def test_oversized_and_symlinked_files_fail_closed(tmp_path: Path):
    (tmp_path / "huge.json").write_bytes(b"a" * (MAX_TRACKED_FILE_BYTES + 1))
    assert any("oversized" in x for x in check_tracked_file(tmp_path, "huge.json"))
    (tmp_path / "link.md").symlink_to(tmp_path / "huge.json")
    assert any("symlink" in x for x in check_tracked_file(tmp_path, "link.md"))


def test_invalid_and_missing_paths_rejected(tmp_path: Path):
    assert check_tracked_file(tmp_path, "../secret") == ["invalid repository-relative path"]
    assert check_tracked_file(tmp_path, "missing.json") == [
        "tracked file absent or not a regular file"
    ]


@pytest.mark.skipif(shutil.which("git") is None, reason="Git executable unavailable")
def test_git_index_scans_staged_files_without_a_commit(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    normal = tmp_path / "README.md"
    normal.write_text("Generated test source, no medical data.\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    assert git_tracked_paths(tmp_path) == ["README.md"]
    assert check_repository(tmp_path) == (1, [])

    forbidden = tmp_path / "private" / "actual.csv"
    forbidden.parent.mkdir()
    forbidden.write_text("synthetic,values\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "private/actual.csv"], check=True)
    count, failures = check_repository(tmp_path)
    assert count == 2 and len(failures) >= 2
    assert not any("actual.csv" in reason for reason in failures)


@pytest.mark.skipif(shutil.which("git") is None, reason="Git executable unavailable")
def test_git_index_missing_fails_closed(tmp_path: Path):
    with pytest.raises(PublicSourceBoundaryError):
        git_tracked_paths(tmp_path)
