"""Unit tests for change detection API endpoints."""

import pytest
from app import app


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_pending_count_returns_json(client):
    """Test GET /api/change-detection/pending-count returns JSON with count."""
    response = client.get('/api/change-detection/pending-count?institution_id=test_inst')
    assert response.status_code == 200
    data = response.get_json()
    assert 'count' in data
    assert isinstance(data['count'], int)


def test_get_reaudit_scope_no_pending_returns_empty(client):
    """Test GET /api/institutions/<id>/changes/scope returns empty when no changes."""
    response = client.get('/api/institutions/test_inst/changes/scope')
    assert response.status_code == 200
    data = response.get_json()
    assert data['total_to_audit'] == 0
    assert data['has_pending_changes'] == False
    assert data['affected_standards'] == []
    assert data['changed_documents'] == []
    assert data['impacted_documents'] == []


def test_preview_scope_requires_document_ids(client):
    """Test POST /api/institutions/<id>/changes/scope/preview requires document_ids."""
    response = client.post('/api/institutions/test_inst/changes/scope/preview',
                          json={})
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
