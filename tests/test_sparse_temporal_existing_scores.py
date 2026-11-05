"""Synthetic-only tests for previously inspected sparse-score temporal replay."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import replay_sparse_temporal_existing_scores as m
from capsule_review.priority import select_positions


def test_gap_aware_max_never_bridges_absent_published_frames():
    frame=[5,10,100,105,110,1000]
    scores=[.1,.9,.1,.2,.0,.7]
    assert m.gap_aware_max(frame,scores) == [.9,.9,.2,.2,.2,.7]


def test_sparse_reference_positions_produce_exact_identity():
    frame=[5,80,155,230,305]
    score=[.0,.9,.2,.1,.7]
    assert m.gap_aware_max(frame,score)==score
    case=[{"frame":str(f),"cnn_score":str(s),"blood":str(int(i==1))}
          for i,(f,s) in enumerate(zip(frame,score))]
    assert m.replay_case(case)["scores_changed_by_truncated_window_three"]==0
    for budget in m.WORKLOADS:
        x=m.replay_case(case)["budgets"][str(budget)]["methods"]
        assert x["temporal_gap_aware_score_bin"]["changed_selected_positions_vs_original"] == 0


@pytest.mark.parametrize("frame",[
    [0,5,5], [0,5,4], [0,5,11], [0,-5,10], [0,5.0,10], [True,5,10]
])
def test_bad_source_indices_rejected(frame):
    with pytest.raises(ValueError):
        m.gap_aware_max(frame,[.1,.2,.3])


@pytest.mark.parametrize("score",[
    [0.0,float("nan")], [0.0,float("inf")],
    [0.0,-.1], [0.0,1.01], [0.0,True]
])
def test_bad_scores_rejected(score):
    with pytest.raises(ValueError):
        m.gap_aware_max([0,5],score)


def test_matches_full_dense_temporal_core_with_fixed_window():
    from capsule_review.temporal_baseline import temporal_max_scores
    source=list(range(100,180,5))
    scores=[(i*7%11)/10 for i in range(len(source))]
    assert m.gap_aware_max(source,scores) == temporal_max_scores(
        scores,source,window=3,source_stride=5)


def test_no_leak_and_outcome_label_blind_queues():
    ids=[10,15,20,90,95,100,400]
    scores=[.1,.9,.0,.2,.1,.8,.1]
    rows=[{"frame":str(f),"cnn_score":str(s),"blood":"0"} for f,s in zip(ids,scores)]
    first=m.replay_case(rows)
    mutated=[dict(x) for x in rows]
    mutated[1]["blood"]="1";mutated[-1]["blood"]="1"
    second=m.replay_case(mutated)
    for p in m.WORKLOADS:
        assert first["budgets"][str(p)]["exact_selected_images"] == second["budgets"][str(p)]["exact_selected_images"]
        assert first["budgets"][str(p)]["methods"]["temporal_gap_aware_score_bin"]["changed_selected_positions_vs_original"] == second["budgets"][str(p)]["methods"]["temporal_gap_aware_score_bin"]["changed_selected_positions_vs_original"]
    assert first["blood_positive_sample_images"]==0
    assert second["blood_positive_sample_images"]==2
    assert "source_frame" not in json.dumps(second)
    assert "source_image_sha" not in json.dumps(second)
    assert "cnn_score" not in json.dumps(second)


def synthetic_private_package(tmp_path, monkeypatch, *, incorrect_label=False):
    p=tmp_path/"synthetic-scores-private.zip"
    buf=io.StringIO()
    fields=list(m.REQUIRED)
    writer=csv.DictWriter(buf,fieldnames=fields,lineterminator="\n")
    writer.writeheader()
    for exam in m.EXAMS:
        for i,frame in enumerate((5,10,15)):
            row={f:"" for f in fields}
            row.update(exam=str(exam),frame=str(frame),
                       source_image_sha256="a"*64,pixel_sha256="b"*64,
                       blood="1" if i==1 else "0",
                       fit_enriched="1",reference_uniform="1",
                       cnn_score=str([.1,.9,.2][i]),
                       red_excess_score=str([.0,.1,.2][i]))
            if incorrect_label and exam==23 and i==1:
                row["blood"]=""
            writer.writerow(row)
    data=buf.getvalue().encode()
    with zipfile.ZipFile(p,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(m.MEMBER,data)
        z.writestr("private/another-sensitive-member.txt","must not be read")
    monkeypatch.setattr(m,"PACKAGE_SHA256",m._sha_file(p) if False else hashlib.sha256(p.read_bytes()).hexdigest())
    monkeypatch.setattr(m,"MEMBER_SHA256",hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(m,"EXPECTED_TOTAL",{21:3,23:3,30:3})
    monkeypatch.setattr(m,"EXPECTED_UNION_POSITIVES",{21:1,23:1,30:1})
    monkeypatch.setattr(m,"REFERENCE_PER_EXAM",3)
    return p


def test_synthetic_replay_returns_aggregate_without_sources(tmp_path,monkeypatch):
    p=synthetic_private_package(tmp_path,monkeypatch)
    report=m.build_report(p)
    assert report["new_training_or_original_image_inference"] is False
    assert report["patient_independent_or_clinical_validation"] is False
    assert report["protected_11_20_evaluation_reopened"] is False
    assert set(report["cases"]) == {"21","23","30"}
    assert sum(c["original_label_blind_512_frame_reference"]["consecutive_source_index_pairs"]
               for c in report["cases"].values())==6
    obj=json.dumps(report)
    assert "source_image_sha256" not in obj
    assert "pixel_sha256" not in obj
    assert '"frame"' not in obj
    assert '"cnn_score"' not in obj


def test_unknown_labels_are_not_coerced_to_negative(tmp_path,monkeypatch):
    p=synthetic_private_package(tmp_path,monkeypatch,incorrect_label=True)
    with pytest.raises(ValueError,match="invalid blood"):
        m.build_report(p)


def test_private_score_package_hash_required(tmp_path,monkeypatch):
    p=synthetic_private_package(tmp_path,monkeypatch)
    monkeypatch.setattr(m,"PACKAGE_SHA256","0"*64)
    with pytest.raises(ValueError,match="SHA"):
        m.build_report(p)


def test_select_bin_preserves_exact_k():
    scores=[(x*13%17)/16 for x in range(41)]
    for k in (1,2,3,10,41):
        chosen=select_positions(scores,k,"score_bin")
        assert len(chosen)==len(set(chosen))==k
