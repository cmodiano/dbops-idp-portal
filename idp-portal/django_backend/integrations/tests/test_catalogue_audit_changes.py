"""
Story 61.4 — INTEGRATION_TYPE_UPDATED et INTEGRATION_ACTION_UPDATED
doivent inclure changes dans details.
"""
import pytest

from core.models import AuditLog, AuditActionType, AuditEntityType
from tests.factories import IntegrationTypeCatalogueFactory, IntegrationActionFactory


@pytest.mark.django_db
class TestIntegrationTypeCatalogueAuditChanges:
    """Story 61.4 — INTEGRATION_TYPE_UPDATED doit inclure changes dans details."""

    def test_name_change_appears_in_changes(self):
        """AC1, AC3 — modification de name → changes contient {"name": {"old": ..., "new": ...}}"""
        t = IntegrationTypeCatalogueFactory(code='itc-name', name='Old Name')
        t.name = 'New Name'
        t.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_UPDATED,
        ).order_by('-id')
        assert entries.exists()
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'name' in details['changes']
        assert details['changes']['name']['old'] == 'Old Name'
        assert details['changes']['name']['new'] == 'New Name'

    def test_is_active_change_appears_in_changes(self):
        """AC1, AC3 — désactivation → changes contient {"is_active": {"old": True, "new": False}}"""
        t = IntegrationTypeCatalogueFactory(code='itc-active', is_active=True)
        t.is_active = False
        t.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'is_active' in details['changes']
        assert details['changes']['is_active']['old'] is True
        assert details['changes']['is_active']['new'] is False

    def test_integration_role_change_appears_in_changes(self):
        """AC1, AC3 — changement de rôle → present dans changes"""
        t = IntegrationTypeCatalogueFactory(code='itc-role', integration_role='platform')
        t.integration_role = 'service'
        t.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'integration_role' in details['changes']
        assert details['changes']['integration_role']['old'] == 'platform'
        assert details['changes']['integration_role']['new'] == 'service'

    def test_version_change_appears_in_changes(self):
        """AC1, AC3 — changement de version → présent dans changes"""
        t = IntegrationTypeCatalogueFactory(code='itc-version', version='1.0')
        t.version = '2.0'
        t.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'version' in details['changes']
        assert details['changes']['version']['old'] == '1.0'
        assert details['changes']['version']['new'] == '2.0'

    def test_unchanged_field_not_in_changes(self):
        """AC4 — champ soumis avec la même valeur → absent de changes (changes == {})"""
        t = IntegrationTypeCatalogueFactory(code='itc-nochange', name='Same Name')
        t.name = 'Same Name'
        t.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'name' not in details['changes']
        assert details['changes'] == {}

    def test_create_does_not_include_changes(self):
        """AC5 — création → 'changes' absent de details"""
        IntegrationTypeCatalogueFactory(code='itc-create')
        entry = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            action_type=AuditActionType.INTEGRATION_TYPE_CREATED,
        ).order_by('-id').first()
        assert entry is not None
        details = entry.get_details()
        assert 'changes' not in details


@pytest.mark.django_db
class TestIntegrationActionAuditChanges:
    """Story 61.4 — INTEGRATION_ACTION_UPDATED doit inclure changes dans details."""

    def test_action_label_change_appears_in_changes(self):
        """AC2, AC3 — modification de action_label → changes contient la modification"""
        t = IntegrationTypeCatalogueFactory(code='ia-label')
        a = IntegrationActionFactory(integration_type=t, action_code='run', action_label='Old Label')
        a.action_label = 'New Label'
        a.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            action_type=AuditActionType.INTEGRATION_ACTION_UPDATED,
        ).order_by('-id')
        assert entries.exists()
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'action_label' in details['changes']
        assert details['changes']['action_label']['old'] == 'Old Label'
        assert details['changes']['action_label']['new'] == 'New Label'

    def test_is_active_change_appears_in_changes(self):
        """AC2, AC3 — désactivation action → présent dans changes"""
        t = IntegrationTypeCatalogueFactory(code='ia-active')
        a = IntegrationActionFactory(integration_type=t, action_code='run2', is_active=True)
        a.is_active = False
        a.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            action_type=AuditActionType.INTEGRATION_ACTION_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'is_active' in details['changes']
        assert details['changes']['is_active']['old'] is True
        assert details['changes']['is_active']['new'] is False

    def test_description_change_appears_in_changes(self):
        """AC2, AC3 — changement de description → présent dans changes"""
        t = IntegrationTypeCatalogueFactory(code='ia-desc')
        a = IntegrationActionFactory(integration_type=t, action_code='run4', description='Old desc')
        a.description = 'New desc'
        a.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            action_type=AuditActionType.INTEGRATION_ACTION_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'description' in details['changes']
        assert details['changes']['description']['old'] == 'Old desc'
        assert details['changes']['description']['new'] == 'New desc'

    def test_unchanged_field_not_in_changes(self):
        """AC4 — champ non modifié → absent de changes (changes == {})"""
        t = IntegrationTypeCatalogueFactory(code='ia-nochange')
        a = IntegrationActionFactory(integration_type=t, action_code='run3', action_label='Same Label')
        a.action_label = 'Same Label'
        a.save()

        entries = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            action_type=AuditActionType.INTEGRATION_ACTION_UPDATED,
        ).order_by('-id')
        details = entries.first().get_details()
        assert 'changes' in details
        assert 'action_label' not in details['changes']
        assert details['changes'] == {}

    def test_create_does_not_include_changes(self):
        """AC5 — création → 'changes' absent de details"""
        t = IntegrationTypeCatalogueFactory(code='ia-create')
        IntegrationActionFactory(integration_type=t, action_code='new-action')

        entry = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            action_type=AuditActionType.INTEGRATION_ACTION_CREATED,
        ).order_by('-id').first()
        assert entry is not None
        details = entry.get_details()
        assert 'changes' not in details
