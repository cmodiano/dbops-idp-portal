"""
Tests de couverture pour executions/builders/response_builder.py (Story 55).
Couvre la ligne 30 : ajout de error_message quand status == INTEGRATION_ERROR.
"""
from unittest.mock import MagicMock
from datetime import datetime, timezone


class TestExecutionResponseBuilder:
    """Tests pour ExecutionResponseBuilder.build."""

    def _make_execution(self, status, error_message=None):
        exec_mock = MagicMock()
        exec_mock.id = 42
        exec_mock.status = status
        exec_mock.error_message = error_message
        exec_mock.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        return exec_mock

    def test_build_normal_status_no_error_message(self):
        """Statut standard : pas de error_message dans la réponse."""
        from executions.builders.response_builder import ExecutionResponseBuilder
        from executions.models import ExecutionStatus

        execution = self._make_execution(ExecutionStatus.RUNNING)
        action = MagicMock()

        response = ExecutionResponseBuilder.build(execution, action)
        assert response.status_code == 201
        assert "error_message" not in response.data["data"]
        assert response.data["data"]["execution_id"] == 42
        assert response.data["data"]["status"] == ExecutionStatus.RUNNING

    def test_build_integration_error_includes_error_message(self):
        """Ligne 30 : statut INTEGRATION_ERROR → error_message présent dans la réponse."""
        from executions.builders.response_builder import ExecutionResponseBuilder
        from executions.models import ExecutionStatus

        execution = self._make_execution(
            ExecutionStatus.INTEGRATION_ERROR,
            error_message="Adapter timeout"
        )
        action = MagicMock()

        response = ExecutionResponseBuilder.build(execution, action)
        assert response.status_code == 201
        assert response.data["data"]["error_message"] == "Adapter timeout"

    def test_build_response_contains_created_at(self):
        """Vérifie que created_at est présent et formaté."""
        from executions.builders.response_builder import ExecutionResponseBuilder
        from executions.models import ExecutionStatus

        execution = self._make_execution(ExecutionStatus.RUNNING)
        action = MagicMock()

        response = ExecutionResponseBuilder.build(execution, action)
        assert "created_at" in response.data["data"]
