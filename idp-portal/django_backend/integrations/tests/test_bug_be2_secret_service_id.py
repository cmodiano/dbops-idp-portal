"""
Tests for BUG-BE-2: secret_service_id in Integration.objects.create() and update_integration().
Story 30.3 — AC1.
"""

import pytest
from django.test import TestCase
from integrations.models import Integration
from integrations.services import IntegrationService
from tests.factories import UserFactory


@pytest.mark.django_db
class TestSecretServiceIdCreate(TestCase):
    """Tests for secret_service_id in create_integration()."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        # Create a Vault integration to use as secret_service
        self.vault_integration = Integration.objects.create(
            type='vault',
            name='Vault Primary',
            base_url='https://vault.example.com',
        )

    def test_create_integration_with_secret_service_id(self):
        """create_integration() with secret_service_id sets FK correctly."""
        data = {
            'type': 'aap',
            'name': 'Test AAP with Vault',
            'base_url': 'https://aap.example.com',
            'secret_service_id': self.vault_integration.id,
        }

        integration = self.service.create_integration(data, user=self.user)

        self.assertEqual(integration.secret_service_id, self.vault_integration.id)
        self.assertEqual(integration.secret_service, self.vault_integration)

    def test_create_integration_with_secret_service_id_none(self):
        """create_integration() with secret_service_id=None keeps it None."""
        data = {
            'type': 'aap',
            'name': 'Test AAP no Vault',
            'base_url': 'https://aap.example.com',
            'secret_service_id': None,
        }

        integration = self.service.create_integration(data, user=self.user)

        self.assertIsNone(integration.secret_service_id)

    def test_create_integration_without_secret_service_id(self):
        """create_integration() without secret_service_id in data keeps it None."""
        data = {
            'type': 'aap',
            'name': 'Test AAP default',
            'base_url': 'https://aap.example.com',
        }

        integration = self.service.create_integration(data, user=self.user)

        self.assertIsNone(integration.secret_service_id)


@pytest.mark.django_db
class TestSecretServiceIdUpdate(TestCase):
    """Tests for secret_service_id in update_integration()."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.vault_integration = Integration.objects.create(
            type='vault',
            name='Vault Primary',
            base_url='https://vault.example.com',
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com',
        )

    def test_update_integration_with_secret_service_id(self):
        """update_integration() with secret_service_id=456 sets it."""
        update_data = {
            'secret_service_id': self.vault_integration.id,
        }

        updated = self.service.update_integration(
            self.integration.id, update_data, user=self.user
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.secret_service_id, self.vault_integration.id)

    def test_update_integration_clear_secret_service_id(self):
        """update_integration() with secret_service_id=None clears it."""
        # First set a value
        self.integration.secret_service = self.vault_integration
        self.integration.save()

        update_data = {
            'secret_service_id': None,
        }

        updated = self.service.update_integration(
            self.integration.id, update_data, user=self.user
        )

        self.assertIsNotNone(updated)
        self.assertIsNone(updated.secret_service_id)
