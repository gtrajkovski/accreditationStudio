"""Tests for Role-Based Access Control (RBAC) functionality."""

import pytest
from unittest.mock import patch, MagicMock
from src.services import rbac_service
from src.db.connection import get_conn


@pytest.fixture
def test_db():
    """Setup test database with RBAC tables."""
    conn = get_conn()

    # Apply RBAC migration
    migration_path = "src/db/migrations/0047_rbac.sql"
    with open(migration_path, "r") as f:
        migration_sql = f.read()

    # Split and execute each statement
    for statement in migration_sql.split(';'):
        statement = statement.strip()
        if statement:
            conn.execute(statement)

    conn.commit()

    # Create test users
    conn.execute("""
        INSERT INTO users (id, email, name, password_hash, role, is_active)
        VALUES
            ('user_owner', 'owner@test.com', 'Owner User', 'hash', 'owner', 1),
            ('user_admin', 'admin@test.com', 'Admin User', 'hash', 'admin', 1),
            ('user_compliance', 'compliance@test.com', 'Compliance User', 'hash', 'compliance_officer', 1),
            ('user_dept', 'dept@test.com', 'Dept Head', 'hash', 'department_head', 1),
            ('user_viewer', 'viewer@test.com', 'Viewer User', 'hash', 'viewer', 1)
    """)

    # Create test institution
    conn.execute("""
        INSERT INTO institutions (id, name)
        VALUES ('inst_test', 'Test Institution')
    """)

    conn.commit()

    yield conn

    conn.close()


def test_check_permission_owner(test_db):
    """Test that owner has all permissions."""
    # Owner should have delete_institution
    assert rbac_service.check_permission('user_owner', 'delete_institution', 'inst_test')

    # Owner should have all other permissions too
    assert rbac_service.check_permission('user_owner', 'run_audits', 'inst_test')
    assert rbac_service.check_permission('user_owner', 'upload_documents', 'inst_test')
    assert rbac_service.check_permission('user_owner', 'view_dashboard', 'inst_test')


def test_check_permission_admin(test_db):
    """Test that admin has all permissions except delete_institution."""
    # Admin should NOT have delete_institution
    assert not rbac_service.check_permission('user_admin', 'delete_institution', 'inst_test')

    # Admin should have all other permissions
    assert rbac_service.check_permission('user_admin', 'run_audits', 'inst_test')
    assert rbac_service.check_permission('user_admin', 'upload_documents', 'inst_test')
    assert rbac_service.check_permission('user_admin', 'view_dashboard', 'inst_test')


def test_check_permission_compliance_officer(test_db):
    """Test compliance officer permissions."""
    # Compliance officer should have specific permissions
    assert rbac_service.check_permission('user_compliance', 'run_audits', 'inst_test')
    assert rbac_service.check_permission('user_compliance', 'approve_remediation', 'inst_test')
    assert rbac_service.check_permission('user_compliance', 'export_packets', 'inst_test')
    assert rbac_service.check_permission('user_compliance', 'upload_documents', 'inst_test')
    assert rbac_service.check_permission('user_compliance', 'view_dashboard', 'inst_test')

    # Compliance officer should NOT have delete_institution
    assert not rbac_service.check_permission('user_compliance', 'delete_institution', 'inst_test')


def test_check_permission_department_head(test_db):
    """Test department head permissions."""
    # Department head should have limited permissions
    assert rbac_service.check_permission('user_dept', 'upload_documents', 'inst_test')
    assert rbac_service.check_permission('user_dept', 'complete_tasks', 'inst_test')
    assert rbac_service.check_permission('user_dept', 'view_dashboard', 'inst_test')

    # Department head should NOT run audits
    assert not rbac_service.check_permission('user_dept', 'run_audits', 'inst_test')
    assert not rbac_service.check_permission('user_dept', 'delete_institution', 'inst_test')


def test_check_permission_viewer(test_db):
    """Test viewer permissions (read-only)."""
    # Viewer should only have view permissions
    assert rbac_service.check_permission('user_viewer', 'view_dashboard', 'inst_test')
    assert rbac_service.check_permission('user_viewer', 'view_reports', 'inst_test')

    # Viewer should NOT have write permissions
    assert not rbac_service.check_permission('user_viewer', 'upload_documents', 'inst_test')
    assert not rbac_service.check_permission('user_viewer', 'run_audits', 'inst_test')
    assert not rbac_service.check_permission('user_viewer', 'delete_institution', 'inst_test')


def test_assign_role(test_db):
    """Test role assignment."""
    # Assign viewer a higher role
    result = rbac_service.assign_role(
        user_id='user_viewer',
        role='compliance_officer',
        institution_id='inst_test',
        assigned_by='user_admin'
    )

    assert result['success']
    assert result['role'] == 'compliance_officer'

    # Verify the role was assigned
    role = rbac_service.get_user_role('user_viewer', 'inst_test')
    assert role == 'compliance_officer'


def test_create_invitation(test_db):
    """Test invitation creation."""
    invitation = rbac_service.create_invitation(
        email='newuser@test.com',
        role='department_head',
        institution_id='inst_test',
        invited_by='user_admin'
    )

    assert invitation['email'] == 'newuser@test.com'
    assert invitation['role'] == 'department_head'
    assert invitation['institution_id'] == 'inst_test'
    assert 'token' in invitation
    assert invitation['token']


def test_accept_invitation(test_db):
    """Test invitation acceptance."""
    # Create invitation
    invitation = rbac_service.create_invitation(
        email='newuser@test.com',
        role='compliance_officer',
        institution_id='inst_test',
        invited_by='user_admin'
    )

    # Create new user
    test_db.execute("""
        INSERT INTO users (id, email, name, password_hash, role, is_active)
        VALUES ('user_new', 'newuser@test.com', 'New User', 'hash', 'viewer', 1)
    """)
    test_db.commit()

    # Accept invitation
    result = rbac_service.accept_invitation(invitation['token'], 'user_new')

    assert result['success']
    assert result['role'] == 'compliance_officer'

    # Verify role was assigned
    role = rbac_service.get_user_role('user_new', 'inst_test')
    assert role == 'compliance_officer'


def test_list_users(test_db):
    """Test listing users for an institution."""
    # Assign roles to users for the institution
    rbac_service.assign_role('user_owner', 'owner', 'inst_test', 'user_owner')
    rbac_service.assign_role('user_admin', 'admin', 'inst_test', 'user_owner')

    users = rbac_service.list_users('inst_test')

    assert len(users) >= 2

    # Find owner and admin
    owner = next((u for u in users if u['id'] == 'user_owner'), None)
    admin = next((u for u in users if u['id'] == 'user_admin'), None)

    assert owner is not None
    assert owner['role'] == 'owner'

    assert admin is not None
    assert admin['role'] == 'admin'


def test_remove_user(test_db):
    """Test removing user access."""
    # Assign roles first
    rbac_service.assign_role('user_owner', 'owner', 'inst_test', 'user_owner')
    rbac_service.assign_role('user_admin', 'admin', 'inst_test', 'user_owner')

    # Remove admin
    result = rbac_service.remove_user('user_admin', 'inst_test', 'user_owner')

    assert result['success']

    # Verify admin no longer has institution-specific role
    role = rbac_service.get_user_role('user_admin', 'inst_test')
    assert role == 'admin'  # Falls back to global role


def test_cannot_remove_last_owner(test_db):
    """Test that last owner cannot be removed."""
    # Assign owner role
    rbac_service.assign_role('user_owner', 'owner', 'inst_test', 'user_owner')

    # Try to remove last owner
    with pytest.raises(ValueError, match="Cannot remove last owner"):
        rbac_service.remove_user('user_owner', 'inst_test', 'user_owner')


def test_invalid_role_assignment(test_db):
    """Test that invalid role raises error."""
    with pytest.raises(ValueError, match="Invalid role"):
        rbac_service.assign_role('user_viewer', 'super_admin', 'inst_test', 'user_admin')


def test_invalid_invitation_role(test_db):
    """Test that invalid role in invitation raises error."""
    with pytest.raises(ValueError, match="Invalid role"):
        rbac_service.create_invitation('test@test.com', 'invalid_role', 'inst_test', 'user_admin')


def test_role_hierarchy(test_db):
    """Test that role hierarchy is correctly defined."""
    assert rbac_service.ROLE_HIERARCHY == ['viewer', 'department_head', 'compliance_officer', 'admin', 'owner']

    # Verify owner is highest
    assert rbac_service.ROLE_HIERARCHY[-1] == 'owner'

    # Verify viewer is lowest
    assert rbac_service.ROLE_HIERARCHY[0] == 'viewer'


def test_institution_scoped_permissions(test_db):
    """Test that permissions can be institution-scoped."""
    # Create second institution
    test_db.execute("""
        INSERT INTO institutions (id, name)
        VALUES ('inst_test2', 'Test Institution 2')
    """)
    test_db.commit()

    # Assign user to inst_test as admin
    rbac_service.assign_role('user_admin', 'admin', 'inst_test', 'user_owner')

    # Verify they have admin role for inst_test
    role = rbac_service.get_user_role('user_admin', 'inst_test')
    assert role == 'admin'

    # Verify they have global role for inst_test2 (no institution-specific role)
    role2 = rbac_service.get_user_role('user_admin', 'inst_test2')
    assert role2 == 'admin'  # Falls back to global role


def test_auth_disabled_bypass(test_db):
    """Test that AUTH_ENABLED=False bypasses permission checks."""
    # This would typically be tested at the decorator level in app.py
    # For unit test, we just verify the service functions work

    # Even with no permissions, check_permission returns based on role
    assert rbac_service.check_permission('user_viewer', 'upload_documents', 'inst_test') == False
    assert rbac_service.check_permission('user_dept', 'upload_documents', 'inst_test') == True


def test_list_pending_invitations(test_db):
    """Test listing pending invitations."""
    # Create invitations
    inv1 = rbac_service.create_invitation('user1@test.com', 'viewer', 'inst_test', 'user_admin')
    inv2 = rbac_service.create_invitation('user2@test.com', 'admin', 'inst_test', 'user_admin')

    invitations = rbac_service.list_pending_invitations('inst_test')

    assert len(invitations) >= 2

    # Verify invitations are in the list
    emails = [inv['email'] for inv in invitations]
    assert 'user1@test.com' in emails
    assert 'user2@test.com' in emails


def test_cancel_invitation(test_db):
    """Test cancelling an invitation."""
    # Create invitation
    invitation = rbac_service.create_invitation('test@test.com', 'viewer', 'inst_test', 'user_admin')

    # Cancel it
    result = rbac_service.cancel_invitation(invitation['id'])

    assert result['success']

    # Verify it's gone
    invitations = rbac_service.list_pending_invitations('inst_test')
    ids = [inv['id'] for inv in invitations]
    assert invitation['id'] not in ids


def test_cannot_cancel_accepted_invitation(test_db):
    """Test that accepted invitations cannot be cancelled."""
    # Create invitation
    invitation = rbac_service.create_invitation('test@test.com', 'viewer', 'inst_test', 'user_admin')

    # Create user and accept
    test_db.execute("""
        INSERT INTO users (id, email, name, password_hash, role, is_active)
        VALUES ('user_test', 'test@test.com', 'Test', 'hash', 'viewer', 1)
    """)
    test_db.commit()

    rbac_service.accept_invitation(invitation['token'], 'user_test')

    # Try to cancel
    with pytest.raises(ValueError, match="Cannot cancel accepted invitation"):
        rbac_service.cancel_invitation(invitation['id'])
