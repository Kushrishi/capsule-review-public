"""Synthetic-only development data gate tests: no medical source data."""
import copy
from hashlib import sha256
import pytest
from capsule_review.development_preflight import inspect, manifest_digest


def fixture(tmp_path, groups=True):
    root=tmp_path/"private"
    root.mkdir(parents=True)
    rows=[]
    for exam,split in (("a","fit"),("b","evaluate")):
        for index,label in enumerate(("positive","negative")):
            name=f"{exam}-{index}.png"
            b=b"synthetic-test-only"+name.encode()
            (root/name).write_bytes(b)
            rows.append(dict(examination_id=exam, source_index=index,
                             split=split,blood_label=label,
                             image_sha256=sha256(b).hexdigest(),
                             image_path=name,patient_group=exam if groups else None))
    return root,dict(schema_version=1,task="sparse_image_ranking",
                     source_coverage="sampled",exhaustive_event_annotations=False,
                     rights_evidence_ref="synthetic-custodian-record",
                     near_duplicate_screened=True,records=rows)


def inspect_case(root,m):
    return inspect(m,source_root=root,pinned_sha256=manifest_digest(m))


def test_valid_structural_preflight_is_not_clinical_approval(tmp_path):
    root,m=fixture(tmp_path)
    report=inspect_case(root,m)
    assert report["decision"]=="PASS"
    assert report["source_images_sha256_reverified"]==4
    assert report["positive_images"]==2 and report["explicit_negative_images"]==2
    assert report["fit_images"]==2 and report["evaluation_images"]==2
    assert report["patient_independence_proven"] is False
    assert report["medical_outcome_access_approved"] is False
    assert report["human_review_required"] is True
    assert "image_path" not in str(report)


def test_no_patient_group_is_not_independent_validation(tmp_path):
    root,m=fixture(tmp_path,False)
    r=inspect_case(root,m)
    assert r["decision"]=="INSUFFICIENT_GROUP_INFORMATION"
    assert "patient_group_not_verified" in r["issues"]


@pytest.mark.parametrize("change,issue",[
    (lambda m:m["records"][2].update(split="fit"),"examination_split_leakage"),
    (lambda m:m["records"][2].update(patient_group="a"),"patient_group_split_leakage"),
    (lambda m:m["records"][3].update(blood_label="unknown"),"unknown_label_not_eligible_as_negative"),
    (lambda m:m.update(rights_evidence_ref=""),"data_rights_evidence_missing"),
    (lambda m:m.update(near_duplicate_screened=False),"near_duplicate_screen_missing"),
    (lambda m:m["records"][0].update(image_sha256=m["records"][2]["image_sha256"]),"identical_source_image_across_examinations"),
    (lambda m:m["records"][3].update(blood_label="positive"),"evaluation_split_missing_binary_class")
])
def test_fail_closed_dataset_changes(tmp_path,change,issue):
    root,m=fixture(tmp_path)
    change(m)
    r=inspect_case(root,m)
    assert r["decision"]=="BLOCKED"
    assert issue in r["issues"]


def test_changed_or_missing_actual_source_image_fails(tmp_path):
    root,m=fixture(tmp_path)
    (root/"a-0.png").write_bytes(b"changed")
    r=inspect_case(root,m)
    assert r["decision"]=="BLOCKED"
    assert r["source_images_sha256_reverified"]==3
    assert "source_image_sha256_mismatch" in r["issues"]
    (root/"b-1.png").unlink()
    assert "source_image_missing" in inspect_case(root,m)["issues"]


def test_unpinned_manifest_rejected(tmp_path):
    root,m=fixture(tmp_path)
    with pytest.raises(ValueError):
        inspect(m,source_root=root,pinned_sha256="0"*64)
    with pytest.raises(ValueError):
        inspect(m,source_root=root,pinned_sha256="UNPINNED")


def test_sparse_images_cannot_satisfy_complete_event_coverage(tmp_path):
    root,m=fixture(tmp_path)
    m["task"]="complete_event_retrieval"
    r=inspect_case(root,m)
    assert r["decision"]=="BLOCKED"
    assert {"sampled_images_not_complete_video","event_annotations_not_exhaustive"} <= set(r["issues"])


def test_source_paths_cannot_escape_private_root(tmp_path):
    root,m=fixture(tmp_path)
    m["records"][0]["image_path"]="../outside.png"
    with pytest.raises(ValueError):
        inspect_case(root,m)


def test_source_symlinks_rejected(tmp_path):
    root,m=fixture(tmp_path)
    (root/"a-0.png").unlink()
    target=tmp_path/"outside.png"
    target.write_bytes(b"not source")
    (root/"a-0.png").symlink_to(target)
    with pytest.raises(ValueError):
        inspect_case(root,m)


def test_canonical_lock_and_output_redaction(tmp_path):
    root,m=fixture(tmp_path)
    altered=copy.deepcopy(m)
    altered["records"].reverse()
    assert manifest_digest(altered)!=manifest_digest(m)
    report=inspect_case(root,m)
    for sensitive in ("a-0.png","b-1.png","source_index","patient_group","image_sha256"):
        assert sensitive not in str(report)
