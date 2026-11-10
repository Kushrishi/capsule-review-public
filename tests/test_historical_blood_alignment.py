"""Synthetic source-identity regression checks for historical blood-score imports.

The three original experiment receipts remain independently pinned by their
respective import scripts. No real Galar image, label or checkpoint is used.
"""
from contextlib import contextmanager

import pytest

from capsule_review.prediction_service import align_fixed_development_scores


class _Store:
    def __init__(self, rows, *, synthetic=False, missing=False):
        self.rows = rows
        self.synthetic = synthetic
        self.missing = missing
        self.sql = []

    def study(self, study_id):
        if self.missing or study_id != "fixture":
            return None
        return {"frame_count": 512, "synthetic": self.synthetic}

    @contextmanager
    def connect(self):
        store = self
        class _Database:
            def execute(self, sql, params):
                assert sql.startswith("SELECT position,source_index,source_sha256")
                assert params == ("fixture",)
                store.sql.append(sql)
                return store.rows
        yield _Database()


def _fixture():
    rows = [dict(position=i, source_index=5*i, source_sha256=f"{i:064x}")
            for i in range(512)]
    scores = {(r["source_index"], r["source_sha256"]): (r["position"] % 101)/100
              for r in rows}
    return rows, scores


def test_original_cnn_and_probe_maps_preserve_all_predictions_without_writes():
    rows, scores = _fixture()
    store = _Store(rows)
    out = align_fixed_development_scores(store, "fixture", scores, "Blood visual cue")
    assert len(out) == 512 and len(store.sql) == 1
    assert [(p.position, p.image_sha256, p.score) for p in out] == [
        (r["position"], r["source_sha256"], scores[(r["source_index"], r["source_sha256"])])
        for r in rows]
    assert all(p.label == "Blood visual cue" for p in out)


def test_domain_adapter_matches_only_the_requested_historical_examination():
    rows, scores = _fixture()
    both = {(ex, *key): (value if ex == 10 else 0.02)
            for ex in (9, 10) for key, value in scores.items()}
    out = align_fixed_development_scores(_Store(rows), "fixture", both,
                                         "Domain blood", exam=10)
    assert len(out) == 512 and out[100].score == scores[(500, f"{100:064x}")]
    with pytest.raises(ValueError, match="hashes/source indices"):
        align_fixed_development_scores(_Store(rows), "fixture", both,
                                       "Domain blood", exam=11)


@pytest.mark.parametrize("tamper,expected", [
    (lambda rows: rows.pop(), "exactly 512"),
    (lambda rows: rows[0].update(position=4), "ordered"),
    (lambda rows: rows[1].update(source_sha256="f"*64), "hashes/source indices"),
    (lambda rows: rows[1].update(source_index=999999), "hashes/source indices"),
    (lambda rows: rows[1].update(source_index=rows[0]["source_index"],
                                 source_sha256=rows[0]["source_sha256"]), "Duplicate"),
])
def test_source_count_order_identity_tampering_fails_before_persistence(tamper, expected):
    rows, scores = _fixture()
    tamper(rows)
    with pytest.raises(ValueError, match=expected):
        align_fixed_development_scores(_Store(rows), "fixture", scores, "Blood cue")


@pytest.mark.parametrize("synthetic,missing", [(True, False), (False, True)])
def test_synthetic_or_missing_study_never_eligible(synthetic, missing):
    rows, scores = _fixture()
    with pytest.raises(ValueError, match="real study"):
        align_fixed_development_scores(_Store(rows, synthetic=synthetic, missing=missing),
                                       "fixture", scores, "Blood cue")


def test_invalid_score_rejected_without_any_database_mutation():
    rows, scores = _fixture()
    scores[(0, "0"*64)] = float("nan")
    with pytest.raises(ValueError):
        align_fixed_development_scores(_Store(rows), "fixture", scores, "Blood cue")
