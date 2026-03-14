"""Tests pour broadcast_step_update — Story 58.3."""
from unittest.mock import MagicMock, patch

import pytest
from django.test import TransactionTestCase



class TestBroadcastStepUpdate(TransactionTestCase):
    """Tests unitaires pour executions.utils.websocket_broadcast.broadcast_step_update."""

    def _make_mock_step(self, execution_id=1, step_id=42, step_order=1,
                        step_name="Gate", step_type="gate", status="WAITING",
                        config_step_id=None):
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
        step.config_step_id = config_step_id
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
                    "config_step_id": None,
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

# Note (Epic 81 PR4) : La classe TestBroadcastIntegrationWithStepExecutor a été supprimée.
# Elle importait executions.workflow_step_executor (supprimé en PR3).
# Les tests de broadcast_step_update ci-dessus (TestBroadcastStepUpdate) couvrent le comportement essentiel.
