"""Tests pour broadcast_step_update — Story 58.3."""
from unittest.mock import MagicMock, patch

import pytest
from django.test import TransactionTestCase

from tests.factories import UserFactory, ActionFactory


class TestBroadcastStepUpdate(TransactionTestCase):
    """Tests unitaires pour executions.utils.websocket_broadcast.broadcast_step_update."""

    def _make_mock_step(self, execution_id=1, step_id=42, step_order=1,
                        step_name="Gate", step_type="gate", status="WAITING"):
        step = MagicMock()
        step.id = step_id
        step.step_order = step_order
        step.step_name = step_name
        step.step_type = step_type
        step.status = status
        step.started_at = None
        step.completed_at = None
        step.platform_job_id = None
        step.error_message = None
        step.get_output = MagicMock(return_value={"gate_conditions": []})
        return step

    def test_broadcast_sends_correct_payload(self):
        """broadcast_step_update appelle group_send avec le bon payload."""
        from executions.utils.websocket_broadcast import broadcast_step_update

        mock_layer = MagicMock()
        mock_send = MagicMock()

        mock_channels = MagicMock()
        mock_channels.get_channel_layer = MagicMock(return_value=mock_layer)
        mock_asgiref = MagicMock()
        mock_asgiref.async_to_sync = MagicMock(return_value=mock_send)

        import sys
        with patch.dict(sys.modules, {
            "channels.layers": mock_channels,
            "asgiref.sync": mock_asgiref,
        }):
            step = self._make_mock_step()
            broadcast_step_update(execution_id=1, step=step)

        mock_send.assert_called_once_with(
            "execution_1",
            {
                "type": "step_update",
                "data": {
                    "id": 42,
                    "execution_id": 1,
                    "step_order": 1,
                    "step_name": "Gate",
                    "step_type": "gate",
                    "status": "WAITING",
                    "started_at": None,
                    "completed_at": None,
                    "output": {"gate_conditions": []},
                    "platform_job_id": None,
                    "error_message": None,
                },
            },
        )

    def test_broadcast_noop_when_channel_layer_none(self):
        """broadcast_step_update ne lève pas d'exception si channel_layer est None."""
        from executions.utils.websocket_broadcast import broadcast_step_update

        mock_channels = MagicMock()
        mock_channels.get_channel_layer = MagicMock(return_value=None)
        mock_asgiref = MagicMock()

        import sys
        with patch.dict(sys.modules, {
            "channels.layers": mock_channels,
            "asgiref.sync": mock_asgiref,
        }):
            step = self._make_mock_step()
            # Ne doit pas lever d'exception
            broadcast_step_update(execution_id=1, step=step)

        # async_to_sync ne doit pas être appelé
        mock_asgiref.async_to_sync.assert_not_called()

    def test_broadcast_noop_when_channels_not_installed(self):
        """broadcast_step_update silently skips ImportError (channels non installé)."""
        from executions.utils.websocket_broadcast import broadcast_step_update

        import sys
        with patch.dict(sys.modules, {"channels.layers": None}):
            step = self._make_mock_step()
            # Ne doit pas lever d'exception (ImportError est catchée)
            try:
                broadcast_step_update(execution_id=1, step=step)
            except Exception as e:
                pytest.fail(f"broadcast_step_update ne devrait pas lever d'exception: {e}")

    def test_broadcast_noop_on_exception(self):
        """broadcast_step_update absorbe les exceptions de transport sans interrompre le flux."""
        from executions.utils.websocket_broadcast import broadcast_step_update

        mock_layer = MagicMock()
        mock_send = MagicMock(side_effect=Exception("Redis down"))

        mock_channels = MagicMock()
        mock_channels.get_channel_layer = MagicMock(return_value=mock_layer)
        mock_asgiref = MagicMock()
        mock_asgiref.async_to_sync = MagicMock(return_value=mock_send)

        import sys
        with patch.dict(sys.modules, {
            "channels.layers": mock_channels,
            "asgiref.sync": mock_asgiref,
        }):
            step = self._make_mock_step()
            # Ne doit pas lever d'exception
            broadcast_step_update(execution_id=99, step=step)

    def test_broadcast_step_type_enum_is_serialized_as_value(self):
        """step_type de type enum (ExecutionStepType) est sérialisé en valeur string."""
        from executions.utils.websocket_broadcast import broadcast_step_update

        mock_layer = MagicMock()
        mock_send = MagicMock()

        mock_channels = MagicMock()
        mock_channels.get_channel_layer = MagicMock(return_value=mock_layer)
        mock_asgiref = MagicMock()
        mock_asgiref.async_to_sync = MagicMock(return_value=mock_send)

        # Simuler un step_type qui est un enum avec .value
        mock_enum = MagicMock()
        mock_enum.value = "gate"

        import sys
        with patch.dict(sys.modules, {
            "channels.layers": mock_channels,
            "asgiref.sync": mock_asgiref,
        }):
            step = self._make_mock_step(step_type=mock_enum)
            broadcast_step_update(execution_id=1, step=step)

        call_args = mock_send.call_args[0]
        payload = call_args[1]
        assert payload["data"]["step_type"] == "gate"


class TestBroadcastIntegrationWithStepExecutor(TransactionTestCase):
    """Test intégration : workflow_step_executor crée étape WAITING et déclenche broadcast."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(item_type="workflow")
        from executions.models import Execution, ExecutionStatus
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    @patch("executions.gate_context.build_waiting_context", return_value={"gates": []})
    @patch("executions.utils.websocket_broadcast.broadcast_step_update")
    def test_waiting_step_triggers_broadcast(self, mock_broadcast, mock_ctx, mock_audit):
        """workflow_step_executor.execute déclenche broadcast après création WAITING step."""
        from executions.workflow_step_executor import StepExecutor
        from executions.models import ExecutionStepStatus

        executor = StepExecutor(self.execution, "test-corr")
        step = {
            'step_id': 'gate-step', 'name': 'Approbation', 'order': 1,
            'gate_conditions': [{'type': 'approval_granted'}],
        }
        result = executor.execute(step, step_order=1, step_parameters={})

        assert result.is_waiting
        mock_broadcast.assert_called_once()

        call_args = mock_broadcast.call_args
        assert call_args[0][0] == self.execution.id  # execution_id en positional
        broadcast_step = call_args[0][1]
        assert broadcast_step.status == ExecutionStepStatus.WAITING

    @patch("executions.workflow_step_executor.AuditService.create_entry")
    @patch("executions.gate_context.build_waiting_context", return_value={"gates": []})
    @patch("executions.utils.websocket_broadcast.broadcast_step_update")
    def test_broadcast_called_with_step_type_gate(self, mock_broadcast, mock_ctx, mock_audit):
        """Le step broadcasté a step_type='platform' (valeur par défaut gate_conditions)."""
        from executions.workflow_step_executor import StepExecutor

        executor = StepExecutor(self.execution, "test-corr")
        step = {
            'step_id': 'gate-step', 'name': 'Gate', 'order': 1,
            'gate_conditions': [{'type': 'approval_granted'}],
        }
        executor.execute(step, step_order=1, step_parameters={})

        broadcast_step = mock_broadcast.call_args[0][1]
        # step sans step_type explicite → step_type_routing='platform' (défaut), step broadcasté avec 'platform'
        assert broadcast_step.step_type == 'platform'
