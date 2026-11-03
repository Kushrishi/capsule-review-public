"""Compare label-blind frame selection on a complete published VCE study.

The script only reports organ-label boundary and temporal-index coverage, *not*
pathology detection, sensitivity, patient-level generalization, or review time.
Run s288 as exploratory development; freeze the protocol before acquiring other
study IDs. Source study ZIPs and individual images remain outside Git.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
from statistics import mean
from zipfile import ZipFile, BadZipFile

from PIL import Image, ImageChops, ImageStat

PATTERN = re.compile(r"^(s\d+)/(1_esophagus|2_stomach|3_small_bowel|4_colon)/image-(\d+)\.png$")
REGION_ORDER = ["1_esophagus", "2_stomach", "3_small_bowel", "4_colon"]


def file_sha256(p: Path) -> str:
    sha = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def uniform(n: int, k: int) -> list[int]:
    if not 1 <= k <= n:
        raise ValueError("invalid selection budget")
    if k == 1:
        return [(n - 1) // 2]
    return [j * (n - 1) // (k - 1) for j in range(k)]


def global_change(scores: list[float], k: int) -> list[int]:
    n = len(scores)
    if not 1 <= k <= n:
        raise ValueError("invalid selection budget")
    if k <= 2:
        return uniform(n, k)
    ranked = sorted(range(1, n - 1), key=lambda i: (-scores[i], i))
    return sorted([0, n - 1] + ranked[:k - 2])


def stratified_change(scores: list[float], k: int) -> list[int]:
    n = len(scores)
    if not 1 <= k <= n:
        raise ValueError("invalid selection budget")
    if k <= 2:
        return uniform(n, k)
    interior, bins = n - 2, k - 2
    result = [0, n - 1]
    for b in range(bins):
        lo = 1 + (b * interior // bins)
        hi = 1 + ((b + 1) * interior // bins)
        if lo >= hi:
            raise ValueError("empty chronological bin")
        choice = min(range(lo, hi), key=lambda i: (-scores[i], i))
        result.append(choice)
    return sorted(result)


def random_anchored(n: int, k: int, seed: int) -> list[int]:
    if not 1 <= k <= n:
        raise ValueError("invalid selection budget")
    if k <= 2:
        return uniform(n, k)
    return sorted([0, n - 1] + random.Random(seed).sample(range(1, n - 1), k - 2))


def coverage(n: int, selected: list[int], regions: list[str], tolerances: list[int]) -> dict:
    if len(regions) != n:
        raise ValueError("region count inconsistent with source frames")
    if selected != sorted(set(selected)) or not selected or selected[-1] >= n or selected[0] < 0:
        raise ValueError("invalid selected positions")
    # Boundary evaluation is separate from selection; policies never receive labels.
    boundaries = [i for i in range(1, n) if regions[i] != regions[i - 1]]
    selected_set = set(selected)
    distance = [n] * n
    closest = -n
    for i in range(n):
        if i in selected_set:
            closest = i
        distance[i] = abs(i - closest)
    closest = 2 * n
    for i in range(n - 1, -1, -1):
        if i in selected_set:
            closest = i
        distance[i] = min(distance[i], abs(i - closest))
    sorted_dist = sorted(distance)
    return {
        "selected_count": len(selected),
        "boundary_count": len(boundaries),
        "boundary_distances": [distance[i] for i in boundaries],
        "boundary_hits": {str(t): sum(distance[i] <= t for i in boundaries) for t in tolerances},
        "max_nearest_position_distance": max(distance),
        "p95_nearest_position_distance": sorted_dist[math.ceil(0.95 * n) - 1],
        "mean_nearest_position_distance": round(mean(distance), 5),
        "max_selected_position_gap": max((b - a for a, b in zip(selected, selected[1:])), default=0),
        "regions_represented": len({regions[i] for i in selected}),
        "selected_regions": dict(sorted(Counter(regions[i] for i in selected).items())),
        "hundred_position_bins_represented": len({i // 100 for i in selected}),
    }


def read_study(archive: Path, study_id: str) -> tuple[list[int], list[str], list[float], dict]:
    """Recompute change scores from all real frames; no precomputed scores trusted."""
    frames = []
    actual_formats = Counter()
    with ZipFile(archive) as z:
        infos = z.infolist()
        if not infos or any(i.is_dir() or i.file_size > 32 * (1 << 20) for i in infos):
            raise ValueError("Invalid or oversized image member")
        if len(infos) > 100_000:
            raise ValueError("Unreasonably many members")
        if z.testzip() is not None:
            raise ValueError("Corrupted ZIP member CRC")
        for info in infos:
            match = PATTERN.fullmatch(info.filename)
            if not match or match.group(1) != study_id:
                raise ValueError(f"Unexpected member: {info.filename}")
            frames.append((int(match.group(3)), match.group(2), info))
        frames.sort(key=lambda t: t[0])
        ids = [f[0] for f in frames]
        if len(ids) != len(set(ids)) or ids != list(range(ids[0], ids[-1] + 1)):
            raise ValueError("Missing or duplicated numeric source-frame identifiers")
        regions = [f[1] for f in frames]
        region_ids = [REGION_ORDER.index(r) for r in regions]
        if region_ids != sorted(region_ids) or len(set(region_ids)) != 4:
            raise ValueError("Unexpected anatomical folder transitions")
        scores = [0.0]
        prev = None
        dimensions = Counter()
        for _, _, info in frames:
            blob = z.read(info)
            with Image.open(io.BytesIO(blob)) as im:
                im.load()
                actual_formats[im.format] += 1
                if im.width > 4096 or im.height > 4096 or im.width < 16 or im.height < 16:
                    raise ValueError("Unexpected image dimensions")
                dimensions[f"{im.width}x{im.height}"] += 1
                thumb = im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
            if prev is not None:
                # Identical mathematical definition to the original normalized RGB MAE.
                diff = ImageStat.Stat(ImageChops.difference(prev, thumb)).mean
                scores.append(sum(diff) / (3.0 * 255.0))
            prev = thumb
    return ids, regions, scores, {"actual_formats": dict(actual_formats), "dimensions": dict(dimensions)}


def evaluate(archive: Path, study_id: str, spec: dict) -> dict:
    spec_path = spec.get("future_studies_selected_without_examining_images_or_labels", [])
    permitted = {spec["existing_development_study"]} | {s["study"] for s in spec_path}
    if study_id not in permitted:
        raise ValueError("Study not included in the frozen protocol")
    source_sha = file_sha256(archive)
    ids, regions, scores, image_info = read_study(archive, study_id)
    n = len(ids)
    tolerances = spec["boundary_tolerances_frames"]
    result = {
        "study": study_id,
        "role": "exploratory / previously inspected" if study_id == spec["existing_development_study"] else "prespecified / to interpret with dataset limitations",
        "source_zip_sha256": source_sha,
        "source_zip_bytes": archive.stat().st_size,
        "image_count": n,
        "source_index_first": ids[0], "source_index_last": ids[-1],
        "source_indices_complete": True,
        "anatomy_counts": dict(sorted(Counter(regions).items())),
        "anatomy_boundary_count": sum(regions[i] != regions[i-1] for i in range(1, n)),
        "image_change_definition": spec["image_change"],
        "image_info": image_info,
        "image_change_stats": {"mean": round(mean(scores[1:]), 8), "max": round(max(scores[1:]), 8)},
        "budget_results": [],
        "capture_timestamps": None,
        "pathology_labels": None,
        "patient_independence_known": False,
        "clinical_claims_supported": False,
    }
    for budget in spec["budgets"]:
        k = math.ceil(n * budget)
        entries = {}
        for name, picked in [
            ("uniform", uniform(n, k)),
            ("global_change", global_change(scores, k)),
            ("stratified_change", stratified_change(scores, k)),
        ]:
            entries[name] = coverage(n, picked, regions, tolerances)
        random_draws = [coverage(n, random_anchored(n, k, 17 + r), regions, tolerances) for r in range(100)]
        numeric = ["max_nearest_position_distance", "p95_nearest_position_distance", "mean_nearest_position_distance", "max_selected_position_gap", "regions_represented", "hundred_position_bins_represented"]
        summary = {key: round(mean(d[key] for d in random_draws), 5) for key in numeric}
        summary["boundary_hits_mean"] = {str(t): round(mean(d["boundary_hits"][str(t)] for d in random_draws), 5) for t in tolerances}
        summary["draws"] = 100
        entries["random_anchored"] = summary
        result["budget_results"].append({"budget": budget, "k": k, "methods": entries})
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--study-id", required=True)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-sha256", default="")
    args = p.parse_args()
    if args.out.exists():
        p.error("Output exists; refusing overwrite")
    spec_bytes = args.spec.read_bytes()
    spec = json.loads(spec_bytes)
    if args.expected_sha256 and file_sha256(args.archive) != args.expected_sha256:
        p.error("Original archive hash differs from trusted receipt")
    results = evaluate(args.archive, args.study_id, spec)
    results["spec_sha256"] = hashlib.sha256(spec_bytes).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"Verified {results['image_count']} real images; {len(results['budget_results'])} budgets -> {args.out}")


if __name__ == "__main__":
    main()
