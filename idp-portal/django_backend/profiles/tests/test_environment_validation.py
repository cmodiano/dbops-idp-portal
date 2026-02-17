"""
Tests for profile environment validation against inventory (Story 21.6).
"""

import pytest

from profiles.validation import validate_environments_against_inventory
from inventory.services import InventoryServiceError
from core.exceptions import BadRequestError, ServiceUnavailableError
from core.models import AuditActionType, AuditEntityType


@pytest.fixture
def mock_inventory_service(mocker):
    """Mock InventoryService for unit tests."""
    mock = mocker.patch('profiles.validation.InventoryService')
    mock.return_value.list_environments.return_value = ['lab', 'dev', 'staging', 'prod']
    return mock.return_value


@pytest.fixture
def mock_audit_service(mocker):
    """Mock AuditService for audit trail tests."""
    return mocker.patch('profiles.validation.AuditService')


class TestValidateEnvironmentsAgainstInventory:
    """Tests for validate_environments_against_inventory() (Story 21.6)."""

    def test_validate_valid_environments(self, mock_inventory_service):
        """Valid environments pass validation (AC1)."""
        result = validate_environments_against_inventory(['lab', 'dev'])
        assert result == ['lab', 'dev']

    def test_validate_invalid_environment_raises_error(self, mock_inventory_service, mock_audit_service):
        """Invalid environment raises BadRequestError with explicit message (AC1)."""
        with pytest.raises(BadRequestError) as exc_info:
            validate_environments_against_inventory(['lab', 'invalid_env'])

        assert exc_info.value.code == "INVALID_ENVIRONMENTS"
        assert "invalid_env" in exc_info.value.message
        assert "Environnements invalides" in exc_info.value.message

    def test_validate_case_insensitive(self, mock_inventory_service):
        """Environment validation is case-insensitive, returns lowercase (AC2)."""
        result = validate_environments_against_inventory(['LAB', 'DEV'])
        assert result == ['lab', 'dev']

    def test_validate_inventory_unavailable_raises_503(self, mocker, mock_audit_service):
        """Block if inventory unavailable with ServiceUnavailableError (SOC1, AC3)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.side_effect = InventoryServiceError("DB down")

        with pytest.raises(ServiceUnavailableError) as exc_info:
            validate_environments_against_inventory(['lab'])

        assert exc_info.value.code == "INVENTORY_UNAVAILABLE"
        assert "Inventaire indisponible" in exc_info.value.message

    def test_validate_empty_list_succeeds(self):
        """Empty environments list succeeds without error (AC4)."""
        result = validate_environments_against_inventory([])
        assert result == []

    def test_validate_none_succeeds(self):
        """None environments succeeds without error (AC4)."""
        result = validate_environments_against_inventory(None)
        assert result == []

    def test_audit_trail_created_for_invalid(self, mock_inventory_service, mock_audit_service):
        """Audit trail created BEFORE error for invalid environments (SOC1, AC7)."""
        with pytest.raises(BadRequestError):
            validate_environments_against_inventory(
                ['invalid_env'],
                user_id=123,
                entity_id=456,
            )

        mock_audit_service.create_entry.assert_called_once()
        call_kwargs = mock_audit_service.create_entry.call_args.kwargs

        assert call_kwargs['action_type'] == AuditActionType.PROFILE_UPDATE_REJECTED
        assert call_kwargs['entity_type'] == AuditEntityType.PROFILE
        assert call_kwargs['entity_id'] == 456
        assert call_kwargs['user_id'] == '123'
        assert 'invalid_env' in call_kwargs['details']['invalid_environments']
        assert call_kwargs['details']['reason'] == 'invalid_environments'
        assert call_kwargs['details']['available_environments'] == ['lab', 'dev', 'staging', 'prod']

    def test_audit_trail_user_id_defaults_to_system(self, mock_inventory_service, mock_audit_service):
        """Audit trail uses 'system' when no user_id provided."""
        with pytest.raises(BadRequestError):
            validate_environments_against_inventory(['invalid_env'])

        call_kwargs = mock_audit_service.create_entry.call_args.kwargs
        assert call_kwargs['user_id'] == 'system'

    def test_validate_mixed_valid_invalid(self, mock_inventory_service, mock_audit_service):
        """Mixed valid/invalid environments raises error listing only invalids (AC1)."""
        with pytest.raises(BadRequestError) as exc_info:
            validate_environments_against_inventory(['lab', 'dev', 'typo_env', 'fake_env'])

        assert "typo_env" in exc_info.value.message
        assert "fake_env" in exc_info.value.message

    def test_validate_all_standard_environments(self, mock_inventory_service):
        """All standard environments pass validation."""
        result = validate_environments_against_inventory(['dev', 'staging', 'prod'])
        assert result == ['dev', 'staging', 'prod']

    def test_validate_non_standard_environments(self, mock_inventory_service):
        """Non-standard environments pass if present in inventory."""
        mock_inventory_service.list_environments.return_value = ['lab', 'qa', 'uat', 'certif']
        result = validate_environments_against_inventory(['lab', 'qa'])
        assert result == ['lab', 'qa']

    def test_validate_mixed_case_normalization(self, mock_inventory_service):
        """Mixed case environments are normalized to lowercase (AC2)."""
        result = validate_environments_against_inventory(['Lab', 'DEV', 'Staging'])
        assert result == ['lab', 'dev', 'staging']

    def test_invalid_environments_in_error_details(self, mock_inventory_service, mock_audit_service):
        """Error details contain both invalid and available environments."""
        with pytest.raises(BadRequestError) as exc_info:
            validate_environments_against_inventory(['invalid_env'])

        assert exc_info.value.details['invalid_environments'] == ['invalid_env']
        assert exc_info.value.details['available_environments'] == ['lab', 'dev', 'staging', 'prod']

    def test_audit_trail_preserves_original_case(self, mock_inventory_service, mock_audit_service):
        """Audit trail preserves original submitted environments for traceability."""
        with pytest.raises(BadRequestError):
            validate_environments_against_inventory(['INVALID_ENV'], user_id=1)

        call_kwargs = mock_audit_service.create_entry.call_args.kwargs
        assert call_kwargs['details']['submitted_environments'] == ['INVALID_ENV']
        assert call_kwargs['details']['invalid_environments'] == ['invalid_env']

    def test_no_audit_trail_for_valid_environments(self, mock_inventory_service, mock_audit_service):
        """No audit trail created for valid environments."""
        validate_environments_against_inventory(['lab', 'dev'])
        mock_audit_service.create_entry.assert_not_called()

    def test_no_audit_trail_for_empty(self, mock_audit_service):
        """No audit trail created for empty environments."""
        validate_environments_against_inventory([])
        mock_audit_service.create_entry.assert_not_called()
