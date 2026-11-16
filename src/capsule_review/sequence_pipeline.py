"""Private, outcome-blind execution of an explicitly frozen frame scorer.

Images are held for at most one configured batch. Only bounded source identity
metadata and selected indices scale with sequence length (at most MAX_FRAMES).
This module neither chooses a model roster nor reads reference annotations.
A seal is a byte commitment; the evaluator must receive its digest separately.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import shutil
import subprocess
import time
from typing import Callable, Mapping, Sequence

from PIL import Image

from .geometry_control import bins
from .priority import MAX_FRAMES, uniform_midpoints
from .unseen_evaluation import exact_k

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 4096
PERCENTS = (10, 25)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ARTIFACTS = (
    "source_manifest.jsonl", "method_manifest.json", "scores.jsonl",
    "selections.json", "receipt.json",
)


@dataclass(frozen=True)
class FrameInput:
    position: int
    source_frame: int
    path: str
    source_sha256: str
    raw: bytes


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _sha256(value: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ValueError("A lowercase SHA-256 commitment is required.")
    return value


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ValueError("Non-finite JSON constant.")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 JSON.") from exc
    if type(value) is not dict:
        raise ValueError("A JSON object is required.")
    return value


def _regular(path: Path, limit: int) -> Path:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Missing, unsafe or oversized regular file.")
    return path


def _relative_name(name: str) -> PurePosixPath:
    if (type(name) is not str or not name or len(name) > 1024
            or "\\" in name or ":" in name):
        raise ValueError("Invalid relative file path.")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or relative.as_posix() != name
            or any(part in ("", ".", "..") for part in relative.parts)):
        raise ValueError("File path must stay within its declared root.")
    return relative


def _relative_file(root: Path, name: str, limit: int) -> Path:
    relative = _relative_name(name)
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("Symlinks are not valid source or model files.")
    return _regular(path, limit)


def _root(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("A regular existing root directory is required.")
    return path.resolve()


def implementation_identity() -> dict[str, str]:
    """Code commitments copied into the method before executing any scorer."""
    root = Path(__file__).parent
    return {name: file_sha256(root / name) for name in (
        "sequence_pipeline.py", "priority.py", "geometry_control.py",
        "unseen_evaluation.py",
    )}


def _method_schema(method: dict) -> None:
    required = {"schema_version", "method_id", "roster_status", "preprocessing",
                "scoring", "files", "runtime", "implementation"}
    if (set(method) != required or type(method["schema_version"]) is not int
            or method["schema_version"] != 1
            or type(method["method_id"]) is not str
            or not 1 <= len(method["method_id"]) <= 160
            or method["roster_status"] != "provisional"):
        raise ValueError("Unsupported or incomplete provisional method manifest.")
    if any(type(method[key]) is not dict or not method[key]
           for key in ("preprocessing", "scoring", "implementation")):
        raise ValueError("Explicit preprocessing, scoring and code identities are required.")
    expected_code = {"sequence_pipeline.py", "priority.py", "geometry_control.py",
                     "unseen_evaluation.py"}
    if set(method["implementation"]) != expected_code:
        raise ValueError("Incomplete pipeline implementation identity.")
    for value in method["implementation"].values():
        _sha256(value)
    runtime = method["runtime"]
    if (type(runtime) is not dict or set(runtime) != {
            "python", "packages", "device", "threads", "batch_size"}
            or type(runtime["python"]) is not str
            or runtime["device"] != "cpu"
            or type(runtime["threads"]) is not int or not 1 <= runtime["threads"] <= 64
            or type(runtime["batch_size"]) is not int or not 1 <= runtime["batch_size"] <= 64
            or type(runtime["packages"]) is not dict
            or "Pillow" not in runtime["packages"]
            or any(type(k) is not str or type(v) is not str or not k or not v
                   for k, v in runtime["packages"].items())):
        raise ValueError("An exact CPU runtime and bounded batch are required.")
    files = method["files"]
    if type(files) is not list or not 1 <= len(files) <= 256:
        raise ValueError("Frozen model/configuration/source files must be declared.")
    names, paths = set(), set()
    for row in files:
        if (type(row) is not dict or set(row) != {"name", "path", "sha256"}
                or type(row["name"]) is not str or not 1 <= len(row["name"]) <= 160
                or type(row["path"]) is not str or row["name"] in names
                or row["path"] in paths):
            raise ValueError("Duplicate or invalid frozen file identity.")
        _sha256(row["sha256"])
        _relative_name(row["path"])
        names.add(row["name"])
        paths.add(row["path"])


def authenticate_method(method_manifest: Path, expected_sha256: str,
                        asset_root: Path, *, check_runtime: bool = True
                        ) -> tuple[dict, dict[str, Path]]:
    """Verify every declared byte before importing an adapter/loading weights.

    Factories remain trusted, frozen application code: their own source and all
    transitive inference dependencies must be included in ``files``. Checking
    hashes does not make arbitrary Python safe to execute.
    """
    raw = _regular(method_manifest, 1024 * 1024).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _sha256(expected_sha256):
        raise ValueError("Method manifest SHA-256 mismatch.")
    method = _json(raw)
    _method_schema(method)
    if method["implementation"] != implementation_identity():
        raise ValueError("Pipeline or selection implementation changed.")
    if check_runtime:
        runtime = method["runtime"]
        if runtime["python"] != platform.python_version():
            raise ValueError("Python version differs from the frozen runtime.")
        for name, version in runtime["packages"].items():
            try:
                actual = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError as exc:
                raise ValueError("A frozen runtime dependency is unavailable.") from exc
            if actual != version:
                raise ValueError("Package version differs from the frozen runtime.")
    root = _root(asset_root)
    files, inodes = {}, set()
    for row in method["files"]:
        path = _relative_file(root, row["path"], 8 * 1024 * 1024 * 1024)
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in inodes:
            raise ValueError("Duplicate model/configuration file alias.")
        inodes.add(identity)
        if file_sha256(path) != row["sha256"]:
            raise ValueError("Frozen model/configuration/source SHA-256 mismatch.")
        files[row["name"]] = path
    return method, files


def _source_rows(path: Path):
    with path.open("rb") as stream:
        first = stream.readline(MAX_LINE_BYTES + 1)
        if len(first) > MAX_LINE_BYTES:
            raise ValueError("Source header exceeds its size bound.")
        header = _json(first)
        if (set(header) not in (
                {"schema_version", "sequence_id", "frame_count"},
                {"schema_version", "sequence_id", "frame_count", "image_size"})
                or type(header["schema_version"]) is not int or header["schema_version"] != 1
                or type(header["frame_count"]) is not int
                or not 1 <= header["frame_count"] <= MAX_FRAMES
                or type(header["sequence_id"]) is not str
                or not 1 <= len(header["sequence_id"]) <= 160):
            raise ValueError("Invalid complete-sequence source header.")
        if "image_size" in header:
            size = header["image_size"]
            if (type(size) is not list or len(size) != 2
                    or any(type(x) is not int or x < 1 for x in size)
                    or size[0] * size[1] > MAX_IMAGE_PIXELS):
                raise ValueError("Invalid declared image dimensions.")
        yield header
        seen_paths = set()
        for position in range(header["frame_count"]):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line or len(line) > MAX_LINE_BYTES:
                raise ValueError("Missing or oversized source frame record.")
            row = _json(line)
            if (set(row) != {"position", "source_frame", "path", "sha256"}
                    or type(row["position"]) is not int or row["position"] != position
                    or type(row["source_frame"]) is not int or row["source_frame"] != position
                    or type(row["path"]) is not str or row["path"] in seen_paths):
                raise ValueError("Missing, duplicate or out-of-order source frame identity.")
            _sha256(row["sha256"])
            _relative_name(row["path"])
            seen_paths.add(row["path"])
            yield row
        if stream.read(1):
            raise ValueError("Source manifest has extra records beyond frame_count.")


def _decode_check(raw: bytes, expected_size: list[int] | None) -> None:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if (image.width * image.height > MAX_IMAGE_PIXELS
                    or getattr(image, "n_frames", 1) != 1):
                raise ValueError("Oversized or multi-frame source image.")
            if expected_size is not None and list(image.size) != expected_size:
                raise ValueError("Source dimensions differ from the committed header.")
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Corrupt or undecodable source image.") from exc


class _Selections:
    """Streaming argmax over the existing floor-boundary bins; earliest tie."""
    def __init__(self, n: int):
        self.n = n
        self.count = 0
        self.state = {}
        for percent in PERCENTS:
            k = exact_k(n, percent)
            self.state[percent] = {
                "k": k, "bins": bins(n, k), "bin": 0,
                "best": None, "selected": [],
            }

    def add(self, position: int, score: float) -> None:
        if (position != self.count or type(score) not in (int, float)
                or not math.isfinite(score)):
            raise ValueError("Incomplete or non-finite frame score stream.")
        for state in self.state.values():
            best = state["best"]
            if best is None or score > best[1]:
                state["best"] = (position, score)
            if position + 1 == state["bins"][state["bin"]][1]:
                state["selected"].append(state["best"][0])
                state["bin"] += 1
                state["best"] = None
        self.count += 1

    def result(self, method_id: str, source_sha: str, method_sha: str) -> dict:
        if self.count != self.n:
            raise ValueError("No selection may be sealed from an incomplete score stream.")
        budgets = []
        for percent, state in self.state.items():
            k, selected = state["k"], state["selected"]
            if len(selected) != k or len(set(selected)) != k:
                raise ValueError("A selector violated its exact-K contract.")
            budgets.append({"percent": percent, "k": k,
                            "uniform": uniform_midpoints(self.n, k),
                            "score_bin": selected})
        return {"schema_version": 1, "method_id": method_id,
                "roster_status": "provisional", "frame_count": self.n,
                "source_manifest_sha256": source_sha,
                "method_manifest_sha256": method_sha,
                "index_coordinate": "zero_based_decoded_frame_position",
                "selected_index_order": "chronological",
                "budgets": budgets}


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _observed_torch_settings(runtime: dict) -> dict | None:
    if "torch" not in runtime["packages"]:
        return None
    import torch
    settings = {
        "threads": torch.get_num_threads(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
    }
    if (settings["threads"] != runtime["threads"]
            or not settings["deterministic_algorithms"]
            or torch.is_deterministic_algorithms_warn_only_enabled()):
        raise ValueError("Frozen CPU scorer must use declared threads and deterministic algorithms.")
    return settings


def _inside_git_worktree(path: Path) -> bool:
    """Use Git's real discovery, including its normal filesystem boundary.

    An unrelated ancestor marker is not sufficient evidence of a checkout.
    The installed source checkout is also checked directly, so environment
    discovery settings cannot accidentally permit output in this repository.
    """
    destination = path.resolve()
    project = Path(__file__).resolve().parents[2]
    if (project / ".git").exists() and destination.is_relative_to(project):
        return True
    existing = destination
    while not existing.exists():
        existing = existing.parent
    if not existing.is_dir():
        existing = existing.parent
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_")}
    try:
        found = subprocess.run(
            ["git", "-C", str(existing), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Cannot verify that private output is outside a Git checkout.") from exc
    return found.returncode == 0


def run_sequence(source_manifest: Path, method_manifest: Path, source_root: Path,
                 asset_root: Path, output: Path, *, expected_source_sha256: str,
                 expected_method_sha256: str,
                 scorer_factory: Callable[[dict, Mapping[str, Path]],
                                          Callable[[Sequence[FrameInput]], Sequence[float]]]
                 ) -> dict:
    """Execute one provisional frozen method; errors leave no success seal.

    The authoritative source manifest defines the population. Directory glob
    order is never used. Equal-content images at different authenticated frame
    positions remain in the population and are counted in the receipt.
    """
    if _inside_git_worktree(output):
        raise ValueError("Private inference artifacts must stay outside Git checkouts.")
    output.mkdir(parents=True, exist_ok=False)
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    peak_before = _peak_rss_bytes()
    scored = 0
    try:
        source_sha = _sha256(expected_source_sha256)
        method_sha = _sha256(expected_method_sha256)
        _regular(source_manifest, MAX_MANIFEST_BYTES)
        shutil.copyfile(source_manifest, output / "source_manifest.jsonl")
        source = output / "source_manifest.jsonl"
        if file_sha256(source) != source_sha:
            raise ValueError("Source manifest SHA-256 mismatch.")
        method, files = authenticate_method(method_manifest, method_sha, asset_root)
        shutil.copyfile(method_manifest, output / "method_manifest.json")
        if file_sha256(output / "method_manifest.json") != method_sha:
            raise ValueError("Method manifest changed during authentication.")
        root = _root(source_root)
        # Validate the complete declared order/population before loading a model.
        rows = _source_rows(source)
        header = next(rows)
        seen_inodes, content_hashes = set(), set()
        duplicate_content = 0
        for row in rows:
            path = _relative_file(root, row["path"], MAX_IMAGE_BYTES)
            identity = (path.stat().st_dev, path.stat().st_ino)
            if identity in seen_inodes:
                raise ValueError("Duplicate source-file alias.")
            seen_inodes.add(identity)
            duplicate_content += row["sha256"] in content_hashes
            content_hashes.add(row["sha256"])
        del seen_inodes, content_hashes
        # Keep the authenticated contract separate from adapter-owned objects.
        # Reviewed Python is trusted, but accidental contract changes must fail.
        adapter_method, adapter_files = deepcopy(method), dict(files)
        contract = _canonical(method)

        def check_adapter_contract() -> None:
            if _canonical(adapter_method) != contract or adapter_files != files:
                raise ValueError("Frozen adapter changed its authenticated method or file mapping.")

        scorer = scorer_factory(adapter_method, adapter_files)
        check_adapter_contract()
        if not callable(scorer):
            raise ValueError("Frozen scorer factory did not return a callable.")
        torch_settings = _observed_torch_settings(method["runtime"])
        selections = _Selections(header["frame_count"])
        batch_size = method["runtime"]["batch_size"]
        pending: list[FrameInput] = []
        batches, maximum_batch = 0, 0
        score_start = time.perf_counter()
        with (output / "scores.jsonl").open("xb") as score_file:
            def flush() -> None:
                nonlocal scored, batches, maximum_batch
                check_adapter_contract()
                _observed_torch_settings(method["runtime"])
                batch = tuple(pending)
                values = list(scorer(batch))
                check_adapter_contract()
                _observed_torch_settings(method["runtime"])
                if len(values) != len(batch):
                    raise ValueError("Frozen scorer returned an incomplete batch.")
                for frame, value in zip(batch, values):
                    selections.add(frame.position, value)
                    score_file.write(_canonical({
                        "position": frame.position, "source_frame": frame.source_frame,
                        "source_sha256": frame.source_sha256, "score": float(value),
                    }))
                    scored += 1
                batches += 1
                maximum_batch = max(maximum_batch, len(pending))
                pending.clear()

            rows = _source_rows(source)
            next(rows)
            for row in rows:
                path = _relative_file(root, row["path"], MAX_IMAGE_BYTES)
                raw = path.read_bytes()
                if not 0 < len(raw) <= MAX_IMAGE_BYTES:
                    raise ValueError("Source file size changed during execution.")
                if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                    raise ValueError("Source frame SHA-256 mismatch.")
                _decode_check(raw, header.get("image_size"))
                pending.append(FrameInput(row["position"], row["source_frame"],
                                          row["path"], row["sha256"], raw))
                if len(pending) == batch_size:
                    flush()
            if pending:
                flush()
            score_file.flush()
            os.fsync(score_file.fileno())
        score_seconds = time.perf_counter() - score_start
        result = selections.result(method["method_id"], source_sha, method_sha)
        (output / "selections.json").write_bytes(_canonical(result))
        # Do not seal a run whose frozen inputs/code changed while it executed.
        authenticate_method(output / "method_manifest.json", method_sha, asset_root)
        if file_sha256(source) != source_sha:
            raise ValueError("Source manifest changed during execution.")
        check_adapter_contract()
        torch_settings = _observed_torch_settings(method["runtime"])
        elapsed = time.perf_counter() - wall_start
        receipt = {
            "schema_version": 1, "status": "complete", "method_id": method["method_id"],
            "roster_status": "provisional", "source_manifest_sha256": source_sha,
            "method_manifest_sha256": method_sha, "sequence_id": header["sequence_id"],
            "frame_count": header["frame_count"], "scored_frames": scored,
            "source_files_authenticated": scored, "duplicate_content_frames_retained": duplicate_content,
            "runtime": method["runtime"], "implementation": method["implementation"],
            "observed_torch_settings": torch_settings,
            "authenticated_files": method["files"], "batches": batches,
            "maximum_batch_frames": maximum_batch, "wall_seconds": elapsed,
            "scoring_and_decode_seconds": score_seconds,
            "frames_per_second_including_preflight": scored / elapsed,
            "frames_per_second_scoring_and_decode": scored / score_seconds,
            "cpu_seconds": time.process_time() - cpu_start,
            "process_peak_rss_bytes": _peak_rss_bytes(),
            "process_peak_rss_before_bytes": peak_before,
            "rss_scope": "process lifetime high-water mark; includes runtime and model",
            "platform": {"system": platform.system(), "machine": platform.machine()},
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "labels_read": False, "clinical_event_evaluator": "provisional_not_implemented",
        }
        (output / "receipt.json").write_bytes(_canonical(receipt))
        seal = {"schema_version": 1, "files": {
            name: {"sha256": file_sha256(output / name),
                   "size_bytes": (output / name).stat().st_size}
            for name in _ARTIFACTS
        }}
        for name in _ARTIFACTS:
            with (output / name).open("rb") as stream:
                os.fsync(stream.fileno())
        _fsync_directory(output)
        temporary_seal = output / "seal.pending"
        with temporary_seal.open("xb") as stream:
            stream.write(_canonical(seal))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_seal, output / "seal.json")
        _fsync_directory(output)
        seal_sha = file_sha256(output / "seal.json")
        verify_seal(output, seal_sha)
        return {"seal_sha256": seal_sha, "receipt": receipt}
    except BaseException as exc:
        (output / "seal.json").unlink(missing_ok=True)
        (output / "seal.pending").unlink(missing_ok=True)
        failure = {"schema_version": 1, "status": "failed", "sealed": False,
                   "scored_frames": scored, "error_type": type(exc).__name__,
                   "error": str(exc), "wall_seconds": time.perf_counter() - wall_start}
        (output / "failure.json").write_bytes(_canonical(failure))
        raise


def verify_seal(bundle: Path, expected_seal_sha256: str) -> dict:
    """Verify a private submission without images, weights or outcome labels."""
    bundle = _root(bundle)
    seal_path = _regular(bundle / "seal.json", 64 * 1024)
    raw = seal_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _sha256(expected_seal_sha256):
        raise ValueError("Seal SHA-256 differs from the independent commitment.")
    seal = _json(raw)
    if (set(seal) != {"schema_version", "files"}
            or type(seal["schema_version"]) is not int or seal["schema_version"] != 1
            or type(seal["files"]) is not dict or set(seal["files"]) != set(_ARTIFACTS)
            or {p.name for p in bundle.iterdir()} != {*_ARTIFACTS, "seal.json"}):
        raise ValueError("Unexpected or incomplete sealed artifact set.")
    for name, identity in seal["files"].items():
        path = _regular(bundle / name, MAX_MANIFEST_BYTES)
        if (type(identity) is not dict or set(identity) != {"sha256", "size_bytes"}
                or type(identity["size_bytes"]) is not int
                or path.stat().st_size != identity["size_bytes"]
                or file_sha256(path) != _sha256(identity["sha256"])):
            raise ValueError("A sealed artifact changed.")
    source_sha = seal["files"]["source_manifest.jsonl"]["sha256"]
    method_sha = seal["files"]["method_manifest.json"]["sha256"]
    method = _json((bundle / "method_manifest.json").read_bytes())
    _method_schema(method)
    source_rows = _source_rows(bundle / "source_manifest.jsonl")
    header = next(source_rows)
    selections = _Selections(header["frame_count"])
    with (bundle / "scores.jsonl").open("rb") as scores:
        for source in source_rows:
            line = scores.readline(MAX_LINE_BYTES + 1)
            if not line or len(line) > MAX_LINE_BYTES:
                raise ValueError("Incomplete sealed score stream.")
            row = _json(line)
            if (set(row) != {"position", "source_frame", "source_sha256", "score"}
                    or type(row["position"]) is not int or row["position"] != source["position"]
                    or type(row["source_frame"]) is not int or row["source_frame"] != source["source_frame"]
                    or row["source_sha256"] != source["sha256"]):
                raise ValueError("Sealed score/source identities do not align.")
            selections.add(row["position"], row["score"])
        if scores.read(1):
            raise ValueError("Extra sealed score records.")
    expected = selections.result(method["method_id"], source_sha, method_sha)
    if _json((bundle / "selections.json").read_bytes()) != expected:
        raise ValueError("Sealed selections differ from the exact frozen policies.")
    receipt = _json((bundle / "receipt.json").read_bytes())
    expected_torch = ({"threads": method["runtime"]["threads"],
                       "deterministic_algorithms": True}
                      if "torch" in method["runtime"]["packages"] else None)
    for key, value in {
        "schema_version": 1, "status": "complete", "method_id": method["method_id"],
        "roster_status": "provisional", "sequence_id": header["sequence_id"],
        "source_manifest_sha256": source_sha, "method_manifest_sha256": method_sha,
        "frame_count": header["frame_count"], "scored_frames": header["frame_count"],
        "source_files_authenticated": header["frame_count"],
        "runtime": method["runtime"], "implementation": method["implementation"],
        "observed_torch_settings": expected_torch,
        "authenticated_files": method["files"],
    }.items():
        if key not in receipt or _canonical(receipt[key]) != _canonical(value):
            raise ValueError("Inference receipt does not match sealed inputs.")
    return {"seal_sha256": expected_seal_sha256, "method_id": method["method_id"],
            "frame_count": header["frame_count"], "budgets": expected["budgets"]}
