import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from capsule_review.app import create_app
from capsule_review.importer import import_sources


@pytest.fixture
def image_bytes():
    image = Image.new('RGB', (64, 48), '#286a78')
    output = io.BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / 'workspace')


@pytest.fixture
def client(app):
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        yield client


@pytest.fixture
def headers(client):
    return {'X-Review-Token': client.get('/api/config').json()['token']}


@pytest.fixture
def study(app, image_bytes):
    return import_sources(app.state.store, [
        ('frame_000002.PNG', image_bytes), ('frame_000009.PNG', image_bytes),
        ('frame_000015.PNG', image_bytes),
    ], title='Local development example', source='Test-generated image bytes; not clinical data')
