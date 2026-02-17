import pytest
from django.test import TestCase
from integrations.models import Integration


@pytest.mark.django_db
class IntegrationModelTest(TestCase):
    """Tests for Integration model."""

    def test_create_integration(self):
        """Test creating an integration."""
        integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com',
            credential_ref='vault/path/to/creds',
            icon='aap-icon'
        )
        self.assertEqual(integration.type, 'aap')
        self.assertEqual(integration.name, 'Test AAP')
        self.assertEqual(integration.base_url, 'https://aap.example.com')
        self.assertIsNotNone(integration.id)
        self.assertIsNotNone(integration.created_at)
        self.assertIsNotNone(integration.updated_at)

    def test_integration_unique_name(self):
        """Test that integration name must be unique."""
        Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com'
        )
        with self.assertRaises(Exception):  # IntegrityError
            Integration.objects.create(
                type='servicenow',
                name='Test AAP',
                base_url='https://servicenow.example.com'
            )

    def test_integration_str(self):
        """Test Integration __str__ method."""
        integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com'
        )
        self.assertEqual(str(integration), 'Test AAP')
