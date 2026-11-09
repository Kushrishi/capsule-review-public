"""Synthetic regression test for the evaluation-only build-return-shape fix."""
import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("numpy", reason="requires optional ML dependencies")
pytest.importorskip("torch", reason="requires optional ML dependencies")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from frozen_representation_comparison import evaluate, sha_file


def test_evaluator_consumes_pair_list_not_manifest_dict(tmp_path, monkeypatch):
    # Source audit build() returns (images, pairs, bank, mapping, missing).
    # No medical input is used, and all 24 prescribed cells are synthetic.
    pairs = [
        {"exam": exam, "positive_index": 0, "negative_index": 1, "run_length": 1}
        for exam in (23, 25, 29, 30)
    ]
    fake = types.ModuleType("recover_frozen_mobilenet")
    fake.build = lambda private_root: ([], pairs, None, [], [])
    monkeypatch.setitem(sys.modules, "recover_frozen_mobilenet", fake)
    base = tmp_path / "scores"
    base.mkdir()
    lock = tmp_path / "PREFIT_LOCKED.json"
    lock.write_text('{"synthetic":true}')
    records = []
    for exam in (23, 25, 29, 30):
        for seed in (17, 29, 43):
            for arm in ("classification", "ranking"):
                name = f"fold{exam}-seed{seed}-{arm}.json"
                path = base / name
                path.write_text(json.dumps({"endpoint_indices": [0, 1], "logits": [[0, 1], [1, 0]]}))
                records.append({"exam": exam, "seed": seed, "arm": arm, "score_file": name, "score_sha256": sha_file(path)})
    receipt = base / "prediction-receipt.json"
    receipt.write_text(json.dumps({"prefit_lock_sha256": sha_file(lock), "records": records}))
    out = tmp_path / "aggregate.json"
    answer = evaluate(tmp_path, base, out, sha_file(receipt), lock)
    assert answer["macro_pair_accuracy"] == {"classification": 1.0, "ranking": 1.0}
    assert answer["prespecified_consistency_pass"] is False
    assert len(json.loads(out.read_text())["records"]) == 24
