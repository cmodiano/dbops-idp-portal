"""
Story 24.3: Tests for IntegrationValidationService and IntegrationStatus model field.
"""

import pytest
from django.test import TestCase

from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue
from integrations.validation_service import IntegrationValidationService
from core.models import AuditLog, AuditActionType


@pytest.mark.django_db
class IntegrationStatusModelTest(TestCase):
    """Tests for the IntegrationStatus enum and Integration.status field."""

    def test_status_enum_values(self):
        assert IntegrationStatus.VALID == 'valid'
        assert IntegrationStatus.INVALID == 'invalid'
        assert IntegrationStatus.DEPRECATED == 'deprecated'

    def test_status_default_is_valid(self):
        integration = Integration.objects.create(
            type='aap', name='Test Default Status', base_url='https://aap.example.com'
        )
        assert integration.status == IntegrationStatus.VALID

    def test_status_field_accepts_all_values(self):
        for status_value in [IntegrationStatus.VALID, IntegrationStatus.INVALID, IntegrationStatus.DEPRECATED]:
            integration = Integration.objects.create(
                type='aap', name=f'Test {status_value}', base_url='https://aap.example.com',
                status=status_value,
            )
            integration.refresh_from_db()
            assert integration.status == status_value

    def test_audit_action_type_integration_status_updated_exists(self):
        assert hasattr(AuditActionType, 'INTEGRATION_STATUS_UPDATED')
        assert AuditActionType.INTEGRATION_STATUS_UPDATED == 'INTEGRATION_STATUS_UPDATED'


@pytest.mark.django_db
class ValidateIntegrationTest(TestCase):
    """Tests for IntegrationValidationService.validate_integration()."""

    def setUp(self):
        self.catalogue_aap = IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        self.catalogue_deprecated = IntegrationTypeCatalogue.objects.create(
            code='old_type', name='Old Type', version='1.0', is_active=False
        )

    def test_valid_type_returns_valid(self):
        integration = Integration.objects.create(
            type='aap', name='AAP Dev', base_url='https://aap.example.com'
        )
        result = IntegrationValidationService.validate_integration(integration)
        assert result == IntegrationStatus.VALID

    def test_inactive_type_returns_deprecated(self):
        integration = Integration.objects.create(
            type='old_type', name='Old Integration', base_url='https://old.example.com'
        )
        result = IntegrationValidationService.validate_integration(integration)
        assert result == IntegrationStatus.DEPRECATED

    def test_missing_type_returns_invalid(self):
        integration = Integration.objects.create(
            type='nonexistent', name='Unknown Integration', base_url='https://unknown.example.com'
        )
        result = IntegrationValidationService.validate_integration(integration)
        assert result == IntegrationStatus.INVALID


@pytest.mark.django_db
class ValidateAllIntegrationsTest(TestCase):
    """Tests for IntegrationValidationService.validate_all_integrations()."""

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='deprecated_type', name='Deprecated', version='1.0', is_active=False
        )

    def test_batch_validation_updates_status(self):
        # Create integrations with status=valid but actual type is deprecated/invalid
        Integration.objects.create(
            type='aap', name='Valid One', base_url='https://aap.example.com',
            status=IntegrationStatus.VALID,
        )
        Integration.objects.create(
            type='deprecated_type', name='Should Be Deprecated', base_url='https://dep.example.com',
            status=IntegrationStatus.VALID,
        )
        Integration.objects.create(
            type='nonexistent', name='Should Be Invalid', base_url='https://inv.example.com',
            status=IntegrationStatus.VALID,
        )

        stats = IntegrationValidationService.validate_all_integrations()

        assert stats['valid'] == 1
        assert stats['deprecated'] == 1
        assert stats['invalid'] == 1
        assert stats['updated'] == 2

        # Verify DB was updated
        assert Integration.objects.get(name='Should Be Deprecated').status == IntegrationStatus.DEPRECATED
        assert Integration.objects.get(name='Should Be Invalid').status == IntegrationStatus.INVALID

    def test_batch_validation_creates_audit_entries(self):
        Integration.objects.create(
            type='deprecated_type', name='Audit Test', base_url='https://dep.example.com',
            status=IntegrationStatus.VALID,
        )

        IntegrationValidationService.validate_all_integrations()

        audit_entries = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED
        )
        assert audit_entries.count() == 1

    def test_dry_run_does_not_update_db(self):
        Integration.objects.create(
            type='deprecated_type', name='DryRun Test', base_url='https://dep.example.com',
            status=IntegrationStatus.VALID,
        )

        stats = IntegrationValidationService.validate_all_integrations(dry_run=True)

        assert stats['updated'] == 1
        assert stats['deprecated'] == 1
        # DB should NOT be updated
        assert Integration.objects.get(name='DryRun Test').status == IntegrationStatus.VALID

    def test_empty_integrations_returns_zeros(self):
        stats = IntegrationValidationService.validate_all_integrations()
        assert stats == {'valid': 0, 'invalid': 0, 'deprecated': 0, 'updated': 0}

    def test_no_change_means_no_update(self):
        Integration.objects.create(
            type='aap', name='Already Valid', base_url='https://aap.example.com',
            status=IntegrationStatus.VALID,
        )

        stats = IntegrationValidationService.validate_all_integrations()

        assert stats['valid'] == 1
        assert stats['updated'] == 0
        assert AuditLog.objects.filter(action_type=AuditActionType.INTEGRATION_STATUS_UPDATED).count() == 0


@pytest.mark.django_db
class GetIntegrationValidationDetailsTest(TestCase):
    """Tests for IntegrationValidationService.get_integration_validation_details()."""

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='2.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='old_type', name='Old', version='1.0', is_active=False
        )

    def test_valid_type_details(self):
        integration = Integration.objects.create(
            type='aap', name='AAP Dev', base_url='https://aap.example.com'
        )
        details = IntegrationValidationService.get_integration_validation_details(integration)

        assert details['status'] == IntegrationStatus.VALID
        assert details['type_exists'] is True
        assert details['type_is_active'] is True
        assert details['catalogue_version'] == '2.0'
        assert 'active and supported' in details['validation_message']

    def test_deprecated_type_details(self):
        integration = Integration.objects.create(
            type='old_type', name='Old Integration', base_url='https://old.example.com'
        )
        details = IntegrationValidationService.get_integration_validation_details(integration)

        assert details['status'] == IntegrationStatus.DEPRECATED
        assert details['type_exists'] is True
        assert details['type_is_active'] is False
        assert details['catalogue_version'] == '1.0'
        assert 'deprecated' in details['validation_message']

    def test_missing_type_details(self):
        integration = Integration.objects.create(
            type='nonexistent', name='Unknown', base_url='https://unknown.example.com'
        )
        details = IntegrationValidationService.get_integration_validation_details(integration)

        assert details['status'] == IntegrationStatus.INVALID
        assert details['type_exists'] is False
        assert details['type_is_active'] is False
        assert details['catalogue_version'] is None
        assert 'not found in catalogue' in details['validation_message']


@pytest.mark.django_db
class ValidateIntegrationDBErrorTest(TestCase):
    """Story 30.15 AC4: validate_integration returns INVALID on DatabaseError/OperationalError."""

    def setUp(self):
        self.integration = Integration.objects.create(
            type='aap', name='DB Error Test', base_url='https://aap.example.com'
        )
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )

    def test_database_error_returns_invalid(self):
        from unittest.mock import patch
        from django.db import DatabaseError

        with patch.object(
            IntegrationTypeCatalogue.objects, 'filter',
            side_effect=DatabaseError("ORA-12541: TNS:no listener"),
        ):
            result = IntegrationValidationService.validate_integration(self.integration)
        assert result == IntegrationStatus.INVALID

    def test_operational_error_returns_invalid(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch.object(
            IntegrationTypeCatalogue.objects, 'filter',
            side_effect=OperationalError("connection timed out"),
        ):
            result = IntegrationValidationService.validate_integration(self.integration)
        assert result == IntegrationStatus.INVALID

    def test_attribute_error_is_not_caught(self):
        """Verify that non-DB exceptions are NOT silently swallowed (Story 30.15 AC4)."""
        from unittest.mock import patch

        with patch.object(
            IntegrationTypeCatalogue.objects, 'filter',
            side_effect=AttributeError("unexpected"),
        ):
            with pytest.raises(AttributeError):
                IntegrationValidationService.validate_integration(self.integration)
