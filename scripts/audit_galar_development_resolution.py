"""Read-only, fail-closed native-resolution audit of already verified Galar selected images.

This is NOT a patient/device identifier, an exhaustive video audit, a model
training tool, or an independent evaluation. Source archives and manifests stay
private. Only aggregate counts and anonymous dimensions may leave that boundary.

Example:
 python scripts/audit_galar_development_resolution.py \
   --private-audit-zip /private/Capsule_Review_Private_Development_Source_Audit_20261105.zip \
   --private-archives /private/retained-galar-images \
   --aggregate-output /private/source_resolution_aggregate.json
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib

FROZEN_AUDIT_ZIP_SHA256 = "5cf828dd0288364bfe0bb2a5e3a6615b9e5ddaac91dec51b1a7765923fd04709"
EXAMS = (21, 22, 23, 24, 25, 27, 29, 30)
SOURCE_SELECTED_N = 11147
EXPECTED_EXAM_N = 7051
ARCHIVES = (
    "galar-exam21-verified-frames-private.zip",
    "galar-negative-22-24-verified-frames-private.zip",
    "galar-exam23-verified-frames-private.zip",
    "galar-exam25-verified-frames-private.zip",
    "galar-exam27-verified-frames-private.zip",
    "galar-exam29-verified-frames-private.zip",
    "galar-exam30-verified-frames-private.zip",
)
PNG_PATH = re.compile(r"images/(\d{3})/frame_(\d{6})\.PNG\Z")
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_path(path: Path, repo_root: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(repo_root.resolve()):
        raise ValueError("Private source input must be outside the public repository")
    return resolved


def ihdr_dimensions(prefix: bytes) -> tuple[int, int, int, int]:
    """Validate 33-byte PNG IHDR including its own CRC (not a full PNG decode)."""
    if len(prefix) != 33 or prefix[:8] != PNG_SIG or prefix[8:16] != b"\x00\x00\x00\rIHDR":
        raise ValueError("Noncanonical PNG/IHDR header")
    expected_crc = int.from_bytes(prefix[29:33], "big")
    if zlib.crc32(prefix[12:29]) != expected_crc:
        raise ValueError("PNG IHDR CRC mismatch")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", prefix[16:29])
    if width <= 0 or height <= 0 or width > 32768 or height > 32768:
        raise ValueError("Invalid native PNG dimensions")
    if compression != 0 or filtering != 0 or interlace not in (0, 1) or bit_depth not in (1, 2, 4, 8, 16) or color_type not in (0, 2, 3, 4, 6):
        raise ValueError("Invalid PNG IHDR encoding")
    return width, height, bit_depth, color_type


def audit(
    audit_zip: Path,
    archives_dir: Path,
    *,
    expected_audit_sha: str = FROZEN_AUDIT_ZIP_SHA256,
    selected_n: int = SOURCE_SELECTED_N,
    exams: tuple[int, ...] = EXAMS,
    archive_names: tuple[str, ...] = ARCHIVES,
    expected_dev_n: int = EXPECTED_EXAM_N,
    repo_root: Path | None = None,
) -> tuple[dict, dict]:
    repo = repo_root or Path(__file__).resolve().parents[1]
    audit_zip = private_path(audit_zip, repo)
    archives_dir = private_path(archives_dir, repo)
    if sha256_path(audit_zip) != expected_audit_sha:
        raise ValueError("Previously sealed source audit SHA mismatch")
    with zipfile.ZipFile(audit_zip) as z:
        selected = json.loads(z.read("PRIVATE_selected_source_metadata.json"))
        dependencies = json.loads(z.read("PRIVATE_source_archive_dependencies.json"))
    if len(selected) != selected_n:
        raise ValueError("Previously verified selected-source count changed")
    expected = set()
    expected_by_exam = Counter()
    for item in selected:
        e, f = item["exam"], item["frame"]
        if not isinstance(e, int) or not isinstance(f, int) or f < 0:
            raise ValueError("Malformed source manifest identity")
        if e in exams:
            key = e, f
            if key in expected:
                raise ValueError("Duplicate private source-manifest identity")
            expected.add(key)
            expected_by_exam[e] += 1
    if len(expected) != expected_dev_n or set(expected_by_exam) != set(exams):
        raise ValueError("Selected development source identity population changed")
    by_name = {d["archive"]: d for d in dependencies}
    if len(by_name) != len(dependencies) or any(n not in by_name for n in archive_names):
        raise ValueError("Missing/duplicate pinned original source archive receipts")

    observed = set()
    sizes = defaultdict(Counter)
    encodings = defaultdict(Counter)
    private_receipts = []
    for archive in archive_names:
        dep = by_name[archive]
        source = private_path(archives_dir / archive, repo)
        if source.stat().st_size != dep["size_bytes"] or sha256_path(source) != dep["sha256"]:
            raise ValueError("Retained private source archive size/SHA mismatch")
        with zipfile.ZipFile(source) as outer:
            nested_names = [n for n in outer.namelist() if n.lower().endswith(".zip")]
            if len(nested_names) != 1:
                raise ValueError("Ambiguous original nested archive structure")
            inner_bytes = outer.read(nested_names[0])  # checks outer nested member CRC
        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as nested:
            members = [m for m in nested.infolist() if m.filename.upper().endswith(".PNG")]
            if not members:
                raise ValueError("No original source PNG members found")
            for member in members:
                match = PNG_PATH.fullmatch(member.filename)
                if match is None or member.is_dir():
                    raise ValueError("Noncanonical original source PNG path")
                key = int(match.group(1)), int(match.group(2))
                if key not in expected or key in observed:
                    raise ValueError("Unexpected or repeated original source identity")
                observed.add(key)
                with nested.open(member) as handle:
                    header = handle.read(33)
                width, height, bit_depth, color_type = ihdr_dimensions(header)
                sizes[key[0]][(width, height)] += 1
                encodings[key[0]][(bit_depth, color_type)] += 1
        private_receipts.append({"archive": archive, "size_bytes": dep["size_bytes"], "sha256": dep["sha256"], "selected_members": len(members)})
    if observed != expected:
        raise ValueError("Missing original source identities")
    if any(sum(sizes[e].values()) != expected_by_exam[e] for e in exams):
        raise ValueError("Wrong exact examination image count")
    report = {
        "audit": "Galar selected-development original PNG IHDR dimension check",
        "scope": "Eight previously device-unclassified, already-inspected source examinations; not full video",
        "date_utc": "2026-11-10",
        "pinned_private_original_source_archive_count": len(archive_names),
        "original_png_header_count": len(observed),
        "pinned_private_archive_hashes_match": True,
        "every_selected_image_identity_reconciled": True,
        "native_header_crc_verified": True,
        "png_headers_only_not_full_image_redecode_this_audit": True,
        "per_exam": [
            {"exam": e, "selected_image_count": expected_by_exam[e],
             "native_dimensions": [
                 {"width": k[0], "height": k[1], "count": v} for k, v in sorted(sizes[e].items())
             ], "png_encodings": [
                 {"bit_depth": k[0], "color_type": k[1], "count": v} for k, v in sorted(encodings[e].items())
             ]} for e in sorted(exams)
        ],
        "exact_device_system_authenticated_for_these_eight": False,
        "patient_group_id_authenticated_for_these_eight": False,
        "collection_site_authenticated_for_these_eight": False,
        "unknown_outside_selected_source_images_remains_unknown": True,
        "qualified_new_patient_independent_experiment": False,
        "decision": "SOURCE_RESOLUTION_PASS__PATIENT_DEVICE_SITE_GROUP_GATE_UNRESOLVED",
        "privacy": "aggregate-only; no per-image source ID, pixel, label, individual score or patient attribute",
    }
    private = {"sealed_source_audit_sha256": expected_audit_sha, "archive_receipts": private_receipts,
               "published_aggregate_sha256": hashlib.sha256((json.dumps(report, sort_keys=True, indent=2) + "\n").encode()).hexdigest(),
               "source_images_redecoded_now": 0, "source_png_IHDR_headers_checked": len(observed)}
    return report, private


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-audit-zip", required=True, type=Path)
    parser.add_argument("--private-archives", required=True, type=Path)
    parser.add_argument("--aggregate-output", required=True, type=Path)
    parser.add_argument("--private-receipt-output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for arg in (args.aggregate_output, args.private_receipt_output):
        if arg.exists():
            parser.error("Refusing to overwrite existing evidence")
    if args.private_receipt_output.resolve().is_relative_to(root.resolve()):
        parser.error("Private receipts must stay outside the public repository")
    aggregate, private = audit(args.private_audit_zip, args.private_archives, repo_root=root)
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_receipt_output.write_text(json.dumps(private, sort_keys=True, indent=2) + "\n")
    args.aggregate_output.write_text(json.dumps(aggregate, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"decision": aggregate["decision"], "source_archives": len(ARCHIVES), "png_headers": aggregate["original_png_header_count"]}))


if __name__ == "__main__":
    main()
