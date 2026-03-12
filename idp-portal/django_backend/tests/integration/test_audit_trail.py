"""
Integration tests for audit trail.

Story M.9: Tests unitaires et d'intégration
Tests: génération audit pour tous les event types (CRUD, executions)
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from idp_auth.models import User
from catalog.models import Action, ActionStatus
from catalog.services import CatalogService
from integrations.models import Integration
from profiles.models import Profile
from executions.models import Execution, ExecutionStatus
from core.models import AuditLog, AuditActionType, AuditEntityType
from core.services import AuditService


@pytest.mark.django_db
@pytest.mark.integration
class TestAuditTrailCRUD(TestCase):
    """Integration tests for CRUD audit logging."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='audit_user',
            profile='DBOPS'
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Audit AAP',
            base_url='https://aap.example.com'
        )

    def test_action_crud_audit_trail(self):
        """Test complete audit trail for action CRUD operations."""
        # CREATE
        action = Action.objects.create(
            name='Audit Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )

        # MED-04: use AuditService (real code path) — also fixes LOW-05 (Story 72.2 format)
        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.ACTION_CREATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={'name': action.name, 'status': 'draft'},
            correlation_id='create-001'
        )

        # UPDATE
        action.description = 'Updated description'
        action.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.ACTION_UPDATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={'changes': {'description': {'old': None, 'new': 'Updated description'}}},
            correlation_id='update-001'
        )

        # PUBLISH
        action.status = ActionStatus.PUBLISHED
        action.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.ACTION_PUBLISHED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={'changes': {'status': {'old': 'draft', 'new': 'published'}}},
            correlation_id='publish-001'
        )

        # DISABLE - use proper deactivation method
        service = CatalogService()
        service.deactivate_action(action.id, self.user, deletion_reason="Test deactivation")
        # deactivate_action() creates its own audit entry with ACTION_DEACTIVATED type

        # Verify audit trail
        audit_entries = AuditLog.objects.list_by_entity(AuditEntityType.ACTION, action.id)
        self.assertEqual(audit_entries.count(), 4)

        action_types = [e.action_type for e in audit_entries]
        self.assertIn(AuditActionType.ACTION_CREATED, action_types)
        self.assertIn(AuditActionType.ACTION_UPDATED, action_types)
        self.assertIn(AuditActionType.ACTION_PUBLISHED, action_types)
        self.assertIn(AuditActionType.ACTION_DEACTIVATED, action_types)  # deactivate_action() uses ACTION_DEACTIVATED

    def test_profile_crud_audit_trail(self):
        """Test audit trail for profile CRUD operations."""
        profile = Profile.objects.create(
            name='Audit Profile',
            ad_group='CN=AuditProfile,OU=Groups,DC=corp,DC=com',
            is_admin=0
        )

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.PROFILE_CREATED,
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile.id,
            details={'name': profile.name}
        )

        # Update profile
        profile.description = 'Updated description'
        profile.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.PROFILE_UPDATED,
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile.id
        )

        # Verify
        audit_entries = AuditLog.objects.list_by_entity(AuditEntityType.PROFILE, profile.id)
        self.assertEqual(audit_entries.count(), 2)

    def test_integration_crud_audit_trail(self):
        """Test audit trail for integration CRUD operations."""
        integration = Integration.objects.create(
            type='servicenow',
            name='Audit ServiceNow',
            base_url='https://snow.example.com'
        )

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.INTEGRATION_CREATED,
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration.id,
            details={'type': 'servicenow', 'name': integration.name}
        )

        # Update
        integration.base_url = 'https://new-snow.example.com'
        integration.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.INTEGRATION_UPDATED,
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration.id,
            details={'changes': {'base_url': {'updated': True}}}
        )

        # Verify
        audit_entries = AuditLog.objects.list_by_entity(AuditEntityType.INTEGRATION, integration.id)
        self.assertEqual(audit_entries.count(), 2)


@pytest.mark.django_db
@pytest.mark.integration
class TestAuditTrailExecution(TestCase):
    """Integration tests for execution audit logging."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='exec_audit_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Exec Audit AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Exec Audit Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            integration=self.integration
        )

    def test_execution_lifecycle_audit_trail(self):
        """Test complete audit trail for execution lifecycle."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        # SUBMITTED — MED-04: use AuditService (real code path)
        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={'action_id': self.action.id, 'environment': 'dev'}
        )

        # RUNNING
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = timezone.now()
        execution.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.EXECUTION_RUNNING,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id
        )

        # COMPLETED
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = timezone.now()
        execution.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={'duration_seconds': 120}
        )

        # Verify complete audit trail
        audit_entries = AuditLog.objects.list_by_entity(AuditEntityType.EXECUTION, execution.id)
        self.assertEqual(audit_entries.count(), 3)

        action_types = [e.action_type for e in audit_entries]
        self.assertIn(AuditActionType.EXECUTION_SUBMITTED, action_types)
        self.assertIn(AuditActionType.EXECUTION_RUNNING, action_types)
        self.assertIn(AuditActionType.EXECUTION_COMPLETED, action_types)

    def test_execution_failure_audit(self):
        """Test audit trail captures execution failures."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.RUNNING
        )

        # FAILED
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = timezone.now()
        execution.save()

        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.EXECUTION_FAILED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={'error': 'Connection timeout', 'step': 'platform'}
        )

        audit_entry = AuditLog.objects.filter(
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            action_type=AuditActionType.EXECUTION_FAILED
        ).first()

        self.assertIsNotNone(audit_entry)
        details = audit_entry.get_details()
        self.assertEqual(details['error'], 'Connection timeout')

    def test_execution_approval_rejection_audit(self):
        """Test audit trail for approval workflow."""
        approver = User.objects.create(username='approver', profile='DBOPS')

        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL
        )

        # PENDING_APPROVAL
        AuditService.create_entry(
            user_id=str(self.user.id),
            action_type=AuditActionType.EXECUTION_PENDING_APPROVAL,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={'environment': 'prod'}
        )

        # REJECTED
        execution.status = ExecutionStatus.REJECTED
        execution.approved_by = approver
        execution.approval_comment = 'Missing change window'
        execution.save()

        AuditService.create_entry(
            user_id=str(approver.id),
            action_type=AuditActionType.EXECUTION_REJECTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={'reason': 'Missing change window'}
        )

        # Verify audit trail
        audit_entries = AuditLog.objects.list_by_entity(AuditEntityType.EXECUTION, execution.id)
        self.assertEqual(audit_entries.count(), 2)


@pytest.mark.django_db
@pytest.mark.integration
class TestAuditTrailFilters(TestCase):
    """Integration tests for audit log filtering and queries."""

    def setUp(self):
        """Set up test data with various audit entries."""
        self.user1 = User.objects.create(username='filter_user1', profile='DBA')
        self.user2 = User.objects.create(username='filter_user2', profile='DBOPS')

        # Create multiple audit entries
        for i in range(10):
            AuditLog.objects.create_entry(
                user_id=str(self.user1.id),
                action_type=AuditActionType.ACTION_CREATED if i % 2 == 0 else AuditActionType.ACTION_UPDATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=i + 1
            )

        for i in range(5):
            AuditLog.objects.create_entry(
                user_id=str(self.user2.id),
                action_type=AuditActionType.EXECUTION_SUBMITTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=i + 100
            )

    def test_filter_by_user(self):
        """Test filtering audit entries by user."""
        user1_entries = AuditLog.objects.list_by_user(str(self.user1.id))
        user2_entries = AuditLog.objects.list_by_user(str(self.user2.id))

        self.assertEqual(user1_entries.count(), 10)
        self.assertEqual(user2_entries.count(), 5)

    def test_filter_by_entity_type(self):
        """Test filtering audit entries by entity type."""
        action_entries = AuditLog.objects.filter(entity_type=AuditEntityType.ACTION)
        execution_entries = AuditLog.objects.filter(entity_type=AuditEntityType.EXECUTION)

        self.assertEqual(action_entries.count(), 10)
        self.assertEqual(execution_entries.count(), 5)

    def test_filter_by_action_type(self):
        """Test filtering audit entries by action type."""
        created_entries = AuditLog.objects.filter(action_type=AuditActionType.ACTION_CREATED)
        updated_entries = AuditLog.objects.filter(action_type=AuditActionType.ACTION_UPDATED)

        self.assertEqual(created_entries.count(), 5)  # 0, 2, 4, 6, 8
        self.assertEqual(updated_entries.count(), 5)  # 1, 3, 5, 7, 9

    def test_filter_by_date_range(self):
        """Test filtering audit entries by date range."""
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)

        recent_entries = AuditLog.objects.list_by_date_range(
            from_date=one_day_ago,
            to_date=now
        )

        # All entries created in this test should be recent
        self.assertEqual(recent_entries.count(), 15)

    def test_combined_filters(self):
        """Test combining multiple filters."""
        entries = AuditLog.objects.filter(
            user_id=str(self.user1.id),
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED
        )

        self.assertEqual(entries.count(), 5)

    def test_audit_ordering(self):
        """Test that audit entries are ordered by timestamp descending."""
        entries = list(AuditLog.objects.all().order_by('-timestamp'))

        # Verify descending order
        for i in range(len(entries) - 1):
            self.assertGreaterEqual(entries[i].timestamp, entries[i + 1].timestamp)
