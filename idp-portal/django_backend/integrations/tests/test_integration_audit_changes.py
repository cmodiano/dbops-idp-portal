"""
Story 61.1 — INTEGRATION_UPDATED doit inclure changes dans details.

Tests unitaires vérifiant que l'entrée d'audit INTEGRATION_UPDATED
contient un champ 'changes' avec la structure { field: { "old": ..., "new": ... } }.
"""
import pytest
from unittest.mock import patch, MagicMock

from integrations.services import IntegrationService
from integrations.models import Integration, IntegrationStatus
from core.models import AuditActionType


@pytest.mark.django_db
class TestIntegrationAuditChanges:
    """Story 61.1 — INTEGRATION_UPDATED doit inclure changes dans details."""

    def setup_method(self):
        self.service = IntegrationService()
        self.user = MagicMock()
        self.user.id = 42

    def _make_integration(self, **kwargs):
        defaults = {
            'name': 'Test Integ',
            'type': 'aap',
            'base_url': 'https://old.example.com',
            'credential_ref': None,
            'icon': None,
            'auth_flow': None,
            'token_url': None,
            'status': IntegrationStatus.VALID,
        }
        defaults.update(kwargs)
        return Integration.objects.create(**defaults)

    def _get_audit_details(self, mock_audit):
        """Extrait details du dernier appel INTEGRATION_UPDATED."""
        for call in mock_audit.call_args_list:
            if call.kwargs.get('action_type') == AuditActionType.INTEGRATION_UPDATED:
                return call.kwargs.get('details', {})
        return {}

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_name_change_appears_in_changes(self, mock_audit, mock_validate):
        """AC1, AC2, AC3 — modification de name → changes contient {"name": {"old": ..., "new": ...}}"""
        integration = self._make_integration(name='Old Name')

        self.service.update_integration(
            integration.id,
            {'name': 'New Name'},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'name' in details['changes']
        assert details['changes']['name']['old'] == 'Old Name'
        assert details['changes']['name']['new'] == 'New Name'

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_multiple_fields_all_appear_in_changes(self, mock_audit, mock_validate):
        """AC1, AC2, AC3 — modification de base_url, type, icon → tous présents dans changes"""
        integration = self._make_integration(
            name='Multi Test',
            type='aap',
            base_url='https://old.example.com',
            icon=None,
        )

        self.service.update_integration(
            integration.id,
            {
                'type': 'servicenow',
                'base_url': 'https://new.example.com',
                'icon': '/static/icons/some-icon.png',
            },
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'type' in details['changes']
        assert details['changes']['type']['old'] == 'aap'
        assert details['changes']['type']['new'] == 'servicenow'
        assert 'base_url' in details['changes']
        assert details['changes']['base_url']['old'] == 'https://old.example.com'
        assert details['changes']['base_url']['new'] == 'https://new.example.com'
        assert 'icon' in details['changes']
        assert details['changes']['icon']['old'] is None
        assert details['changes']['icon']['new'] == '/static/icons/some-icon.png'

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_credential_ref_masked_in_changes(self, mock_audit, mock_validate):
        """AC4 — modification de credential_ref → changes contient {"credential_ref": {"old": "***", "new": "***"}}"""
        integration = self._make_integration(
            name='Cred Test',
            credential_ref='old-cred-ref',
        )

        self.service.update_integration(
            integration.id,
            {'credential_ref': 'new-cred-ref'},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'credential_ref' in details['changes']
        assert details['changes']['credential_ref']['old'] == '***'
        assert details['changes']['credential_ref']['new'] == '***'

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_config_masked_in_changes(self, mock_audit, mock_validate):
        """AC4 — modification de config → changes contient {"config": {"old": "***", "new": "***"}}"""
        integration = self._make_integration(name='Config Test')
        # Définir un config initial pour avoir un vrai changement (old ≠ new)
        integration.set_config({'client_id': 'initial-value'})
        integration.save(update_fields=['config'])

        # Config=None contourne la validation JSON schema dans update_integration
        self.service.update_integration(
            integration.id,
            {'config': None},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'config' in details['changes']
        assert details['changes']['config']['old'] == '***'
        assert details['changes']['config']['new'] == '***'

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_sensitive_field_unchanged_not_in_changes(self, mock_audit, mock_validate):
        """AC3 — champ sensible soumis sans changement réel → absent de changes"""
        integration = self._make_integration(
            name='Sensitive No Change',
            credential_ref='same-cred-ref',
        )

        # Soumettre la même valeur → pas de changement réel
        self.service.update_integration(
            integration.id,
            {'credential_ref': 'same-cred-ref'},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'credential_ref' not in details['changes']

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_no_real_change_not_in_changes(self, mock_audit, mock_validate):
        """AC3 — mise à jour sans changement réel → champ absent de changes"""
        integration = self._make_integration(
            name='Same Name',
            base_url='https://same.example.com',
        )

        self.service.update_integration(
            integration.id,
            {'name': 'Same Name', 'base_url': 'https://same.example.com'},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'name' not in details['changes']
        assert 'base_url' not in details['changes']

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_empty_update_data_gives_empty_changes(self, mock_audit, mock_validate):
        """AC3 — aucun champ dans update_data → changes est vide"""
        integration = self._make_integration(name='No Change Test')

        self.service.update_integration(
            integration.id,
            {},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert details['changes'] == {}

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_auth_flow_and_token_url_appear_in_changes(self, mock_audit, mock_validate):
        """AC1, AC2 — modification de auth_flow et token_url → présents dans changes"""
        integration = self._make_integration(
            name='Auth Test',
            auth_flow=None,
            token_url=None,
        )

        self.service.update_integration(
            integration.id,
            {
                'auth_flow': 'client_credentials',
                'token_url': 'https://token.example.com',
            },
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'auth_flow' in details['changes']
        assert details['changes']['auth_flow']['old'] is None
        assert details['changes']['auth_flow']['new'] == 'client_credentials'
        assert 'token_url' in details['changes']
        assert details['changes']['token_url']['old'] is None
        assert details['changes']['token_url']['new'] == 'https://token.example.com'

    @patch('integrations.services.IntegrationValidationService.validate_integration',
           return_value=IntegrationStatus.VALID)
    @patch('integrations.services.AuditService.create_entry')
    def test_secret_service_id_appears_in_changes(self, mock_audit, mock_validate):
        """AC1, AC2 — modification de secret_service_id → présent dans changes"""
        vault_integration = Integration.objects.create(
            name='Vault Integ',
            type='aap',
            base_url='https://vault.example.com',
            status=IntegrationStatus.VALID,
        )
        integration = self._make_integration(name='Secret Test')

        self.service.update_integration(
            integration.id,
            {'secret_service_id': vault_integration.id},
            user=self.user,
        )

        details = self._get_audit_details(mock_audit)
        assert 'changes' in details
        assert 'secret_service_id' in details['changes']
        assert details['changes']['secret_service_id']['old'] is None
        assert details['changes']['secret_service_id']['new'] == vault_integration.id
