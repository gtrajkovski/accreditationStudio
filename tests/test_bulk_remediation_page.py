"""Tests for bulk remediation page route."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    """Create a test Flask app."""
    # Patch AI client before importing app
    with patch('src.ai.client.AIClient'):
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        yield flask_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_institution():
    """Create a mock institution."""
    from src.core.models import Institution, Program
    inst = Institution(
        id="inst_test123",
        name="Test University"
    )
    inst.programs = [
        Program(id="prog_1", name="Program A"),
        Program(id="prog_2", name="Program B")
    ]
    return inst


def test_bulk_remediation_page_loads(client, mock_institution):
    """Verify bulk remediation page renders for valid institution."""
    with patch('app.workspace_manager') as mock_wm:
        mock_wm.load_institution.return_value = mock_institution
        with patch('app.get_conn') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {'doc_type': 'policy'},
                {'doc_type': 'catalog'}
            ]
            mock_conn.return_value.execute.return_value = mock_cursor
            with patch('app._get_readiness_score', return_value=75):
                response = client.get('/institutions/inst_test123/bulk-remediation')

    assert response.status_code == 200
    assert b'Bulk Remediation' in response.data or b'bulk' in response.data.lower()


def test_bulk_remediation_page_404_for_invalid_institution(client):
    """Verify 404 returned for non-existent institution."""
    with patch('app.workspace_manager') as mock_wm:
        mock_wm.load_institution.return_value = None
        response = client.get('/institutions/invalid_id/bulk-remediation')

    assert response.status_code == 404


def test_bulk_remediation_page_has_scope_options(client, mock_institution):
    """Verify page includes scope selection options."""
    with patch('app.workspace_manager') as mock_wm:
        mock_wm.load_institution.return_value = mock_institution
        with patch('app.get_conn') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.execute.return_value = mock_cursor
            with patch('app._get_readiness_score', return_value=75):
                response = client.get('/institutions/inst_test123/bulk-remediation')

    html = response.data.decode('utf-8')
    # Check for scope type radio inputs
    assert 'name="scope_type"' in html
    assert 'value="all"' in html


def test_bulk_remediation_page_includes_programs(client, mock_institution):
    """Verify page includes program options for scope selection."""
    with patch('app.workspace_manager') as mock_wm:
        mock_wm.load_institution.return_value = mock_institution
        with patch('app.get_conn') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.execute.return_value = mock_cursor
            with patch('app._get_readiness_score', return_value=75):
                response = client.get('/institutions/inst_test123/bulk-remediation')

    html = response.data.decode('utf-8')
    # Check that programs are included
    assert 'Program A' in html or 'program-select' in html
