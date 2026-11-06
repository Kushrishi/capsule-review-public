"""Exploratory fixed-bin score randomization; no clinical or causal inference.

Only aggregates leave this module. Imported positions are not capture times.
NumPy is loaded only for optional repeated simulations (the existing ml extra).
"""
from __future__ import annotations

import math
from .priority import select_positions


def bins(n: int, k: int) -> list[tuple[int, int]]:
    if type(n) is not int or type(k) is not int or not 1 <= k <= n:
        raise ValueError('Require 1 <= K <= N.')
    return [(i*n//k, (i+1)*n//k) for i in range(k)]


def winner_probabilities(length: int, maxima: int = 1) -> list[float]:
    """Earliest of m uniformly permuted maxima, retaining original tie rule."""
    if type(length) is not int or type(maxima) is not int or not 1 <= maxima <= length:
        raise ValueError('Invalid bin length or maximum multiplicity.')
    denominator = math.comb(length, maxima)
    return [math.comb(length-j-1, maxima-1)/denominator
            if length-j >= maxima else 0.0 for j in range(length)]


def annotation_runs(labels: list[int], frames: list[int], stride: int) -> list[list[int]]:
    if (not labels or len(labels) != len(frames) or type(stride) is not int or stride < 1
            or any(type(y) is not int or y not in (0, 1) for y in labels)
            or any(type(f) is not int or f < 0 for f in frames)
            or any(b <= a for a, b in zip(frames, frames[1:]))):
        raise ValueError('Require explicit binary labels and ordered source identities.')
    result: list[list[int]] = []
    for i, y in enumerate(labels):
        if y:
            if i == 0 or not labels[i-1] or frames[i]-frames[i-1] != stride:
                result.append([])
            result[-1].append(i)
    return result


def stratum(run: list[int]) -> str:
    return 'short_1_5' if len(run) <= 5 else 'medium_6_25' if len(run) <= 25 else 'long_26_plus'


def metrics(labels: list[int], runs: list[list[int]], selected: list[int]) -> dict:
    if (not selected or len(set(selected)) != len(selected)
            or any(type(p) is not int or not 0 <= p < len(labels) for p in selected)):
        raise ValueError('Invalid exact-K selection.')
    chosen = set(selected)
    hits = sum(labels[p] for p in selected)
    reached = [bool(chosen.intersection(r)) for r in runs]
    strata = {}
    for key in ('short_1_5', 'medium_6_25', 'long_26_plus'):
        mask = [i for i, r in enumerate(runs) if stratum(r) == key]
        count = sum(reached[i] for i in mask)
        strata[key] = {'total': len(mask), 'reached': count,
                       'recall': count/len(mask) if mask else None}
    return {'positive_images': hits,
            'positive_image_recall': hits/sum(labels) if sum(labels) else None,
            'runs_reached': sum(reached),
            'run_recall': sum(reached)/len(runs) if runs else None, 'strata': strata}


def expected_metrics(labels: list[int], runs: list[list[int]], scores: list[float], k: int,
                     *, permuted_scores: bool) -> dict:
    """Exact expected counts, including runs spanning multiple independent bins."""
    cuts = bins(len(labels), k)
    probabilities = []
    bin_ids = []
    for i, (a, b) in enumerate(cuts):
        m = sum(s == max(scores[a:b]) for s in scores[a:b]) if permuted_scores else 1
        probabilities.extend(winner_probabilities(b-a, m))
        bin_ids.extend([i]*(b-a))
    run_prob = []
    for run in runs:
        mass: dict[int, float] = {}
        for p in run:
            mass[bin_ids[p]] = mass.get(bin_ids[p], 0.0)+probabilities[p]
        run_prob.append(1-math.prod(max(0.0, 1-q) for q in mass.values()))
    return {'positive_images': sum(p*y for p, y in zip(probabilities, labels)),
            'runs_reached': sum(run_prob),
            'strata': {key: sum(p for r, p in zip(runs, run_prob) if stratum(r) == key)
                       for key in ('short_1_5', 'medium_6_25', 'long_26_plus')}}


def analyze(scores: list[float], labels: list[int], frames: list[int], *, stride: int,
            percent: int, exam: int, repetitions: int = 10_000,
            shift_repetitions: int = 1_000) -> tuple[dict, dict]:
    """Return aggregate report and private repetition arrays; never input vectors."""
    import numpy as np
    if type(percent) is not int or percent not in (10, 25):
        raise ValueError('Only fixed 10/25 percent workloads are supported.')
    if type(repetitions) is not int or repetitions < 2 or type(shift_repetitions) is not int or shift_repetitions < 2:
        raise ValueError('Require repeated controls.')
    n = len(scores)
    if len(labels) != n:
        raise ValueError('Score/label length mismatch.')
    k = max(1, (n*percent+50)//100)
    # Production validation and actual fixed selectors, before any null draws.
    actual = {m: select_positions(scores, k, m)
              for m in ('uniform', 'score_bin', 'score', 'score_diverse')}
    runs = annotation_runs(labels, frames, stride)
    keys = ('positive_images', 'runs_reached', 'short_1_5', 'medium_6_25', 'long_26_plus')
    run_id = np.full(n, -1, dtype=int)
    for j, r in enumerate(runs):
        run_id[r] = j
    masks = {key: np.array([stratum(r) == key for r in runs], dtype=bool) for key in keys[2:]}
    y = np.asarray(labels)
    def counts(selected):
        ids = np.unique(run_id[selected]); ids = ids[ids >= 0]
        return [int(y[selected].sum()), len(ids), *[int(masks[key][ids].sum()) for key in keys[2:]]]
    cuts = bins(n, k)
    lengths = np.array([b-a for a, b in cuts])
    starts = np.array([a for a, _ in cuts])
    probs = []
    multiplicities = []
    for a, b in cuts:
        m = sum(s == max(scores[a:b]) for s in scores[a:b])
        multiplicities.append(m)
        probs.append(np.cumsum(winner_probabilities(b-a, m)))
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261106, exam, percent, 1])))
    permutation, geometry = [], []
    for _ in range(repetitions):
        u = rng.random(k)
        g = starts + np.minimum((u*lengths).astype(int), lengths-1)
        # Coupled draws: identical for unique maxima, otherwise exact earliest-tie CDF.
        p = g.copy()
        for j, m in enumerate(multiplicities):
            if m != 1:
                p[j] = starts[j]+np.searchsorted(probs[j], u[j], side='right')
        geometry.append(counts(g)); permutation.append(counts(p))
    phases = [counts([math.floor((i+(j+.5)/100)*n/k) for i in range(k)])
              for j in range(100)]
    # Preserve score autocorrelation inside fixed coarse blocks, excluding identity shifts.
    blocks = bins(n, min(16, n))
    block_id = np.empty(n, dtype=int)
    for j, (a, b) in enumerate(blocks):
        block_id[a:b] = j
    ba = np.array([a for a, _ in blocks]); bl = np.array([b-a for a, b in blocks])
    ordinal = np.arange(n)
    gather = starts[:, None] + np.arange(int(lengths.max()))[None, :]
    valid = gather < (starts+lengths)[:, None]
    gather = np.minimum(gather, n-1)
    score_array = np.asarray(scores)
    def fast_bin(v):
        padded = np.where(valid, v[gather], -np.inf)
        return starts+np.argmax(padded, axis=1)
    if set(fast_bin(score_array).tolist()) != set(actual['score_bin']):
        raise AssertionError('Independent vectorized bin selector disagrees.')
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261106, exam, percent, 2])))
    shifted = []
    for _ in range(shift_repetitions):
        offsets = np.array([rng.integers(1, length) if length > 1 else 0 for length in bl])
        source = ba[block_id]+(ordinal-ba[block_id]+offsets[block_id]) % bl[block_id]
        shifted.append(counts(fast_bin(score_array[source])))
    observed = counts(actual['score_bin'])
    def summary(values):
        arr = np.asarray(values, dtype=float)
        return {key: {'mean': float(arr[:, j].mean()),
                      'sd': float(arr[:, j].std(ddof=1)),
                      'mean_mc_se': float(arr[:, j].std(ddof=1)/math.sqrt(len(arr))),
                      'reference_95_interval': np.quantile(arr[:, j], [.025, .975]).tolist(),
                      'observed_minus_mean': float(observed[j]-arr[:, j].mean()),
                      'upper_tail_fraction_plus_one': float((1+(arr[:, j]>=observed[j]).sum())/(len(arr)+1))}
                for j, key in enumerate(keys)}
    controls = {'within_bin_permuted_scores': summary(permutation),
                'geometry_uniform_in_bin': summary(geometry),
                'systematic_phase_sensitivity': summary(phases),
                'coarse16_circular_shift': summary(shifted)}
    # The phase grid is deterministic sensitivity, not a Monte Carlo sample.
    for item in controls['systematic_phase_sensitivity'].values():
        item.pop('mean_mc_se')
        item.pop('upper_tail_fraction_plus_one')
    exact = expected_metrics(labels, runs, scores, k, permuted_scores=True)
    geometry_exact = expected_metrics(labels, runs, scores, k, permuted_scores=False)
    for name, expectation in [('within_bin_permuted_scores', exact), ('geometry_uniform_in_bin', geometry_exact)]:
        controls[name]['analytic_expected_counts'] = expectation
        controls[name]['simulation_minus_analytic'] = {
            key: controls[name][key]['mean']-(expectation[key] if key in keys[:2] else expectation['strata'][key])
            for key in keys}
    report = {'percent': percent, 'n': n, 'k': k, 'positive_images': sum(labels),
              'positive_runs': len(runs), 'bins_with_tied_maximum': sum(m>1 for m in multiplicities),
              'policies': {m: metrics(labels, runs, p) for m, p in actual.items()}, 'controls': controls}
    private = {'keys': keys, 'permutation': permutation, 'geometry': geometry,
               'phases': phases, 'coarse_shift': shifted}
    return report, private
