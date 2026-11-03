"""Synthetic-only tests: do not open Galar 11–20 labels, pixels or private weights."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from scripts import verify_unseen_galar_checkpoint_preflight as gate


SPEC = Path(__file__).resolve().parents[1] / "docs/GALAR_UNSEEN_11_20_EVALUATION_LOCK.json"


def _synthetic_archive(tmp_path: Path, *, model_epoch=8, fitted=None):
    spec = copy.deepcopy(json.loads(SPEC.read_text(encoding="utf-8")))
    model = spec["original_model"]
    weights = b"not a real checkpoint; generated test fixture"
    sha = hashlib.sha256(weights).hexdigest()
    model["weights_sha256"] = sha
    metadata = {
        "model_weights_sha256": sha,
        "source_git_commit": model["source_commit"],
        "architecture": model["architecture"],
        "selected_epoch": model_epoch,
        "classes": ["blood label absent", "blood label present"],
    }
    metrics = {
        "weights_sha256": sha,
        "architecture": model["architecture"],
        "fitting_examinations": fitted if fitted is not None else list(gate.TRAIN),
        "development_examinations": list(gate.DEV),
        "future_unopened_evaluation_examinations": list(gate.UNSEEN),
        "training": {"best_epoch": 8},
    }
    payloads = {
        "model/weights.pt": weights,
        "model/model.json": json.dumps(metadata).encode(),
        "model/metrics.json": json.dumps(metrics).encode(),
        # Protected references intentionally invalid and never loaded.
        "11.csv": b"SYNTHETIC PROTECTED SOURCE: MUST NOT OPEN",
        "61.csv": b"SYNTHETIC AUTHOR HOLDOUT: MUST NOT OPEN",
    }
    path = tmp_path / "synthetic-private-pilot.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in payloads.items():
            z.writestr(name, data)
    model["private_package_bytes"] = path.stat().st_size
    model["private_package_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ("weights", "metadata", "metrics"):
        model[f"{key}_sha256"] = hashlib.sha256(payloads[model[f"{key}_member"]]).hexdigest()
    return path, spec


def test_original_spec_is_frozen_and_contains_no_source_data():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["scope"]["training_examination_ids"] == list(gate.TRAIN)
    assert spec["scope"]["historical_checkpoint_selection_examination_ids"] == list(gate.DEV)
    assert spec["scope"]["locked_evaluation_examination_ids"] == list(gate.UNSEEN)
    assert spec["scope"]["authors_original_reserved_examination_ids"] == list(gate.AUTHOR_RESERVED)
    assert spec["methods"]["policies"] == list(gate.METHODS)
    assert spec["original_model"]["weights_sha256"] == (
        "f2c77f669b75ddddb4604c2f15070e97b7aef470d4c3af5193dd3e0eacbcc9f3"
    )
    assert spec["status"].startswith("Locked research design")
    assert spec["privacy"]["public_actions_real_data_access_forbidden"] is True


def test_provenance_read_only_three_explicit_members(tmp_path, monkeypatch):
    package, spec = _synthetic_archive(tmp_path)
    visited = []
    original = zipfile.ZipFile.read

    def monitored(self, member, *args, **kwargs):
        visited.append(member.filename if hasattr(member, "filename") else member)
        return original(self, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", monitored)
    receipt = gate.audit_package(package, spec)
    assert set(visited) == {"model/weights.pt", "model/model.json", "model/metrics.json"}
    assert len(visited) == 3
    assert receipt["source_or_holdout_labels_or_images_opened"] is False
    assert receipt["independent_evaluation_performed"] is False
    assert receipt["model_promoted"] is False


def test_any_changed_model_zip_fails_closed(tmp_path):
    package, spec = _synthetic_archive(tmp_path)
    package.write_bytes(package.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="checksum"):
        gate.audit_package(package, spec)


@pytest.mark.parametrize("field,value", [
    ("locked_evaluation_examination_ids", list(range(10, 20))),
    ("locked_evaluation_examination_ids", list(range(61, 71))),
    ("training_examination_ids", [1, 2, 3]),
])
def test_changed_cohort_fails_before_source_access(tmp_path, field, value):
    package, spec = _synthetic_archive(tmp_path)
    spec["scope"][field] = value
    with pytest.raises(ValueError, match="protocol"):
        gate.audit_package(package, spec)


def test_changed_model_epoch_or_training_cohort_fails(tmp_path):
    package, spec = _synthetic_archive(tmp_path, model_epoch=7)
    with pytest.raises(ValueError, match="provenance"):
        gate.audit_package(package, spec)
    package, spec = _synthetic_archive(tmp_path, fitted=list(range(2, 10)))
    with pytest.raises(ValueError, match="provenance"):
        gate.audit_package(package, spec)


def test_banned_workflow_policy_change_fails(tmp_path):
    package, spec = _synthetic_archive(tmp_path)
    spec["methods"]["policies"].append("tuned_using_holdout_labels")
    with pytest.raises(ValueError, match="protocol"):
        gate.audit_package(package, spec)


def test_symlink_and_absent_private_archive_fail_closed(tmp_path):
    package, spec = _synthetic_archive(tmp_path)
    link = tmp_path / "indirect.zip"
    link.symlink_to(package)
    with pytest.raises(ValueError, match="absent or size changed"):
        gate.audit_package(link, spec)
    package.unlink()
    with pytest.raises(ValueError, match="absent or size changed"):
        gate.audit_package(package, spec)
