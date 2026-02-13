import pytest
from django.test import TestCase
from core.models import AuditLog


@pytest.mark.django_db
class AuditLogModelTest(TestCase):
    """Tests for AuditLog model."""

    def test_create_audit_log(self):
        """Test creating an audit log entry."""
        audit = AuditLog.objects.create(
            user_id='testuser',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1,
            details='{"action_name": "Test Action"}',
            ip_address='192.168.1.1'
        )
        self.assertEqual(audit.user_id, 'testuser')
        self.assertEqual(audit.action_type, 'ACTION_CREATED')
        self.assertEqual(audit.entity_type, 'action')
        self.assertEqual(audit.entity_id, 1)
        self.assertIsNotNone(audit.id)
        self.assertIsNotNone(audit.timestamp)

    def test_audit_log_json_details(self):
        """Test JSON details field helper."""
        details = {'action_name': 'Test Action', 'previous_status': 'draft', 'new_status': 'published'}
        # AuditLog is immutable - must set details at creation time
        audit = AuditLog.objects.create(
            user_id='testuser',
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=1
        )
        audit.set_details(details)
        # Don't save - AuditLog is immutable, just test get_details works
        self.assertEqual(audit.get_details(), details)

    def test_audit_log_str(self):
        """Test AuditLog __str__ method."""
        audit = AuditLog.objects.create(
            user_id='testuser',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        self.assertIn('ACTION_CREATED', str(audit))
        self.assertIn('action', str(audit))
