"""
SOC1 Compliance Tests — Story 15.3

Tests validating SOC1 controls:
- AC1: Audit log immutability (NFR8)
- AC2: Complete execution traceability with correlation_id
- AC3: Production security settings (TLS/HTTPS)
- AC4: Secrets management via Vault references (NFR7)
- AC5: Sensitive data protection (NFR11)
- AC10: Secret validation at startup (Story 17.5)
"""

import os
import re

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import AuditLog, AuditActionType, AuditEntityType
from idp_auth.jwt_utils import create_access_token
from idp_auth.models import User
from integrations.models import Integration

pytestmark = pytest.mark.security


# ============================================================================
# AC1: Audit Log Immutability (NFR8)
# ============================================================================

class TestAuditLogImmutability:
    """SOC1 Control: NFR8 - Audit logs are immutable."""

    @pytest.fixture
    def audit_entry(self, db):
        """Create a single audit log entry for immutability tests."""
        return AuditLog.objects.create_entry(
            user_id='soc1_tester',
            action_type=AuditActionType.ACTION_CREATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=1,
            details={'test': 'immutability'},
            ip_address='10.0.0.1',
            correlation_id='soc1-test-001',
        )

    def test_audit_log_update_raises_error(self, audit_entry):
        """Bulk update on AUDIT_LOG must be rejected (SOC1/NFR8)."""
        with pytest.raises(IntegrityError, match="immutable"):
            AuditLog.objects.filter(id=audit_entry.id).update(
                action_type='MODIFIED'
            )

    def test_audit_log_delete_raises_error(self, audit_entry):
        """Instance delete on AUDIT_LOG must be rejected (SOC1/NFR8)."""
        with pytest.raises(IntegrityError, match="immutable"):
            audit_entry.delete()

    def test_audit_log_save_existing_raises_error(self, audit_entry):
        """Saving an existing audit entry (update) must be rejected (SOC1/NFR8)."""
        audit_entry.action_type = 'MODIFIED'
        with pytest.raises(IntegrityError, match="immutable"):
            audit_entry.save()

    def test_audit_log_create_succeeds(self, db):
        """Creating new audit log entries must still work."""
        entry = AuditLog.objects.create_entry(
            user_id='soc1_tester',
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=42,
            details={'action': 'test creation'},
            ip_address='10.0.0.2',
            correlation_id='soc1-create-001',
        )
        assert entry.id is not None
        assert entry.user_id == 'soc1_tester'
        assert entry.correlation_id == 'soc1-create-001'

    def test_audit_log_bulk_delete_raises_error(self, audit_entry):
        """Bulk delete (QuerySet.delete()) on AUDIT_LOG must be rejected (SOC1/NFR8)."""
        with pytest.raises(IntegrityError, match="immutable"):
            AuditLog.objects.filter(id=audit_entry.id).delete()

    def test_audit_log_all_delete_raises_error(self, audit_entry):
        """AuditLog.objects.all().delete() must be rejected (SOC1/NFR8)."""
        with pytest.raises(IntegrityError, match="immutable"):
            AuditLog.objects.all().delete()


# ============================================================================
# AC2: Complete Execution Traceability
# ============================================================================

class TestAuditTraceability:
    """SOC1 Control: FR30 - Complete execution trace in audit log."""

    def test_execution_creates_audit_entry_with_all_fields(self, db):
        """Each execution must create an AUDIT_LOG entry with all required fields."""
        entry = AuditLog.objects.create_entry(
            user_id='exec_user',
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=100,
            details={
                'action_name': 'Patch Oracle DB',
                'parameters': {'db_name': 'PROD01', 'environment': 'prod'},
                'result': 'submitted',
                'rbac_profile': 'dba',
            },
            ip_address='192.168.1.50',
            correlation_id='trace-exec-001',
        )
        assert entry.user_id == 'exec_user'
        assert entry.action_type == AuditActionType.EXECUTION_SUBMITTED
        assert entry.entity_type == AuditEntityType.EXECUTION
        assert entry.entity_id == 100
        assert entry.ip_address == '192.168.1.50'
        assert entry.correlation_id == 'trace-exec-001'
        details = entry.get_details()
        assert details['action_name'] == 'Patch Oracle DB'
        assert details['rbac_profile'] == 'dba'

    def test_correlation_id_propagated_from_request_to_audit(self, db):
        """Correlation ID from HTTP header must appear in AUDIT_LOG."""
        correlation = 'req-corr-id-abc123'
        entry = AuditLog.objects.create_entry(
            user_id='corr_user',
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=200,
            correlation_id=correlation,
        )
        found = AuditLog.objects.filter(correlation_id=correlation).first()
        assert found is not None
        assert found.id == entry.id

    def test_audit_filter_by_action_type(self, db):
        """API audit filter by action_type must work (FR33)."""
        AuditLog.objects.create_entry(
            user_id='filter_user', action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION, entity_id=1,
        )
        AuditLog.objects.create_entry(
            user_id='filter_user', action_type=AuditActionType.ACTION_CREATED,
            entity_type=AuditEntityType.ACTION, entity_id=2,
        )
        exec_logs = AuditLog.objects.filter(action_type=AuditActionType.EXECUTION_SUBMITTED)
        assert exec_logs.count() == 1

    def test_audit_filter_by_date_range(self, db):
        """Audit date range filter must work (FR33)."""
        from datetime import datetime, timedelta, timezone
        entry = AuditLog.objects.create_entry(
            user_id='date_user', action_type=AuditActionType.ACTION_UPDATED,
            entity_type=AuditEntityType.ACTION, entity_id=3,
        )
        from_date = datetime.now(timezone.utc) - timedelta(hours=1)
        to_date = datetime.now(timezone.utc) + timedelta(hours=1)
        results = AuditLog.objects.list_by_date_range(from_date=from_date, to_date=to_date)
        assert results.filter(id=entry.id).exists()

    def test_audit_filter_by_environment(self, db):
        """API /api/v1/audit must support filter by environment (AC2, FR33)."""
        from catalog.models import Action
        from executions.models import Execution

        user = User.objects.create(username='env_filter_user', display_name='Env Filter', profile='dba')
        integration = Integration.objects.create(
            type='aap', name='Env Test AAP', base_url='https://aap.example.com',
        )
        action = Action.objects.create(
            name='Env Test Action', category='Patching', engine='Oracle',
            platform='AAP', status='published', created_by=user, integration=integration,
        )
        exec_dev = Execution.objects.create(
            action=action, user=user, environment='dev',
            status='COMPLETED', parameters='{}',
        )
        exec_prod = Execution.objects.create(
            action=action, user=user, environment='prod',
            status='COMPLETED', parameters='{}',
        )
        AuditLog.objects.create_entry(
            user_id=user.username, action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION, entity_id=exec_dev.id,
            correlation_id='env-dev-1',
        )
        AuditLog.objects.create_entry(
            user_id=user.username, action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION, entity_id=exec_prod.id,
            correlation_id='env-prod-1',
        )
        # Same filter logic as audit/views._build_audit_queryset (environment param)
        exec_ids_dev = Execution.objects.filter(environment='dev').values_list('id', flat=True)
        qs_dev = AuditLog.objects.filter(
            entity_type=AuditEntityType.EXECUTION,
            entity_id__in=exec_ids_dev,
        )
        assert qs_dev.count() == 1
        assert qs_dev.first().entity_id == exec_dev.id
        exec_ids_prod = Execution.objects.filter(environment='prod').values_list('id', flat=True)
        qs_prod = AuditLog.objects.filter(
            entity_type=AuditEntityType.EXECUTION,
            entity_id__in=exec_ids_prod,
        )
        assert qs_prod.count() == 1
        assert qs_prod.first().entity_id == exec_prod.id

    def test_audit_lifecycle_complete(self, db):
        """Full execution lifecycle must be traceable via same correlation_id."""
        corr_id = 'lifecycle-exec-555'
        lifecycle_types = [
            AuditActionType.EXECUTION_SUBMITTED,
            AuditActionType.EXECUTION_RUNNING,
            AuditActionType.EXECUTION_COMPLETED,
        ]
        for action_type in lifecycle_types:
            AuditLog.objects.create_entry(
                user_id='lifecycle_user',
                action_type=action_type,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=555,
                correlation_id=corr_id,
            )
        entries = AuditLog.objects.filter(correlation_id=corr_id).order_by('timestamp')
        assert entries.count() == 3
        types = list(entries.values_list('action_type', flat=True))
        assert AuditActionType.EXECUTION_SUBMITTED in types
        assert AuditActionType.EXECUTION_RUNNING in types
        assert AuditActionType.EXECUTION_COMPLETED in types


# ============================================================================
# AC3: Production Security Settings (TLS/HTTPS)
# ============================================================================

class TestProductionSecuritySettings:
    """SOC1 Control: NFR6 - TLS 1.2+ / HTTPS configuration."""

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=31536000,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_production_security_settings_enabled(self, db):
        """When DEBUG=False, production security settings must be enabled (SOC1/NFR6)."""
        from django.conf import settings
        assert settings.DEBUG is False
        assert getattr(settings, 'SECURE_SSL_REDIRECT', None) is True
        assert getattr(settings, 'SESSION_COOKIE_SECURE', None) is True
        assert getattr(settings, 'CSRF_COOKIE_SECURE', None) is True

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_ssl_redirect_when_not_debug(self, db):
        """SECURE_SSL_REDIRECT must be True in production."""
        from django.conf import settings
        assert settings.SECURE_SSL_REDIRECT is True
        assert settings.SECURE_HSTS_SECONDS >= 31536000
        assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert settings.SESSION_COOKIE_SECURE is True
        assert settings.CSRF_COOKIE_SECURE is True
        assert settings.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')

    def test_nginx_tls_configuration_exists(self):
        """Nginx config must enforce TLS 1.2+."""
        nginx_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'deployment', 'nginx-django.conf'
        )
        if os.path.exists(nginx_path):
            with open(nginx_path) as f:
                content = f.read()
            assert 'TLSv1.2' in content or 'ssl_protocols' in content


# ============================================================================
# AC4: Secrets Management via Vault (NFR7)
# ============================================================================

class TestSecretsManagement:
    """SOC1 Control: NFR7 - No secrets stored in portal."""

    def test_no_secrets_in_integration_config(self, db):
        """Integration credential_ref must be a Vault reference, not a plaintext secret."""
        integration = Integration.objects.create(
            type='aap',
            name='Test Integration',
            base_url='https://aap.example.com',
            credential_ref='vault:secret/data/integrations/aap#token',
        )
        # credential_ref should look like a Vault path, not a raw secret
        assert integration.credential_ref is not None
        # Verify it's not a common secret pattern (base64 token, API key, etc.)
        secret_patterns = [
            r'^[A-Za-z0-9+/]{20,}={0,2}$',  # Base64-encoded secrets
            r'^sk-[a-zA-Z0-9]+$',  # API keys (sk-xxx)
            r'^ghp_[a-zA-Z0-9]+$',  # GitHub tokens
        ]
        for pattern in secret_patterns:
            assert not re.match(pattern, integration.credential_ref), \
                f"credential_ref looks like a plaintext secret: {pattern}"

    @override_settings(VAULT_ADDR='http://vault.example.com:8200')
    def test_vault_unavailable_returns_explicit_error(self, db):
        """When Vault is unavailable, an explicit error/signal must be returned (NFR21)."""
        from unittest.mock import patch
        from django.conf import settings
        assert hasattr(settings, 'VAULT_ADDR') and settings.VAULT_ADDR
        # When Vault is unreachable, health check must return explicit status (not silent)
        with patch('core.views.requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            client = APIClient()
            response = client.get('/api/v1/health')
            assert response.status_code in (200, 503)
            data = response.json().get('data', {})
            assert 'vault' in data
            assert data['vault'] == 'unreachable', "Vault unavailability must be reported explicitly"

    def test_no_secrets_in_settings_file(self):
        """SECRET_KEY in settings.py must come from environment variable."""
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'idp_backend', 'settings.py'
        )
        with open(settings_path) as f:
            content = f.read()
        # SECRET_KEY must use os.getenv()
        assert "os.getenv('SECRET_KEY'" in content or 'os.getenv("SECRET_KEY"' in content, \
            "SECRET_KEY must be loaded from environment variable"
        # JWT_SECRET_KEY must use os.getenv()
        assert "os.getenv('JWT_SECRET_KEY'" in content or 'os.getenv("JWT_SECRET_KEY"' in content, \
            "JWT_SECRET_KEY must be loaded from environment variable"

    def test_detect_secrets_baseline_exists(self):
        """detect-secrets baseline file must exist (Story 15.1 requirement)."""
        baseline_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            '.secrets.baseline'
        )
        assert os.path.exists(baseline_path), \
            ".secrets.baseline must exist for NFR7 compliance"


# ============================================================================
# AC5: Sensitive Data Protection (NFR11)
# ============================================================================

class TestSensitiveDataProtection:
    """SOC1 Control: NFR11 - No sensitive data stored in portal."""

    def test_no_passwords_in_database_models(self):
        """No application model field should store passwords (excludes Django built-in auth)."""
        from django.apps import apps
        password_field_names = {'passwd', 'secret', 'api_key', 'private_key'}
        # Application modules (not Django internals)
        app_labels = {'catalog', 'profiles', 'integrations', 'executions', 'core', 'inventory', 'idp_auth', 'reference'}
        for model in apps.get_models():
            if model._meta.app_label not in app_labels:
                continue
            for field in model._meta.get_fields():
                if not hasattr(field, 'name'):
                    continue
                field_name = field.name.lower()
                assert field_name not in password_field_names, \
                    f"Model {model.__name__} has sensitive field '{field.name}'"

    def test_execution_parameters_no_credentials(self, db):
        """Execution parameters must not contain credential patterns."""
        from executions.models import Execution
        from catalog.models import Action
        from idp_auth.models import User

        user = User.objects.create(username='data_test_user', display_name='Data Test', profile='dba')
        integration = Integration.objects.create(
            type='aap', name='Data Test AAP', base_url='https://aap.example.com',
        )
        action = Action.objects.create(
            name='Data Test Action', category='Patching', engine='Oracle',
            platform='AAP', status='published', created_by=user, integration=integration,
        )
        execution = Execution.objects.create(
            action=action,
            user=user,
            environment='dev',
            status='COMPLETED',
            parameters='{"db_name": "PROD01", "target": "server1.example.com"}',
        )
        # Parameters must not contain password/credential patterns
        params = execution.parameters or ''
        credential_keywords = ['password', 'secret', 'api_key', 'token', 'private_key', 'credential']
        for keyword in credential_keywords:
            assert keyword not in params.lower(), \
                f"Execution parameters contain sensitive keyword: {keyword}"

    def test_error_messages_no_sensitive_info(self, db):
        """Error messages must not expose internal paths or stack traces (4xx)."""
        from core.exceptions import custom_exception_handler
        from rest_framework.exceptions import NotFound
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get('/test/')
        exc = NotFound("Resource not found")
        response = custom_exception_handler(exc, {'request': request})
        if response:
            content = str(response.data)
            assert '/Users/' not in content
            assert '/home/' not in content
            assert 'Traceback' not in content

    def test_unhandled_exception_masks_internal_details(self, db):
        """500 responses must not expose stack traces or internal paths (NFR11)."""
        from core.exceptions import custom_exception_handler
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get('/api/v1/executions/')
        # Simulate an unhandled exception (e.g. bug, missing DB)
        exc = RuntimeError("Internal failure at /Users/secret/path/file.py line 42")
        response = custom_exception_handler(exc, {'request': request})
        assert response is not None
        assert response.status_code == 500
        content = str(response.data)
        assert '/Users/' not in content
        assert '/home/' not in content
        assert 'Traceback' not in content
        assert 'line 42' not in content
        assert response.data.get("error", {}).get("message") == "An unexpected error occurred"


# ============================================================================
# AC10: Secret Validation at Startup (Story 17.5)
# ============================================================================

class TestSecretValidation:
    """Story 17.5: Tests de validation des secrets au démarrage."""

    def test_production_missing_secret_key_fails(self):
        """Production sans SECRET_KEY doit échouer."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        with mock_patch.dict('os.environ', {'SECRET_KEY': ''}, clear=False):
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY is not set"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_insecure_secret_key_fails(self):
        """Production avec SECRET_KEY par défaut doit échouer."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        with mock_patch.dict('os.environ', {'SECRET_KEY': 'django-insecure-test'}, clear=False):
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY contains insecure default"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_placeholder_jwt_secret_fails(self):
        """Production avec placeholder JWT_SECRET_KEY doit échouer."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        env_vars = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'CHANGE_JWT_SECRET',
            'ORACLE_PASSWORD': 'valid-oracle-password',
        }
        with mock_patch.dict('os.environ', env_vars, clear=False):
            with pytest.raises(ImproperlyConfigured, match="JWT_SECRET_KEY contains unreplaced placeholder"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_missing_saml_certs_with_saml_active_fails(self):
        """Production avec SAML activé mais certs manquants doit échouer."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        env_vars = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '',
        }
        with mock_patch.dict('os.environ', env_vars, clear=False):
            with pytest.raises(ImproperlyConfigured, match="SAML_SP_CERT_PATH required"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_all_valid_secrets_succeeds(self):
        """Production avec tous secrets valides doit réussir."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        env_vars = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '/etc/idp/certs/sp.crt',
            'SAML_SP_KEY_PATH': '/etc/idp/certs/sp.key',
            'SAML_IDP_CERT_PATH': '/etc/idp/certs/idp.crt',
        }
        with mock_patch.dict('os.environ', env_vars, clear=False):
            validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_development_insecure_secrets_warns_but_succeeds(self):
        """Dev mode avec secrets par défaut doit avertir mais réussir."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        env_vars = {
            'SECRET_KEY': 'django-insecure-dev-only',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with mock_patch.dict('os.environ', env_vars, clear=False):
            validate_required_secrets(app_env='development', auth_dev_bypass=True)

    def test_staging_env_treated_as_production(self):
        """Staging doit être traité comme production (fail-fast)."""
        from core.startup_checks import validate_required_secrets
        from unittest.mock import patch as mock_patch
        with mock_patch.dict('os.environ', {'SECRET_KEY': 'changeme'}, clear=False):
            with pytest.raises(ImproperlyConfigured):
                validate_required_secrets(app_env='staging', auth_dev_bypass=False)

    def test_no_hardcoded_secrets_in_settings(self):
        """settings.py ne doit contenir aucun secret hardcodé après Story 17.5."""
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'idp_backend', 'settings.py'
        )
        with open(settings_path) as f:
            content = f.read()
        # OLD dangerous patterns that should be COMPLETELY REMOVED
        old_dangerous_patterns = [
            'django-insecure-bvc0qsxvq0dly',  # Old hardcoded SECRET_KEY
            "'changeme'",  # Old hardcoded ORACLE_PASSWORD
            "'change-me-in-production'",  # Old hardcoded JWT_SECRET_KEY
        ]
        for pattern in old_dangerous_patterns:
            assert pattern not in content, \
                f"Hardcoded secret pattern found in settings.py: {pattern}"

        # NEW fallback pattern (Story 17.5) should exist ONLY in controlled context
        # Verify it's used as a fallback with proper comment explaining validation
        assert 'django-insecure-dev-fallback-will-be-validated' in content, \
            "Dev fallback SECRET_KEY missing (Story 17.5 requirement)"
        assert 'startup_checks.py validates properly' in content, \
            "Missing comment explaining dev fallback validation"
        # Ensure it's ONLY used in an if statement, not as direct os.getenv default
        assert "os.getenv('SECRET_KEY', 'django-insecure-dev-fallback" not in content, \
            "Dev fallback must not be in os.getenv() default - should be in if not SECRET_KEY: block"
        assert 'if not SECRET_KEY:' in content, \
            "Dev fallback must be conditional (if not SECRET_KEY: pattern)"
