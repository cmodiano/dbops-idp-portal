"""
Story 61.2 — ACTION_UPDATED doit inclure changes dans details.

Tests unitaires vérifiant que l'entrée d'audit ACTION_UPDATED
contient un champ 'changes' avec la structure { field: { "old": ..., "new": ... } }
pour update_action et update_execution_steps.
"""
import pytest
from unittest.mock import patch, MagicMock

from catalog.services import CatalogService
from catalog.models import Action, ActionStatus, ActionItemType
from core.models import AuditActionType


@pytest.mark.django_db
class TestActionAuditChanges:
    """Story 61.2 — ACTION_UPDATED doit inclure changes dans details."""

    def setup_method(self):
        self.service = CatalogService()
        self.user = MagicMock()
        self.user.id = 1

    def _make_action(self, **kwargs):
        defaults = {
            'name': 'Test Action',
            'description': 'Desc',
            'engine': 'ansible',
            'platform': 'linux',
            'documentation_md': None,
            'default_impact_level': None,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        defaults.update(kwargs)
        return Action.objects.create(**defaults)

    def _get_audit_details(self, mock_audit):
        """Extrait details du dernier appel ACTION_UPDATED."""
        for call in mock_audit.call_args_list:
            if call.kwargs.get('action_type') == AuditActionType.ACTION_UPDATED:
                return call.kwargs.get('details', {})
        return {}

    # --- update_action ---

    @patch('catalog.services.AuditService.create_entry')
    def test_name_change_appears_in_changes(self, mock_audit):
        """AC1, AC2, AC3 — modification de name → changes contient {"name": {"old": ..., "new": ...}}"""
        action = self._make_action(name='Old Name')

        self.service.update_action(action.id, {'name': 'New Name'}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'name' in details['changes']
        assert details['changes']['name']['old'] == 'Old Name'
        assert details['changes']['name']['new'] == 'New Name'

    @patch('catalog.services.AuditService.create_entry')
    def test_multiple_scalar_fields_all_appear_in_changes(self, mock_audit):
        """AC1, AC2, AC3 — modification de description, engine, platform → tous dans changes"""
        action = self._make_action(
            description='Old desc',
            engine='ansible',
            platform='linux',
        )

        self.service.update_action(
            action.id,
            {'description': 'New desc', 'engine': 'bash', 'platform': 'windows'},
            self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert details['changes']['description']['old'] == 'Old desc'
        assert details['changes']['description']['new'] == 'New desc'
        assert details['changes']['engine']['old'] == 'ansible'
        assert details['changes']['engine']['new'] == 'bash'
        assert details['changes']['platform']['old'] == 'linux'
        assert details['changes']['platform']['new'] == 'windows'

    @patch('catalog.services.AuditService.create_entry')
    def test_integration_id_change_appears_in_changes(self, mock_audit):
        """AC1, AC2 — modification de integration_id → changes contient {"integration_id": {"old": ..., "new": ...}}"""
        from integrations.models import Integration
        integration = Integration.objects.create(
            name='Test Integration',
            type='aap',
            base_url='https://aap.example.com',
        )
        action = self._make_action()

        self.service.update_action(action.id, {'integration_id': integration.id}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'integration_id' in details['changes']
        assert details['changes']['integration_id']['old'] is None
        assert details['changes']['integration_id']['new'] == integration.id

    @patch('catalog.services.AuditService.create_entry')
    def test_json_field_tracked_as_updated(self, mock_audit):
        """AC4, AC6 — modification de parameters_schema → changes contient {"parameters_schema": {"updated": true}}"""
        action = self._make_action()
        new_schema = {'type': 'object', 'properties': {}}

        self.service.update_action(action.id, {'parameters_schema': new_schema}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert details['changes'].get('parameters_schema') == {'updated': True}

    @patch('catalog.services.AuditService.create_entry')
    def test_unchanged_field_not_in_changes(self, mock_audit):
        """AC3 — mise à jour avec la même valeur → champ absent de changes"""
        action = self._make_action(name='Same Name')

        self.service.update_action(action.id, {'name': 'Same Name'}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'name' not in details['changes']
        assert details['changes'] == {}  # Task 3.6: changes doit être vide {}

    @patch('catalog.services.AuditService.create_entry')
    def test_empty_update_gives_empty_changes(self, mock_audit):
        """AC3 — aucun champ dans update_data → changes est vide {}"""
        action = self._make_action()

        self.service.update_action(action.id, {}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert details['changes'] == {}

    @patch('catalog.services.AuditService.create_entry')
    def test_integration_id_cleared_in_changes(self, mock_audit):
        """AC1, AC2 — retrait d'intégration (integration_id → None) → changes contient {"integration_id": {"old": <id>, "new": None}}"""
        from integrations.models import Integration
        integration = Integration.objects.create(
            name='Integration To Remove',
            type='aap',
            base_url='https://aap.example.com',
        )
        action = self._make_action()
        # D'abord affecter l'intégration
        self.service.update_action(action.id, {'integration_id': integration.id}, self.user)
        mock_audit.reset_mock()

        # Puis la retirer
        self.service.update_action(action.id, {'integration_id': None}, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'integration_id' in details['changes']
        assert details['changes']['integration_id']['old'] == integration.id
        assert details['changes']['integration_id']['new'] is None

    # --- update_execution_steps ---

    @patch('catalog.services.AuditService.create_entry')
    def test_execution_steps_count_tracked(self, mock_audit):
        """AC5 — passage de 3 à 5 steps → steps_count_before=3, steps_count_after=5"""
        action = self._make_action(
            execution_steps=[{'id': 1}, {'id': 2}, {'id': 3}],
        )
        new_steps = [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}, {'id': 5}]

        self.service.update_execution_steps(action.id, new_steps, self.user)

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        exec_changes = details['changes']['execution_steps']
        assert exec_changes['steps_count_before'] == 3
        assert exec_changes['steps_count_after'] == 5

    @patch('catalog.services.AuditService.create_entry')
    def test_execution_steps_count_before_zero_when_no_existing_steps(self, mock_audit):
        """AC5 — action sans steps existantes → steps_count_before == 0"""
        action = self._make_action()

        self.service.update_execution_steps(action.id, [{'id': 1}], self.user)

        details = self._get_audit_details(mock_audit)
        exec_changes = details['changes']['execution_steps']
        assert exec_changes['steps_count_before'] == 0
        assert exec_changes['steps_count_after'] == 1

    @patch('catalog.services.AuditService.create_entry')
    def test_no_audit_without_user(self, mock_audit):
        """AC5 — sans user → pas d'appel à AuditService.create_entry"""
        action = self._make_action()

        self.service.update_execution_steps(action.id, [], user=None)

        mock_audit.assert_not_called()
