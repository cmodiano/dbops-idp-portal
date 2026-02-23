"""
Story 31.6: Tests for ServiceNow change creation before RUNNING (AC#6–#8, AC#10).

Tests:
- 5.4: execution creates servicenow change before RUNNING
- 5.5: execution fails if servicenow change fails
- 5.6: no servicenow call if not required
- 5.7: fallback to first servicenow integration when no gate_config
"""
import pytest
from unittest.mock import patch, MagicMock

from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.models import ExecutionStatus
from catalog.models import ActionStatus, ActionItemType
from core.exceptions import ServiceUnavailableError
from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory


def _make_steps(action_id):
    return [{"order": 1, "name": "Step 1", "referenced_action_id": action_id, "step_id": "step-1"}]


@pytest.mark.django_db
class TestServiceNowChangeHook:
    """Test _create_servicenow_change_if_required in ContainerWorkflowRuntime."""

    def setup_method(self):
        self.user = UserFactory(username="sn_hook_test_user")
        self.sn_integration = IntegrationFactory(
            type='servicenow',
            name='ServiceNow Prod',
            base_url='https://snow.example.com',
            credential_ref='sn-token-123',
            auth_flow='token',
        )

    def _make_runtime(self, change_type_config=None, gate_config=None):
        """Helper to create a runtime with the given configs."""
        child_action = ActionFactory(
            name="Child Action SN",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="Workflow SN Test",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps(child_action.id),
            change_type_config=change_type_config,
            gate_config=gate_config,
            created_by=self.user,
        )
        execution = ExecutionFactory(
            action=workflow_action,
            user=self.user,
            environment='production',
            status='SUBMITTED',
        )
        return ContainerWorkflowRuntime(execution)

    @patch("services.servicenow_service.httpx.Client")
    def test_execution_creates_servicenow_change_before_running(self, mock_client_class):
        """5.4: ServiceNow change created before RUNNING, servicenow_change_id set."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "CHG0001234"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        runtime = self._make_runtime(
            change_type_config={'production': {'required': True, 'change_model_code': 'MDL001'}},
            gate_config={'servicenow_change': {'integration_id': self.sn_integration.id}},
        )

        # Call the hook directly
        runtime._create_servicenow_change_if_required('production')

        # Verify change number saved
        runtime.execution.refresh_from_db()
        assert runtime.execution.servicenow_change_id == "CHG0001234"

    @patch("services.servicenow_service.ServiceNowService.create_change")
    def test_execution_fails_if_servicenow_change_fails(self, mock_create_change):
        """5.5: Execution FAILED if create_change raises ServiceUnavailableError."""
        mock_create_change.side_effect = ServiceUnavailableError(
            code="SERVICENOW_TIMEOUT",
            message="ServiceNow create_change timeout",
        )

        runtime = self._make_runtime(
            change_type_config={'production': {'required': True, 'change_model_code': 'MDL001'}},
            gate_config={'servicenow_change': {'integration_id': self.sn_integration.id}},
        )

        # run_sync should catch the error and set FAILED
        status = runtime.run_sync()

        runtime.execution.refresh_from_db()
        assert runtime.execution.status == ExecutionStatus.FAILED
        assert "ServiceNow" in runtime.execution.error_message
        assert status == ExecutionStatus.FAILED

    def test_execution_no_servicenow_if_not_required(self):
        """5.6: No ServiceNow call when required=False."""
        runtime = self._make_runtime(
            change_type_config={'production': {'required': False}},
        )

        with patch("services.servicenow_service.ServiceNowService.create_change") as mock_create:
            runtime._create_servicenow_change_if_required('production')
            mock_create.assert_not_called()

    @patch("services.servicenow_service.httpx.Client")
    def test_execution_servicenow_fallback_no_gate_config(self, mock_client_class):
        """5.7: Without gate_config, uses first servicenow integration available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "CHG0009999"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        runtime = self._make_runtime(
            change_type_config={'production': {'required': True, 'change_model_code': 'MDL002'}},
            gate_config=None,  # No gate_config → fallback
        )

        runtime._create_servicenow_change_if_required('production')

        runtime.execution.refresh_from_db()
        assert runtime.execution.servicenow_change_id == "CHG0009999"

    def test_execution_no_servicenow_when_no_env_config(self):
        """No ServiceNow call when environment is not in change_type_config."""
        runtime = self._make_runtime(
            change_type_config={'staging': {'required': True, 'change_model_code': 'MDL001'}},
        )

        with patch("services.servicenow_service.ServiceNowService.create_change") as mock_create:
            runtime._create_servicenow_change_if_required('production')  # Not in config
            mock_create.assert_not_called()
