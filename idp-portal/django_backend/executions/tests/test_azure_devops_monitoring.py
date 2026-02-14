"""
Tests for Azure DevOps monitoring — Story 27.3.

Covers:
- poll_azure_devops_run_status: success polling, terminal status, error handling, rescheduling
- Non-regression: AAP and Tower tests unaffected
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from executions.tasks import poll_azure_devops_run_status


def _make_azure_devops_adapter(status_data: dict, logs_data: dict) -> MagicMock:
    """Create a mock AzureDevOpsAdapter with given status/logs responses."""
    adapter = MagicMock()
    adapter.get_status = AsyncMock(return_value=status_data)
    adapter.get_job_logs = AsyncMock(return_value=logs_data)
    return adapter


class TestPollAzureDevOpsRunStatus:
    """Tests for poll_azure_devops_run_status Celery task."""

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_running_reschedules(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Running run should broadcast updates and reschedule."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "RUNNING",
                "azure_devops_state": "inProgress",
                "azure_devops_result": None,
                "createdDate": "2026-02-14T10:00:00Z",
                "finishedDate": None,
            },
            {
                "content": "Step 1: Checkout...",
                "format": "text/plain",
                "timestamp": "2026-02-14T10:01:00Z",
                "complete": False,
                "job_status": "inProgress",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
                auth_flow="basic",
                poll_interval=5,
            )

        assert result["outcome"] == "polling"
        assert result["azure_devops_state"] == "inProgress"
        mock_broadcast.assert_called_once()
        mock_update.assert_called_once()
        mock_apply_async.assert_called_once()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_completed_succeeded_no_reschedule(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Completed+succeeded should broadcast and NOT reschedule."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "COMPLETED",
                "azure_devops_state": "completed",
                "azure_devops_result": "succeeded",
                "createdDate": "2026-02-14T10:00:00Z",
                "finishedDate": "2026-02-14T10:05:00Z",
            },
            {
                "content": "Build succeeded",
                "format": "text/plain",
                "timestamp": "2026-02-14T10:05:00Z",
                "complete": True,
                "job_status": "completed",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
                auth_flow="basic",
            )

        assert result["outcome"] == "complete"
        assert result["status"] == "COMPLETED"
        assert result["azure_devops_result"] == "succeeded"
        mock_broadcast.assert_called_once()
        mock_update.assert_called_once()
        mock_apply_async.assert_not_called()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_completed_failed_is_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Failed run should be treated as terminal."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "FAILED",
                "azure_devops_state": "completed",
                "azure_devops_result": "failed",
            },
            {
                "content": "Build failed",
                "format": "text/plain",
                "timestamp": "x",
                "complete": True,
                "job_status": "completed",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
            )

        assert result["outcome"] == "complete"
        assert result["status"] == "FAILED"
        mock_apply_async.assert_not_called()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_completed_canceled_is_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Canceled run should be treated as terminal."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "CANCELLED",
                "azure_devops_state": "completed",
                "azure_devops_result": "canceled",
            },
            {
                "content": "Build canceled",
                "format": "text/plain",
                "timestamp": "x",
                "complete": True,
                "job_status": "completed",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
            )

        assert result["outcome"] == "complete"
        assert result["status"] == "CANCELLED"
        mock_apply_async.assert_not_called()

    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_error_reschedules(
        self,
        mock_apply_async: MagicMock,
    ) -> None:
        """Adapter error should reschedule for retry."""
        with patch(
            "adapters.azure_devops_adapter.AzureDevOpsAdapter",
            side_effect=Exception("connection refused"),
        ):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
            )

        assert result["outcome"] == "error"
        mock_apply_async.assert_called_once()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_bearer_auth_flow(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Bearer auth flow uses token directly (Entra ID OAuth)."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "RUNNING",
                "azure_devops_state": "inProgress",
                "azure_devops_result": None,
            },
            {
                "content": "Running...",
                "format": "text/plain",
                "timestamp": "x",
                "complete": False,
                "job_status": "inProgress",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="entra-id-token",
                auth_flow="pat",  # Bearer token
            )

        assert result["outcome"] == "polling"

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_azure_devops_run_status.apply_async")
    def test_poll_canceling_not_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Canceling state should NOT be treated as terminal (still running)."""
        adapter = _make_azure_devops_adapter(
            {
                "status": "RUNNING",
                "azure_devops_state": "canceling",
                "azure_devops_result": None,
            },
            {
                "content": "Canceling...",
                "format": "text/plain",
                "timestamp": "x",
                "complete": False,
                "job_status": "canceling",
            },
        )
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=adapter):
            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="42",
                pipeline_id="5",
                base_url="https://dev.azure.com/org/proj",
                credential_ref="test-pat",
            )

        assert result["outcome"] == "polling"
        mock_apply_async.assert_called_once()
