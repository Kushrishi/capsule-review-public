"""Evaluate the three unchanged blood CNNs on frozen Galar-27 source positions.

This adapter reuses the independently verified examination-25 evaluation engine,
but locks the new source identity/label-blind reference roles. No model training,
checkpoint selection, calibration, or clinical claims are permitted.
"""
from __future__ import annotations

import evaluate_galar25_frozen as engine

EXAM = 27
REQUESTED_SOURCE_PNGS = 1005
UNIFORM_REFERENCE_PNGS = 512
UNIFORM_REFERENCE_BLOOD_POSITIVE = 26


def configure() -> None:
    """Require the exact prespecified 27 source-frame population."""
    engine.EXAM = EXAM
    engine.UNION_COUNT = REQUESTED_SOURCE_PNGS
    engine.REFERENCE_COUNT = UNIFORM_REFERENCE_PNGS
    engine.REFERENCE_POSITIVES = UNIFORM_REFERENCE_BLOOD_POSITIVE
    engine.ENRICHED_COUNT = 512
    engine.ENRICHED_POSITIVES = 256
    engine.OVERLAP = 19
    assert engine.BUDGETS == (5, 10, 25, 50, 75, 100)
    assert set(engine.MODEL_HASHES) == {
        'original_checkpoint', 'original_only_continued', 'expanded_continued'
    }


def main() -> None:
    configure()
    engine.main()


if __name__ == '__main__':
    main()
