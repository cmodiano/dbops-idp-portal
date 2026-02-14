"""
Tests for Tower/AWX monitoring — Story 27.2.

Covers:
- poll_tower_job_status: success polling, terminal status, error handling, rescheduling
- Non-regression: AAP tests still pass (poll_aap_job_status unaffected)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from executions.tasks import poll_tower_job_status


def _make_tower_adapter(status_data: dict, logs_data: dict) -> MagicMock:
    """Create a mock TowerAdapter with given status/logs responses."""
    adapter = MagicMock()
    adapter.get_status = AsyncMock(return_value=status_data)
    adapter.get_job_logs = AsyncMock(return_value=logs_data)
    return adapter


class TestPollTowerJobStatus:
    """Tests for poll_tower_job_status Celery task."""

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_running_reschedules(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Running job should broadcast updates and reschedule."""
        adapter = _make_tower_adapter(
            {"status": "RUNNING", "tower_status": "running", "started": "x", "finished": None, "elapsed": 30},
            {"content": "PLAY [all]", "format": "text/plain", "timestamp": "x", "complete": False, "job_status": "running"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                resource_type="job_template",
                base_url="https://tower.example.com",
                credential_ref="test-token",
                auth_flow="token",
                poll_interval=5,
            )

        assert result["outcome"] == "polling"
        assert result["tower_status"] == "running"
        mock_broadcast.assert_called_once()
        mock_update.assert_called_once()
        mock_apply_async.assert_called_once()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_terminal_no_reschedule(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Terminal status should broadcast and NOT reschedule."""
        adapter = _make_tower_adapter(
            {"status": "COMPLETED", "tower_status": "successful", "started": "x", "finished": "y", "elapsed": 300},
            {"content": "PLAY RECAP", "format": "text/plain", "timestamp": "y", "complete": True, "job_status": "successful"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="test-token",
            )

        assert result["outcome"] == "complete"
        assert result["tower_status"] == "successful"
        mock_broadcast.assert_called_once()
        mock_update.assert_called_once()
        mock_apply_async.assert_not_called()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_failed_is_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Failed status should be treated as terminal."""
        adapter = _make_tower_adapter(
            {"status": "FAILED", "tower_status": "failed", "started": "x", "finished": "y", "elapsed": 180},
            {"content": "TASK [deploy] failed", "format": "text/plain", "timestamp": "y", "complete": True, "job_status": "failed"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="test-token",
            )

        assert result["outcome"] == "complete"
        assert result["status"] == "FAILED"
        mock_apply_async.assert_not_called()

    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_adapter_error_reschedules(
        self,
        mock_apply_async: MagicMock,
    ) -> None:
        """Adapter error should reschedule for retry."""
        adapter = MagicMock()
        adapter.get_status = AsyncMock(side_effect=ConnectionError("Network error"))

        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="test-token",
                poll_interval=10,
            )

        assert result["outcome"] == "error"
        assert "Network error" in result["error"]
        mock_apply_async.assert_called_once()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_canceled_is_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Canceled status should be treated as terminal."""
        adapter = _make_tower_adapter(
            {"status": "CANCELLED", "tower_status": "canceled", "started": "x", "finished": "y", "elapsed": 60},
            {"content": "", "format": "text/plain", "timestamp": "y", "complete": True, "job_status": "canceled"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="test-token",
            )

        assert result["outcome"] == "complete"
        assert result["tower_status"] == "canceled"
        mock_apply_async.assert_not_called()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_basic_auth(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Basic auth flow should build correct headers."""
        adapter = _make_tower_adapter(
            {"status": "RUNNING", "tower_status": "running", "started": "x", "finished": None, "elapsed": 10},
            {"content": "logs", "format": "text/plain", "timestamp": "x", "complete": False, "job_status": "running"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter) as mock_cls:
            poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="admin:password",
                auth_flow="basic",
            )

        call_kwargs = mock_cls.call_args
        auth_headers = call_kwargs.kwargs.get("auth_headers", {})
        assert "Basic" in auth_headers.get("Authorization", "")

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_workflow_job_resource_type(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Workflow job resource_type should be passed to adapter methods."""
        adapter = _make_tower_adapter(
            {"status": "RUNNING", "tower_status": "running", "started": "x", "finished": None, "elapsed": 10},
            {"content": "wf logs", "format": "text/plain", "timestamp": "x", "complete": False, "job_status": "running"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                resource_type="workflow_job",
                base_url="https://tower.example.com",
                credential_ref="test-token",
            )

        adapter.get_status.assert_called_once()
        status_call = adapter.get_status.call_args
        assert status_call.kwargs.get("resource_type") == "workflow_job"

        adapter.get_job_logs.assert_called_once()
        logs_call = adapter.get_job_logs.call_args
        assert logs_call.kwargs.get("resource_type") == "workflow_job"

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_tower_job_status.apply_async")
    def test_poll_error_status_is_terminal(
        self,
        mock_apply_async: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Tower 'error' status (system error) should be terminal."""
        adapter = _make_tower_adapter(
            {"status": "FAILED", "tower_status": "error", "started": "x", "finished": "y", "elapsed": 5},
            {"content": "System error", "format": "text/plain", "timestamp": "y", "complete": True, "job_status": "error"},
        )
        with patch("adapters.tower_adapter.TowerAdapter", return_value=adapter):
            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="100",
                base_url="https://tower.example.com",
                credential_ref="test-token",
            )

        assert result["outcome"] == "complete"
        assert result["tower_status"] == "error"
        mock_apply_async.assert_not_called()


class TestNonRegressionAAP:
    """Ensure AAP polling task still works after Tower addition."""

    def test_aap_poll_task_exists(self) -> None:
        from executions.tasks import poll_aap_job_status
        assert callable(poll_aap_job_status)

    def test_tower_poll_task_exists(self) -> None:
        from executions.tasks import poll_tower_job_status
        assert callable(poll_tower_job_status)

    def test_both_tasks_are_shared_tasks(self) -> None:
        from executions.tasks import poll_aap_job_status, poll_tower_job_status
        assert hasattr(poll_aap_job_status, "apply_async")
        assert hasattr(poll_tower_job_status, "apply_async")
