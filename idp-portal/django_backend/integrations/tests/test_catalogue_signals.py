"""
Story 24.1: Tests for audit trail signals on catalogue models.
"""

import pytest

from core.models import AuditLog, AuditActionType, AuditEntityType
from tests.factories import IntegrationTypeCatalogueFactory, IntegrationActionFactory


@pytest.mark.django_db
class TestCatalogueAuditSignals:
    """Tests for audit trail signals on IntegrationTypeCatalogue and IntegrationAction."""

    def test_create_type_logs_audit(self):
        IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        entry = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_TYPE_CREATED,
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
        ).first()
        assert entry is not None
        details = entry.get_details()
        assert details['code'] == 'aap'
        assert details['name'] == 'AAP'

    def test_update_type_logs_audit(self):
        t = IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        t.name = 'AAP Updated'
        t.save()
        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
        ).order_by('id')
        assert entries.count() == 2
        assert entries[0].action_type == AuditActionType.INTEGRATION_TYPE_CREATED
        assert entries[1].action_type == AuditActionType.INTEGRATION_TYPE_UPDATED

    def test_create_action_logs_audit(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        entry = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_ACTION_CREATED,
            entity_type=AuditEntityType.INTEGRATION_ACTION,
        ).first()
        assert entry is not None
        details = entry.get_details()
        assert details['action_code'] == 'start_job'
        assert details['integration_type_code'] == 'aap'

    def test_update_action_logs_audit(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        a = IntegrationActionFactory(integration_type=t, action_code='start_job')
        a.action_label = 'Updated Label'
        a.save()
        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
        ).order_by('id')
        assert entries.count() == 2
        assert entries[1].action_type == AuditActionType.INTEGRATION_ACTION_UPDATED

    def test_audit_entries_have_user_system(self):
        IntegrationTypeCatalogueFactory(code='test')
        entry = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
        ).first()
        assert entry.user_id == 'system'

    def test_audit_details_include_is_active(self):
        IntegrationTypeCatalogueFactory(code='test', is_active=False)
        entry = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
        ).first()
        details = entry.get_details()
        assert details['is_active'] is False
