"""A viewer must not silently present sparse source IDs as consecutive video."""

from capsule_review.source_coverage import summarize_source_spacing


def test_consecutive_indexed_input_does_not_claim_complete_video():
    result = summarize_source_spacing([100, 101, 102, 103])
    assert result['assessment'] == 'consecutive-imported-indices'
    assert result['adjacent_index_jumps'] == 0
    assert result['maximum_forward_index_step'] == 1
    assert result['complete_original_sequence_verified'] is False
    assert result['capture_time_verified'] is False


def test_sparse_indexed_input_discloses_jumps():
    result = summarize_source_spacing([2, 10, 15])
    assert result['assessment'] == 'index-jumps'
    assert result['adjacent_index_jumps'] == 2
    assert result['maximum_forward_index_step'] == 8


def test_unknown_and_out_of_order_fail_closed():
    unknown = summarize_source_spacing([10, None, 20])
    assert unknown['assessment'] == 'unknown'
    assert unknown['unnumbered_frames'] == 1
    assert unknown['adjacent_index_jumps'] == 0  # No invented adjacency across unknown source.
    assert summarize_source_spacing([100, 90])['assessment'] == 'nonmonotonic'
    assert summarize_source_spacing([7])['assessment'] == 'unknown'
    assert summarize_source_spacing([None, None])['assessment'] == 'unknown'


def test_viewer_exposes_correct_sparse_source_coverage(client, headers, image_bytes):
    response = client.post('/api/studies/import', headers=headers, data={'title':'Sparse source'}, files=[
        ('files', ('frame_10.png', image_bytes, 'image/png')),
        ('files', ('frame_2.png', image_bytes, 'image/png')),
    ])
    assert response.status_code == 201, response.text
    base = f"/api/studies/{response.json()['id']}"
    data = client.get(base + '/source-coverage').json()
    assert data['imported_frames'] == 2
    assert data['numbered_frames'] == 2
    assert data['adjacent_index_jumps'] == 1
    assert data['maximum_forward_index_step'] == 8
    assert data['assessment'] == 'index-jumps'
    assert client.get('/api/studies/missing/source-coverage').status_code == 404


def test_unindexed_names_cannot_be_assumed_contiguous(client, headers, image_bytes):
    response = client.post('/api/studies/import', headers=headers, data={'title':'Unknown spacing'}, files=[
        ('files', ('picture_a.png', image_bytes, 'image/png')),
        ('files', ('picture_b.png', image_bytes, 'image/png')),
    ])
    data = client.get(f"/api/studies/{response.json()['id']}/source-coverage").json()
    assert data['unnumbered_frames'] == 2
    assert data['assessment'] == 'unknown'


def test_browser_has_visible_continuity_warning(client):
    markup = client.get('/').text
    assert 'id="sourceContinuity"' in markup
    assert 'id="sourceStep"' in markup
