"""
Tests for core services (AuditService).
"""

import pytest
from django.test import TestCase
from core.models import AuditLog
from core.services import AuditService


@pytest.mark.django_db
class TestAuditService(TestCase):
    """Tests for AuditService."""
    
    def test_create_entry(self):
        """Test create_entry() creates audit log entry."""
        entry = AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1,
            details={'name': 'Test Action'}
        )
        
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.user_id, '123')
        self.assertEqual(entry.action_type, 'ACTION_CREATED')
    
    def test_list_all_with_filters(self):
        """Test list_all() with filters."""
        AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        AuditService.create_entry(
            user_id='456',
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=2
        )
        
        # Filter by user_id
        results, total = AuditService.list_all(user_id='123')
        self.assertEqual(total, 1)
        
        # Filter by action_type
        results, total = AuditService.list_all(action_type='ACTION_CREATED')
        self.assertEqual(total, 1)
    
    def test_get_by_entity(self):
        """Test get_by_entity() returns audit entries for entity."""
        AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        
        entries = AuditService.get_by_entity('action', 1)
        self.assertEqual(entries.count(), 1)
