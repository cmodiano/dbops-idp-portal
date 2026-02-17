"""
Story 24.3: Tests for automatic status calculation in IntegrationService create/update.
"""

import pytest
from django.test import TestCase

from integrations.models import IntegrationStatus, IntegrationTypeCatalogue
from integrations.services import IntegrationService
from core.models import AuditLog, AuditActionType
from idp_auth.models import User


@pytest.mark.django_db
class TestServiceAutoStatus(TestCase):
    """Tests for auto-status computation in create and update."""

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='old_type', name='Old', version='1.0', is_active=False
        )
        self.user = User.objects.create(username='testuser', profile='dbops')
        self.service = IntegrationService()

    def test_create_integration_valid_type_gets_valid_status(self):
        integration = self.service.create_integration({
            'type': 'aap', 'name': 'AAP Test', 'base_url': 'https://aap.example.com',
        }, user=self.user)
        assert integration.status == IntegrationStatus.VALID

    def test_create_integration_deprecated_type_gets_deprecated_status(self):
        integration = self.service.create_integration({
            'type': 'old_type', 'name': 'Old Test', 'base_url': 'https://old.example.com',
        }, user=self.user)
        assert integration.status == IntegrationStatus.DEPRECATED

    def test_create_integration_unknown_type_gets_invalid_status(self):
        integration = self.service.create_integration({
            'type': 'nonexistent', 'name': 'Unknown Test', 'base_url': 'https://unknown.example.com',
        }, user=self.user)
        assert integration.status == IntegrationStatus.INVALID

    def test_create_integration_non_valid_has_warnings(self):
        integration = self.service.create_integration({
            'type': 'old_type', 'name': 'Deprecated Test', 'base_url': 'https://dep.example.com',
        }, user=self.user)
        assert len(integration._warnings) > 0

    def test_update_integration_recalculates_status(self):
        integration = self.service.create_integration({
            'type': 'aap', 'name': 'Will Change', 'base_url': 'https://aap.example.com',
        }, user=self.user)
        assert integration.status == IntegrationStatus.VALID

        updated = self.service.update_integration(
            integration.id,
            {'type': 'old_type'},
            user=self.user,
        )
        assert updated.status == IntegrationStatus.DEPRECATED

    def test_update_integration_status_change_creates_audit(self):
        integration = self.service.create_integration({
            'type': 'aap', 'name': 'Audit Change', 'base_url': 'https://aap.example.com',
        }, user=self.user)

        self.service.update_integration(
            integration.id,
            {'type': 'nonexistent'},
            user=self.user,
        )

        audits = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
            entity_id=integration.id,
        )
        assert audits.count() == 1
