"""
Tests de couverture pour executions/validators/target_validator.py (Story 55).
Couvre les lignes manquantes :
  - 52-59 : except InventoryServiceError → BadRequestError INVENTORY_UNAVAILABLE
  - 92    : details_403["inventory_truncated"] = True (target non autorisée + inventaire tronqué)
"""
import pytest
from unittest.mock import patch, MagicMock

from core.exceptions import BadRequestError, ForbiddenError
from inventory.services import InventoryServiceError


class TestTargetValidatorCoverage:
    """Tests pour TargetValidator.validate_targets."""

    def _make_user(self, user_id=1):
        user = MagicMock()
        user.id = user_id
        return user

    # ── Lignes 52-59 : InventoryServiceError ─────────────────────────────────

    def test_inventory_service_error_raises_bad_request(self):
        """Lignes 52-59 : InventoryServiceError → BadRequestError INVENTORY_UNAVAILABLE."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with patch('executions.validators.target_validator.InventoryService') as MockService:
            instance = MockService.return_value
            instance.list_targets_for_user.side_effect = InventoryServiceError("DB unavailable")

            with pytest.raises(BadRequestError) as exc_info:
                TargetValidator.validate_targets(
                    target_names=["server1"],
                    action_id=10,
                    user=user,
                    ad_groups=["group1"],
                    correlation_id="corr-test",
                )
            assert exc_info.value.code == "INVENTORY_UNAVAILABLE"

    def test_inventory_service_error_logs_error(self):
        """Lignes 52-59 : InventoryServiceError → logger.error appelé."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user(user_id=42)

        with patch('executions.validators.target_validator.InventoryService') as MockService, \
             patch('executions.validators.target_validator.logger') as mock_logger:
            instance = MockService.return_value
            instance.list_targets_for_user.side_effect = InventoryServiceError("Timeout")

            with pytest.raises(BadRequestError):
                TargetValidator.validate_targets(
                    target_names=["server1"],
                    action_id=5,
                    user=user,
                    ad_groups=[],
                    correlation_id="corr-42",
                )
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "inventory_service_error_during_execution"

    # ── Ligne 92 : inventory_truncated = True ────────────────────────────────

    def test_forbidden_target_with_truncated_inventory_adds_flag(self):
        """Ligne 92 : target non autorisée + inventory_truncated=True → details contient flag."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with patch('executions.validators.target_validator.InventoryService') as MockService, \
             patch('executions.validators.target_validator.AuditService') as _MockAudit:
            instance = MockService.return_value
            # inventory_truncated=True → ligne 92 déclenchée
            instance.list_targets_for_user.return_value = (
                [{"name": "authorized_server", "environment": "prod"}],
                1,
                True,  # inventory_truncated
            )

            with pytest.raises(ForbiddenError) as exc_info:
                TargetValidator.validate_targets(
                    target_names=["unauthorized_server"],
                    action_id=10,
                    user=user,
                    ad_groups=["group1"],
                    correlation_id="corr-forbidden",
                )
            assert exc_info.value.code == "FORBIDDEN"
            # Vérifier que inventory_truncated est dans les details
            assert exc_info.value.details.get("inventory_truncated") is True

    def test_forbidden_target_without_truncation_no_flag(self):
        """inventory_truncated=False → pas de flag inventory_truncated dans details."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with patch('executions.validators.target_validator.InventoryService') as MockService, \
             patch('executions.validators.target_validator.AuditService'):
            instance = MockService.return_value
            instance.list_targets_for_user.return_value = (
                [{"name": "authorized_server", "environment": "prod"}],
                1,
                False,  # inventory_truncated = False → ligne 92 non exécutée
            )

            with pytest.raises(ForbiddenError) as exc_info:
                TargetValidator.validate_targets(
                    target_names=["unauthorized_server"],
                    action_id=10,
                    user=user,
                    ad_groups=["group1"],
                    correlation_id="corr-ok",
                )
            assert "inventory_truncated" not in exc_info.value.details

    # ── Cas nominal ──────────────────────────────────────────────────────────

    def test_invalid_target_names_not_a_list_raises_bad_request(self):
        """Ligne 38-42 : target_names non-liste → BadRequestError BAD_REQUEST."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with pytest.raises(BadRequestError) as exc_info:
            TargetValidator.validate_targets(
                target_names="not_a_list",
                action_id=1,
                user=user,
                ad_groups=[],
                correlation_id="corr-bad",
            )
        assert exc_info.value.code == "BAD_REQUEST"

    def test_empty_target_names_raises_bad_request(self):
        """Ligne 38-42 : target_names vide → BadRequestError."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with pytest.raises(BadRequestError) as exc_info:
            TargetValidator.validate_targets(
                target_names=[],
                action_id=1,
                user=user,
                ad_groups=[],
                correlation_id="corr-empty",
            )
        assert exc_info.value.code == "BAD_REQUEST"

    def test_valid_targets_returns_tuple(self):
        """Lignes 109-110 : succès → retourne (validated_targets, environment)."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with patch('executions.validators.target_validator.InventoryService') as MockService:
            instance = MockService.return_value
            instance.list_targets_for_user.return_value = (
                [{"name": "server1", "environment": "prod"}],
                1,
                False,
            )

            validated, environment = TargetValidator.validate_targets(
                target_names=["server1"],
                action_id=10,
                user=user,
                ad_groups=["group1"],
                correlation_id="corr-success",
            )
            assert len(validated) == 1
            assert validated[0]["name"] == "server1"
            assert environment == "prod"

    def test_mixed_environments_raises_bad_request(self):
        """Lignes 102-107 : targets dans des environnements différents → BadRequestError MIXED_ENVIRONMENTS."""
        from executions.validators.target_validator import TargetValidator

        user = self._make_user()

        with patch('executions.validators.target_validator.InventoryService') as MockService:
            instance = MockService.return_value
            instance.list_targets_for_user.return_value = (
                [
                    {"name": "server1", "environment": "prod"},
                    {"name": "server2", "environment": "staging"},
                ],
                2,
                False,
            )

            with pytest.raises(BadRequestError) as exc_info:
                TargetValidator.validate_targets(
                    target_names=["server1", "server2"],
                    action_id=10,
                    user=user,
                    ad_groups=[],
                    correlation_id="corr-mixed",
                )
            assert exc_info.value.code == "MIXED_ENVIRONMENTS"
