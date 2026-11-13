"""Check Git-tracked public source for prohibited private research file formats.

This is a conservative accidental-disclosure guard, not a substitute for
reviewing file contents, Git history, external Actions artifacts or logs.
It never reads medical input directories or downloads research material.
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path, PurePosixPath
import subprocess

MAX_TRACKED_FILE_BYTES = 2 * 1024 * 1024

# Manually inspected synthetic UI captures from browser smoke run 43461132951.
# Desktop is cropped to its first 1180 pixels; the comparison is unaltered.
# A path alone never permits a replacement image: exact bytes must match.
REVIEWED_SYNTHETIC_SCREENSHOTS = {
    "docs/images/viewer-desktop.png": "cbda5fa7c0154a2c8c8f9eda319264ea1a4f59deab072185950f0297f080516b",
    "docs/images/synthetic-policy-comparison.png": "d80f5c298e9dc52a35177c644c1f408cdcf6e8bc0c37351480deaf7ccac9b462",
}

PRIVATE_SUFFIXES = frozenset({
    ".7z", ".bmp", ".bz2", ".ckpt", ".csv", ".db", ".dcm", ".dicom",
    ".feather", ".gif", ".gz", ".h5", ".hdf5", ".jpeg", ".jpg",
    ".key", ".npy", ".npz", ".onnx", ".p12", ".parquet", ".pem",
    ".pfx", ".pickle", ".pkl", ".png", ".pt", ".pth", ".safetensors",
    ".sqlite", ".sqlite3", ".tar", ".tgz", ".tif", ".tiff", ".tsv",
    ".webp", ".xz", ".zip", ".zst",
})

PRIVATE_DIRECTORY_SEGMENTS = frozenset({
    "checkpoints", "credentials", "datasets", "downloads", "exports",
    "images", "labels", "model_outputs", "patient_data", "predictions",
    "private", "private_outputs", "raw_data", "runs", "secrets",
    "uploads", "weights", "workspace",
})

BINARY_PREFIXES = (
    b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"PK\x03\x04",
    b"7z\xbc\xaf\x27\x1c", b"SQLite format 3\x00",
)


class PublicSourceBoundaryError(RuntimeError):
    """The public Git checkout cannot be certified by this conservative gate."""


def check_tracked_file(root: Path, relative_path: str) -> list[str]:
    """Return generic reasons; never echo potentially sensitive filenames."""
    relative = PurePosixPath(relative_path)
    reasons: list[str] = []
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return ["invalid repository-relative path"]
    segments = [part.casefold() for part in relative.parts]
    name = segments[-1]
    if set(segments[:-1]) & PRIVATE_DIRECTORY_SEGMENTS:
        reasons.append("private research directory")
    if name == ".env" or name.startswith(".env."):
        reasons.append("environment credential filename")
    if PurePosixPath(name).suffix in PRIVATE_SUFFIXES:
        reasons.append("blocked research, archive, model, credential or binary suffix")

    path = root.joinpath(*relative.parts)
    if path.is_symlink():
        reasons.append("tracked symlink")
        return reasons
    if not path.is_file():
        reasons.append("tracked file absent or not a regular file")
        return reasons
    if path.stat().st_size > MAX_TRACKED_FILE_BYTES:
        reasons.append("oversized tracked file requires separate privacy review")
        return reasons

    if relative_path in REVIEWED_SYNTHETIC_SCREENSHOTS:
        if hashlib.sha256(path.read_bytes()).hexdigest() == REVIEWED_SYNTHETIC_SCREENSHOTS[relative_path]:
            return []
        return ["reviewed synthetic screenshot hash mismatch"]

    with path.open("rb") as source:
        first_bytes = source.read(4096)
    if any(first_bytes.startswith(prefix) for prefix in BINARY_PREFIXES):
        reasons.append("binary medical image, archive, or database signature")
    if b"\x00" in first_bytes:
        reasons.append("embedded NUL in nominal public source")
    return reasons


def git_tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--full-name"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise PublicSourceBoundaryError("Cannot enumerate Git-tracked files; fail closed.")
    paths = [os.fsdecode(p) for p in result.stdout.split(b"\x00") if p]
    if not paths:
        raise PublicSourceBoundaryError("Empty tracked-file manifest; fail closed.")
    return paths


def check_repository(root: Path) -> tuple[int, list[str]]:
    paths = git_tracked_paths(root)
    failures: list[str] = []
    for relative in paths:
        failures.extend(check_tracked_file(root, relative))
    return len(paths), failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        checked, failures = check_repository(root)
    except PublicSourceBoundaryError as exc:
        print(f"PUBLIC SOURCE PRIVACY GATE FAILED: {exc}")
        return 1
    if failures:
        print(f"PUBLIC SOURCE PRIVACY GATE FAILED: {len(failures)} violations in {checked} tracked files.")
        for reason in sorted(set(failures)):
            print(f"- {reason}")
        print("No source paths or file contents printed; review locally before publication.")
        return 1
    print(f"Public source boundary: {checked} tracked paths passed format/path checks.")
    print("This does not validate content, history, CI artifacts, or medical efficacy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
