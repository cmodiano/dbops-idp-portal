"""
Tests for execution environment validation against inventory.
Story 13.7 - Tests for environment validation in executions.
Story 21.3 - Comprehensive tests for raw environment values (lab, certif, etc.)
Story 26.10 - Updated imports and patch paths after function renaming.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionStatus
from inventory.services import InventoryServiceError
from tests.factories import UserFactory


class ExecutionEnvironmentValidationTests(TestCase):
    """Tests for environment validation in execution creation."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory(
            username='testuser',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

        # Create a published action (requires_target=False so environment is accepted directly)
        self.action = Action.objects.create(
            name='Test Action',
            description='Test',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            requires_target=False,
            created_by=self.user
        )

    # Story 26.10: Environment validation is not performed for regular executions
    # It's only done for scheduled executions. This test just verifies execution succeeds.
    def test_create_execution_with_valid_environment(self):
        """Test creating execution with valid environment."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
            'parameters': {}
        }, format='json')

        # Should succeed (environment validation not enforced for regular executions)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Story 26.10: Environment validation is not performed for regular executions
    # Invalid environments are accepted (validation is only enforced for scheduled executions)
    def test_create_execution_with_invalid_environment(self):
        """Test creating execution with invalid environment is accepted (no validation for regular executions)."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'invalid_env',
            'parameters': {}
        }, format='json')

        # Should succeed (environment validation not enforced for regular executions)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Story 53.2 AC3: Valeurs brutes inventaire acceptées par l'API
    def test_create_execution_with_certification_environment(self):
        """Story 53.2 AC3 : Création d'exécution avec environment='certification' → HTTP 201
        et valeur enregistrée telle quelle en base (pas d'alias vers 'staging')."""
        from executions.models import Execution

        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'certification',
            'parameters': {}
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution_id = response.data['data']['execution_id']
        execution = Execution.objects.get(id=execution_id)
        self.assertEqual(execution.environment, 'certification')

    def test_create_execution_with_developpement_environment(self):
        """Story 53.2 AC4 : Création d'exécution avec environment='developpement' → HTTP 201
        et valeur enregistrée telle quelle en base (pas d'alias vers 'dev')."""
        from executions.models import Execution

        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'developpement',
            'parameters': {}
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution_id = response.data['data']['execution_id']
        execution = Execution.objects.get(id=execution_id)
        self.assertEqual(execution.environment, 'developpement')

    def test_regular_execution_accepts_any_env_no_inventory_validation(self):
        """Story 53.2 / Story 26.10 : Les exécutions régulières n'effectuent pas de validation
        d'environnement contre l'inventaire — tout env string est accepté (HTTP 201).
        Le RBAC/permission_aggregator contrôle l'accès, pas cette couche.
        """
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
            'parameters': {}
        }, format='json')

        # 'dev' n'est plus dans l'inventaire brut mais aucune validation n'est faite ici
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch('executions.views.scheduled_views.validate_environment_against_inventory')
    @patch('executions.views.scheduled_views.SchedulingService')
    def test_create_scheduled_execution_with_valid_environment(self, mock_sched_service, mock_validate):
        """Test creating scheduled execution with valid environment."""
        mock_validate.return_value = None  # Validation passes
        mock_sched_service.return_value.create_scheduled_execution.return_value = MagicMock(id=1)

        self.client.post('/api/v1/scheduled-executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
            'parameters': {},
            'scheduled_at': '2026-02-10T10:00:00Z'
        }, format='json')

        # Should call validation
        mock_validate.assert_called_once_with('dev', user_id=self.user.id)

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_environment_lab_case_insensitive(self, mock_list_envs):
        """
        Story 21.2, AC2 / Task 5.3: _validate_environment_against_inventory
        should validate 'lab' case-insensitively against inventory.
        """
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['dev', 'lab', 'staging', 'prod']

        # Should not raise - lab is valid
        validate_environment_against_inventory('lab')
        validate_environment_against_inventory('LAB')  # Case-insensitive
        validate_environment_against_inventory('Lab')  # Case-insensitive

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_environment_invalid_raises_error(self, mock_list_envs):
        """Story 21.2, AC2: Invalid environment should raise BadRequestError."""
        from executions.utils import validate_environment_against_inventory
        from core.exceptions import BadRequestError

        mock_list_envs.return_value = ['dev', 'lab', 'staging', 'prod']

        with self.assertRaises(BadRequestError) as cm:
            validate_environment_against_inventory('invalid')

        self.assertEqual(cm.exception.code, 'INVALID_ENVIRONMENT')


class EnvironmentConfigLookupTests(TestCase):
    """
    Story 21.2, AC3 / Task 5.3: Tests for case-insensitive environment config lookup.
    """

    def test_get_env_config_case_insensitive(self):
        """Helper should match environment keys case-insensitively."""
        from executions.utils import get_env_config_case_insensitive

        config = {
            "DEV": {"required": False},
            "STAGING": {"required": True, "change_model_code": "STG-001"},
            "PROD": {"required": True, "change_model_code": "PRD-001"},
        }

        # Lowercase lookup should work
        result = get_env_config_case_insensitive(config, "dev")
        self.assertEqual(result, {"required": False})

        # Uppercase lookup should work
        result = get_env_config_case_insensitive(config, "STAGING")
        self.assertEqual(result, {"required": True, "change_model_code": "STG-001"})

        # Mixed case should work
        result = get_env_config_case_insensitive(config, "Prod")
        self.assertEqual(result, {"required": True, "change_model_code": "PRD-001"})

        # Not found should return empty dict
        result = get_env_config_case_insensitive(config, "unknown")
        self.assertEqual(result, {})

    def test_get_env_config_with_lab_environment(self):
        """Story 21.2, AC3: Lab environment should be looked up case-insensitively."""
        from executions.utils import get_env_config_case_insensitive

        config = {
            "lab": {"required": False},
            "staging": {"required": True},
        }

        result = get_env_config_case_insensitive(config, "lab")
        self.assertEqual(result, {"required": False})

        result = get_env_config_case_insensitive(config, "LAB")
        self.assertEqual(result, {"required": False})

    def test_get_env_config_empty_config(self):
        """Helper should handle empty config gracefully."""
        from executions.utils import get_env_config_case_insensitive

        result = get_env_config_case_insensitive({}, "dev")
        self.assertEqual(result, {})

        result = get_env_config_case_insensitive(None, "dev")
        self.assertEqual(result, {})


# =============================================================================
# Story 21.3, Task 3: Execution environment validation tests
# =============================================================================


class ValidateEnvironmentAgainstInventoryTests(TestCase):
    """
    Story 21.3, Task 3: Tests for _validate_environment_against_inventory.
    Validates lab, case-insensitive matching, invalid env, inventory down, audit trail.
    """

    # -- Task 3.1: lab success --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_lab_success(self, mock_list_envs):
        """Valid 'lab' in inventory → no exception raised."""
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['dev', 'lab', 'staging', 'prod']

        # Should not raise
        validate_environment_against_inventory('lab')

    # -- Task 3.2: case-insensitive --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_lab_case_insensitive_variants(self, mock_list_envs):
        """'LAB', 'Lab', 'lAb' all match 'lab' in inventory."""
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['dev', 'lab', 'staging', 'prod']

        # All case variants should pass
        validate_environment_against_inventory('LAB')
        validate_environment_against_inventory('Lab')
        validate_environment_against_inventory('lAb')

    # -- Task 3.3: invalid environment --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_invalid_environment_raises_bad_request(self, mock_list_envs):
        """Invalid env raises BadRequestError with INVALID_ENVIRONMENT code."""
        from executions.utils import validate_environment_against_inventory
        from core.exceptions import BadRequestError

        mock_list_envs.return_value = ['dev', 'lab', 'staging', 'prod']

        with self.assertRaises(BadRequestError) as cm:
            validate_environment_against_inventory('invalid_env', user_id=123)

        self.assertEqual(cm.exception.code, 'INVALID_ENVIRONMENT')
        self.assertIn('invalid_env', cm.exception.message)
        self.assertIn('valid_environments', cm.exception.details)

    # -- Task 3.4: Inventory unavailable → blocking exception (SOC1) --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_inventory_unavailable_blocks_execution(self, mock_list_envs):
        """Inventory down → BadRequestError INVENTORY_UNAVAILABLE (SOC1 security)."""
        from executions.utils import validate_environment_against_inventory
        from core.exceptions import BadRequestError

        mock_list_envs.side_effect = InventoryServiceError("Oracle connection refused")

        with self.assertRaises(BadRequestError) as cm:
            validate_environment_against_inventory('lab', user_id=123)

        self.assertEqual(cm.exception.code, 'INVENTORY_UNAVAILABLE')

    # -- Task 3.5: Audit trail for invalid environment attempt --

    @patch('executions.utils.AuditService')
    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_invalid_env_creates_audit_entry(self, mock_list_envs, mock_audit):
        """Invalid environment attempt → audit trail with user_id (SOC1)."""
        from executions.utils import validate_environment_against_inventory
        from core.exceptions import BadRequestError

        mock_list_envs.return_value = ['dev', 'staging', 'prod']

        with self.assertRaises(BadRequestError):
            validate_environment_against_inventory('invalid_env', user_id=456)

        # Verify audit entry was created
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args
        # user_id should be in the audit entry
        self.assertEqual(call_kwargs.kwargs.get('user_id') or call_kwargs[1].get('user_id'), '456')

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_empty_environment_skips_validation(self, mock_list_envs):
        """Empty environment → no validation (returns early)."""
        from executions.utils import validate_environment_against_inventory

        # Should not raise, should not call list_environments
        validate_environment_against_inventory('')
        validate_environment_against_inventory(None)

        mock_list_envs.assert_not_called()

    # -- Additional: non-standard environments --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_qa_uat_certif_environments(self, mock_list_envs):
        """Non-standard envs (qa, uat, certif) pass if present in inventory."""
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['dev', 'lab', 'qa', 'uat', 'certif', 'staging', 'prod']

        # All should pass without exception
        validate_environment_against_inventory('qa')
        validate_environment_against_inventory('uat')
        validate_environment_against_inventory('certif')

    # -- Story 53.2: Valeurs brutes inventaire (developpement, certification, production) --

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_certification_raw_value(self, mock_list_envs):
        """Story 53.2 AC8 : 'certification' (valeur brute inventaire) est acceptée sans alias."""
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['developpement', 'certification', 'production']

        # Should not raise — certification est valide dans l'inventaire
        validate_environment_against_inventory('certification')

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_developpement_raw_value(self, mock_list_envs):
        """Story 53.2 AC8 : 'developpement' (valeur brute inventaire) est acceptée sans alias."""
        from executions.utils import validate_environment_against_inventory

        mock_list_envs.return_value = ['developpement', 'certification', 'production']

        # Should not raise — developpement est valide dans l'inventaire
        validate_environment_against_inventory('developpement')

    @patch('inventory.services.InventoryService.list_environments')
    def test_validate_dev_rejected_when_not_in_inventory(self, mock_list_envs):
        """Story 53.2 Task 5.4 : 'dev' est rejeté par validate_environment_against_inventory()
        si l'inventaire ne contient que les valeurs brutes.

        Note : cette fonction est appelée pour les EXÉCUTIONS PLANIFIÉES uniquement
        (Story 26.10). Pour les exécutions régulières, aucune validation d'environnement
        n'est effectuée à ce niveau — le rejet éventuel passe par le RBAC/permission_aggregator.
        """
        from executions.utils import validate_environment_against_inventory
        from core.exceptions import BadRequestError

        mock_list_envs.return_value = ['developpement', 'certification', 'production']

        with self.assertRaises(BadRequestError) as cm:
            validate_environment_against_inventory('dev')

        self.assertEqual(cm.exception.code, 'INVALID_ENVIRONMENT')


# =============================================================================
# Story 21.3, Task 4: Environment config lookup tests
# =============================================================================


class EnvironmentConfigLookupAdvancedTests(TestCase):
    """
    Story 21.3, Task 4: Tests for _get_env_config_case_insensitive.
    Case-insensitive lookup, impact_rules fallback, change_type_config fallback.
    """

    def _get_helper(self):
        from executions.utils import get_env_config_case_insensitive
        return get_env_config_case_insensitive

    # -- Task 4.1: Case-insensitive match --

    def test_lab_config_case_insensitive(self):
        """config={'LAB': {...}} → lookup 'lab' returns config."""
        helper = self._get_helper()
        config = {'LAB': {'impact_level': 'LOW'}}

        result = helper(config, 'lab')
        self.assertEqual(result, {'impact_level': 'LOW'})

        result = helper(config, 'LAB')
        self.assertEqual(result, {'impact_level': 'LOW'})

        result = helper(config, 'Lab')
        self.assertEqual(result, {'impact_level': 'LOW'})

    # -- Task 4.2: Multiple keys --

    def test_multiple_keys_case_insensitive(self):
        """config={'dev': {...}, 'staging': {...}} → lookup 'DEV' returns config['dev']."""
        helper = self._get_helper()
        config = {
            'dev': {'impact_level': 'LOW'},
            'STAGING': {'impact_level': 'HIGH'},
        }

        result = helper(config, 'DEV')
        self.assertEqual(result, {'impact_level': 'LOW'})

        result = helper(config, 'staging')
        self.assertEqual(result, {'impact_level': 'HIGH'})

    # -- Task 4.3: Not found → empty dict --

    def test_not_found_returns_empty_dict(self):
        """Environment not in config → returns {}."""
        helper = self._get_helper()
        config = {'dev': {'impact_level': 'LOW'}}

        result = helper(config, 'lab')
        self.assertEqual(result, {})

    # -- Task 4.4: None config → {} --

    def test_none_config_returns_empty_dict(self):
        """config=None → returns {} (no error)."""
        helper = self._get_helper()

        result = helper(None, 'lab')
        self.assertEqual(result, {})

    def test_empty_config_returns_empty_dict(self):
        """config={} → returns {}."""
        helper = self._get_helper()

        result = helper({}, 'lab')
        self.assertEqual(result, {})

    def test_empty_env_returns_empty_dict(self):
        """env='' or env=None → returns {}."""
        helper = self._get_helper()
        config = {'dev': {'impact_level': 'LOW'}}

        result = helper(config, '')
        self.assertEqual(result, {})

        result = helper(config, None)
        self.assertEqual(result, {})

    # -- Task 4.5: impact_rules fallback to default_impact_level --

    def test_impact_rules_lab_no_rule_uses_default(self):
        """No impact_rules for 'lab' → should use default_impact_level."""
        helper = self._get_helper()
        impact_rules = {
            'DEV': {'impact_level': 'LOW'},
            'PROD': {'impact_level': 'CRITICAL'},
        }

        # Lab not in rules
        env_config = helper(impact_rules, 'lab')
        self.assertEqual(env_config, {})

        # Application code should fallback:
        # impact_level = env_config.get('impact_level') or action.default_impact_level
        default_impact_level = 'MEDIUM'
        impact_level = env_config.get('impact_level') or default_impact_level
        self.assertEqual(impact_level, 'MEDIUM')

    def test_impact_rules_lab_with_rule(self):
        """impact_rules has 'LAB' config → returns it case-insensitively."""
        helper = self._get_helper()
        impact_rules = {
            'LAB': {'impact_level': 'LOW'},
            'PROD': {'impact_level': 'CRITICAL'},
        }

        result = helper(impact_rules, 'lab')
        self.assertEqual(result.get('impact_level'), 'LOW')

    # -- Task 4.6: change_type_config fallback --

    def test_change_type_config_lab_no_config_returns_empty(self):
        """No change_type_config for 'lab' → returns {} (no change required)."""
        helper = self._get_helper()
        change_type_config = {
            'PROD': {'required': True, 'change_model_code': 'PRD-001'},
            'STAGING': {'required': True, 'change_model_code': 'STG-001'},
        }

        result = helper(change_type_config, 'lab')
        self.assertEqual(result, {})

        # Application code default behavior:
        change_required = result.get('required', False)
        self.assertFalse(change_required)

    def test_change_type_config_lab_with_config(self):
        """change_type_config with 'lab' → returns config."""
        helper = self._get_helper()
        change_type_config = {
            'lab': {'required': False},
            'PROD': {'required': True, 'change_model_code': 'PRD-001'},
        }

        result = helper(change_type_config, 'lab')
        self.assertEqual(result, {'required': False})

    def test_whitespace_trimmed_in_lookup(self):
        """Keys and env values are trimmed before comparison."""
        helper = self._get_helper()
        config = {'  LAB  ': {'impact_level': 'LOW'}}

        result = helper(config, ' lab ')
        self.assertEqual(result, {'impact_level': 'LOW'})
