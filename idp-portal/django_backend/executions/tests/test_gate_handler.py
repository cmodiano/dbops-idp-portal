"""
Tests unitaires pour GateHandler (story 57.7).

Gate steps are no-op in this runtime; handler returns skipped status.
"""
from unittest.mock import MagicMock

from executions.step_handlers.gate_handler import GateHandler


class TestGateHandler:
    """Tests de GateHandler.execute() (story 57.7)."""

    def setup_method(self):
        self.handler = GateHandler()

    def test_execute_returns_skipped_status(self):
        """GateHandler.execute returns dict with status skipped and outputs."""
        result = self.handler.execute(
            step_config={'step_type': 'gate', 'step_id': 'g1', 'name': 'Gate'},
            resolved_params={},
            execution=MagicMock(id=1),
            step={},
            correlation_id=None,
        )
        assert result['status'] == 'skipped'
        assert result['outputs'] == {}
        assert 'message' in result
        assert 'story 57.7' in result['message']
