"""
Tests de couverture pour executions/gate_context.py (Story 55).
Couvre les lignes 29-34 : validation de type gate_conditions + ValueError.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestBuildWaitingContext:
    """Tests pour executions.gate_context.build_waiting_context."""

    def _make_exec_step(self, created_at=None):
        step = MagicMock()
        step.id = 10
        step.created_at = created_at or datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        return step

    def test_valid_gate_conditions_returns_context(self):
        """Cas nominal : liste valide → contexte retourné correctement."""
        from executions.gate_context import build_waiting_context

        exec_step = self._make_exec_step()
        gate_conditions = [
            {"type": "approval"},
            {"type": "timer"},
        ]

        with patch("executions.gate_context.get_correlation_id", return_value="corr-123"):
            ctx = build_waiting_context(exec_step, gate_conditions)

        assert "waiting_since" in ctx
        assert ctx["gate_conditions"] == gate_conditions
        assert len(ctx["gate_status"]) == 2
        assert ctx["gate_status"][0]["type"] == "approval"
        assert ctx["gate_status"][0]["satisfied"] is False

    def test_invalid_gate_conditions_type_raises_value_error(self):
        """Lignes 29-34 : gate_conditions non-liste → logger.error + ValueError."""
        from executions.gate_context import build_waiting_context

        exec_step = self._make_exec_step()

        with patch("executions.gate_context.get_correlation_id", return_value="corr-456"), \
             patch("executions.gate_context.logger") as mock_logger:
            with pytest.raises(ValueError, match="gate_conditions must be a list"):
                build_waiting_context(exec_step, "not_a_list")

            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args
            assert call_kwargs[0][0] == "build_waiting_context_invalid_type"

    def test_invalid_gate_conditions_dict_raises_value_error(self):
        """Variante : dict passé à la place d'une liste → ValueError."""
        from executions.gate_context import build_waiting_context

        exec_step = self._make_exec_step()

        with patch("executions.gate_context.get_correlation_id", return_value="corr-789"):
            with pytest.raises(ValueError):
                build_waiting_context(exec_step, {"type": "approval"})

    def test_invalid_gate_conditions_none_raises_value_error(self):
        """Variante : None passé → ValueError."""
        from executions.gate_context import build_waiting_context

        exec_step = self._make_exec_step()

        with patch("executions.gate_context.get_correlation_id", return_value="corr-000"):
            with pytest.raises(ValueError):
                build_waiting_context(exec_step, None)

    def test_exec_step_without_created_at_uses_now(self):
        """Branche exec_step.created_at falsy → timezone.now() utilisé."""
        from executions.gate_context import build_waiting_context

        exec_step = MagicMock()
        exec_step.id = 99
        exec_step.created_at = None

        with patch("executions.gate_context.get_correlation_id", return_value="corr-now"):
            ctx = build_waiting_context(exec_step, [{"type": "approval"}])

        assert "waiting_since" in ctx
        assert ctx["waiting_since"] is not None

    def test_empty_gate_conditions_list(self):
        """Liste vide : gate_status doit être vide."""
        from executions.gate_context import build_waiting_context

        exec_step = self._make_exec_step()

        with patch("executions.gate_context.get_correlation_id", return_value="corr-empty"):
            ctx = build_waiting_context(exec_step, [])

        assert ctx["gate_status"] == []
        assert ctx["gate_conditions"] == []
