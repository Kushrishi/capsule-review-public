import csv
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_kvasir_multi_abnormality import prepare


def catalogues(tmp_path, positives=6):
    rows = []
    for category in ('Angiectasia','Erosion','Normal'):
        for video in range(positives):
            for frame in range(140):
                rows.append([f'{category}V{video}_{frame}.jpg',category])
    # An ambiguous multi-label source frame cannot become a forced single target.
    rows.extend([['Ambiguous_0.jpg','Erosion'],['Ambiguous_0.jpg','Ulcer']])
    paths = []
    for index, part in enumerate((rows[::2],rows[1::2])):
        path = tmp_path/f'{index}.csv'
        with path.open('w') as stream:
            writer = csv.writer(stream); writer.writerow(['filename','label']);writer.writerows(part)
        paths.append(path)
    return paths


def test_group_split_cap_and_repeatability(tmp_path):
    paths = catalogues(tmp_path)
    result = prepare(*paths, authenticate=False)
    assert result == prepare(*paths, authenticate=False)
    groups = {}
    counts = {}
    for row in result['records_private']:
        key = row['video'],row['label']
        counts[key] = counts.get(key,0)+1
        groups.setdefault(row['video'],set()).add(row['split'])
    assert all(len(splits)==1 for splits in groups.values())
    assert max(counts.values()) == 128
    assert result['excluded_multilabel_frames'] == 1
    assert all(row['video']!='Ambiguous' for row in result['records_private'])
    assert all(result['video_support']['train'][label]>=3 for label in result['classes'])
    assert result['status'] == 'METADATA_PREPARED_NOT_FIT_AUTHORIZED'


def test_sparse_support_stops_instead_of_relaxing_split(tmp_path):
    with pytest.raises(ValueError, match='support|training videos'):
        prepare(*catalogues(tmp_path,positives=3),authenticate=False)


def test_unknown_catalogue_version_fails(tmp_path):
    with pytest.raises(ValueError, match='version'):
        prepare(*catalogues(tmp_path))
