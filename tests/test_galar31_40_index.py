"""Synthetic-only regression tests for bounded Galar 31–40 source index gate."""
from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import probe_galar_archive as probe
import audit_galar31_40_index as gate


def catalog():
    p = probe.APPROVED_SOURCES["fitting-31-40"]
    return {"id": 25304616, "version": 2, "files": [{
        "id": p["id"], "name": p["name"], "size": p["size"],
        "supplied_md5": p["md5"], "computed_md5": p["md5"],
        "download_url": p["url"], "is_link_only": False,
    }]}


def receipt():
    p = probe.APPROVED_SOURCES["fitting-31-40"]
    return {
        "record_type": p["receipt_type"], "official_file_id": p["id"],
        "official_full_archive_bytes": p["size"],
        "official_full_archive_md5_expected_not_verified": p["md5"],
        "actual_index_only_bytes_transferred": 34,
        "full_archive_downloaded": False, "pixels_acquired": 0,
        "no_automatic_large_transfer": True,
        "parts": [
            {"name": "signature-header.bin", "offset": 0,
             "length": 32, "sha256": "a"*64},
            {"name": "next-header.bin", "offset": p["size"]-2,
             "length": 2, "sha256": "b"*64},
        ],
    }


def synthetic_listing(*, omit=None, extra=""):
    rows = []
    for exam in sorted(gate.EXAMS):
        if exam == omit:
            continue
        step = gate.STRIDE[exam]
        for offset, packed in [(0, str(150+exam)), (step, "")]:
            rows.append(
                f"Path = demo/{exam}/frame_{exam*10+offset:07d}.PNG\n"
                f"Size = 150\nPacked Size = {packed}\n"
                f"Folder = -\nBlock = {exam-31}"
            )
    return "7z synthetic metadata\n----------\n" + "\n\n".join(rows) + extra


def test_catalog_pinned_and_fails_closed():
    p = probe.validate_official_catalog(catalog(), "fitting-31-40")
    assert p["id"] == 44755700
    assert p["size"] == 69_219_317_963
    assert p["md5"] == "3bd4f9c9132e32d1a15d1ead5d96d0e2"
    assert probe.MAX_TRANSFER == 8*1024*1024
    probe.RangeClient(p["url"], p["size"], source="fitting-31-40")
    with pytest.raises(ValueError):
        probe.RangeClient(p["url"], p["size"]+1, source="fitting-31-40")
    with pytest.raises(ValueError):
        probe.RangeClient("https://example.com/evil.7z", p["size"], source="fitting-31-40")
    for key,val in (
        ("size", 123), ("name", "evil.7z"),
        ("supplied_md5", "0"*32), ("computed_md5", "0"*32),
        ("download_url", "https://evil.com/evil.7z"),
        ("is_link_only", True),
    ):
        bad = catalog()
        bad["files"][0][key] = val
        with pytest.raises(ValueError):
            probe.validate_official_catalog(bad, "fitting-31-40")


def test_private_index_only_summary_is_blocked_when_source_counts_mismatch():
    result = gate.audit(synthetic_listing(), receipt())
    assert result["decision"] == "BLOCKED_INDEX_COUNT_MISMATCH"
    assert result["block_count"] == 10
    assert set(result["examinations"]) == {str(x) for x in range(31, 41)}
    assert result["examinations"]["31"]["native_export_stride"] == 5
    assert result["examinations"]["39"]["native_export_stride"] == 1
    assert result["examinations"]["40"]["required_whole_solid_blocks"] == [9]
    assert result["source_image_pixels_acquired"] == 0
    assert result["patient_independence_verified"] is False
    assert result["complete_clinical_outcomes_verified"] is False
    assert result["original_full_source_md5_verified"] is False
    assert "frame_" not in str(result)


@pytest.mark.parametrize("path,message", [
    ("demo/31/frame_0000310.PNG", "Duplicate"),
    ("demo/61/frame_0000061.PNG", "outside selected"),
    ("demo/31/unknown.png", "Unexpected source"),
    ("demo/31/frame_0000311.PNG", "native stride"),
])
def test_untrusted_extra_member_fails_closed(path,message):
    extra = ("\n\nPath = "+path+"\nSize = 1\nPacked Size =\nFolder = -\nBlock = 0")
    with pytest.raises(ValueError, match=message):
        gate.audit(synthetic_listing(extra=extra), receipt())


def test_incomplete_group_fails_closed():
    with pytest.raises(ValueError, match="missing"):
        gate.audit(synthetic_listing(omit=40), receipt())


@pytest.mark.parametrize("key,value", [
    ("record_type", "galar-11-20-7z-index-only-v1"),
    ("official_file_id", 44725302),
    ("official_full_archive_bytes", 10),
    ("official_full_archive_md5_expected_not_verified", "0"*32),
    ("full_archive_downloaded", True),
    ("pixels_acquired", 1),
    ("no_automatic_large_transfer", False),
    ("actual_index_only_bytes_transferred", 10*1024*1024),
])
def test_receipt_violations_never_approved(key,value):
    r = receipt()
    r[key] = value
    with pytest.raises(ValueError):
        gate.audit(synthetic_listing(), r)


def test_missing_block_size_and_offset_mismatch_refused():
    listing = synthetic_listing()
    with pytest.raises(ValueError, match="Missing solid block"):
        gate.audit(listing.replace("Packed Size = 181", "Packed Size =", 1), receipt())
    r = receipt()
    r["parts"][0]["length"] = 31
    with pytest.raises(ValueError, match="accounting"):
        gate.audit(listing, r)


def test_no_read_of_nonconsecutive_native_export_grid():
    # Source 31 native stride 5; index step 6 must fail.
    listing = synthetic_listing().replace(
        "demo/31/frame_0000315.PNG", "demo/31/frame_0000316.PNG")
    with pytest.raises(ValueError, match="native stride"):
        gate.audit(listing, receipt())
