"""
Tests for integrations managers (IntegrationManager).
"""

import pytest
from django.test import TestCase
from integrations.models import Integration, IntegrationManager


@pytest.mark.django_db
class TestIntegrationManager(TestCase):
    """Tests for IntegrationManager."""
    
    def setUp(self):
        """Set up test data."""
        self.integration1 = Integration.objects.create(
            type='aap',
            name='AAP Integration',
            base_url='https://aap.example.com'
        )
        self.integration2 = Integration.objects.create(
            type='servicenow',
            name='ServiceNow Integration',
            base_url='https://servicenow.example.com'
        )
    
    def test_list_active(self):
        """Test list_active() returns all integrations."""
        results = Integration.objects.list_active()
        self.assertGreaterEqual(results.count(), 2)
    
    def test_get_by_type(self):
        """Test get_by_type() returns integration by type."""
        result = Integration.objects.get_by_type('aap')
        self.assertIsNotNone(result)
        self.assertEqual(result.type, 'aap')
        self.assertEqual(result.id, self.integration1.id)
