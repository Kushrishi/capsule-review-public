"""Generated CSVs only: no original annotations, pixels or trained models."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts import verify_galar_eligibility as gate


def text(binary='0', extra='concealed clinical text'):
    return f'frame,blood,other\n0,{binary},{extra}\n5,,ignored\n10,{binary},ignored\n15,{binary},ignored\n'


def package(tmp_path, content):
    path = tmp_path / 'synthetic.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for exam in gate.EXAMS:
            z.writestr(f'{exam}.csv', content)
        z.writestr('61.csv', 'INVALID RESERVED MEMBER MUST NOT BE READ')
    return path, gate.digest_file(path)


def test_binary_polarity_and_unrelated_clinical_values_cannot_change_projection():
    first = gate.project_csv(io.StringIO(text('0', 'DO_NOT_DISCLOSE_FIRST')))
    second = gate.project_csv(io.StringIO(text('1', 'DO_NOT_DISCLOSE_SECOND')))
    assert gate.canonical(first) == gate.canonical(second)
    assert first[1] == {'frame': 5, 'eligibility': 'unknown'}
    assert set(first[0]) == {'frame', 'eligibility'}
    assert b'DO_NOT_DISCLOSE' not in gate.canonical(first)


def test_archive_reads_only_allowlisted_members(tmp_path, monkeypatch):
    path, sha = package(tmp_path, text())
    visited = []
    original = zipfile.ZipFile.open

    def tracked(self, name, *args, **kwargs):
        visited.append(name.filename if hasattr(name, 'filename') else name)
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, 'open', tracked)
    result = gate.project_archive(path, expected_sha256=sha)
    assert visited == [f'{e}.csv' for e in gate.EXAMS]
    assert set(result) == {str(e) for e in gate.EXAMS}


def test_wrong_outer_hash_stops_before_decompressing_any_member(tmp_path, monkeypatch):
    path, _ = package(tmp_path, text())
    monkeypatch.setattr(zipfile.ZipFile, 'open', lambda *a, **kw: pytest.fail('Member opened'))
    with pytest.raises(ValueError, match='identity mismatch'):
        gate.project_archive(path, expected_sha256='0' * 64)


@pytest.mark.parametrize('csv_text', [
    'frame,blood\n0,0\n0,1\n', 'frame,blood\n5,0\n0,1\n',
    'frame,blood\nBAD,0\n', 'frame,blood\n0,SECRET_OUTCOME\n',
    'frame,blood,blood\n0,0,1\n', 'frame,blood\n0\n', 'frame,blood\n',
])
def test_malformed_projection_is_rejected_without_raw_values(csv_text):
    with pytest.raises(ValueError) as error:
        gate.project_csv(io.StringIO(csv_text))
    assert 'SECRET_OUTCOME' not in str(error.value)


def test_missing_image_binary_unknown_and_absent_rows_are_distinct():
    images = {str(e): {0, 5, 15} for e in gate.EXAMS}
    source = {str(e): gate.project_csv(io.StringIO(text())) for e in gate.EXAMS}
    result = gate.compare_projection(source, images)
    assert result['all_eligible_images_present'] is False
    assert result['aggregate']['15']['eligible_images_missing'] == 1
    assert result['aggregate']['15']['inferred_gap_eligible_rows'] == 1
    assert result['private_examinations']['15']['missing_eligible_source_frames'] == [10]
    # Prespecified alternatives: a genuinely unknown row or no annotation row.
    for replacement, category in [(
        text().replace('10,0,ignored', '10,,ignored'), 'inferred_gap_unknown_rows'),
        (text().replace('10,0,ignored\n', ''), 'inferred_gap_absent_rows')]:
        source = {str(e): gate.project_csv(io.StringIO(replacement)) for e in gate.EXAMS}
        result = gate.compare_projection(source, images)
        assert result['all_eligible_images_present'] is True
        assert result['aggregate']['15'][category] == 1
        assert result['aggregate']['15']['eligible_images_missing'] == 0


def test_endpoints_are_checked_instead_of_only_internal_grid_gaps():
    images = {str(e): {5, 10, 15} for e in gate.EXAMS}
    projection = {str(e): gate.project_csv(io.StringIO(text())) for e in gate.EXAMS}
    result = gate.compare_projection(projection, images)
    assert result['aggregate']['15']['inferred_gap_eligible_rows'] == 0
    assert result['aggregate']['15']['eligible_images_missing'] == 1


def test_invalid_external_action_is_denied():
    for event in ['socket.__new__', 'subprocess.Popen', 'os.system', 'os.fork']:
        with pytest.raises(RuntimeError, match='forbidden'):
            gate.deny_external_actions(event, ())


def test_cli_failure_has_no_traceback_cells_or_partial_record(tmp_path):
    path, _ = package(tmp_path, text('0', 'SECRET_OUTCOME'))
    listing = tmp_path / 'listing.txt'
    listing.write_text('not a real listing')
    amendment = tmp_path / 'amendment.md'
    amendment.write_text('generated synthetic amendment')
    output = tmp_path / 'private.json'
    result = subprocess.run([
        sys.executable, '-I', '-S', str(Path(gate.__file__).resolve()),
        '--labels', str(path), '--listing', str(listing),
        '--listing-sha256', gate.digest_file(listing), '--amendment', str(amendment),
        '--amendment-sha256', gate.digest_file(amendment),
        '--amendment-commit', 'a' * 40, '--output', str(output),
    ], capture_output=True, text=True, env={'PATH': '/usr/bin:/bin'}, timeout=10)
    assert result.returncode == 1
    assert result.stdout == ''
    assert 'SECRET_OUTCOME' not in result.stderr and 'Traceback' not in result.stderr
    assert not output.exists()


def test_aggregate_and_coverage_are_invariant_to_binary_polarity():
    images = {str(e): {0, 5, 15} for e in gate.EXAMS}
    outputs = []
    for binary in ['0', '1']:
        source = {str(e): gate.project_csv(io.StringIO(text(binary))) for e in gate.EXAMS}
        outputs.append(gate.canonical(gate.compare_projection(source, images)))
    assert outputs[0] == outputs[1]
    aggregate = gate.compare_projection(source, images)['aggregate']
    assert 'source_frames' not in str(aggregate) and 'positive' not in str(aggregate)
