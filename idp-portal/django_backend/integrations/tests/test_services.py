"""
Tests for integrations services (IntegrationService).
"""

import pytest
from django.test import TestCase
from integrations.models import Integration
from integrations.services import IntegrationService
from core.models import AuditLog


@pytest.mark.django_db
class TestIntegrationService(TestCase):
    """Tests for IntegrationService."""
    
    def setUp(self):
        """Set up test data."""
        self.service = IntegrationService()
    
    def test_create_integration(self):
        """Test create_integration() creates integration with audit."""
        integration_data = {
            'type': 'aap',
            'name': 'Test AAP',
            'base_url': 'https://aap.example.com',
            'config': {'api_key': 'test123'}
        }
        
        integration = self.service.create_integration(integration_data)
        
        self.assertIsNotNone(integration.id)
        self.assertEqual(integration.name, 'Test AAP')
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='integration',
            entity_id=integration.id,
            action_type='INTEGRATION_CREATED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_get_integration_by_type(self):
        """Test get_integration_by_type() retrieves integration."""
        Integration.objects.create(
            type='aap',
            name='AAP Integration',
            base_url='https://aap.example.com'
        )
        
        result = self.service.get_integration_by_type('aap')
        self.assertIsNotNone(result)
        self.assertEqual(result.type, 'aap')
