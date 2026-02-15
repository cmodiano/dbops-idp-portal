"""
Tests for Story 27.11 — secret_service_id and vault credential_ref validation.
Tests cover:
- Model: secret_service FK on Integration
- Serializer: credential_ref validation for vault type, secret_service_id validation
- API: Create/update integration with secret_service_id
"""

import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock

from integrations.models import Integration, IntegrationType
from integrations.serializers import (
    IntegrationCreateSerializer,
    IntegrationUpdateSerializer,
    IntegrationSerializer,
    IntegrationListSerializer,
)


@pytest.mark.django_db
class TestIntegrationSecretServiceModel(TestCase):
    """Tests for Integration.secret_service FK field."""

    def setUp(self):
        self.vault_integration = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Production',
            base_url='https://vault-prod.company.com',
        )

    def test_create_integration_with_secret_service(self):
        """An integration can reference a Vault integration as its secret service."""
        aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Production',
            base_url='https://aap.company.com',
            credential_ref='vault:secret/data/aap/prod#token',
            secret_service=self.vault_integration,
        )
        self.assertEqual(aap.secret_service_id, self.vault_integration.id)
        self.assertEqual(aap.secret_service, self.vault_integration)

    def test_create_integration_without_secret_service(self):
        """secret_service defaults to NULL."""
        aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Default',
            base_url='https://aap.company.com',
        )
        self.assertIsNone(aap.secret_service_id)
        self.assertIsNone(aap.secret_service)

    def test_vault_integration_no_secret_service(self):
        """Vault integrations should not have a secret_service (bootstrap problem)."""
        vault2 = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Dev',
            base_url='https://vault-dev.company.com',
        )
        self.assertIsNone(vault2.secret_service_id)

    def test_secret_service_set_null_on_delete(self):
        """When the Vault integration is deleted, secret_service_id is set to NULL."""
        aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP With Vault',
            base_url='https://aap.company.com',
            secret_service=self.vault_integration,
        )
        vault_id = self.vault_integration.id
        self.vault_integration.delete()
        aap.refresh_from_db()
        self.assertIsNone(aap.secret_service_id)

    def test_dependent_integrations_reverse_relation(self):
        """Vault integration can access its dependent integrations."""
        aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Prod',
            base_url='https://aap.company.com',
            secret_service=self.vault_integration,
        )
        tower = Integration.objects.create(
            type=IntegrationType.TOWER,
            name='Tower Prod',
            base_url='https://tower.company.com',
            secret_service=self.vault_integration,
        )
        dependents = list(self.vault_integration.dependent_integrations.all())
        self.assertEqual(len(dependents), 2)
        self.assertIn(aap, dependents)
        self.assertIn(tower, dependents)


@pytest.mark.django_db
class TestVaultCredentialRefValidation(TestCase):
    """Tests for credential_ref validation when type is vault."""

    def test_vault_type_with_credential_ref_rejected(self):
        """Creating a vault integration with credential_ref should fail validation."""
        data = {
            'type': 'vault',
            'name': 'Vault Test',
            'base_url': 'https://vault.example.com',
            'credential_ref': 'vault:secret/data/something#key',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('credential_ref', s.errors)

    def test_vault_type_without_credential_ref_accepted(self):
        """Creating a vault integration without credential_ref should succeed."""
        data = {
            'type': 'vault',
            'name': 'Vault OK',
            'base_url': 'https://vault.example.com',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_vault_type_with_empty_credential_ref_accepted(self):
        """Creating a vault integration with empty credential_ref should succeed."""
        data = {
            'type': 'vault',
            'name': 'Vault Empty',
            'base_url': 'https://vault.example.com',
            'credential_ref': '',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_vault_type_with_credential_ref_accepted(self):
        """Non-vault types can have credential_ref."""
        data = {
            'type': 'aap',
            'name': 'AAP Test',
            'base_url': 'https://aap.example.com',
            'credential_ref': 'vault:secret/data/aap/prod#token',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


@pytest.mark.django_db
class TestSecretServiceIdValidation(TestCase):
    """Tests for secret_service_id validation in create/update serializers."""

    def setUp(self):
        self.vault = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Prod',
            base_url='https://vault-prod.company.com',
        )
        self.aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Existing',
            base_url='https://aap.company.com',
        )

    def test_create_with_valid_secret_service_id(self):
        """Creating an integration with valid vault secret_service_id succeeds."""
        data = {
            'type': 'aap',
            'name': 'AAP New',
            'base_url': 'https://aap2.company.com',
            'secret_service_id': self.vault.id,
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_create_with_non_vault_secret_service_id_rejected(self):
        """secret_service_id must reference a vault integration."""
        data = {
            'type': 'tower',
            'name': 'Tower Test',
            'base_url': 'https://tower.company.com',
            'secret_service_id': self.aap.id,
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_create_with_nonexistent_secret_service_id_rejected(self):
        """secret_service_id must reference an existing integration."""
        data = {
            'type': 'aap',
            'name': 'AAP Bad Ref',
            'base_url': 'https://aap.company.com',
            'secret_service_id': 99999,
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_vault_type_with_secret_service_id_rejected(self):
        """Vault integrations cannot have a secret_service_id."""
        data = {
            'type': 'vault',
            'name': 'Vault Bad',
            'base_url': 'https://vault2.company.com',
            'secret_service_id': self.vault.id,
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_create_with_null_secret_service_id_accepted(self):
        """NULL secret_service_id is fine (default behavior)."""
        data = {
            'type': 'aap',
            'name': 'AAP Default Vault',
            'base_url': 'https://aap3.company.com',
            'secret_service_id': None,
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


@pytest.mark.django_db
class TestIntegrationSerializerSecretServiceId(TestCase):
    """Tests for secret_service_id in read serializers."""

    def setUp(self):
        self.vault = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Read',
            base_url='https://vault.company.com',
        )
        self.aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Read',
            base_url='https://aap.company.com',
            secret_service=self.vault,
        )

    def test_serializer_includes_secret_service_id(self):
        """IntegrationSerializer includes secret_service_id in output."""
        s = IntegrationSerializer(self.aap)
        self.assertEqual(s.data['secret_service_id'], self.vault.id)

    def test_serializer_null_secret_service_id(self):
        """IntegrationSerializer returns null for missing secret_service_id."""
        s = IntegrationSerializer(self.vault)
        self.assertIsNone(s.data['secret_service_id'])

    def test_list_serializer_includes_secret_service_id(self):
        """IntegrationListSerializer includes secret_service_id."""
        s = IntegrationListSerializer(self.aap)
        self.assertEqual(s.data['secret_service_id'], self.vault.id)


@pytest.mark.django_db
class TestResolveCredentialMultiInstance(TestCase):
    """Tests for resolve_credential() with multi-instance Vault."""

    def setUp(self):
        self.vault_prod = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Prod',
            base_url='https://vault-prod.company.com',
        )
        self.vault_dev = Integration.objects.create(
            type=IntegrationType.VAULT,
            name='Vault Dev',
            base_url='https://vault-dev.company.com',
        )
        self.aap = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Multi',
            base_url='https://aap.company.com',
            credential_ref='vault:secret/data/aap/prod#token',
            secret_service=self.vault_prod,
        )

    @patch('services.vault_service.VaultService')
    def test_resolve_with_custom_vault_instance(self, MockVaultService):
        """resolve_credential uses the specified Vault instance."""
        from adapters.utils import resolve_credential

        mock_instance = MagicMock()
        mock_instance.get_secret.return_value = 'resolved-token'
        MockVaultService.return_value = mock_instance

        result = resolve_credential(
            'vault:secret/data/aap/prod#token',
            correlation_id='test-123',
            integration=self.aap,
        )

        self.assertEqual(result, 'resolved-token')
        MockVaultService.assert_called_once_with(
            vault_addr='https://vault-prod.company.com',
            vault_namespace=None,
            instance_id=str(self.vault_prod.id),
        )

    @patch('services.vault_service.get_vault_service')
    def test_resolve_without_secret_service_uses_singleton(self, mock_get_vault):
        """resolve_credential uses singleton when no secret_service_id."""
        from adapters.utils import resolve_credential

        mock_service = MagicMock()
        mock_service.get_secret.return_value = 'default-token'
        mock_get_vault.return_value = mock_service

        aap_default = Integration.objects.create(
            type=IntegrationType.AAP,
            name='AAP Default Multi',
            base_url='https://aap2.company.com',
            credential_ref='vault:secret/data/aap/dev#token',
        )

        result = resolve_credential(
            'vault:secret/data/aap/dev#token',
            integration=aap_default,
        )

        self.assertEqual(result, 'default-token')
        mock_get_vault.assert_called_once()

    def test_resolve_direct_token(self):
        """Non-vault credential_ref is returned as-is."""
        from adapters.utils import resolve_credential

        result = resolve_credential('my-direct-token')
        self.assertEqual(result, 'my-direct-token')

    @patch('services.vault_service.VaultService')
    def test_resolve_with_vault_namespace_config(self, MockVaultService):
        """Vault config namespace is passed to VaultService instance."""
        from adapters.utils import resolve_credential
        import json

        self.vault_prod.config = json.dumps({'namespace': 'team-ops'})
        self.vault_prod.save()

        mock_instance = MagicMock()
        mock_instance.get_secret.return_value = 'ns-token'
        MockVaultService.return_value = mock_instance

        result = resolve_credential(
            'vault:secret/data/aap/prod#token',
            integration=self.aap,
        )

        MockVaultService.assert_called_once_with(
            vault_addr='https://vault-prod.company.com',
            vault_namespace='team-ops',
            instance_id=str(self.vault_prod.id),
        )


@pytest.mark.django_db
class TestVaultServiceCacheKeyMultiInstance(TestCase):
    """Tests for VaultService cache key with instance_id."""

    def test_cache_key_includes_instance_id(self):
        """Cache key contains instance_id for isolation."""
        from services.vault_service import VaultService, ParsedCredentialRef

        service = VaultService.__new__(VaultService)
        service.instance_id = 'vault-42'

        parsed = ParsedCredentialRef(
            namespace=None, mount='secret', path='aap/prod', key='token',
        )
        key = service._build_cache_key(parsed)
        self.assertIn('vault-42', key)
        self.assertIn('secret', key)
        self.assertIn('aap/prod', key)
        self.assertIn('#token', key)

    def test_cache_key_default_instance(self):
        """Default instance_id is 'default' when None."""
        from services.vault_service import VaultService, ParsedCredentialRef

        service = VaultService.__new__(VaultService)
        service.instance_id = None

        parsed = ParsedCredentialRef(
            namespace=None, mount='secret', path='db/creds', key=None,
        )
        key = service._build_cache_key(parsed)
        self.assertIn('default', key)

    def test_cache_key_different_instances_dont_collide(self):
        """Different instance_ids produce different cache keys."""
        from services.vault_service import VaultService, ParsedCredentialRef

        parsed = ParsedCredentialRef(
            namespace=None, mount='secret', path='same/path', key='key',
        )

        s1 = VaultService.__new__(VaultService)
        s1.instance_id = 'instance-1'
        key1 = s1._build_cache_key(parsed)

        s2 = VaultService.__new__(VaultService)
        s2.instance_id = 'instance-2'
        key2 = s2._build_cache_key(parsed)

        self.assertNotEqual(key1, key2)
