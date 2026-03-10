"""
Tests for Story 34.5 — Poller générique unifié (SOLID-BE-3).

Couvre poll_platform_job_status (AC1, AC2, AC4, AC5) :
- AC1: Aucun if/elif sur platform_type dans la logique de polling
- AC2: is_terminal = logs_data.get("complete", False)
- AC5: Au moins 3 tests pour poll_platform_job_status
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock


from executions.tasks import (
    MAX_POLLING_RETRIES,
    poll_platform_job_status,
    _forward_platform_logs_to_splunk,
)


# ---------------------------------------------------------------------------
# Test 1 — Terminal : adapter retourne complete=True
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusTerminal:
    """AC2: is_terminal basé sur logs_data['complete'], pas sur platform-specific fields."""

    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-term")
    def test_terminal_when_complete_true(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ) -> None:
        """AC2: platform_type='aap', logs_data['complete']=True → outcome='complete'."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "COMPLETED"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"complete": True, "content": "Job done."}
        )

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=1,
                    platform_job_id="job-term-1",
                    platform_type="aap",
                    poll_kwargs={"resource_type": "job_template"},
                )

        assert result["outcome"] == "complete"
        assert result["status"] == "COMPLETED"
        mock_broadcast.assert_called_once()
        mock_update.assert_called_once()

    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-term2")
    def test_terminal_platform_type_agnostic(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ) -> None:
        """AC1: Même logique pour platform_type='tower' — pas de if/elif."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "COMPLETED"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"complete": True, "content": ""}
        )

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=2,
                    platform_job_id="job-tower-1",
                    platform_type="tower",
                    poll_kwargs={"resource_type": "workflow_job"},
                )

        assert result["outcome"] == "complete"


# ---------------------------------------------------------------------------
# Test 2 — Non-terminal : adapter retourne complete=False
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusNonTerminal:
    """AC2: complete=False → reschedule via poll_platform_job_status.apply_async."""

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-poll")
    def test_reschedule_when_not_complete(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
        mock_apply: MagicMock,
    ) -> None:
        """Non-terminal : poll_platform_job_status.apply_async appelé avec retry_count=0."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"complete": False, "content": "Running..."}
        )

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=3,
                    platform_job_id="job-poll-1",
                    platform_type="aap",
                    retry_count=5,
                )

        assert result["outcome"] == "polling"
        mock_apply.assert_called_once()
        # Reschedule via poll_platform_job_status.apply_async avec retry_count=0
        reschedule_kwargs = mock_apply.call_args[1]["kwargs"]
        assert reschedule_kwargs["retry_count"] == 0
        # platform_type transmis en args positionnel
        reschedule_args = mock_apply.call_args[1]["args"]
        assert reschedule_args[2] == "aap"


# ---------------------------------------------------------------------------
# Test 3 — Épuisement : exception + retry_count >= MAX_POLLING_RETRIES
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusExhaustion:
    """AC5: adapter lève Exception, retry_count=MAX → exhausted + _mark_exhausted appelé."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-exhaust")
    def test_exhausted_when_max_retries_reached(
        self,
        mock_corr: MagicMock,
        mock_exhausted: MagicMock,
    ) -> None:
        """retry_count >= MAX_POLLING_RETRIES + exception → outcome='exhausted'."""
        with patch(
            "adapters.get_platform_adapter",
            side_effect=Exception("adapter connection error"),
        ):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=4,
                    platform_job_id="job-exhaust-1",
                    platform_type="aap",
                    retry_count=MAX_POLLING_RETRIES,
                )

        assert result["outcome"] == "exhausted"
        assert result["retry_count"] == MAX_POLLING_RETRIES
        mock_exhausted.assert_called_once_with(
            execution_id=4,
            platform_job_id="job-exhaust-1",
            retry_count=MAX_POLLING_RETRIES,
            error="adapter connection error",
            correlation_id="test-corr-exhaust",
        )

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-retry")
    def test_reschedule_incremented_retry_on_error(
        self,
        mock_corr: MagicMock,
        mock_apply: MagicMock,
    ) -> None:
        """Erreur + retry_count < MAX → reschedule avec retry_count+1."""
        with patch(
            "adapters.get_platform_adapter",
            side_effect=Exception("timeout"),
        ):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=5,
                    platform_job_id="job-retry-1",
                    platform_type="tower",
                    retry_count=3,
                )

        assert result["outcome"] == "error"
        assert result["retry_count"] == 3
        mock_apply.assert_called_once()
        reschedule_kwargs = mock_apply.call_args[1]["kwargs"]
        assert reschedule_kwargs["retry_count"] == 4


# ---------------------------------------------------------------------------
# Test 4 — Export et nom Celery
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusExport:
    """AC6: poll_platform_job_status exporté et nom Celery correct."""

    def test_task_name(self) -> None:
        """AC6: nom Celery = 'executions.tasks.poll_platform_job_status'."""
        assert poll_platform_job_status.name == "executions.tasks.poll_platform_job_status"

    def test_task_importable_from_executions_tasks(self) -> None:
        """AC6: importable depuis executions.tasks."""
        from executions.tasks import poll_platform_job_status as task
        assert task is not None
        assert task.name == "executions.tasks.poll_platform_job_status"

    def test_task_in_all(self) -> None:
        """AC6: 'poll_platform_job_status' dans __all__."""
        import executions.tasks as tasks_pkg
        assert "poll_platform_job_status" in tasks_pkg.__all__



# ---------------------------------------------------------------------------
# Test 7 — Splunk platform log forwarding
# ---------------------------------------------------------------------------


class TestForwardPlatformLogsToSplunk:
    """Platform logs are forwarded to Splunk at terminal state (best-effort)."""

    @patch("integrations.models.Integration.objects")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer tok123"})
    @patch("services.get_service_client")
    @patch("asgiref.sync.async_to_sync")
    def test_terminal_calls_splunk(
        self,
        mock_async_to_sync: MagicMock,
        mock_get_client: MagicMock,
        mock_build_auth: MagicMock,
        mock_integration_qs: MagicMock,
    ) -> None:
        """When a splunk integration exists, send_event is called with correct payload."""
        mock_integration = MagicMock(base_url="https://splunk.example.com")
        mock_integration_qs.filter.return_value.first.return_value = mock_integration

        mock_send_event = MagicMock()
        mock_async_to_sync.return_value = mock_send_event

        _forward_platform_logs_to_splunk(
            execution_id=100,
            platform_job_id="job-splunk-1",
            platform_type="aap",
            logs_content="Job output here",
            correlation_id="corr-splunk-1",
        )

        # Verify integration query
        mock_integration_qs.filter.assert_called_once_with(type="splunk", status="valid")

        # Verify auth header Bearer→Splunk transformation
        mock_build_auth.assert_called_once_with(mock_integration, correlation_id="corr-splunk-1")
        mock_get_client.assert_called_once_with(
            "splunk",
            base_url="https://splunk.example.com",
            auth_headers={"Authorization": "Splunk tok123"},
        )

        # Verify send_event called with correct payload
        mock_send_event.assert_called_once()
        call_kwargs = mock_send_event.call_args[1]
        assert call_kwargs["event"]["event"] == "platform_log"
        assert call_kwargs["event"]["execution_id"] == 100
        assert call_kwargs["event"]["platform_job_id"] == "job-splunk-1"
        assert call_kwargs["event"]["platform_type"] == "aap"
        assert call_kwargs["event"]["content"] == "Job output here"
        assert call_kwargs["event"]["correlation_id"] == "corr-splunk-1"
        assert call_kwargs["sourcetype"] == "idp:platform_log"
        assert call_kwargs["correlation_id"] == "corr-splunk-1"

    @patch("integrations.models.Integration.objects")
    def test_no_splunk_integration_skips_gracefully(
        self,
        mock_integration_qs: MagicMock,
    ) -> None:
        """When no splunk integration configured, function returns silently."""
        mock_integration_qs.filter.return_value.first.return_value = None

        # Should not raise
        _forward_platform_logs_to_splunk(
            execution_id=101,
            platform_job_id="job-no-splunk",
            platform_type="aap",
            logs_content="Some logs",
            correlation_id="corr-no-splunk",
        )

    @patch("integrations.models.Integration.objects")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer x"})
    @patch("services.get_service_client")
    @patch("asgiref.sync.async_to_sync")
    def test_splunk_error_is_best_effort(
        self,
        mock_async_to_sync: MagicMock,
        mock_get_client: MagicMock,
        mock_build_auth: MagicMock,
        mock_integration_qs: MagicMock,
    ) -> None:
        """When send_event raises, the error is swallowed (best-effort)."""
        mock_integration = MagicMock(base_url="https://splunk.example.com")
        mock_integration_qs.filter.return_value.first.return_value = mock_integration

        mock_async_to_sync.return_value = MagicMock(side_effect=ConnectionError("Splunk down"))

        # Should not raise
        _forward_platform_logs_to_splunk(
            execution_id=102,
            platform_job_id="job-err",
            platform_type="github_actions",
            logs_content="Some logs",
            correlation_id="corr-err",
        )

    def test_empty_logs_skips(self) -> None:
        """When logs_content is empty, no DB query or Splunk call is made."""
        # If it tried to query Integration, it would fail (no Django DB configured in unit test)
        _forward_platform_logs_to_splunk(
            execution_id=103,
            platform_job_id="job-empty",
            platform_type="aap",
            logs_content="",
            correlation_id="corr-empty",
        )


class TestPollTerminalCallsSplunk:
    """Integration: poll_platform_job_status calls _forward_platform_logs_to_splunk at terminal."""

    @patch("executions.tasks._forward_platform_logs_to_splunk")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-splunk")
    def test_terminal_triggers_splunk_forward(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
        mock_forward: MagicMock,
    ) -> None:
        """At terminal state, _forward_platform_logs_to_splunk is called."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "COMPLETED"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"complete": True, "content": "Final output"}
        )

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=200,
                    platform_job_id="job-fwd-1",
                    platform_type="aap",
                )

        assert result["outcome"] == "complete"
        mock_forward.assert_called_once_with(
            execution_id=200,
            platform_job_id="job-fwd-1",
            platform_type="aap",
            logs_content="Final output",
            correlation_id="test-corr-splunk",
        )

    @patch("executions.tasks._forward_platform_logs_to_splunk")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr-nosplunk")
    def test_non_terminal_skips_splunk(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
        mock_apply: MagicMock,
        mock_forward: MagicMock,
    ) -> None:
        """Non-terminal state does NOT call _forward_platform_logs_to_splunk."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"complete": False, "content": "Still running..."}
        )

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers_from_credentials", return_value={}):
                result = poll_platform_job_status(
                    execution_id=201,
                    platform_job_id="job-fwd-2",
                    platform_type="aap",
                )

        assert result["outcome"] == "polling"
        mock_forward.assert_not_called()
