"""Full-sequence custody tests using generated pixels and a fixed fake scorer.

No medical inputs, learned-model fitting, or reference outcomes are used.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import platform
import subprocess
import sys

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


@pytest.mark.parametrize("defect", ["policy", "score_index", "receipt_count"])
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
        receipt["scored_frames"] -= 1
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
            seen.append([f.position for f in frames])
            return [float(f.position) for f in frames]
        return scorer
    result = execute(data, tmp_path / "bundle", factory=factory)
    assert seen == [[0, 1, 2, 3], [4, 5, 6, 7], [8]]
    assert result["receipt"]["batches"] == 3
    assert result["receipt"]["maximum_batch_frames"] == 4


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
