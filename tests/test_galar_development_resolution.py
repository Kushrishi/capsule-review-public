"""All tests use synthetic PNG headers, synthetic archives and synthetic identities only."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import zipfile
import zlib

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_galar_development_resolution.py"
spec = importlib.util.spec_from_file_location("audit_galar_development_resolution", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def png(width=512, height=512):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return mod.PNG_SIG + struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk)) + b"synthetic body"


def make_case(tmp_path, images=((21, 55), (22, 65)), corrupt=False, path_override=None):
    source = tmp_path / "private"
    source.mkdir()
    archive_name = "synthetic-source.zip"
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as inner:
        for idx, (exam, frame) in enumerate(images):
            name = path_override if idx == 0 and path_override else f"images/{exam:03d}/frame_{frame:06d}.PNG"
            b = bytearray(png())
            if corrupt and idx == 0: b[29] ^= 1
            inner.writestr(name, b)
    outer_path = source / archive_name
    with zipfile.ZipFile(outer_path, "w") as outer:
        outer.writestr("source.zip", raw.getvalue())
    deps = [{"archive": archive_name, "sha256": mod.sha256_path(outer_path), "size_bytes": outer_path.stat().st_size}]
    za = tmp_path / "private-audit.zip"
    with zipfile.ZipFile(za, "w") as archive:
        archive.writestr("PRIVATE_selected_source_metadata.json", json.dumps([{"exam": e, "frame": f, "blood": 1} for e, f in images]))
        archive.writestr("PRIVATE_source_archive_dependencies.json", json.dumps(deps))
    options = {"expected_audit_sha": mod.sha256_path(za), "selected_n": len(images),
               "exams": tuple(sorted({e for e, _ in images})), "archive_names": (archive_name,),
               "expected_dev_n": len(set(images)), "repo_root": SCRIPT.parents[2]}
    return za, source, options, outer_path


def test_good_replay(tmp_path):
    a, s, kw, _ = make_case(tmp_path)
    public, private = mod.audit(a, s, **kw)
    assert public["original_png_header_count"] == 2
    assert public["every_selected_image_identity_reconciled"] is True
    assert public["per_exam"][0]["native_dimensions"] == [{"width": 512, "height": 512, "count": 1}]
    assert len(private["archive_receipts"]) == 1
    assert "blood" not in json.dumps(public)


def test_tampered_outer_archive(tmp_path):
    a, s, kw, outer = make_case(tmp_path)
    outer.write_bytes(outer.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="archive size/SHA"):
        mod.audit(a, s, **kw)


def test_tampered_manifest(tmp_path):
    a, s, kw, _ = make_case(tmp_path)
    a.write_bytes(a.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="audit SHA"):
        mod.audit(a, s, **kw)


def test_duplicate_source_identity(tmp_path):
    a, s, kw, _ = make_case(tmp_path, images=((21, 55), (21, 55)))
    with pytest.raises(ValueError, match="Duplicate private source"):
        mod.audit(a, s, **kw)


def test_wrong_source_identity(tmp_path):
    a, s, kw, _ = make_case(tmp_path, path_override="images/023/frame_000055.PNG")
    with pytest.raises(ValueError, match="Unexpected or repeated"):
        mod.audit(a, s, **kw)


def test_png_header_crc_tamper(tmp_path):
    a, s, kw, _ = make_case(tmp_path, corrupt=True)
    with pytest.raises(ValueError, match="CRC"):
        mod.audit(a, s, **kw)


def test_reject_wrong_png_member_path(tmp_path):
    a, s, kw, _ = make_case(tmp_path, path_override="images/../../frame_000055.PNG")
    with pytest.raises(ValueError, match="Noncanonical"):
        mod.audit(a, s, **kw)


def test_reject_bad_png_signature():
    bad = b"notpng!!" + png()[8:]
    with pytest.raises(ValueError, match="Noncanonical"):
        mod.ihdr_dimensions(bad)


def test_reject_missing_original_member(tmp_path):
    a, s, kw, _ = make_case(tmp_path, images=((21, 55), (22, 65)))
    # Manufacture a pinned private audit that expects an additional identity.
    from zipfile import ZIP_DEFLATED
    with zipfile.ZipFile(a) as z:
        sources = json.loads(z.read("PRIVATE_selected_source_metadata.json"))
        deps = z.read("PRIVATE_source_archive_dependencies.json")
    sources.append({"exam": 22, "frame": 70, "blood": 1})
    with zipfile.ZipFile(a, "w", ZIP_DEFLATED) as z:
        z.writestr("PRIVATE_selected_source_metadata.json", json.dumps(sources))
        z.writestr("PRIVATE_source_archive_dependencies.json", deps)
    kw.update(expected_audit_sha=mod.sha256_path(a), selected_n=3, expected_dev_n=3)
    with pytest.raises(ValueError, match="Missing original source identities"):
        mod.audit(a, s, **kw)


def test_reject_private_source_inside_public_repo(tmp_path):
    bad = SCRIPT.parents[2] / "data" / "private-archive.zip"
    with pytest.raises(ValueError, match="outside the public repository"):
        mod.private_path(bad, SCRIPT.parents[2])


def test_valid_ihdr_encoding():
    assert mod.ihdr_dimensions(png(336, 336)[:33]) == (336, 336, 8, 2)
    assert mod.ihdr_dimensions(png(512, 512)[:33]) == (512, 512, 8, 2)

INDEPENDENT_SCRIPT = SCRIPT.parents[0] / "independent_galar_resolution_replay.py"
ind_spec = importlib.util.spec_from_file_location("independent_galar_resolution_replay", INDEPENDENT_SCRIPT)
ind_mod = importlib.util.module_from_spec(ind_spec)
sys.modules[ind_spec.name] = ind_mod
ind_spec.loader.exec_module(ind_mod)


def test_independent_replay_good_and_tampered_aggregate(tmp_path):
    a, s, kw, _ = make_case(tmp_path)
    published, _private = mod.audit(a, s, **kw)
    out = tmp_path / "aggregate.json"
    out.write_text(json.dumps(published))
    arguments = {"pinned_audit": kw["expected_audit_sha"], "all_selected": 2,
                 "dev_selected": 2, "archive_names": kw["archive_names"], "exams": kw["exams"],
                 "repo_root": SCRIPT.parents[2]}
    result = ind_mod.replay(a, s, out, **arguments)
    assert result["status"] == "PASS"
    published["per_exam"][0]["native_dimensions"][0]["width"] = 999
    out.write_text(json.dumps(published))
    with pytest.raises(ValueError, match="dimensions/encoding"):
        ind_mod.replay(a, s, out, **arguments)
