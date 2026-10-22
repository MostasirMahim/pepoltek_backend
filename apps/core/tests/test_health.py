import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_check_endpoint():
    client = APIClient()
    response = client.get('/api/v1/health/')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'django' in data
    assert 'python' in data
