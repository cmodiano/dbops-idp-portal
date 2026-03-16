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
from integrations.models import Integration, AuthFlow, IntegrationTypeCatalogue
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

    # --- Story 54.1: IPv4-mapped IPv6 bypass prevention ---

    def test_ipv4_mapped_ipv6_loopback_rejected(self):
        """AC-6: IPv4-mapped IPv6 loopback ::ffff:127.0.0.1 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::ffff:127.0.0.1]/api')

    def test_ipv4_mapped_ipv6_private_10_rejected(self):
        """AC-6: IPv4-mapped IPv6 private ::ffff:10.0.0.1 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::ffff:10.0.0.1]/api')

    def test_ipv4_mapped_ipv6_private_192_rejected(self):
        """AC-6: IPv4-mapped IPv6 private ::ffff:192.168.1.1 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::ffff:192.168.1.1]/api')

    def test_ipv4_mapped_ipv6_metadata_rejected(self):
        """AC-5: IPv4-mapped IPv6 metadata ::ffff:169.254.169.254 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::ffff:169.254.169.254]/latest/meta-data/')

    # --- Story 54.1: Port 0 and empty hostname ---

    def test_port_zero_rejected(self):
        """URL with port 0 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('https://example.com:0/api')

    def test_empty_hostname_rejected(self):
        """URL without hostname is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http:///path')

    # --- Story 54.1: Explicit exotic scheme tests ---

    def test_file_scheme_rejected(self):
        """AC-1: file:// scheme is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('file:///etc/passwd')

    def test_data_scheme_rejected(self):
        """AC-1: data: scheme is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('data:text/html,<h1>test</h1>')

    def test_javascript_scheme_rejected(self):
        """AC-1: javascript: scheme is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('javascript:alert(1)')

    # --- Story 54.1: Additional edge cases ---

    def test_username_only_in_url_rejected(self):
        """AC-2: URL with username only (no password) is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('https://admin@api.example.com')

    def test_ipv4_mapped_ipv6_private_172_rejected(self):
        """AC-4: IPv4-mapped IPv6 private ::ffff:172.16.0.1 is rejected."""
        with self.assertRaises(drf_serializers.ValidationError):
            validate_url('http://[::ffff:172.16.0.1]/api')

    def test_ipv4_mapped_ipv6_public_accepted(self):
        """IPv4-mapped IPv6 with public IP is accepted."""
        result = validate_url('http://[::ffff:8.8.8.8]/api')
        self.assertEqual(result, 'http://[::ffff:8.8.8.8]/api')

    def test_percent_encoded_ip_not_resolved(self):
        """Percent-encoded IP in hostname is treated as FQDN, not decoded.

        urlparse does not decode percent-encoding in hostnames, so
        http://127%2E0%2E0%2E1 is parsed as hostname '127%2e0%2e0%2e1'
        (not as IP 127.0.0.1). This is safe because HTTP clients will
        attempt DNS resolution on the literal string, which won't resolve.
        """
        result = validate_url('http://127%2E0%2E0%2E1/api')
        self.assertEqual(result, 'http://127%2E0%2E0%2E1/api')


class TestIntegrationCreateSerializerSsrf(TestCase):
    """Story 48.1: SSRF validation applied to base_url and token_url in IntegrationCreateSerializer."""

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

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


class TestIntegrationCreateSerializerSsrfStory541(TestCase):
    """Story 54.1: IPv4-mapped IPv6 SSRF validation on create serializer."""

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_base_url_ipv4_mapped_ipv6_rejected(self):
        """AC-8: base_url with IPv4-mapped IPv6 private IP is rejected on create."""
        data = {'type': 'aap', 'name': 'Test', 'base_url': 'http://[::ffff:10.0.0.1]/api'}
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_token_url_ipv4_mapped_ipv6_rejected(self):
        """AC-8: token_url with IPv4-mapped IPv6 loopback is rejected on create."""
        data = {
            'type': 'aap', 'name': 'Test', 'base_url': 'https://api.example.com',
            'token_url': 'http://[::ffff:127.0.0.1]/token',
        }
        s = IntegrationCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)


class TestIntegrationUpdateSerializerSsrfStory541(TestCase):
    """Story 54.1: IPv4-mapped IPv6 SSRF validation on update serializer."""

    def test_base_url_ipv4_mapped_ipv6_rejected(self):
        """AC-8: base_url with IPv4-mapped IPv6 private IP is rejected on update."""
        data = {'base_url': 'http://[::ffff:192.168.1.1]/api'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('base_url', s.errors)

    def test_token_url_ipv4_mapped_ipv6_rejected(self):
        """AC-8: token_url with IPv4-mapped IPv6 metadata is rejected on update."""
        data = {'token_url': 'http://[::ffff:169.254.169.254]/token'}
        s = IntegrationUpdateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('token_url', s.errors)


class TestIntegrationCreateSerializer(TestCase):
    """Tests for IntegrationCreateSerializer."""

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

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

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

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

    def setUp(self):
        from django.core.management import call_command
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

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


# ============================================================================
# Story 83-1: Catalogue-based type validation tests (AC#3-#7)
# ============================================================================

@pytest.mark.django_db
class TestIntegrationCreateSerializerTypeCatalogueValidation(TestCase):
    """Story 83-1: IntegrationCreateSerializer validates type against catalogue (AC#3, #5, #6, #7)."""

    def setUp(self):
        self.active_type = IntegrationTypeCatalogue.objects.create(
            code='custom_platform',
            name='Custom Platform',
            description='A test platform type',
            version='1.0',
            is_active=True,
        )
        self.inactive_type = IntegrationTypeCatalogue.objects.create(
            code='legacy_platform',
            name='Legacy Platform',
            description='An inactive platform type',
            version='1.0',
            is_active=False,
        )

    def _base_data(self, type_code):
        return {'type': type_code, 'name': 'Test Integration', 'base_url': 'https://platform.example.com'}

    def test_type_valid_in_catalogue_accepted(self):
        """AC#5: Type present and active in catalogue is accepted."""
        s = IntegrationCreateSerializer(data=self._base_data('custom_platform'))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['type'], 'custom_platform')

    def test_type_absent_from_catalogue_rejected(self):
        """AC#6: Type absent from catalogue raises ValidationError."""
        s = IntegrationCreateSerializer(data=self._base_data('unknown_type'))
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)
        self.assertIn("Type inconnu ou inactif", str(s.errors['type']))

    def test_type_inactive_in_catalogue_rejected(self):
        """AC#7: Type present but is_active=False raises ValidationError."""
        s = IntegrationCreateSerializer(data=self._base_data('legacy_platform'))
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)
        self.assertIn("Type inconnu ou inactif", str(s.errors['type']))

    def test_type_not_in_enum_but_active_in_catalogue_accepted(self):
        """AC#5: Type outside IntegrationType enum but active in catalogue is accepted."""
        # 'custom_platform' is not in IntegrationType enum — validates purely via catalogue
        s = IntegrationCreateSerializer(data=self._base_data('custom_platform'))
        self.assertTrue(s.is_valid(), s.errors)

    def test_error_message_mentions_api(self):
        """AC#6: Error message references the capabilities API for discovery."""
        s = IntegrationCreateSerializer(data=self._base_data('no_such_type'))
        s.is_valid()
        self.assertIn('/api/capabilities/', str(s.errors['type']))


@pytest.mark.django_db
class TestIntegrationUpdateSerializerTypeCatalogueValidation(TestCase):
    """Story 83-1: IntegrationUpdateSerializer validates type against catalogue (AC#4, #7)."""

    def setUp(self):
        self.active_type = IntegrationTypeCatalogue.objects.create(
            code='custom_platform',
            name='Custom Platform',
            description='A test platform type',
            version='1.0',
            is_active=True,
        )
        IntegrationTypeCatalogue.objects.create(
            code='legacy_platform',
            name='Legacy Platform',
            description='An inactive platform type',
            version='1.0',
            is_active=False,
        )

    def test_type_valid_in_catalogue_accepted(self):
        """AC#4: Update with type present and active in catalogue is accepted."""
        s = IntegrationUpdateSerializer(data={'type': 'custom_platform'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_type_absent_from_catalogue_rejected(self):
        """AC#7: Update with type absent from catalogue raises ValidationError."""
        s = IntegrationUpdateSerializer(data={'type': 'unknown_type'})
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)
        self.assertIn("Type inconnu ou inactif", str(s.errors['type']))

    def test_type_inactive_in_catalogue_rejected(self):
        """AC#7: Update with type inactive in catalogue raises ValidationError."""
        s = IntegrationUpdateSerializer(data={'type': 'legacy_platform'})
        self.assertFalse(s.is_valid())
        self.assertIn('type', s.errors)

    def test_type_null_on_update_accepted(self):
        """AC#4: Update with type=None (not provided) skips validation, no error."""
        s = IntegrationUpdateSerializer(data={'type': None})
        self.assertTrue(s.is_valid(), s.errors)

    def test_type_not_provided_on_update_accepted(self):
        """AC#4: Update without type field skips validation entirely."""
        s = IntegrationUpdateSerializer(data={'name': 'Updated'})
        self.assertTrue(s.is_valid(), s.errors)
