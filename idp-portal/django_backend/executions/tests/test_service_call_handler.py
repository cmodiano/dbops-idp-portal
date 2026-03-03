"""
Tests unitaires pour ServiceCallHandler (story 57.4, AC#1–#7).

Pas de @pytest.mark.django_db — IntegrationService est mocké.
"""
import pytest
from unittest.mock import patch, MagicMock

from executions.step_handlers.service_call_handler import ServiceCallHandler


class TestServiceCallHandler:
    """Tests de ServiceCallHandler.execute() (story 57.4)."""

    def setup_method(self):
        self.handler = ServiceCallHandler()

    def _make_execution(self, exec_id=1):
        m = MagicMock()
        m.id = exec_id
        return m

    def _make_integration(self, integration_type="servicenow", base_url="https://snow.example.com"):
        m = MagicMock()
        m.type = integration_type
        m.base_url = base_url
        return m

    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_create_change_success(self, mock_is_class, mock_bah, mock_gsc):
        """AC#1 : ServiceNowService.create_change() appelé avec resolved_params."""
        integration = self._make_integration()
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {"Authorization": "Bearer token"}

        mock_service = MagicMock()
        mock_service.create_change.return_value = {"number": "CHG001", "sys_id": "abc"}
        mock_gsc.return_value = mock_service

        step_config = {
            "integration_type": "servicenow",
            "operation": "create_change",
        }
        resolved_params = {"short_description": "Patching Oracle"}

        result = self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id="corr-123",
        )

        mock_service.create_change.assert_called_once_with(short_description="Patching Oracle")
        assert result == {"number": "CHG001", "sys_id": "abc"}

    def test_private_operation_raises_value_error(self):
        """AC#3 : opération _private interdite."""
        step_config = {"integration_type": "servicenow", "operation": "_internal_method"}
        with pytest.raises(ValueError, match="private methods cannot be called"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_unknown_integration_type_raises(self, mock_is_class, mock_bah, mock_gsc):
        """AC#5 : integration_type non enregistrée → ValueError via get_service_client."""
        integration = self._make_integration(integration_type="pagerduty")
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {}
        mock_gsc.side_effect = ValueError("Unsupported service_type: 'pagerduty'")

        step_config = {"integration_type": "pagerduty", "operation": "notify"}
        with pytest.raises(ValueError, match="pagerduty"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )
        # Unknown integration_type short-circuits before integration resolution
        mock_is_class.assert_not_called()
        mock_bah.assert_not_called()
        mock_gsc.assert_not_called()

    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_no_integration_found_raises_service_unavailable(self, mock_is_class):
        """AC#6 : aucune intégration disponible → ServiceUnavailableError."""
        mock_is_class.return_value.get_by_id.return_value = None
        mock_is_class.return_value.get_by_type.return_value = None

        from core.exceptions import ServiceUnavailableError
        step_config = {"integration_type": "servicenow", "operation": "create_change"}
        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )
        assert exc_info.value.code == "SERVICE_INTEGRATION_MISSING"

    @patch("executions.step_handlers.service_call_handler._ALLOWED_OPERATIONS", {
        "servicenow": frozenset({"create_change", "update_change", "close_change", "get_change_status", "cancel_change", "nonexistent_op"}),
        "vault": frozenset({"get_secret"}),
        "jira": frozenset({"create_issue", "update_issue", "get_issue"}),
    })
    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_nonexistent_operation_raises_value_error(self, mock_is_class, mock_bah, mock_gsc):
        """AC#3 : opération inexistante sur le service → ValueError (allowlist OK, hasattr False)."""
        integration = self._make_integration()
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {}

        mock_service = MagicMock(spec=[])  # Pas d'attributs → hasattr retourne False
        mock_gsc.return_value = mock_service

        step_config = {"integration_type": "servicenow", "operation": "nonexistent_op"}
        with pytest.raises(ValueError, match="nonexistent_op"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_service_exception_propagates(self, mock_is_class, mock_bah, mock_gsc):
        """AC#7 : exception du service propagée vers _execute_handler_step."""
        from core.exceptions import ServiceUnavailableError
        integration = self._make_integration()
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {}

        mock_service = MagicMock()
        mock_service.close_change.side_effect = ServiceUnavailableError(
            code="SERVICENOW_TIMEOUT", message="timeout"
        )
        mock_gsc.return_value = mock_service

        step_config = {"integration_type": "servicenow", "operation": "close_change"}
        with pytest.raises(ServiceUnavailableError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={"change_id": "CHG001"},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_scalar_result_normalized_to_dict(self, mock_is_class, mock_bah, mock_gsc):
        """Résultat scalaire normalisé en dict {'result': ...} pour output_mapping."""
        integration = self._make_integration()
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {}

        mock_service = MagicMock()
        mock_service.get_secret.return_value = "my-password"  # scalaire
        mock_gsc.return_value = mock_service

        step_config = {"integration_type": "vault", "operation": "get_secret"}
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={"credential_ref": "vault:secret/data/db#pass"},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert result == {"result": "my-password"}

    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_integration_id_fallback_on_type_mismatch(self, mock_is_class, mock_bah, mock_gsc):
        """AC#6 : integration_id avec type mismatch → fallback sur get_by_type."""
        wrong_integration = self._make_integration(integration_type="jira")
        correct_integration = self._make_integration(integration_type="servicenow")

        mock_is_class.return_value.get_by_id.return_value = wrong_integration
        mock_is_class.return_value.get_by_type.return_value = correct_integration
        mock_bah.return_value = {}

        mock_service = MagicMock()
        mock_service.create_change.return_value = {"number": "CHG002", "sys_id": "xyz"}
        mock_gsc.return_value = mock_service

        step_config = {
            "integration_type": "servicenow",
            "operation": "create_change",
            "integration_id": 99,
        }
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        # get_by_type doit être appelé en fallback
        mock_is_class.return_value.get_by_type.assert_called_once_with("servicenow")
        assert result == {"number": "CHG002", "sys_id": "xyz"}

    def test_missing_integration_type_raises(self):
        """ValueError si integration_type manquant."""
        step_config = {"operation": "create_change"}
        with pytest.raises(ValueError, match="integration_type"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    def test_missing_operation_raises(self):
        """ValueError si operation manquante."""
        step_config = {"integration_type": "servicenow"}
        with pytest.raises(ValueError, match="operation"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch("executions.step_handlers.service_call_handler.logger")
    @patch("executions.step_handlers.service_call_handler.get_service_client")
    @patch("executions.step_handlers.service_call_handler.build_auth_headers")
    @patch("executions.step_handlers.service_call_handler.IntegrationService")
    def test_service_exception_logs_error(self, mock_is_class, mock_bah, mock_gsc, mock_logger):
        """H1 fix: service_call_handler_error est loggué quand le service lève une exception."""
        from core.exceptions import ServiceUnavailableError
        integration = self._make_integration()
        mock_is_class.return_value.get_by_type.return_value = integration
        mock_bah.return_value = {}

        mock_service = MagicMock()
        mock_service.create_change.side_effect = ServiceUnavailableError(
            code="SERVICENOW_TIMEOUT", message="timeout"
        )
        mock_gsc.return_value = mock_service

        step_config = {"integration_type": "servicenow", "operation": "create_change"}
        with pytest.raises(ServiceUnavailableError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id="corr-err",
            )

        mock_logger.error.assert_called_once_with(
            "service_call_handler_error",
            integration_type="servicenow",
            operation="create_change",
            execution_id=1,
            correlation_id="corr-err",
            exc_info=True,
        )

    def test_operation_not_in_allowlist_raises(self):
        """M1 fix: opération non autorisée par _ALLOWED_OPERATIONS → ValueError."""
        step_config = {"integration_type": "servicenow", "operation": "delete_change"}
        with pytest.raises(ValueError, match="allowed list"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )
