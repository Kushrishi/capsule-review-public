"""Reconcile PRIVATE image-resemblance candidate scores without disclosing identities.

This module does not open clinical images. It validates the second-stage
numeric results produced by a separate private, source-SHA-verified image
comparison. An identical coarse dHash is NOT proof of duplicate content;
a low pixel-aligned similarity is NOT proof of patient independence or
absence of altered/rotated/transformed copies outside the candidate set.

The caller must keep full individual source identities and pair metrics private.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
import re

SOURCE_KEY_RE = re.compile(r"[0-9a-f]{16}\Z")
EXPECTED_FIELDS = frozenset({
    "a", "b", "dh", "gray_ssim", "rgb_mae", "center_mae", "rgb_rmse", "high"
})
MAX_PAIRS = 250_000


def summarize_private_pair_scores(records: list) -> dict:
    """Return a strictly non-identifying summary; validate all private rows.

    Strict close-copy candidate is SSIM >= .95 and RGB MAE <= .06, with
    central RGB MAE <= .07. The thresholds are descriptive triage rules,
    NOT validated patient linkage or medical-label quality metrics.
    """
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_PAIRS:
        raise ValueError("Invalid bounded private pair-score collection.")
    seen_pairs = set()
    frames = set()
    ssim = []
    high_count = 0
    ssim_70 = 0
    ssim_90 = 0
    for row in records:
        if type(row) is not dict or set(row) != EXPECTED_FIELDS:
            raise ValueError("Malformed private pair-score row.")
        a, b = row["a"], row["b"]
        for token in (a, b):
            if (type(token) is not list or len(token) != 2
                or any(type(v) is not int or not 0 <= v < 10**11 for v in token)):
                raise ValueError("Invalid private image identity.")
        if a == b or a[0] == b[0]:
            raise ValueError("Pair must be between different source examinations.")
        if type(row["dh"]) is not str or not SOURCE_KEY_RE.fullmatch(row["dh"]):
            raise ValueError("Invalid coarse-hash identity.")
        pair = tuple(sorted(((a[0], a[1]), (b[0], b[1]))))
        if pair in seen_pairs:
            raise ValueError("Duplicate private cross-examination pair.")
        seen_pairs.add(pair)
        frames.update(pair)
        for key in ("gray_ssim", "rgb_mae", "center_mae", "rgb_rmse"):
            value = row[key]
            if type(value) not in (float, int) or not isfinite(value):
                raise ValueError("Nonfinite private image resemblance metric.")
            if key == "gray_ssim" and not -1 <= value <= 1:
                raise ValueError("Invalid grayscale structural similarity.")
            if key != "gray_ssim" and not 0 <= value <= 1:
                raise ValueError("Invalid normalized image difference.")
        structure = row["gray_ssim"]
        close = (structure >= .95 and row["rgb_mae"] <= .06
                 and row["center_mae"] <= .07)
        if type(row["high"]) is not bool or row["high"] != close:
            raise ValueError("Stored strict candidate classification does not replay.")
        high_count += close
        ssim_70 += structure >= .7
        ssim_90 += structure >= .9
        ssim.append(structure)

    return {
        "schema_version": 1,
        "method": "Private source-verified 64x64 pixel-aligned full-gray SSIM and RGB MAE on previously equal-dHash cross-examination pairs only",
        "candidate_pairs_scored": len(records),
        "candidate_original_image_identities": len(frames),
        "ssim_at_least_0_70": ssim_70,
        "ssim_at_least_0_90": ssim_90,
        "maximum_gray_ssim": round(max(ssim), 7),
        "mean_gray_ssim": round(sum(ssim) / len(ssim), 7),
        "strict_pixel_aligned_close_copy_pairs": high_count,
        "complete_pairwise_nearest_neighbor_search": False,
        "transformation_invariant_matching_performed": False,
        "clinical_patient_linkage_proven": False,
        "source_groups_independent_proven": False,
        "near_duplicates_globally_ruled_out": False,
        "human_adjudication_complete": False,
        "safe_to_promote_medical_model": False,
    }


def summarize_private_embedding_neighbors(records: list, *, min_cosine: float = 0.92) -> dict:
    """Replay an identity-redacted aggregate of already measured image pairs.

    This function checks stored numerical scores and the *same strict aligned*
    close-copy rule as the earlier dHash study. It cannot redo original-PNG
    verification; the source-dependent computation stays in a private archive.
    Embedding neighbours are similarity candidates, never patient matches.
    """
    if (not isinstance(records, list) or not 1 <= len(records) <= MAX_PAIRS
        or type(min_cosine) not in (int, float) or not .0 < min_cosine < 1):
        raise ValueError("Invalid bounded private embedding candidate records.")
    fields = {"a", "b", "cosine", "gray_ssim", "rgb_mae", "center_mae",
              "high_pixel_aligned_close_copy_candidate"}
    seen = set()
    frames = set()
    ssim_values = []
    cosine_values = []
    close_count = 0
    for row in records:
        if type(row) is not dict or set(row) != fields:
            raise ValueError("Unexpected private embedding score fields.")
        a, b = row["a"], row["b"]
        for key in (a, b):
            if (type(key) is not list or len(key) != 2
                or any(type(n) is not int or not 0 <= n < 10**11 for n in key)):
                raise ValueError("Malformed private source identity.")
        if a == b or a[0] == b[0]:
            raise ValueError("Candidate must cross distinct examinations.")
        pair = tuple(sorted((tuple(a), tuple(b))))
        if pair in seen:
            raise ValueError("Repeated private candidate pair.")
        seen.add(pair)
        frames.update(pair)
        for name in ("cosine", "gray_ssim", "rgb_mae", "center_mae"):
            value = row[name]
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError("Invalid nonfinite source similarity metric.")
        cosine = row["cosine"]
        if cosine < min_cosine - 1e-6 or cosine > 1 + 1e-6:
            raise ValueError("Candidate outside its predefined cosine threshold.")
        ssim = row["gray_ssim"]
        if not -1 <= ssim <= 1:
            raise ValueError("Invalid structural similarity metric.")
        if not all(0 <= row[name] <= 1 for name in ("rgb_mae", "center_mae")):
            raise ValueError("Invalid normalized pixel difference.")
        is_close = (ssim >= .95 and row["rgb_mae"] <= .06
                    and row["center_mae"] <= .07)
        if (type(row["high_pixel_aligned_close_copy_candidate"]) is not bool
            or row["high_pixel_aligned_close_copy_candidate"] != is_close):
            raise ValueError("Close-copy classification differs from frozen rule.")
        ssim_values.append(ssim)
        cosine_values.append(cosine)
        close_count += is_close
    return {
        "schema_version": 1,
        "method": "Retrospective exact cross-exam top-five MobileNetV3 cosine neighbours, original 64px pixel-aligned grayscale SSIM and RGB MAE",
        "candidate_pairs_scored": len(records),
        "unique_original_source_frames": len(frames),
        "minimum_embedding_cosine": min_cosine,
        "maximum_embedding_cosine": round(max(cosine_values), 8),
        "maximum_gray_ssim": round(max(ssim_values), 7),
        "mean_gray_ssim": round(sum(ssim_values) / len(ssim_values), 7),
        "ssim_at_least_0_90": sum(s >= .90 for s in ssim_values),
        "ssim_at_least_0_95": sum(s >= .95 for s in ssim_values),
        "strict_pixel_aligned_close_copy_pairs": close_count,
        "original_image_bytes_verified_by_this_function": False,
        "complete_full_image_population_scanned_with_embeddings": False,
        "transformation_invariant_matching_performed": False,
        "source_groups_independent_proven": False,
        "human_adjudication_complete": False,
        "safe_to_promote_medical_model": False,
    }
