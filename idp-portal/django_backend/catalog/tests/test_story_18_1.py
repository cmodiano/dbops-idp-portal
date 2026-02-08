"""
Tests for Story 18.1: Admin Actions — suppression, désactivation et filtres.
Covers AC1-AC6: hard delete, soft delete, cascade, filters, reactivate, conditional buttons.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from idp_auth.models import User
from catalog.models import Action, ActionStatus, ActionItemType, Tag, ActionTag
from catalog.services import CatalogService
from core.exceptions import ConflictError
from core.models import AuditLog
from tests.factories import UserFactory


def _create_dbops_user(username='dbops_user'):
    return UserFactory(username=username, profile='dbops')


def _create_regular_user(username='regular_user'):
    return UserFactory(username=username, profile='dba')


def _create_action(name='Test Action', user=None, item_type='action', action_status='draft'):
    return Action.objects.create(
        name=name,
        description=f'Description for {name}',
        engine='Oracle',
        platform='AAP',
        status=action_status,
        item_type=item_type,
        created_by=user,
    )


def _create_execution(action, user=None):
    """Create a fake execution for the action."""
    from executions.models import Execution, ExecutionStatus
    return Execution.objects.create(
        action=action,
        user=user,
        status=ExecutionStatus.COMPLETED,
        parameters={},
    )


# ─── AC1: Hard delete (execution_count = 0) ───────────────────────────────

@pytest.mark.django_db
class TestDeleteActionNoExecutions(TestCase):
    """AC1: Suppression des actions jamais exécutées."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        self.action = _create_action(user=self.dbops_user)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_delete_action_success(self, _mock_perm):
        """DELETE /admin/actions/{id} — 204 quand execution_count=0."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.delete(f'/api/v1/admin/actions/{self.action.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Action.objects.filter(id=self.action.id).exists())

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_delete_action_creates_audit_entry(self, _mock_perm):
        """DELETE creates audit log entry with action_type='ACTION_DELETED'."""
        self.client.force_authenticate(user=self.dbops_user)
        action_id = self.action.id
        self.client.delete(f'/api/v1/admin/actions/{action_id}/')
        audit = AuditLog.objects.filter(entity_id=action_id, action_type='ACTION_DELETED')
        self.assertTrue(audit.exists())

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_delete_action_conflict_executions_exist(self, _mock_perm):
        """DELETE returns 409 when action has executions."""
        self.client.force_authenticate(user=self.dbops_user)
        _create_execution(self.action, self.dbops_user)
        response = self.client.delete(f'/api/v1/admin/actions/{self.action.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error']['code'], 'EXECUTION_EXISTS')
        # Action not deleted
        self.assertTrue(Action.objects.filter(id=self.action.id).exists())

    def test_delete_action_forbidden_non_admin(self):
        """DELETE returns 403 for non-DBOPS users."""
        regular_user = _create_regular_user()
        self.client.force_authenticate(user=regular_user)
        response = self.client.delete(f'/api/v1/admin/actions/{self.action.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_delete_action_not_found(self, _mock_perm):
        """DELETE returns 404 for non-existent action."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.delete('/api/v1/admin/actions/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─── AC2: Soft delete / deactivation ──────────────────────────────────────

@pytest.mark.django_db
class TestDeactivateAction(TestCase):
    """AC2: Désactivation des actions avec historique d'exécution."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        self.action = _create_action(
            name='Action Published',
            user=self.dbops_user,
            action_status='published',
        )

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_action_no_workflows(self, _mock_perm):
        """PUT /admin/actions/{id}/deactivate — success, no cascade."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            {'deletion_reason': 'Plus utilisée'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, 'disabled')
        self.assertIsNotNone(self.action.deleted_at)
        self.assertEqual(self.action.deleted_by, self.dbops_user)
        self.assertEqual(self.action.deletion_reason, 'Plus utilisée')

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_already_disabled_returns_409(self, _mock_perm):
        """PUT deactivate returns 409 if already disabled."""
        self.client.force_authenticate(user=self.dbops_user)
        # First disable
        self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            format='json',
        )
        # Try again
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_creates_audit_entry(self, _mock_perm):
        """Deactivation creates audit log."""
        self.client.force_authenticate(user=self.dbops_user)
        self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            format='json',
        )
        audit = AuditLog.objects.filter(
            entity_id=self.action.id,
            action_type='ACTION_DEACTIVATED',
        )
        self.assertTrue(audit.exists())


# ─── AC3: Cascade to workflows ────────────────────────────────────────────

@pytest.mark.django_db
class TestDeactivateCascadeWorkflows(TestCase):
    """AC3: Cascade vers workflows référençant l'action."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        self.action = _create_action(
            name='Referenced Action',
            user=self.dbops_user,
            action_status='published',
        )
        # Create a workflow that references the action
        self.workflow = Action.objects.create(
            name='Workflow Referencing',
            description='Workflow with reference',
            engine='Oracle',
            platform='AAP',
            status='published',
            item_type='workflow',
            created_by=self.dbops_user,
            execution_steps=[
                {'order': 1, 'name': 'Step 1', 'referenced_action_id': self.action.id},
            ],
        )

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_requires_confirmation_when_workflows(self, _mock_perm):
        """PUT deactivate without confirmed returns requires_confirmation with workflow list."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'requires_confirmation')
        self.assertEqual(len(response.data['affected_workflows']), 1)
        self.assertEqual(response.data['affected_workflows'][0]['name'], 'Workflow Referencing')

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_cascades_workflows(self, _mock_perm):
        """PUT deactivate with confirmed=true cascades to workflows."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            {'deletion_reason': 'Cascade test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.status, 'disabled')
        self.assertIsNotNone(self.workflow.deleted_at)
        # Response includes deactivated workflows
        self.assertEqual(len(response.data['deactivated_workflows']), 1)


# ─── AC4/AC5: Filters ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestListActionsFilter(TestCase):
    """AC4/AC5: Filtre par défaut et toggle include_disabled."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        self.draft_action = _create_action(
            name='Draft Action', user=self.dbops_user, action_status='draft',
        )
        self.published_action = _create_action(
            name='Published Action', user=self.dbops_user, action_status='published',
        )
        from django.utils import timezone
        self.disabled_action = Action.objects.create(
            name='Disabled Action',
            description='Was disabled',
            engine='Oracle',
            platform='AAP',
            status='disabled',
            item_type='action',
            created_by=self.dbops_user,
            deleted_at=timezone.now(),
            deleted_by=self.dbops_user,
            deletion_reason='Test disable',
        )

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_list_actions_default_excludes_disabled(self, _mock_perm):
        """GET /admin/actions/ par défaut exclut les disabled."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a['name'] for a in response.data['data']]
        self.assertIn('Draft Action', names)
        self.assertIn('Published Action', names)
        self.assertNotIn('Disabled Action', names)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_list_actions_include_disabled_shows_all(self, _mock_perm):
        """GET /admin/actions/?include_disabled=true inclut les disabled."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/?include_disabled=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a['name'] for a in response.data['data']]
        self.assertIn('Draft Action', names)
        self.assertIn('Published Action', names)
        self.assertIn('Disabled Action', names)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_list_actions_includes_soft_delete_fields(self, _mock_perm):
        """GET /admin/actions/?include_disabled=true includes soft-delete fields."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/?include_disabled=true')
        disabled = next(a for a in response.data['data'] if a['name'] == 'Disabled Action')
        self.assertIsNotNone(disabled['deleted_at'])
        self.assertIsNotNone(disabled['deleted_by'])
        self.assertEqual(disabled['deletion_reason'], 'Test disable')


# ─── AC5: Reactivation ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReactivateAction(TestCase):
    """AC5: Réactivation d'une action désactivée."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        from django.utils import timezone
        self.disabled_action = Action.objects.create(
            name='Disabled Action',
            description='Disabled',
            engine='Oracle',
            platform='AAP',
            status='disabled',
            item_type='action',
            created_by=self.dbops_user,
            deleted_at=timezone.now(),
            deleted_by=self.dbops_user,
            deletion_reason='Test',
        )

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_reactivate_disabled_action(self, _mock_perm):
        """PUT /admin/actions/{id}/reactivate — 200, status=published, cleared soft-delete."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.disabled_action.id}/reactivate/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.disabled_action.refresh_from_db()
        self.assertEqual(self.disabled_action.status, 'published')
        self.assertIsNone(self.disabled_action.deleted_at)
        self.assertIsNone(self.disabled_action.deleted_by)
        self.assertIsNone(self.disabled_action.deletion_reason)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_reactivate_active_action_fails(self, _mock_perm):
        """PUT reactivate on a non-disabled action returns 409."""
        active = _create_action(name='Active', user=self.dbops_user, action_status='published')
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{active.id}/reactivate/',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_reactivate_creates_audit_entry(self, _mock_perm):
        """Reactivation creates audit log."""
        self.client.force_authenticate(user=self.dbops_user)
        self.client.put(
            f'/api/v1/admin/actions/{self.disabled_action.id}/reactivate/',
        )
        audit = AuditLog.objects.filter(
            entity_id=self.disabled_action.id,
            action_type='ACTION_REACTIVATED',
        )
        self.assertTrue(audit.exists())


# ─── Service layer unit tests ─────────────────────────────────────────────

@pytest.mark.django_db
class TestCatalogServiceDeleteDeactivate(TestCase):
    """Unit tests for CatalogService delete/deactivate/reactivate."""

    def setUp(self):
        self.user = _create_dbops_user()
        self.service = CatalogService()

    def test_delete_action_no_executions(self):
        """delete_action succeeds when no executions exist."""
        action = _create_action(user=self.user)
        result = self.service.delete_action(action.id, user=self.user)
        self.assertTrue(result)
        self.assertFalse(Action.objects.filter(id=action.id).exists())

    def test_delete_action_with_executions_raises_conflict(self):
        """delete_action raises ConflictError when executions exist."""
        action = _create_action(user=self.user)
        _create_execution(action, self.user)
        with self.assertRaises(ConflictError) as ctx:
            self.service.delete_action(action.id, user=self.user)
        self.assertEqual(ctx.exception.code, 'EXECUTION_EXISTS')

    def test_deactivate_action(self):
        """deactivate_action sets status=disabled with soft-delete fields."""
        action = _create_action(user=self.user, action_status='published')
        result = self.service.deactivate_action(action.id, user=self.user, deletion_reason='test')
        action.refresh_from_db()
        self.assertEqual(action.status, 'disabled')
        self.assertIsNotNone(action.deleted_at)
        self.assertEqual(action.deletion_reason, 'test')
        self.assertEqual(result['deactivated_workflows'], [])

    def test_reactivate_action(self):
        """reactivate_action resets status to published."""
        from django.utils import timezone
        action = Action.objects.create(
            name='To Reactivate', engine='Oracle', platform='AAP',
            status='disabled', item_type='action', created_by=self.user,
            deleted_at=timezone.now(), deleted_by=self.user,
        )
        result = self.service.reactivate_action(action.id, user=self.user)
        self.assertEqual(result.status, 'published')
        self.assertIsNone(result.deleted_at)

    def test_count_executions(self):
        """count_executions returns correct count."""
        action = _create_action(user=self.user)
        self.assertEqual(self.service.count_executions(action.id), 0)
        _create_execution(action, self.user)
        self.assertEqual(self.service.count_executions(action.id), 1)

    def test_find_workflows_referencing_action(self):
        """get_workflows_referencing_action returns correct list."""
        action = _create_action(user=self.user, action_status='published')
        wf = Action.objects.create(
            name='WF', engine='Oracle', platform='AAP',
            status='published', item_type='workflow', created_by=self.user,
            execution_steps=[{'order': 1, 'referenced_action_id': action.id}],
        )
        result = self.service.get_workflows_referencing_action(action.id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], wf.id)


# ─── RBAC tests ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRBACAdminEndpoints(TestCase):
    """Tests RBAC: non-admin rejected (403), admin accepted."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()
        self.regular_user = _create_regular_user()
        self.action = _create_action(user=self.dbops_user, action_status='published')

    def test_delete_forbidden_non_admin(self):
        """Non-admin cannot delete."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(f'/api/v1/admin/actions/{self.action.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivate_forbidden_non_admin(self):
        """Non-admin cannot deactivate."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/deactivate/?confirmed=true',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reactivate_forbidden_non_admin(self):
        """Non-admin cannot reactivate."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/reactivate/',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ─── Edge cases ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEdgeCases(TestCase):
    """Tests edge cases: action inexistante, double deactivation."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = _create_dbops_user()

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_delete_nonexistent_action(self, _mock_perm):
        """DELETE on non-existent action returns 404."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.delete('/api/v1/admin/actions/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_deactivate_nonexistent_action(self, _mock_perm):
        """PUT deactivate on non-existent action returns 404."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            '/api/v1/admin/actions/99999/deactivate/?confirmed=true',
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('core.permissions.DBOPSProfilePermission.has_permission', return_value=True)
    def test_reactivate_nonexistent_action(self, _mock_perm):
        """PUT reactivate on non-existent action returns 404."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put('/api/v1/admin/actions/99999/reactivate/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
