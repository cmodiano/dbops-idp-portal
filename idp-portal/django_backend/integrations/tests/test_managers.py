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

    # =========================================================================
    # Story M.9: Additional manager tests for edge cases
    # =========================================================================

    def test_get_by_type_nonexistent(self):
        """Test get_by_type() with non-existent type returns None."""
        result = Integration.objects.get_by_type('nonexistent')
        self.assertIsNone(result)

    def test_get_by_type_returns_most_recent(self):
        """Test get_by_type() returns most recently created integration of type."""
        newer_aap = Integration.objects.create(
            type='aap',
            name='Newer AAP Integration',
            base_url='https://newer-aap.example.com'
        )

        result = Integration.objects.get_by_type('aap')
        self.assertIsNotNone(result)
        # Should return the newer one (most recent by created_at)
        self.assertEqual(result.id, newer_aap.id)

    def test_list_active_ordering(self):
        """Test list_active() returns integrations ordered by name."""
        Integration.objects.create(
            type='terraform',
            name='A-Terraform',
            base_url='https://terraform.example.com'
        )

        results = list(Integration.objects.list_active())
        names = [i.name for i in results]
        self.assertEqual(names, sorted(names))


@pytest.mark.django_db
class TestIntegrationManagerAdvanced(TestCase):
    """Story M.9: Advanced tests for IntegrationManager."""

    def test_filter_by_type_multiple(self):
        """Test filtering integrations by multiple types."""
        Integration.objects.create(
            type='aap',
            name='AAP 1',
            base_url='https://aap1.example.com'
        )
        Integration.objects.create(
            type='servicenow',
            name='ServiceNow 1',
            base_url='https://snow1.example.com'
        )
        Integration.objects.create(
            type='terraform',
            name='Terraform 1',
            base_url='https://tf1.example.com'
        )

        aap_and_snow = Integration.objects.filter(type__in=['aap', 'servicenow'])
        self.assertEqual(aap_and_snow.count(), 2)

    def test_config_json_field(self):
        """Test integration config JSON field serialization."""
        config = {'timeout': 60, 'verify_ssl': False, 'retry_count': 3}
        integration = Integration.objects.create(
            type='aap',
            name='AAP with Config',
            base_url='https://aap.example.com'
        )
        integration.set_config(config)
        integration.save()

        # Reload from DB
        integration.refresh_from_db()
        loaded_config = integration.get_config()

        self.assertEqual(loaded_config['timeout'], 60)
        self.assertEqual(loaded_config['verify_ssl'], False)
        self.assertEqual(loaded_config['retry_count'], 3)

    def test_integration_auth_flows(self):
        """Test different authentication flows."""
        token_int = Integration.objects.create(
            type='aap',
            name='Token Auth',
            base_url='https://aap.example.com',
            auth_flow='token',
            token_url='https://aap.example.com/oauth/token'
        )
        basic_int = Integration.objects.create(
            type='servicenow',
            name='Basic Auth',
            base_url='https://snow.example.com',
            auth_flow='basic'
        )

        self.assertEqual(token_int.auth_flow, 'token')
        self.assertIsNotNone(token_int.token_url)
        self.assertEqual(basic_int.auth_flow, 'basic')
        self.assertIsNone(basic_int.token_url)
