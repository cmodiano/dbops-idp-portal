"""
Tests for core managers (AuditLogManager).
"""

import pytest
from django.test import TestCase
from core.models import AuditLog, AuditLogManager


@pytest.mark.django_db
class TestAuditLogManager(TestCase):
    """Tests for AuditLogManager."""
    
    def test_create_entry(self):
        """Test create_entry() creates audit log entry."""
        entry = AuditLog.objects.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1,
            details={'name': 'Test Action'},
            ip_address='192.168.1.1'
        )
        
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.user_id, '123')
        self.assertEqual(entry.action_type, 'ACTION_CREATED')
        self.assertEqual(entry.entity_type, 'action')
        self.assertEqual(entry.entity_id, 1)
    
    def test_list_by_entity(self):
        """Test list_by_entity() returns audit entries for entity."""
        AuditLog.objects.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        AuditLog.objects.create_entry(
            user_id='123',
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=1
        )
        
        entries = AuditLog.objects.list_by_entity('action', 1)
        self.assertEqual(entries.count(), 2)
    
    def test_list_by_user(self):
        """Test list_by_user() returns audit entries for user."""
        AuditLog.objects.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        
        entries = AuditLog.objects.list_by_user('123')
        self.assertEqual(entries.count(), 1)
