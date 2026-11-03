"""Synthetic source-index tests for the locked reviewer interval evidence protocol.

No original Galar labels, medical images or private manifests are included.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from capsule_review import interval_evidence as m


EXAM = 23  # Allowed fitting source ID, but all the test frame IDs are synthetic.
FRAMES = (5, 10, 20, 30, 40, 50, 60, 65)
LABELS = {5: 0, 10: 0, 15: 1, 20: 1, 25: 0, 30: 0, 35: 1,
          40: 0, 45: 1, 50: 1, 55: 1, 60: 0, 65: 0}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_bytes(n: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (n % 255, n * 2 % 255, 35)).save(buf, format="PNG")
    return buf.getvalue()


def sample(interval: bool = True, explicit_positive: bool = True):
    """Source runs: (15,20), (35), and (45,50,55); only two represented in import."""
    labels = [{"frame": frame, "blood": str(blood)} for frame, blood in LABELS.items()]
    imported, receipt, pixel = [], [], {}
    for pos, frame in enumerate(FRAMES):
        png = image_bytes(frame)
        display = digest(png)
        original = digest(f"synthetic original {frame}".encode())
        pixel[pos] = png
        imported.append({"position": pos, "source_index": frame,
                         "source_sha256": original, "display_sha256": display,
                         "filename": f"frame_{frame:06d}.PNG"})
        receipt.append({"exam": EXAM, "frame": frame,
                        "filename": f"frame_{frame:06d}.PNG", "blood": LABELS[frame],
                        "source_image_sha256": original, "source_bytes": 300,
                        "reference_uniform": 1, "fit_enriched": 0})
    study_id = "local-software-test"
    sha = digest(b"synthetic source manifest only")
    manifest = {"schema_version": 1, "study_id": study_id, "synthetic": False,
                "manifest_sha256": sha, "frames": imported}
    intervals = ([{"id": 1, "start_position": 1, "end_position": 6,
                   "start_source_index": FRAMES[1], "end_source_index": FRAMES[6],
                   "note": "Synthetic researcher span; no lesion claim."}] if interval else [])
    selected = [1, 6] if interval else []
    if explicit_positive:
        selected.append(2)
    review_frames = []
    for pos in sorted(set(selected)):
        original = imported[pos]
        review_frames.append({"position": pos, "source_index": original["source_index"],
                              "source_sha256": original["source_sha256"],
                              "display_sha256": original["display_sha256"],
                              "source_filename": original["filename"],
                              "image": f"images/frame_{pos:06d}.png",
                              "interval_boundary": interval and pos in {1, 6},
                              "review": {"revision": 1 if pos == 2 else 0,
                                         "bookmarked": False,
                                         "note": "Synthetic positive-image reviewer note" if pos == 2 else "",
                                         "label": ""}})
    review = {"schema_version": 1, "application": "capsule-review",
              "study": {"id": study_id, "manifest_sha256": sha,
                        "frame_count": len(imported), "source": "Synthetic fixture"},
              "frames": review_frames,
              "intervals": intervals,
              "interval_history": ([{"interval_id": 1, "action": "created", "start_position": 1,
                                     "end_position": 6, "note": "Synthetic researcher span; no lesion claim.", "created_at": "2026-11-02"}]
                                   if interval else []),
              "review_history": []}
    return review, manifest, receipt, labels, pixel


def make_zip(path: Path, review: dict, pixel: dict[int, bytes], *, extra=False, tamper=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("review.json", json.dumps(review))
        z.writestr("review.html", "<p>Synthetic software test only</p>")
        for item in review["frames"]:
            pos = item["position"]
            data = b"tampered" if tamper == pos else pixel[pos]
            z.writestr(item["image"], data)
        if extra:
            z.writestr("images/unapproved.png", b"not allowed")


def test_source_run_segmentation_preserves_unknown_and_original_stride():
    source = [{"frame": frame, "blood": str(LABELS[frame])} for frame in LABELS]
    runs, hits = m.segment_positive_runs(source)
    assert len(runs) == 3
    assert [x["frames"] for x in runs] == [(15, 20), (35,), (45, 50, 55)]
    assert hits == {15: 0, 20: 0, 35: 1, 45: 2, 50: 2, 55: 2}
    broken = [{"frame": 5, "blood": "1"}, {"frame": 10, "blood": ""},
              {"frame": 15, "blood": "1"}, {"frame": 25, "blood": "1"}]
    parts, _ = m.segment_positive_runs(broken)
    assert len(parts) == 3
    with pytest.raises(ValueError):
        m.segment_positive_runs([{"frame": 10, "blood": "0"}, {"frame": 10, "blood": "1"}])


def test_source_verified_direct_evidence_never_substitutes_interval_overlap():
    review, manifest, receipt, rows, _ = sample()
    result = m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    assert result["source_annotation_rows"] == 13
    assert result["source_positive_annotation_runs"] == 3
    assert result["source_blood_positive_rows"] == 6
    assert result["imported_reference_images"] == 8
    assert result["imported_positive_annotated_images"] == 2
    assert result["imported_representable_positive_runs"] == 2
    assert result["selected_export_images"] == 3
    assert result["selected_export_positive_images"] == 1
    assert result["direct_selected_positive_annotation_runs"] == 1
    assert result["direct_selected_source_run_fraction"] == pytest.approx(1 / 3, abs=1e-8)
    assert result["explicit_bookmark_or_note_selected_images"] == 1
    assert result["explicit_bookmark_or_note_positive_annotation_runs"] == 1
    assert result["interval_boundary_images"] == 2
    assert result["interval_boundary_positive_annotation_runs"] == 0
    assert result["reviewer_marked_image_intervals"] == 1
    assert result["span_overlapped_source_positive_runs"] == 3
    assert result["span_overlapped_without_direct_selected_evidence"] == 2
    assert sum(x["direct_selected_export_runs"] for x in result["source_run_length_strata"]) == 1
    assert result["source_provenance"]["original_source_png_pixel_bytes_not_rehashed_in_this_audit"] is True
    assert all("frames" not in row for row in result["source_run_length_strata"])
    out = json.dumps(result)
    assert "Synthetic researcher span" not in out
    assert "source_image_sha256" not in out
    assert '"filename"' not in out


def test_span_overlaps_with_zero_exported_positive_images_are_not_hits():
    review, manifest, receipt, labels, _ = sample(explicit_positive=False)
    report = m.evaluate_interval_evidence(review, manifest, receipt, labels, exam=EXAM)
    assert report["selected_export_images"] == 2
    assert report["selected_export_positive_images"] == 0
    assert report["direct_selected_positive_annotation_runs"] == 0
    assert report["span_overlapped_source_positive_runs"] == 3
    assert report["span_overlapped_without_direct_selected_evidence"] == 3


def test_negative_labelled_exam_has_undefined_run_fraction_and_recorded_workload():
    review, manifest, receipt, labels, _ = sample()
    for row in receipt:
        row["blood"] = 0
    for row in labels:
        row["blood"] = "0"
    report = m.evaluate_interval_evidence(review, manifest, receipt, labels, exam=EXAM)
    assert report["source_positive_annotation_runs"] == 0
    assert report["direct_selected_source_run_fraction"] is None
    assert report["selected_export_images"] == 3
    assert report["selected_export_positive_images"] == 0
    assert report["source_run_length_strata"][0]["full_source_annotation_runs"] == 0


def test_source_verification_rejects_enrichment_identity_and_label_changes():
    review, manifest, receipt, rows, _ = sample()
    receipt[1]["reference_uniform"] = 0
    with pytest.raises(ValueError, match="label-blind reference"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    receipt[1]["reference_uniform"] = 1
    receipt[1]["source_image_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original PNG identity"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    receipt[1]["source_image_sha256"] = manifest["frames"][1]["source_sha256"]
    receipt[1]["blood"] = 1
    with pytest.raises(ValueError, match="corrected source blood"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)


def test_interval_and_export_tampering_refused_before_aggregate():
    review, manifest, receipt, rows, _ = sample()
    review["intervals"][0]["end_source_index"] = 999
    with pytest.raises(ValueError, match="source IDs"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    review, manifest, receipt, rows, _ = sample()
    review["frames"][0]["interval_boundary"] = False
    with pytest.raises(ValueError, match="boundary membership"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    review, manifest, receipt, rows, _ = sample()
    review["frames"][0]["source_index"] = 999
    with pytest.raises(ValueError, match="does not match"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    review, manifest, receipt, rows, _ = sample()
    manifest["synthetic"] = True
    with pytest.raises(ValueError, match="identities do not match"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    with pytest.raises(ValueError, match="Reserved"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=11)
    with pytest.raises(ValueError, match="Reserved"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=61)


def test_review_zip_integrity_detects_unlisted_and_changed_exported_images(tmp_path):
    review, _, _, _, pixels = sample()
    path = tmp_path / "review.zip"
    make_zip(path, review, pixels)
    assert m.read_review_export(path)["frames"] == review["frames"]
    path.unlink()
    make_zip(path, review, pixels, tamper=2)
    with pytest.raises(ValueError, match="SHA-256"):
        m.read_review_export(path)
    path.unlink()
    make_zip(path, review, pixels, extra=True)
    with pytest.raises(ValueError, match="Extra or unlisted"):
        m.read_review_export(path)


def test_one_allowed_member_of_mock_galar_zip_only_and_no_reserved_read(tmp_path, monkeypatch):
    text = "frame,blood\n" + "".join(f"{frame},{LABELS[frame]}\n" for frame in LABELS)
    archive = tmp_path / "corrected-labels.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("23.csv", text)
        z.writestr("11.csv", "unopened private source fixture")
        z.writestr("61.csv", "unopened authors holdout fixture")
    monkeypatch.setattr(m, "OFFICIAL_LABELS_SHA256", m.sha256_file(archive))
    original = zipfile.ZipFile.read
    seen = []

    def watched(self, name, *args, **kwargs):
        name = name.filename if isinstance(name, zipfile.ZipInfo) else name
        seen.append(name)
        if name in ("11.csv", "61.csv"):
            raise AssertionError("Protected source was improperly opened")
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", watched)
    assert len(m.load_official_source(archive, EXAM)) == 13
    assert seen == ["23.csv"]
    with pytest.raises(ValueError, match="allowlisted"):
        m.load_official_source(archive, 11)
    assert seen == ["23.csv"]


def test_source_csv_must_preserve_unknown_not_infer_negative():
    raw = b"frame,blood\n" + b"".join(f"{n},{'' if n == 15 else '0'}\n".encode() for n in range(5, 105, 5))
    rows = m.parse_corrected_source_rows(raw)
    assert rows[2]["blood"] == ""
    review, manifest, receipt, labels, _ = sample()
    receipt[2]["blood"] = 0
    labels[3]["blood"] = ""  # source frame 20 is imported and now unknown
    with pytest.raises(ValueError):
        m.evaluate_interval_evidence(review, manifest, receipt, labels, exam=EXAM)


def test_private_cli_refuses_overwrite_and_any_nonofficial_source(tmp_path):
    review, manifest, receipt, labels, pixel = sample()
    z = tmp_path / "review.zip"
    make_zip(z, review, pixel)
    study = tmp_path / "study.json"; study.write_text(json.dumps(manifest))
    verified = tmp_path / "verified.json"; verified.write_text(json.dumps(receipt))
    fake_zip = tmp_path / "labels.zip"
    with zipfile.ZipFile(fake_zip, "w") as archive:
        archive.writestr("23.csv", "frame,blood\n5,0\n10,0\n")
    output = tmp_path / "aggregate.json"
    with pytest.raises(ValueError, match="SHA-256"):
        m.evaluate_private_galar_export(review_zip=z, study_manifest_path=study,
            verified_source_manifest_path=verified, corrected_labels_zip=fake_zip,
            exam=EXAM, output=output)
    assert not output.exists()
    output.write_text("existing private aggregate")
    with pytest.raises(FileExistsError):
        m.evaluate_private_galar_export(review_zip=z, study_manifest_path=study,
            verified_source_manifest_path=verified, corrected_labels_zip=fake_zip,
            exam=EXAM, output=output)


def test_corrupt_interval_history_and_duplicate_original_pngs_fail_closed():
    review, manifest, receipt, rows, _ = sample()
    review['interval_history'][0]['note'] = 'changed after the original creation record'
    with pytest.raises(ValueError, match="immutable event trail"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    review, manifest, receipt, rows, _ = sample()
    receipt[1]['source_image_sha256'] = receipt[0]['source_image_sha256']
    with pytest.raises(ValueError, match="Duplicate original PNG"):
        m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)


def test_user_specified_interval_source_ids_cannot_redefine_galar_annotation_runs():
    review, manifest, receipt, rows, _ = sample()
    # An interval's note cannot turn a negative boundary into direct evidence.
    review['intervals'][0]['note'] = 'Observed bleeding event claimed without support'
    review['interval_history'][0]['note'] = 'Observed bleeding event claimed without support'
    audit = m.evaluate_interval_evidence(review, manifest, receipt, rows, exam=EXAM)
    assert audit['direct_selected_positive_annotation_runs'] == 1
    assert audit['span_overlapped_source_positive_runs'] == 3
    assert 'bleeding event' not in json.dumps(audit)
