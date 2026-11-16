"""Freeze a private, video-grouped three-category development catalogue.

Metadata only: no image download, outcome access, inference or fitting.
This is not an authorization to train: the authoritative image catalogue,
rights, byte/decoded-duplicate checks and private split seal remain gates.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import argparse
import json
from pathlib import Path

from audit_kvasir_official_splits import _read
from capsule_review.priority import uniform_midpoints

CLASSES = ('Angiectasia', 'Erosion', 'Normal')
EXPECTED = ('fc7ed45cb061a378403c1b31375345462c90408960ee555727f7c00f8c3c0b3d',
            '5757b5ac99bdba4642edc2fde7eb2e1dbb2e0392b591b6866ec837720508134a')


def prepare(first, second, *, authenticate=True):
    parts = [_read(first), _read(second)]
    if authenticate and tuple(p['sha256'] for p in parts) != EXPECTED:
        raise ValueError('Published split catalogue version differs from the inspected source.')
    frames = defaultdict(set)
    for part in parts:
        for key, labels in part['files'].items():
            frames[key].update(labels)
    eligible = {key: next(iter(labels)) for key, labels in frames.items()
                if len(labels) == 1 and next(iter(labels)) in CLASSES}
    groups = defaultdict(set)
    for (video, _), label in eligible.items():
        groups[video].add(label)
    order = sorted(groups, key=lambda v: sha256(('CR-MA-01-v1|' + v).encode()).hexdigest())
    assignment = {}
    support = {split: Counter() for split in ('test', 'validation', 'train')}
    for split, minimum in (('test', 2), ('validation', 1)):
        for label in CLASSES:
            while support[split][label] < minimum:
                available = [v for v in order if v not in assignment and label in groups[v]]
                if not available:
                    raise ValueError('Insufficient video support for the fixed split.')
                video = available[0]
                assignment[video] = split
                support[split].update(groups[video])
    for video in order:
        if video not in assignment:
            assignment[video] = 'train'
            support['train'].update(groups[video])
    if any(support['train'][label] < 3 for label in CLASSES):
        raise ValueError('Fewer than three training videos for a target category; stop.')
    buckets = defaultdict(list)
    for (video, index), label in eligible.items():
        buckets[video, label].append(index)
    selected = []
    for (video, label), indices in sorted(buckets.items()):
        indices.sort()
        # Uniform coverage of published selected frames, not inferred video time.
        for pos in uniform_midpoints(len(indices), min(128, len(indices))):
            selected.append({'video': video, 'frame_index': indices[pos], 'label': label,
                             'split': assignment[video]})
    return {
        'schema_version': 'capsule-review-multi-abnormality-catalogue-v1',
        'status': 'METADATA_PREPARED_NOT_FIT_AUTHORIZED', 'experiment': 'CR-MA-01',
        'source_commit': '553601dc316fef82f39c952e28f60aaad66039e2',
        'catalogue_sha256': [p['sha256'] for p in parts], 'classes': list(CLASSES),
        'eligible_rows': dict(Counter(eligible.values())),
        'excluded_multilabel_frames': sum(len(labels)>1 for labels in frames.values()),
        'video_support': {s: dict(c) for s,c in support.items()},
        'selected_support': {s: dict(Counter(r['label'] for r in selected if r['split']==s)) for s in support},
        'records_private': selected,
        'gates': ['Reconcile published labels with authoritative metadata and archive membership.',
                  'Map source keys to real files without guessing extension or frame numbering.',
                  'Seal image SHA256 and decoded-pixel duplicate connected components; regroup or stop on overlap.',
                  'Confirm research-use terms and institutional requirements.',
                  'Retain a private split/method seal before fitting; no test outcome access.'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path); parser.add_argument('second', type=Path)
    parser.add_argument('--output-private', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.first,args.second)
    with args.output_private.open('x') as out:
        json.dump(result,out,indent=2,sort_keys=True); out.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'records_private'},indent=2,sort_keys=True))
