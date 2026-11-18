"""Full-sequence custody tests using generated pixels and a fixed fake scorer.

No medical inputs, learned-model fitting, or reference outcomes are used.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from capsule_review import sequence_pipeline as pipeline
from capsule_review.priority import select_positions, uniform_midpoints


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")


def fixture(tmp_path: Path, *, n=37, batch_size=4):
    source = tmp_path / "generated"
    assets = tmp_path / "assets"
    source.mkdir()
    assets.mkdir()
    asset = assets / "fixture.txt"
    asset.write_text("Deterministic software fixture; no learned weights.\n")
    rows = []
    for i in range(n):
        path = source / f"frame_{i:06d}.png"
        Image.new("RGB", (20 + i % 3, 17), (i % 256, 70, 90)).save(path)
        rows.append({"position": i, "source_frame": i, "path": path.name,
                     "sha256": sha(path)})
    source_manifest = tmp_path / "source.jsonl"
    header = {"schema_version": 1, "frame_count": n,
              "sequence_id": "generated-software-sequence"}
    save_source(source_manifest, header, rows)
    method_manifest = tmp_path / "method.json"
    method = {
        "schema_version": 1,
        "method_id": "generated-software-fixture",
        "roster_status": "provisional",
        "preprocessing": {"definition": "Generated PNG bytes, RGB red channel"},
        "scoring": {"definition": "Fixed synthetic position table; no clinical meaning"},
        "implementation": pipeline.implementation_identity(),
        "files": [{"name": "fixture", "path": asset.name, "sha256": sha(asset)}],
        "runtime": {"python": platform.python_version(),
                    "packages": {"Pillow": version("Pillow")},
                    "device": "cpu", "threads": 1, "batch_size": batch_size},
    }
    write_json(method_manifest, method)
    return {"source_manifest": source_manifest, "method_manifest": method_manifest,
            "source_root": source, "asset_root": assets, "rows": rows,
            "header": header, "method": method}


def save_source(path: Path, header, rows):
    path.write_text("".join(json.dumps(x, sort_keys=True) + "\n"
                            for x in [header, *rows]), encoding="utf-8")


def execute(data, output: Path, *, scores=None, factory=None,
            source_sha=None, method_sha=None):
    if factory is None:
        def factory(method, verified_files):
            assert verified_files["fixture"].is_file()
            def scorer(frames):
                assert 0 < len(frames) <= method["runtime"]["batch_size"]
                for frame in frames:
                    assert hashlib.sha256(frame.raw).hexdigest() == frame.source_sha256
                    with Image.open(io.BytesIO(frame.raw)) as image:
                        assert image.getpixel((0, 0))[0] == frame.position % 256
                return [float(scores[f.position] if scores is not None else f.position)
                        for f in frames]
            return scorer
    return pipeline.run_sequence(
        data["source_manifest"], data["method_manifest"], data["source_root"],
        data["asset_root"], output,
        expected_source_sha256=source_sha or sha(data["source_manifest"]),
        expected_method_sha256=method_sha or sha(data["method_manifest"]),
        scorer_factory=factory,
    )


@pytest.mark.parametrize("defect", ["missing_position", "duplicate_position",
                                   "out_of_order", "source_gap", "duplicate_path",
                                   "declared_count", "extra_row", "empty"])
def test_invalid_frame_population_is_never_sealed(tmp_path, defect):
    data = fixture(tmp_path, n=15)
    rows = deepcopy(data["rows"])
    header = deepcopy(data["header"])
    if defect == "missing_position":
        del rows[6]
    elif defect == "duplicate_position":
        rows[6]["position"] = rows[5]["position"]
    elif defect == "out_of_order":
        rows[5], rows[6] = rows[6], rows[5]
    elif defect == "source_gap":
        rows[6]["source_frame"] += 1
    elif defect == "duplicate_path":
        rows[6]["path"] = rows[5]["path"]
        rows[6]["sha256"] = rows[5]["sha256"]
    elif defect == "declared_count":
        header["frame_count"] += 1
    elif defect == "extra_row":
        rows.append(deepcopy(rows[-1]))
    elif defect == "empty":
        header["frame_count"] = 0
        rows.clear()
    save_source(data["source_manifest"], header, rows)
    output = tmp_path / "rejected"
    with pytest.raises((ValueError, OSError)):
        execute(data, output)
    assert not (output / "seal.json").exists()


@pytest.mark.parametrize("n", [1, 5, 15, 37, 101])
def test_complete_sequence_exact_budgets_and_repeatable_records(tmp_path, n):
    data = fixture(tmp_path, n=n)
    # Deliberate exact ties; arbitrary synthetic scores remain within the
    # existing production selector's domain for independent reference replay.
    scores = [((i * 7) % 11) / 10 for i in range(n)]
    first, second = tmp_path / "first", tmp_path / "second"
    run = execute(data, first, scores=scores)
    execute(data, second, scores=scores)
    for name in ("scores.jsonl", "selections.json", "source_manifest.jsonl",
                 "method_manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    records = [json.loads(line) for line in (first / "scores.jsonl").read_text().splitlines()]
    assert [r["position"] for r in records] == list(range(n))
    assert [r["score"] for r in records] == scores
    result = json.loads((first / "selections.json").read_text())
    assert result["roster_status"] == "provisional"
    for budget in result["budgets"]:
        # Decimal half-up is independent of the implementation's integer rule.
        expected_k = max(1, int((Decimal(n) * budget["percent"] / 100)
                               .quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        assert budget["k"] == expected_k
        assert budget["uniform"] == uniform_midpoints(n, expected_k)
        assert budget["score_bin"] == sorted(select_positions(scores, expected_k, "score_bin"))
        assert len(set(budget["score_bin"])) == expected_k
    assert run["receipt"]["scored_frames"] == n
    assert run["receipt"]["maximum_batch_frames"] <= 4
    assert pipeline.verify_seal(first, run["seal_sha256"])["frame_count"] == n


def test_raw_margins_and_earliest_ties_are_preserved(tmp_path):
    data = fixture(tmp_path, n=20)
    margins = [-4.0, -4.0, 9.0, 9.0, -1.0, -2.0, -3.0, -4.0,
               80.0, 70.0, 1.0, 2.0, 3.0, 4.0, 90.0, 90.0,
               -8.0, -7.0, -6.0, -5.0]
    output = tmp_path / "raw-margins"
    execute(data, output, scores=margins)
    result = json.loads((output / "selections.json").read_text())
    assert result["budgets"] == [
        {"percent": 10, "k": 2, "uniform": [5, 15], "score_bin": [8, 14]},
        {"percent": 25, "k": 5, "uniform": [2, 6, 10, 14, 18],
         "score_bin": [2, 4, 8, 14, 19]},
    ]
    saved = [json.loads(x)["score"] for x in (output / "scores.jsonl").read_text().splitlines()]
    assert saved == margins


def test_identical_pixels_in_distinct_declared_frames_are_retained(tmp_path):
    data = fixture(tmp_path, n=8)
    original = data["source_root"] / data["rows"][0]["path"]
    duplicate = data["source_root"] / data["rows"][3]["path"]
    duplicate.write_bytes(original.read_bytes())
    data["rows"][3]["sha256"] = sha(duplicate)
    save_source(data["source_manifest"], data["header"], data["rows"])
    output = tmp_path / "repeat-content"
    result = execute(data, output, factory=lambda *_: lambda frames: [0.0] * len(frames))
    assert result["receipt"]["scored_frames"] == 8
    assert result["receipt"]["duplicate_content_frames_retained"] == 1
    assert pipeline.verify_seal(output, result["seal_sha256"])["frame_count"] == 8


def test_hardlinked_source_alias_is_rejected(tmp_path):
    data = fixture(tmp_path, n=8)
    original = data["source_root"] / data["rows"][0]["path"]
    alias = data["source_root"] / data["rows"][3]["path"]
    alias.unlink()
    alias.hardlink_to(original)
    data["rows"][3]["sha256"] = sha(alias)
    save_source(data["source_manifest"], data["header"], data["rows"])
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="alias"):
        execute(data, output)
    assert not (output / "seal.json").exists()


def reseal_for_semantic_test(output):
    """Recompute the byte envelope to test deeper policy validation separately."""
    seal_file = output / "seal.json"
    seal = json.loads(seal_file.read_text())
    for name, identity in seal["files"].items():
        path = output / name
        identity.update(sha256=sha(path), size_bytes=path.stat().st_size)
    write_json(seal_file, seal)
    return sha(seal_file)


@pytest.mark.parametrize("artifact", ["scores.jsonl", "selections.json", "receipt.json"])
def test_changed_bundle_bytes_fail_the_original_seal(tmp_path, artifact):
    data = fixture(tmp_path, n=15)
    output = tmp_path / "bundle"
    result = execute(data, output)
    path = output / artifact
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed"):
        pipeline.verify_seal(output, result["seal_sha256"])


def test_rewritten_envelope_cannot_pass_original_digest(tmp_path):
    data = fixture(tmp_path, n=15)
    output = tmp_path / "bundle"
    result = execute(data, output)
    path = output / "selections.json"
    selections = json.loads(path.read_text())
    selections["budgets"][0]["score_bin"][0] = 0
    write_json(path, selections)
    reseal_for_semantic_test(output)
    with pytest.raises(ValueError, match="commitment"):
        pipeline.verify_seal(output, result["seal_sha256"])


@pytest.mark.parametrize("defect", ["policy", "score_index", "receipt_count",
                                   "receipt_schema", "receipt_roster", "receipt_sequence",
                                   "receipt_authenticated", "receipt_torch"])
def test_semantically_invalid_bundle_fails_even_with_matching_envelope(tmp_path, defect):
    data = fixture(tmp_path, n=15)
    output = tmp_path / "bundle"
    execute(data, output)
    if defect == "policy":
        path = output / "selections.json"
        selections = json.loads(path.read_text())
        selections["budgets"][0]["score_bin"][0] = 0
        write_json(path, selections)
    elif defect == "score_index":
        path = output / "scores.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[3]["position"] = 4
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    else:
        path = output / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt.update({
            "receipt_count": {"scored_frames": receipt["scored_frames"] - 1},
            "receipt_schema": {"schema_version": True},
            "receipt_roster": {"roster_status": "approved"},
            "receipt_sequence": {"sequence_id": "different-sequence"},
            "receipt_authenticated": {"source_files_authenticated": 0},
            "receipt_torch": {"observed_torch_settings": {
                "threads": 1, "deterministic_algorithms": True}},
        }[defect])
        write_json(path, receipt)
    new_digest = reseal_for_semantic_test(output)
    with pytest.raises(ValueError):
        pipeline.verify_seal(output, new_digest)


def test_existing_destination_cannot_be_overwritten(tmp_path):
    data = fixture(tmp_path, n=5)
    output = tmp_path / "bundle"
    result = execute(data, output)
    with pytest.raises(FileExistsError):
        execute(data, output)
    assert pipeline.verify_seal(output, result["seal_sha256"])["frame_count"] == 5


@pytest.mark.parametrize("defect", ["oversized_population", "boolean_count",
                                   "zero_batch", "oversized_batch", "code_hash"])
def test_explicit_resource_and_code_bounds_fail_closed(tmp_path, defect):
    data = fixture(tmp_path, n=5)
    if defect in {"oversized_population", "boolean_count"}:
        data["header"]["frame_count"] = 200_001 if defect == "oversized_population" else True
        save_source(data["source_manifest"], data["header"], data["rows"])
    else:
        if defect == "code_hash":
            data["method"]["implementation"]["priority.py"] = "0" * 64
        else:
            data["method"]["runtime"]["batch_size"] = 0 if defect == "zero_batch" else 65
        write_json(data["method_manifest"], data["method"])
    output = tmp_path / "rejected"
    with pytest.raises(ValueError):
        execute(data, output)
    assert not (output / "seal.json").exists()


def test_each_frame_is_scored_once_in_a_bounded_batch(tmp_path):
    data = fixture(tmp_path, n=9, batch_size=4)
    seen = []
    def factory(*args):
        def scorer(frames):
            assert isinstance(frames, tuple)
            seen.append([f.position for f in frames])
            return [float(f.position) for f in frames]
        return scorer
    result = execute(data, tmp_path / "bundle", factory=factory)
    assert seen == [[0, 1, 2, 3], [4, 5, 6, 7], [8]]
    assert result["receipt"]["batches"] == 3
    assert result["receipt"]["maximum_batch_frames"] == 4


@pytest.mark.parametrize("stage", ["factory", "scoring"])
@pytest.mark.parametrize("target", ["scoring", "preprocessing", "files"])
def test_adapter_cannot_change_authenticated_contract(tmp_path, stage, target):
    data = fixture(tmp_path, n=5)
    original = data["method_manifest"].read_bytes()

    def factory(method, verified_files):
        def mutate():
            if target == "files":
                verified_files["fixture"] = tmp_path / "unverified-asset.txt"
            else:
                method[target]["definition"] = "Changed synthetic contract"
        if stage == "factory":
            mutate()
        def scorer(frames):
            if stage == "scoring":
                mutate()
            return [float(frame.position) for frame in frames]
        return scorer

    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="authenticated method or file mapping"):
        execute(data, output, factory=factory)
    assert data["method_manifest"].read_bytes() == original
    assert not (output / "seal.json").exists()
    assert json.loads((output / "failure.json").read_text())["scored_frames"] == 0


@pytest.mark.parametrize("mutation", ["replace", "reorder"])
def test_adapter_cannot_mutate_source_batch(tmp_path, mutation):
    data = fixture(tmp_path, n=5)
    def factory(*args):
        def scorer(frames):
            if mutation == "replace":
                frames[0] = replace(frames[0], raw=b"Unrelated replacement bytes")
            else:
                frames.reverse()
            return [float(frame.position) for frame in frames]
        return scorer
    output = tmp_path / "rejected"
    with pytest.raises((TypeError, AttributeError)):
        execute(data, output, factory=factory)
    assert not (output / "seal.json").exists()


def mocked_torch_runtime(data, monkeypatch):
    """Exercise runtime guards without importing Torch or executing a model."""
    state = {"threads": 1, "deterministic_algorithms": True, "warn_only": False}
    stub = SimpleNamespace(
        get_num_threads=lambda: state["threads"],
        are_deterministic_algorithms_enabled=lambda: state["deterministic_algorithms"],
        is_deterministic_algorithms_warn_only_enabled=lambda: state["warn_only"],
    )
    real_version = pipeline.importlib.metadata.version
    monkeypatch.setitem(sys.modules, "torch", stub)
    monkeypatch.setattr(pipeline.importlib.metadata, "version", lambda name:
                        "synthetic-runtime" if name == "torch" else real_version(name))
    data["method"]["runtime"]["packages"]["torch"] = "synthetic-runtime"
    write_json(data["method_manifest"], data["method"])
    return state


@pytest.mark.parametrize("field,value", [
    ("threads", 2), ("deterministic_algorithms", False), ("warn_only", True),
])
def test_torch_runtime_drift_during_scoring_prevents_sealing(tmp_path, monkeypatch, field, value):
    data = fixture(tmp_path, n=5)
    state = mocked_torch_runtime(data, monkeypatch)
    def factory(*args):
        def scorer(frames):
            state[field] = value
            return [float(frame.position) for frame in frames]
        return scorer
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="declared threads and deterministic algorithms"):
        execute(data, output, factory=factory)
    assert not (output / "seal.json").exists()
    assert json.loads((output / "failure.json").read_text())["scored_frames"] == 0


def test_verifier_rejects_wrong_observed_torch_settings(tmp_path, monkeypatch):
    data = fixture(tmp_path, n=5)
    mocked_torch_runtime(data, monkeypatch)
    output = tmp_path / "bundle"
    result = execute(data, output)
    assert pipeline.verify_seal(output, result["seal_sha256"])["frame_count"] == 5
    path = output / "receipt.json"
    receipt = json.loads(path.read_text())
    receipt["observed_torch_settings"]["deterministic_algorithms"] = False
    write_json(path, receipt)
    new_digest = reseal_for_semantic_test(output)
    with pytest.raises(ValueError, match="receipt does not match"):
        pipeline.verify_seal(output, new_digest)


def test_asset_mutation_during_inference_prevents_sealing(tmp_path):
    data = fixture(tmp_path, n=9)
    def factory(method, verified_files):
        def scorer(frames):
            verified_files["fixture"].write_text("Changed during inference.\n")
            return [float(f.position) for f in frames]
        return scorer
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="SHA-256"):
        execute(data, output, factory=factory)
    assert not (output / "seal.json").exists()
    failure = json.loads((output / "failure.json").read_text())
    assert failure["sealed"] is False
    assert failure["scored_frames"] == 9


def cli_fixture(tmp_path):
    data = fixture(tmp_path, n=15)
    adapter = data["asset_root"] / "generated_adapter.py"
    adapter.write_text(
        '"""Synthetic fixed scorer; no model fitting."""\n'
        'def create_scorer(method, files):\n'
        '    return lambda frames: [float(f.position) for f in frames]\n',
        encoding="utf-8",
    )
    data["method"]["files"].append(
        {"name": "adapter", "path": adapter.name, "sha256": sha(adapter)}
    )
    write_json(data["method_manifest"], data["method"])
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_frozen_sequence.py"
    output = tmp_path / "cli-bundle"
    args = [sys.executable, str(script), "run",
            "--source-manifest", str(data["source_manifest"]),
            "--source-sha256", sha(data["source_manifest"]),
            "--method-manifest", str(data["method_manifest"]),
            "--method-sha256", sha(data["method_manifest"]),
            "--source-root", str(data["source_root"]),
            "--asset-root", str(data["asset_root"]), "--output", str(output)]
    return data, adapter, script, output, args


def test_cli_scores_and_verifies_complete_synthetic_submission(tmp_path):
    data, adapter, script, output, args = cli_fixture(tmp_path)
    executed = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert executed.returncode == 0, executed.stderr
    receipt = json.loads(executed.stdout)
    checked = subprocess.run(
        [sys.executable, str(script), "verify", "--bundle", str(output),
         "--seal-sha256", receipt["seal_sha256"]],
        capture_output=True, text=True, timeout=30,
    )
    assert checked.returncode == 0, checked.stderr
    result = json.loads(checked.stdout)
    assert result["frame_count"] == 15
    assert [x["k"] for x in result["budgets"]] == [2, 4]
    assert all(set(row) == {"percent", "k"} for row in result["budgets"])
    assert "source_sha256" not in executed.stdout + checked.stdout
    assert "score_bin" not in checked.stdout
    assert (output / "source_manifest.jsonl").read_bytes() == data["source_manifest"].read_bytes()


def test_cli_rejects_tampered_adapter_before_any_import_side_effect(tmp_path):
    data, adapter, script, output, args = cli_fixture(tmp_path)
    adapter.write_text(
        'from pathlib import Path\n'
        'Path(__file__).with_name("imported-marker.txt").write_text("must not run")\n'
        + adapter.read_text(), encoding="utf-8",
    )
    executed = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert executed.returncode != 0
    assert "Sequence operation failed" in executed.stderr
    assert "Traceback" not in executed.stderr
    assert str(tmp_path) not in executed.stderr
    assert not (data["asset_root"] / "imported-marker.txt").exists()
    assert not (output / "seal.json").exists()
    failure = json.loads((output / "failure.json").read_text())
    assert failure["sealed"] is False
    assert "SHA-256 mismatch" in failure["error"]


# Prospective generated plumbing canary, not a rewritten SEE-AI manifest.
# These runner identities are inherited from Pro M3 / Work 2's November 18
# packet at a688f37fe0af79c67a383f62083437b89d3ea09f. No scorer/model bytes
# from that private packet are opened, substituted or reauthenticated here.
CURRENT_BINDING = {
    "sequence_pipeline.py": "2a63c5cffe01d7ac4102d7d69f51a49cce4ec85cc7f71399be927e35e453ca3c",
    "priority.py": "10b16b2a856a45b092e26b87bbacfdb1675355f7067b7acecd4f6d80fd39a62c",
    "geometry_control.py": "28b0d41bbb3e3e801ba43c134475ddacafdea625b5c321783f6bef546a4cc547",
    "unseen_evaluation.py": "7f588882ec3325926d509ff9c4489e0803757def703cde0d07b62c969cf02778",
}
HISTORICAL_PIPELINE = "188d46a9d78c550d3529a5f2dd169a39d7fa902b7be6cf332ef13dd4a676eae0"
ENTRYPOINT_BINDING = "07311cd499588359502e430fac5e693b20ebbab8163511987f7b574defbaba39"
BINDING_SCORES = [.6, .6, .4, .9, .9, .1, .7, .7, .2, .2, .8, .8, .3, .5, .5]


def binding_cli_fixture(tmp_path):
    """Actual CLI, generated bytes, batch one and an observable import marker."""
    data, adapter, script, output, args = cli_fixture(tmp_path)
    # Names intentionally disagree with ordinal order. The authenticated
    # manifest must win over lexical or natural directory sorting.
    for row in data['rows']:
        old = data['source_root'] / row['path']
        row['path'] = f'generated_{99 - row["position"]}.png'
        old.rename(data['source_root'] / row['path'])
    save_source(data['source_manifest'], data['header'], data['rows'])
    data['method']['method_id'] = 'generated-current-binding-canary-not-seeai'
    data['method']['runtime']['batch_size'] = 1
    data['method']['scoring'] = {'definition': 'Generated fixed table; no learned model or clinical meaning'}
    scores = data['asset_root'] / 'fixture.txt'
    scores.write_text(json.dumps(BINDING_SCORES), encoding='utf-8')
    adapter.write_text(
        'import hashlib, io, json\nfrom pathlib import Path\nfrom PIL import Image\n'
        'Path(__file__).with_name("imported-marker.txt").write_text("generated import executed")\n'
        'def create_scorer(method, files):\n'
        '    values = json.loads(files["fixture"].read_text())\n'
        '    def score(frames):\n'
        '        assert isinstance(frames, tuple) and len(frames) == 1\n'
        '        for frame in frames:\n'
        '            assert frame.source_frame == frame.position\n'
        '            assert hashlib.sha256(frame.raw).hexdigest() == frame.source_sha256\n'
        '            with Image.open(io.BytesIO(frame.raw)) as image:\n'
        '                assert image.getpixel((0, 0))[0] == frame.position\n'
        '        return [values[frame.position] for frame in frames]\n'
        '    return score\n', encoding='utf-8')
    for asset in data['method']['files']:
        asset['sha256'] = sha(data['asset_root'] / asset['path'])
    write_json(data['method_manifest'], data['method'])
    args[args.index('--source-sha256') + 1] = sha(data['source_manifest'])
    args[args.index('--method-sha256') + 1] = sha(data['method_manifest'])
    return data, adapter, script, output, args


def test_current_runner_matches_proposed_binding(record_property):
    assert pipeline.implementation_identity() == CURRENT_BINDING
    script = Path(__file__).resolve().parents[1] / 'scripts/run_frozen_sequence.py'
    assert sha(script) == ENTRYPOINT_BINDING
    assert CURRENT_BINDING['sequence_pipeline.py'] != HISTORICAL_PIPELINE
    record_property('binding', json.dumps({**CURRENT_BINDING, 'entrypoint': sha(script)}, sort_keys=True))


def test_current_binding_two_fresh_cli_runs_and_independent_selection(tmp_path, record_property):
    data, _, script, output, args = binding_cli_fixture(tmp_path)
    first = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert first.returncode == 0, first.stderr
    second_output = tmp_path / 'second-fresh-process'
    args[args.index('--output') + 1] = str(second_output)
    second = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert second.returncode == 0, second.stderr
    receipts = []
    identities = []
    for bundle, completed in [(output, first), (second_output, second)]:
        summary = json.loads(completed.stdout)
        verified = subprocess.run([sys.executable, str(script), 'verify', '--bundle', str(bundle),
                                   '--seal-sha256', summary['seal_sha256']],
                                  capture_output=True, text=True, timeout=30)
        assert verified.returncode == 0, verified.stderr
        scores = [json.loads(line) for line in (bundle / 'scores.jsonl').read_text().splitlines()]
        assert [item['position'] for item in scores] == list(range(15))
        assert [item['source_frame'] for item in scores] == list(range(15))
        assert [item['source_sha256'] for item in scores] == [row['sha256'] for row in data['rows']]
        assert [item['score'] for item in scores] == BINDING_SCORES
        selections = json.loads((bundle / 'selections.json').read_text())
        assert selections['roster_status'] == 'provisional'
        assert selections['budgets'] == [
            {'percent': 10, 'k': 2, 'score_bin': [3, 10], 'uniform': [3, 11]},
            {'percent': 25, 'k': 4, 'score_bin': [0, 3, 10, 11], 'uniform': [1, 5, 9, 13]},
        ]
        for budget in selections['budgets']:
            k = int((Decimal(15) * budget['percent'] / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            assert budget['k'] == k
            # Independent enumeration; do not use the production selectors.
            chosen = [max(range(j * 15 // k, (j + 1) * 15 // k),
                          key=lambda p: (BINDING_SCORES[p], -p)) for j in range(k)]
            assert budget['score_bin'] == chosen
            assert budget['uniform'] == [(2 * j + 1) * 15 // (2 * k) for j in range(k)]
        receipt = json.loads((bundle / 'receipt.json').read_text())
        assert receipt['maximum_batch_frames'] == 1 and receipt['scored_frames'] == 15
        assert receipt['implementation'] == CURRENT_BINDING
        receipts.append(receipt)
        identities.append({'seal_sha256': summary['seal_sha256'],
                           'artifacts': {name: sha(bundle / name) for name in
                                         ['source_manifest.jsonl', 'method_manifest.json', 'scores.jsonl', 'selections.json']}})
    for name in identities[0]['artifacts']:
        assert identities[0]['artifacts'][name] == identities[1]['artifacts'][name]
    variable = {'wall_seconds', 'scoring_and_decode_seconds', 'frames_per_second_including_preflight',
                'frames_per_second_scoring_and_decode', 'cpu_seconds', 'process_peak_rss_bytes',
                'process_peak_rss_before_bytes', 'completed_at_utc'}
    assert {k: v for k, v in receipts[0].items() if k not in variable} == {
        k: v for k, v in receipts[1].items() if k not in variable}
    # Receipt timing/memory/timestamp fields and full seals need not match.
    record_property('fresh_process_replay', json.dumps(identities, sort_keys=True))


@pytest.mark.parametrize('control,expected_error,before_import', [
    ('historical-binding', 'Pipeline or selection implementation changed', True),
    ('selection-binding', 'Pipeline or selection implementation changed', True),
    ('method-byte', 'Method manifest SHA-256 mismatch', True),
    ('adapter-byte', 'Frozen model/configuration/source SHA-256 mismatch', True),
    ('asset-byte', 'Frozen model/configuration/source SHA-256 mismatch', True),
    ('source-manifest-byte', 'Source manifest SHA-256 mismatch', True),
    ('source-frame-byte', 'Source frame SHA-256 mismatch', False),
    ('runtime-mismatch', 'Python version differs from the frozen runtime', True),
    ('unapproved-roster', 'Unsupported or incomplete provisional method manifest', True),
])
def test_current_binding_rejects_changed_commitments(
        tmp_path, record_property, control, expected_error, before_import):
    data, adapter, _, output, args = binding_cli_fixture(tmp_path)
    if control in {'historical-binding', 'selection-binding', 'runtime-mismatch', 'unapproved-roster'}:
        if control == 'historical-binding':
            data['method']['implementation']['sequence_pipeline.py'] = HISTORICAL_PIPELINE
        elif control == 'selection-binding':
            data['method']['implementation']['priority.py'] = '0' * 64
        elif control == 'runtime-mismatch':
            data['method']['runtime']['python'] = '0.0.0'
        else:
            data['method']['roster_status'] = 'approved'
        write_json(data['method_manifest'], data['method'])
        args[args.index('--method-sha256') + 1] = sha(data['method_manifest'])
    else:
        target = {'method-byte': data['method_manifest'], 'adapter-byte': adapter,
                  'asset-byte': data['asset_root'] / 'fixture.txt',
                  'source-manifest-byte': data['source_manifest'],
                  'source-frame-byte': data['source_root'] / data['rows'][0]['path']}[control]
        target.write_bytes(target.read_bytes() + b' ')
    completed = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 1
    assert 'Sequence operation failed' in completed.stderr
    assert 'Traceback' not in completed.stderr and str(tmp_path) not in completed.stderr
    assert not (output / 'seal.json').exists() and not (output / 'seal.pending').exists()
    assert (data['asset_root'] / 'imported-marker.txt').exists() == (not before_import)
    failure = json.loads((output / 'failure.json').read_text())
    assert failure['sealed'] is False and failure['scored_frames'] == 0
    assert expected_error in failure['error']
    record_property('rejection', json.dumps({'control': control, 'error': failure['error'],
                    'scored_frames': 0, 'adapter_imported': not before_import}, sort_keys=True))


def test_keyboard_interrupt_preserves_failure_receipt_without_a_seal(tmp_path):
    data = fixture(tmp_path, n=9, batch_size=4)
    calls = []
    def factory(*args):
        def scorer(frames):
            calls.append(True)
            if len(calls) == 2:
                raise KeyboardInterrupt("Synthetic interruption")
            return [float(f.position) for f in frames]
        return scorer
    output = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        execute(data, output, factory=factory)
    assert not (output / "seal.json").exists()
    assert not (output / "seal.pending").exists()
    failure = json.loads((output / "failure.json").read_text())
    assert failure["error_type"] == "KeyboardInterrupt"
    assert failure["sealed"] is False
    assert failure["scored_frames"] == 4


def test_unrelated_git_marker_does_not_override_actual_discovery(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    mounted = tmp_path / "mounted"
    mounted.mkdir()
    monkeypatch.setenv("GIT_DIR", "/unrelated/private-checkout")
    monkeypatch.setenv("GIT_DISCOVERY_ACROSS_FILESYSTEM", "1")
    calls = []
    def no_discovered_worktree(command, **kwargs):
        calls.append(command)
        assert command == ["git", "-C", str(mounted), "rev-parse", "--show-toplevel"]
        assert not any(key.startswith("GIT_") for key in kwargs["env"])
        return subprocess.CompletedProcess(command, 128, "", "not a worktree")
    monkeypatch.setattr(pipeline.subprocess, "run", no_discovered_worktree)
    assert pipeline._inside_git_worktree(mounted / "new-output") is False
    assert len(calls) == 1


def test_private_output_in_a_real_git_checkout_is_rejected(tmp_path):
    data = fixture(tmp_path, n=5)
    checkout = tmp_path / "unrelated-checkout"
    subprocess.run(["git", "init", "--quiet", str(checkout)], check=True,
                   capture_output=True, timeout=10)
    output = checkout / "private-output"
    assert pipeline._inside_git_worktree(output) is True
    with pytest.raises(ValueError, match="outside Git"):
        execute(data, output)
    assert not output.exists()


def test_current_source_checkout_is_always_excluded():
    project = Path(__file__).resolve().parents[1]
    assert pipeline._inside_git_worktree(project / "not-created-private-output") is True


@pytest.mark.parametrize("defect", ["missing", "changed_bytes", "corrupt_png",
                                   "path_escape", "symlink"])
def test_invalid_source_bytes_are_never_silently_skipped(tmp_path, defect):
    data = fixture(tmp_path, n=8)
    row = data["rows"][3]
    frame = data["source_root"] / row["path"]
    if defect == "missing":
        frame.unlink()
    elif defect == "changed_bytes":
        frame.write_bytes(frame.read_bytes() + b"different bytes")
    elif defect == "corrupt_png":
        frame.write_bytes(b"Not an image, although its manifest hash matches.")
        row["sha256"] = sha(frame)
    elif defect == "path_escape":
        row["path"] = "../outside.png"
    elif defect == "symlink":
        other = tmp_path / "outside.png"
        other.write_bytes(frame.read_bytes())
        frame.unlink()
        frame.symlink_to(other)
    save_source(data["source_manifest"], data["header"], data["rows"])
    output = tmp_path / "rejected"
    with pytest.raises((ValueError, OSError)):
        execute(data, output)
    assert not (output / "seal.json").exists()


@pytest.mark.parametrize("defect", ["source_hash", "method_hash", "asset_bytes",
                                   "runtime_version"])
def test_authentication_fails_before_scorer_load(tmp_path, defect):
    data = fixture(tmp_path, n=5)
    kwargs = {}
    if defect == "source_hash":
        kwargs["source_sha"] = "0" * 64
    elif defect == "method_hash":
        kwargs["method_sha"] = "0" * 64
    elif defect == "asset_bytes":
        (data["asset_root"] / "fixture.txt").write_text("Changed fixture.")
    elif defect == "runtime_version":
        data["method"]["runtime"]["packages"]["Pillow"] = "0.0.0"
        write_json(data["method_manifest"], data["method"])
    loaded = []
    def must_not_load(*args):
        loaded.append(True)
        raise AssertionError("An unauthenticated scorer must not load.")
    output = tmp_path / "rejected"
    with pytest.raises((ValueError, OSError)):
        execute(data, output, factory=must_not_load, **kwargs)
    assert not loaded
    assert not (output / "seal.json").exists()


@pytest.mark.parametrize("bad_output", ["exception", "short", "nan", "inf", "boolean"])
def test_failed_or_incomplete_inference_has_no_seal(tmp_path, bad_output):
    data = fixture(tmp_path, n=9)
    def factory(*args):
        def scorer(frames):
            if bad_output == "exception":
                raise RuntimeError("Synthetic scorer failure")
            if bad_output == "short":
                return [0.0] * (len(frames) - 1)
            value = {"nan": float("nan"), "inf": float("inf"), "boolean": True}[bad_output]
            return [value] * len(frames)
        return scorer
    output = tmp_path / "rejected"
    with pytest.raises((ValueError, RuntimeError)):
        execute(data, output, factory=factory)
    assert not (output / "seal.json").exists()
