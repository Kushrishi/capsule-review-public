"""CI routing checks use generated text in temporary Git repositories only."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import ci_scope


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=CI fixture", "-c",
         "user.email=ci@example.invalid", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def commit(root: Path, relative: str, contents: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    git(root, "add", "--all")
    git(root, "commit", "-qm", "Generated text fixture")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    base = commit(tmp_path, "README.md", "Generated source fixture.\n")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", base)
    git(tmp_path, "checkout", "-qb", "sequence-fixture")
    return tmp_path, base


def push_event(head):
    return {"after": head, "ref": "refs/heads/sequence-fixture",
            "repository": {"default_branch": "main"}}


def pr_event(base, head):
    return {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}


@pytest.mark.parametrize("path", sorted(ci_scope.SEQUENCE_ONLY_PATHS))
def test_each_reviewed_path_uses_sequence_scope(path):
    assert ci_scope.scope_for_paths([path]) == "sequence"


@pytest.mark.parametrize("paths", [
    [], ["pyproject.toml"], ["src/capsule_review/priority.py"],
    ["tests/test_sequence_pipeline.py", "src/capsule_review/app.py"],
    ["tests/test_sequence_pipeline.py.backup"],
])
def test_unknown_empty_or_mixed_changes_require_full_scope(paths):
    assert ci_scope.scope_for_paths(paths) == "full"


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
def test_sequence_only_branch_uses_scoped_checks(repository, event_name):
    root, base = repository
    head = commit(root, "tests/test_sequence_pipeline.py", "# Synthetic fixture\n")
    event = push_event(head) if event_name == "push" else pr_event(base, head)
    assert ci_scope.event_scope(root, event_name, event) == "sequence"


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
def test_earlier_unrelated_commit_cannot_hide_behind_last_scoped_commit(repository, event_name):
    root, base = repository
    commit(root, "src/capsule_review/app.py", "# Unrelated change\n")
    head = commit(root, "tests/test_sequence_pipeline.py", "# Last scoped change\n")
    event = push_event(head) if event_name == "push" else pr_event(base, head)
    assert ci_scope.event_scope(root, event_name, event) == "full"


def test_rename_does_not_hide_deleted_unknown_path(repository):
    root, base = repository
    (root / "tests").mkdir()
    git(root, "mv", "README.md", "tests/test_sequence_pipeline.py")
    git(root, "commit", "-qm", "Rename unchanged generated text")
    head = git(root, "rev-parse", "HEAD")
    paths = ci_scope.changed_paths(root, base, head)
    assert "README.md" in paths and "tests/test_sequence_pipeline.py" in paths
    assert ci_scope.scope_for_paths(paths) == "full"


@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/tags/v0-fixture"])
def test_default_branch_and_tags_always_keep_full_checks(repository, ref):
    root, _ = repository
    head = commit(root, "tests/test_sequence_pipeline.py", "# Scoped change\n")
    event = push_event(head)
    event["ref"] = ref
    assert ci_scope.event_scope(root, "push", event) == "full"


def test_pr_diff_uses_common_ancestor_when_base_advances(repository):
    root, base = repository
    head = commit(root, "tests/test_sequence_pipeline.py", "# Scoped change\n")
    git(root, "checkout", "-q", "main")
    advanced_base = commit(root, "unrelated-main.txt", "# Main-only change\n")
    git(root, "checkout", "-q", head)
    assert ci_scope.event_scope(root, "pull_request", pr_event(advanced_base, head)) == "sequence"


def test_mismatched_checkout_fails_closed(repository):
    root, base = repository
    commit(root, "tests/test_sequence_pipeline.py", "# Scoped change\n")
    with pytest.raises(ValueError, match="Checkout"):
        ci_scope.event_scope(root, "pull_request", pr_event(base, base))


def test_missing_default_branch_history_fails_closed(repository):
    root, _ = repository
    head = commit(root, "tests/test_sequence_pipeline.py", "# Scoped change\n")
    git(root, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(subprocess.CalledProcessError):
        ci_scope.event_scope(root, "push", push_event(head))


@pytest.mark.parametrize("value", [None, "HEAD", "a" * 39, "--output=unsafe"])
def test_only_complete_commit_ids_are_accepted(value):
    with pytest.raises(ValueError):
        ci_scope._sha(value)


def test_invalid_event_does_not_write_a_route(tmp_path, monkeypatch, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {}}), encoding="utf-8")
    output = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert ci_scope.main() == 1
    assert not output.exists()
    assert "no route selected" in capsys.readouterr().out
