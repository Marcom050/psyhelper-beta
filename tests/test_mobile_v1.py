from starlette.testclient import TestClient

from api.app import app


def test_v1_me_requires_auth():
    client = TestClient(app)
    response = client.get('/v1/me')
    assert response.status_code == 401
