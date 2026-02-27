"""
Tests for integrations serializers.
Story 20.5: Cover create/update serializer validation branches.
"""

import pytest
from django.test import TestCase
from integrations.serializers import (
    IntegrationCreateSerializer,
    IntegrationUpdateSerializer,
    IntegrationSerializer,
    IntegrationListSerializer,
    validate_url,
)
from integrations.models import Integration, AuthFlow
from rest_framework import serializers as drf_serializers


class TestValidateUrl(TestCase):
    """Tests for standalone validate_url helper."""

    def test_valid_https(self):
        self.assertEqual(validate_url('https://example.com'), 'https://example.com')

    def test_valid_http(self):
        self.assertEqual(validate_url('http://example.com'), 'http://example.com')

    def test_invalid_url_raises(self):
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('ftp://example.com')

    def test_empty_url_passthrough(self):
        self.assertIsNone(validate_url(None))

    def test_empty_string_passthrough(self):
        self.assertEqual(validate_url(''), '')

    # --- Story 48.1: SSRF prevention tests ---

    def test_localhost_rejected(self):
        """AC1: localhost is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://localhost/api')

    def test_127_0_0_1_rejected(self):
        """AC1: 127.0.0.1 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://127.0.0.1:8080/')

    def test_ipv6_loopback_rejected(self):
        """AC1: ::1 (IPv6 loopback) is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::1]/api')

    def test_private_ip_10_rejected(self):
        """AC2: RFC 1918 10.x.x.x is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://10.0.0.1/api')

    def test_private_ip_172_16_rejected(self):
        """AC2: RFC 1918 172.16.x.x is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://172.16.0.1/api')

    def test_private_ip_192_168_rejected(self):
        """AC2: RFC 1918 192.168.x.x is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://192.168.1.1/api')

    def test_credentials_in_url_rejected(self):
        """AC3: URL with user:pass@host is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('https://user:pass@api.example.com')

    def test_valid_public_https(self):
        """AC5: Public HTTPS URL is accepted."""
        result = validate_url('https://api.example.com')
        self.assertEqual(result, 'https://api.example.com')

    def test_valid_public_http(self):
        """AC5: Public HTTP URL is accepted."""
        result = validate_url('http://api.example.com')
        self.assertEqual(result, 'http://api.example.com')

    def test_valid_public_with_port(self):
        """AC5: Public URL with port is accepted."""
        result = validate_url('https://api.example.com:8443/path')
        self.assertEqual(result, 'https://api.example.com:8443/path')

    def test_valid_internal_fqdn_accepted(self):
        """AC5: Internal FQDN (non-IP) is accepted — only IPs and localhost are blocked."""
        result = validate_url('https://aap.prod.internal.corp')
        self.assertEqual(result, 'https://aap.prod.internal.corp')

    # --- Story 48.1 code-review fixes ---

    def test_link_local_aws_metadata_rejected(self):
        """HIGH fix: 169.254.169.254 (AWS/GCP/Azure metadata service) is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://169.254.169.254/latest/meta-data/')

    def test_link_local_range_rejected(self):
        """HIGH fix: Any 169.254.x.x address is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://169.254.0.1/api')

    def test_ipv6_link_local_rejected(self):
        """HIGH fix: IPv6 link-local fe80::/10 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[fe80::1]/api')

    def test_zero_network_rejected(self):
        """MEDIUM fix: 0.0.0.1 (0.0.0.0/8 network) is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://0.0.0.1/api')

    def test_ipv6_ula_rejected(self):
        """MEDIUM fix: IPv6 ULA fc00::/7 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[fd00::1]/api')

    def test_0_0_0_0_rejected(self):
        """LOW: 0.0.0.0 exact address is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://0.0.0.0/api')


class TestIntegrationCreateSerializerSsrf(TestCase):
    """Story 48.1: SSRF validation applied to base_url and token_url in IntegrationCreateSerializer."""

    def test_base_url_localhost_rejected(self):
        """AC6: base_url with localhost is rejected by IntegrationCreateSerializer."""
        data = {'type': 'aap', 'name': 'Test', 'base_url': 'http://localhost/api'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_token_url_private_ip_rejected(self):
        """AC6: token_url with private IP is rejected by IntegrationCreateSerializer."""
        data = {
            'type': 'aap', 'name': 'Test', 'base_url': 'https://api.example.com',
            'token_url': 'http://192.168.1.1/token',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)


class TestIntegrationUpdateSerializerSsrf(TestCase):
    """Story 48.1: SSRF validation applied to base_url and token_url in IntegrationUpdateSerializer."""

    def test_base_url_private_ip_rejected(self):
        """AC6: base_url with private IP is rejected by IntegrationUpdateSerializer."""
        data = {'base_url': 'http://10.0.0.1/api'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_token_url_private_ip_rejected(self):
        """AC6 (code-review fix): token_url with private IP is rejected by IntegrationUpdateSerializer."""
        data = {'token_url': 'http://192.168.1.1/token'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)

    def test_token_url_link_local_rejected(self):
        """AC6 (code-review fix): token_url with link-local (metadata service) is rejected."""
        data = {'token_url': 'http://169.254.169.254/token'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)


class TestIntegrationCreateSerializer(TestCase):
    """Tests for IntegrationCreateSerializer."""

    def test_valid_minimal(self):
        data = {'type': 'aap', 'name': 'Test', 'base_url': 'https://aap.example.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_name(self):
        data = {'type': 'aap', 'base_url': 'https://aap.example.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_missing_type(self):
        data = {'name': 'Test', 'base_url': 'https://aap.example.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)

    def test_missing_base_url(self):
        data = {'type': 'aap', 'name': 'Test'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_invalid_type(self):
        data = {'type': 'invalid_type', 'name': 'Test', 'base_url': 'https://a.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)

    def test_whitespace_name_rejected(self):
        data = {'type': 'aap', 'name': '   ', 'base_url': 'https://a.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_name_strips_whitespace(self):
        data = {'type': 'aap', 'name': '  Test  ', 'base_url': 'https://a.com'}
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['name'], 'Test')

    def test_invalid_base_url(self):
        data = {'type': 'aap', 'name': 'Test', 'base_url': 'not-a-url'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_whitespace_base_url_rejected(self):
        data = {'type': 'aap', 'name': 'Test', 'base_url': '   '}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_token_url_validation(self):
        data = {
            'type': 'aap', 'name': 'Test', 'base_url': 'https://a.com',
            'token_url': 'not-a-url'
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)

    def test_token_url_empty_becomes_none(self):
        data = {
            'type': 'aap', 'name': 'Test', 'base_url': 'https://a.com',
            'token_url': ''
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data.get('token_url'))

    def test_valid_with_all_fields(self):
        data = {
            'type': 'aap', 'name': 'Full AAP', 'base_url': 'https://aap.com',
            'credential_ref': 'vault:creds', 'icon': '/icons/aap.png',
            'auth_flow': 'token', 'token_url': 'https://aap.com/token',
            'config': {'key': 'value'}
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


class TestIntegrationUpdateSerializer(TestCase):
    """Tests for IntegrationUpdateSerializer."""

    def test_valid_partial_update(self):
        data = {'name': 'Updated'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_empty_update_valid(self):
        data = {}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_null_type_accepted(self):
        data = {'type': None}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_type_rejected(self):
        data = {'type': 'invalid_type'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_whitespace_name_rejected(self):
        data = {'name': '   '}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_null_name_accepted(self):
        data = {'name': None}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_null_base_url_accepted(self):
        data = {'base_url': None}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_whitespace_base_url_rejected(self):
        data = {'base_url': '   '}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_token_url_empty_becomes_none(self):
        data = {'token_url': ''}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data.get('token_url'))

    def test_token_url_whitespace_becomes_none(self):
        data = {'token_url': '   '}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data.get('token_url'))


@pytest.mark.django_db
class TestIntegrationUpdateSerializerVaultValidation(TestCase):
    """Story 30.8 ERR-2: Cross-field validation for IntegrationUpdateSerializer."""

    def test_update_vault_type_with_credential_ref_rejected(self):
        """Updating to vault type with credential_ref should be rejected."""
        data = {'type': 'vault', 'credential_ref': 'vault:secret/path'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('credential_ref', s.errors)

    def test_update_vault_type_with_secret_service_id_rejected(self):
        """Updating to vault type with secret_service_id should be rejected."""
        vault = Integration.objects.create(
            type='vault', name='Vault Instance', base_url='https://vault.example.com'
        )
        data = {'type': 'vault', 'secret_service_id': vault.id}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_update_secret_service_id_invalid_rejected(self):
        """Referencing a non-existent secret_service_id should be rejected."""
        data = {'secret_service_id': 99999}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_update_secret_service_id_non_vault_rejected(self):
        """Referencing a non-vault integration as secret_service_id should be rejected."""
        aap = Integration.objects.create(
            type='aap', name='AAP Instance', base_url='https://aap.example.com'
        )
        data = {'secret_service_id': aap.id}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('secret_service_id', s.errors)

    def test_update_valid_secret_service_id_accepted(self):
        """Referencing a valid vault integration should be accepted."""
        vault = Integration.objects.create(
            type='vault', name='Vault OK', base_url='https://vault.example.com'
        )
        data = {'secret_service_id': vault.id}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_update_partial_no_vault_fields_accepted(self):
        """A partial update without vault fields should pass."""
        data = {'name': 'Updated Name'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_update_with_instance_merges_for_vault_check(self):
        """When instance exists, validation merges instance data with update data."""
        instance = Integration.objects.create(
            type='vault', name='Vault', base_url='https://vault.example.com'
        )
        # Partial update: only credential_ref, but instance.type is vault → should reject
        data = {'credential_ref': 'vault:secret/path'}
        s = IntegrationUpdateSerializer(data=data, instance=instance)
        self.assertFalse(s.is_valid())
        self.assertIn('credential_ref', s.errors)


class TestIntegrationCreateSerializerStory3112(TestCase):
    """Story 31.12: oauth2_client_credentials and api_key are valid auth_flow values."""

    def test_create_with_oauth2_client_credentials(self):
        data = {
            'type': 'aap', 'name': 'Jira Cloud', 'base_url': 'https://jira.example.com',
            'auth_flow': 'oauth2_client_credentials',
            'token_url': 'https://login.microsoftonline.com/tenant/oauth2/v2.0/token',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_create_with_api_key(self):
        data = {
            'type': 'aap', 'name': 'Custom API', 'base_url': 'https://api.example.com',
            'auth_flow': 'api_key',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


@pytest.mark.django_db
class TestIntegrationReadSerializers(TestCase):
    """Tests for IntegrationSerializer and IntegrationListSerializer."""

    def setUp(self):
        self.integration = Integration.objects.create(
            type='aap', name='Read Test', base_url='https://aap.com',
            auth_flow=AuthFlow.TOKEN
        )
        self.integration.set_config({'key': 'value'})
        self.integration.save()

    def test_integration_serializer_fields(self):
        s = IntegrationSerializer(self.integration)
        data = s.data
        self.assertEqual(data['name'], 'Read Test')
        self.assertEqual(data['config'], {'key': 'value'})
        self.assertIn('created_at', data)

    def test_integration_list_serializer_excludes_config(self):
        s = IntegrationListSerializer(self.integration)
        data = s.data
        self.assertEqual(data['name'], 'Read Test')
        self.assertNotIn('config', data)
