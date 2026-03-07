"""
Tests for Story 30.7 — Polling max retries, gate timeout, and cache documentation.

Covers:
- RACE-1: MAX_POLLING_RETRIES for all 5 polling tasks
- CELERY-3: async_to_sync() usage (implicit — tasks work correctly)
- CELERY-4: Gate timeout workflow continuation
- CELERY-5: Gate timeout SKIPPED with error_message
- RACE-2: select_for_update() in catalog services
- RACE-3: Cache TTL validation
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from executions.tasks import (
    MAX_POLLING_RETRIES,
    poll_aap_job_status,
    poll_tower_job_status,
    poll_azure_devops_run_status,
    poll_github_actions_run_status,
    poll_terraform_cloud_run_status,
    _mark_execution_polling_exhausted,
    _handle_gate_timeout,
)
from executions.models import ExecutionStatus, ExecutionStepStatus


# ---------------------------------------------------------------------------
# MAX_POLLING_RETRIES constant
# ---------------------------------------------------------------------------


class TestMaxPollingRetries:
    """Verify MAX_POLLING_RETRIES constant is defined and reasonable."""

    def test_max_polling_retries_defined(self) -> None:
        assert MAX_POLLING_RETRIES == 20

    def test_max_polling_retries_positive(self) -> None:
        assert MAX_POLLING_RETRIES > 0


# ---------------------------------------------------------------------------
# poll_aap_job_status — exhaustion scenario
# ---------------------------------------------------------------------------


class TestPollAAPExhaustion:
    """Test poll_aap_job_status stops after MAX_POLLING_RETRIES."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_exhaustion_on_adapter_error(
        self, mock_corr: MagicMock, mock_exhausted: MagicMock
    ) -> None:
        """When retry_count >= MAX_POLLING_RETRIES and adapter raises, mark exhausted."""
        with patch("adapters.aap_adapter.AAPAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("connection refused")

            result = poll_aap_job_status(
                execution_id=1,
                platform_job_id="job-123",
                retry_count=MAX_POLLING_RETRIES,
            )

        assert result["outcome"] == "exhausted"
        assert result["retry_count"] == MAX_POLLING_RETRIES
        mock_exhausted.assert_called_once()

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_reschedule_with_incremented_retry(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        """When retry_count < MAX, re-schedule with retry_count+1.

        Story 34.5: Le shim poll_aap_job_status délègue à poll_platform_job_status,
        qui est responsable du re-schedule via poll_platform_job_status.apply_async.
        """
        with patch("adapters.aap_adapter.AAPAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("timeout")

            result = poll_aap_job_status(
                execution_id=1,
                platform_job_id="job-123",
                retry_count=5,
            )

        assert result["outcome"] == "error"
        assert result["retry_count"] == 5
        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args[1]["kwargs"]
        assert kwargs["retry_count"] == 6

    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_successful_poll_resets_retry_count(
        self,
        mock_corr: MagicMock,
        mock_apply: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ) -> None:
        """After a successful poll (non-terminal), retry_count resets to 0.

        Story 34.5: Le re-schedule se fait via poll_platform_job_status.apply_async.
        """
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING", "aap_status": "running"})
        mock_adapter.get_job_logs = AsyncMock(return_value={"content": "log line", "complete": False})

        with patch("adapters.aap_adapter.AAPAdapter", return_value=mock_adapter):
            result = poll_aap_job_status(
                execution_id=1,
                platform_job_id="job-123",
                retry_count=10,
            )

        assert result["outcome"] == "polling"
        kwargs = mock_apply.call_args[1]["kwargs"]
        assert kwargs["retry_count"] == 0


# ---------------------------------------------------------------------------
# poll_tower_job_status — exhaustion scenario
# ---------------------------------------------------------------------------


class TestPollTowerExhaustion:
    """Test poll_tower_job_status stops after MAX_POLLING_RETRIES."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_exhaustion_on_adapter_error(
        self, mock_corr: MagicMock, mock_exhausted: MagicMock
    ) -> None:
        with patch("adapters.tower_adapter.TowerAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("connection refused")

            result = poll_tower_job_status(
                execution_id=1,
                platform_job_id="job-456",
                retry_count=MAX_POLLING_RETRIES,
            )

        assert result["outcome"] == "exhausted"
        mock_exhausted.assert_called_once()


# ---------------------------------------------------------------------------
# poll_azure_devops_run_status — exhaustion scenario
# ---------------------------------------------------------------------------


class TestPollAzureDevOpsExhaustion:
    """Test poll_azure_devops_run_status stops after MAX_POLLING_RETRIES."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_exhaustion_on_adapter_error(
        self, mock_corr: MagicMock, mock_exhausted: MagicMock
    ) -> None:
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("connection refused")

            result = poll_azure_devops_run_status(
                execution_id=1,
                platform_job_id="run-789",
                retry_count=MAX_POLLING_RETRIES,
            )

        assert result["outcome"] == "exhausted"
        mock_exhausted.assert_called_once()


# ---------------------------------------------------------------------------
# poll_github_actions_run_status — exhaustion scenario
# ---------------------------------------------------------------------------


class TestPollGitHubActionsExhaustion:
    """Test poll_github_actions_run_status stops after MAX_POLLING_RETRIES."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_exhaustion_on_adapter_error(
        self, mock_corr: MagicMock, mock_exhausted: MagicMock
    ) -> None:
        with patch("adapters.github_actions_adapter.GitHubActionsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("connection refused")

            result = poll_github_actions_run_status(
                execution_id=1,
                platform_job_id="run-101",
                retry_count=MAX_POLLING_RETRIES,
            )

        assert result["outcome"] == "exhausted"
        mock_exhausted.assert_called_once()


# ---------------------------------------------------------------------------
# poll_terraform_cloud_run_status — exhaustion scenario
# ---------------------------------------------------------------------------


class TestPollTerraformCloudExhaustion:
    """Test poll_terraform_cloud_run_status stops after MAX_POLLING_RETRIES."""

    @patch("executions.tasks._mark_execution_polling_exhausted")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_exhaustion_on_adapter_error(
        self, mock_corr: MagicMock, mock_exhausted: MagicMock
    ) -> None:
        with patch("adapters.terraform_cloud_adapter.TerraformCloudAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("connection refused")
            result = poll_terraform_cloud_run_status(
                execution_id=1,
                platform_job_id="run-202",
                retry_count=MAX_POLLING_RETRIES,
            )

        assert result["outcome"] == "exhausted"
        mock_exhausted.assert_called_once()


# ---------------------------------------------------------------------------
# _mark_execution_polling_exhausted
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMarkExecutionPollingExhausted:
    """Test the helper that marks execution as FAILED on exhaustion."""

    def test_marks_execution_failed(self) -> None:
        from tests.factories import ExecutionFactory, ExecutionStepFactory

        execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory(
            execution=execution,
            platform_job_id="job-exhaust-1",
            status=ExecutionStepStatus.RUNNING,
        )

        with patch("executions.tasks.AuditService.create_entry"):
            _mark_execution_polling_exhausted(
                execution_id=execution.id,
                platform_job_id="job-exhaust-1",
                retry_count=20,
                error="timeout",
            )

        execution.refresh_from_db()
        step.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED
        assert step.status == ExecutionStepStatus.FAILED
        assert "Polling exhausted" in step.error_message

    def test_does_not_overwrite_terminal_status(self) -> None:
        from tests.factories import ExecutionFactory

        execution = ExecutionFactory(status=ExecutionStatus.COMPLETED)

        with patch("executions.tasks.AuditService.create_entry"):
            _mark_execution_polling_exhausted(
                execution_id=execution.id,
                platform_job_id="job-exhaust-2",
                retry_count=20,
                error="timeout",
            )

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

    def test_handles_nonexistent_execution(self) -> None:
        """Should not raise on missing execution."""
        _mark_execution_polling_exhausted(
            execution_id=999999,
            platform_job_id="job-missing",
            retry_count=20,
            error="timeout",
        )


# ---------------------------------------------------------------------------
# _handle_gate_timeout — CELERY-4 / CELERY-5
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHandleGateTimeout:
    """Test gate timeout handling — CELERY-4 and CELERY-5."""

    def test_skipped_step_gets_error_message(self) -> None:
        """CELERY-5: SKIPPED steps must have an explicit error_message."""
        from tests.factories import ExecutionFactory, ExecutionStepFactory

        execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_name="gate-step",
        )

        gate_status = {"action": "SKIPPED", "timeout_hours": 2}

        with patch("executions.tasks.AuditService.create_entry"):
            with patch("executions.tasks.retry_workflow_step.apply_async"):
                _handle_gate_timeout(step, gate_status, "test-corr")

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.SKIPPED
        assert step.error_message is not None
        assert "Gate timeout exceeded" in step.error_message

    def test_failed_step_marks_execution_failed(self) -> None:
        """CELERY-4: FAILED timeout marks execution as FAILED."""
        from tests.factories import ExecutionFactory, ExecutionStepFactory

        execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_name="gate-step",
        )

        gate_status = {"action": "FAILED", "timeout_hours": 4}

        with patch("executions.tasks.AuditService.create_entry"):
            _handle_gate_timeout(step, gate_status, "test-corr")

        step.refresh_from_db()
        execution.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert "Gate timeout exceeded" in step.error_message
        assert execution.status == ExecutionStatus.FAILED

    def test_skipped_triggers_next_step(self) -> None:
        """CELERY-4: SKIPPED timeout triggers next step execution."""
        from tests.factories import ExecutionFactory, ExecutionStepFactory, ActionFactory

        action = ActionFactory(
            execution_steps=[
                {"name": "gate-step", "step_id": "s1"},
                {"name": "next-step", "step_id": "s2"},
            ]
        )
        execution = ExecutionFactory(action=action, status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_name="gate-step",
        )

        gate_status = {"action": "SKIPPED", "timeout_hours": 1}

        with patch("executions.tasks.AuditService.create_entry"):
            with patch("executions.tasks.retry_workflow_step.apply_async") as mock_apply:
                _handle_gate_timeout(step, gate_status, "test-corr")

        mock_apply.assert_called_once()
        args = mock_apply.call_args[1]["args"]
        assert args[0] == execution.id
        assert args[1]["name"] == "next-step"


# ---------------------------------------------------------------------------
# select_for_update() — RACE-2 (catalog services)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCatalogSelectForUpdate:
    """Test that catalog service methods with select_for_update() work correctly."""

    def test_update_action_works_with_locking(self) -> None:
        """update_action() should acquire row lock and update successfully."""
        from catalog.services import CatalogService
        from tests.factories import ActionFactory, UserFactory

        action = ActionFactory()
        user = UserFactory()
        service = CatalogService()

        result = service.update_action(action.id, {"name": "Updated-30-7"}, user)
        assert result is not None
        assert result.name == "Updated-30-7"

    def test_update_status_works_with_locking(self) -> None:
        """update_status() should acquire row lock and transition correctly."""
        from catalog.services import CatalogService
        from catalog.models import ActionStatus
        from tests.factories import ActionFactory, UserFactory

        action = ActionFactory(status=ActionStatus.DRAFT)
        user = UserFactory()
        service = CatalogService()

        result = service.update_status(action.id, "publish", user)
        assert result is not None
        assert result.status == ActionStatus.PUBLISHED

    def test_delete_action_works_with_locking(self) -> None:
        """delete_action() should acquire row lock and delete successfully."""
        from catalog.services import CatalogService
        from catalog.models import Action
        from tests.factories import ActionFactory, UserFactory

        action = ActionFactory()
        user = UserFactory()
        service = CatalogService()

        result = service.delete_action(action.id, user)
        assert result is True
        assert not Action.objects.filter(id=action.id).exists()

    def test_deactivate_action_works_with_locking(self) -> None:
        """deactivate_action() should acquire row lock and deactivate."""
        from catalog.services import CatalogService
        from catalog.models import ActionStatus
        from tests.factories import ActionFactory, UserFactory

        action = ActionFactory(status=ActionStatus.PUBLISHED)
        user = UserFactory()
        service = CatalogService()

        result = service.deactivate_action(action.id, user, "test reason")
        assert result is not None
        action.refresh_from_db()
        assert action.status == ActionStatus.DISABLED


# ---------------------------------------------------------------------------
# Cache TTL verification — RACE-3
# ---------------------------------------------------------------------------


class TestCacheTTL:
    """Verify caches have appropriate TTL settings."""

    def test_catalog_cache_ttl(self) -> None:
        from catalog.views import _catalog_cache
        assert _catalog_cache.ttl == 300  # 5 minutes

    def test_tags_cache_ttl(self) -> None:
        from catalog.views import _tags_cache
        assert _tags_cache.ttl == 300

    def test_environments_cache_ttl(self) -> None:
        from inventory.services import _environments_cache
        assert _environments_cache.ttl == 300  # 5 minutes (aligned with catalog cache)


# ---------------------------------------------------------------------------
# _mark_execution_polling_exhausted — exception branch (line 106-107)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMarkExecutionPollingExhaustedExceptionBranch:
    """Test the generic exception handler in _mark_execution_polling_exhausted."""

    def test_generic_exception_is_swallowed(self) -> None:
        """Generic exceptions inside the try block must not propagate (resilience)."""
        from tests.factories import ExecutionFactory

        execution = ExecutionFactory(status="RUNNING")

        # AuditService.create_entry raising should be swallowed
        with patch("executions.tasks.AuditService.create_entry", side_effect=RuntimeError("db down")):
            # Must not raise
            _mark_execution_polling_exhausted(
                execution_id=execution.id,
                platform_job_id="job-exc-1",
                retry_count=20,
                error="timeout",
            )


# ---------------------------------------------------------------------------
# _broadcast_execution_update (lines 124-181)
# ---------------------------------------------------------------------------


class TestBroadcastExecutionUpdate:
    """Test _broadcast_execution_update broadcast helper."""

    def test_broadcasts_status_log_and_terminal_complete(self) -> None:
        """Sends status_update, log_update, and execution_complete when terminal COMPLETED."""
        from executions.tasks import _broadcast_execution_update

        mock_channel_layer = MagicMock()
        mock_group_send = MagicMock()

        with patch("channels.layers.get_channel_layer", return_value=mock_channel_layer):
            with patch("asgiref.sync.async_to_sync", return_value=mock_group_send):
                _broadcast_execution_update(
                    execution_id=1,
                    status_data={"status": "COMPLETED", "aap_status": "successful"},
                    logs_data={"content": "done", "complete": True},
                    is_terminal=True,
                    correlation_id="corr-1",
                )

        # Three group_send calls: status_update, log_update, execution_complete
        assert mock_group_send.call_count == 3

    def test_broadcasts_status_and_log_only_when_not_terminal(self) -> None:
        """Sends only status_update and log_update when not terminal."""
        from executions.tasks import _broadcast_execution_update

        mock_channel_layer = MagicMock()
        mock_group_send = MagicMock()

        with patch("channels.layers.get_channel_layer", return_value=mock_channel_layer):
            with patch("asgiref.sync.async_to_sync", return_value=mock_group_send):
                _broadcast_execution_update(
                    execution_id=2,
                    status_data={"status": "RUNNING"},
                    logs_data={"content": "running...", "complete": False},
                    is_terminal=False,
                )

        assert mock_group_send.call_count == 2

    def test_broadcasts_execution_failed_event_on_failure(self) -> None:
        """When terminal and status is FAILED, sends execution_failed event type."""
        from executions.tasks import _broadcast_execution_update

        sent_messages = []

        def fake_async_to_sync(fn):
            def caller(group, msg):
                sent_messages.append(msg)
            return caller

        mock_channel_layer = MagicMock()

        with patch("channels.layers.get_channel_layer", return_value=mock_channel_layer):
            with patch("asgiref.sync.async_to_sync", side_effect=fake_async_to_sync):
                _broadcast_execution_update(
                    execution_id=3,
                    status_data={"status": "FAILED"},
                    logs_data={"content": "", "complete": True},
                    is_terminal=True,
                )

        types_sent = [m["type"] for m in sent_messages]
        assert "execution_failed" in types_sent

    def test_channel_layer_none_returns_early(self) -> None:
        """When channel_layer is None, function returns without sending."""
        from executions.tasks import _broadcast_execution_update

        with patch("channels.layers.get_channel_layer", return_value=None):
            # Should not raise and should do nothing
            _broadcast_execution_update(
                execution_id=4,
                status_data={"status": "RUNNING"},
                logs_data={"content": "", "complete": False},
                is_terminal=False,
            )

    def test_import_error_is_swallowed(self) -> None:
        """ImportError (no channels installed) must not propagate."""
        import builtins
        from executions.tasks import _broadcast_execution_update

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "channels.layers":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", fake_import):
            # Must not raise
            _broadcast_execution_update(
                execution_id=5,
                status_data={"status": "RUNNING"},
                logs_data={"content": "", "complete": False},
                is_terminal=False,
            )

    def test_generic_exception_is_swallowed(self) -> None:
        """Generic exception from channel layer must not propagate (non-critical path)."""
        from executions.tasks import _broadcast_execution_update

        mock_channel_layer = MagicMock()

        with patch("channels.layers.get_channel_layer", return_value=mock_channel_layer):
            with patch("asgiref.sync.async_to_sync", side_effect=RuntimeError("channel error")):
                # Must not raise
                _broadcast_execution_update(
                    execution_id=6,
                    status_data={"status": "RUNNING"},
                    logs_data={"content": "", "complete": False},
                    is_terminal=False,
                )


# ---------------------------------------------------------------------------
# _update_execution_from_poll (lines 199-241)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateExecutionFromPoll:
    """Test _update_execution_from_poll DB update helper."""

    def test_updates_status_when_changed(self) -> None:
        """Status is updated when execution status differs from polled idp_status."""
        from executions.tasks import _update_execution_from_poll
        from executions.services import ExecutionService
        from tests.factories import ExecutionFactory, ExecutionStepFactory

        execution = ExecutionFactory(status="SUBMITTED")
        _step = ExecutionStepFactory(
            execution=execution,
            platform_job_id="job-upd-1",
            status="SUBMITTED",
        )

        with patch.object(ExecutionService, "update_status") as mock_update:
            _update_execution_from_poll(
                execution_id=execution.id,
                platform_job_id="job-upd-1",
                idp_status="RUNNING",
                logs_content="some logs",
            )

        mock_update.assert_called_once_with(execution.id, "RUNNING", str(execution.user_id))

    def test_skips_status_update_when_terminal(self) -> None:
        """No status update when execution is already in a terminal state."""
        from executions.tasks import _update_execution_from_poll
        from executions.services import ExecutionService
        from tests.factories import ExecutionFactory

        execution = ExecutionFactory(status="COMPLETED")

        with patch.object(ExecutionService, "update_status") as mock_update:
            _update_execution_from_poll(
                execution_id=execution.id,
                platform_job_id="job-upd-2",
                idp_status="RUNNING",
                logs_content="",
            )

        mock_update.assert_not_called()

    def test_handles_nonexistent_execution(self) -> None:
        """Should not raise on missing execution."""
        from executions.tasks import _update_execution_from_poll

        _update_execution_from_poll(
            execution_id=999999,
            platform_job_id="job-missing",
            idp_status="RUNNING",
            logs_content="",
        )

    def test_invalid_transition_is_logged_not_raised(self) -> None:
        """ValueError from update_status must be caught and logged, not re-raised."""
        from executions.tasks import _update_execution_from_poll
        from executions.services import ExecutionService
        from tests.factories import ExecutionFactory

        execution = ExecutionFactory(status="SUBMITTED")

        with patch.object(ExecutionService, "update_status", side_effect=ValueError("bad transition")):
            # Must not raise
            _update_execution_from_poll(
                execution_id=execution.id,
                platform_job_id="job-upd-3",
                idp_status="FAILED",
                logs_content="",
            )

    def test_generic_exception_is_swallowed(self) -> None:
        """Generic exceptions inside the try block are swallowed (resilience)."""
        from executions.tasks import _update_execution_from_poll
        from tests.factories import ExecutionFactory

        execution = ExecutionFactory(status="SUBMITTED")

        with patch("executions.models.Execution.objects") as mock_mgr:
            mock_mgr.get.side_effect = RuntimeError("unexpected db error")
            # Must not raise
            _update_execution_from_poll(
                execution_id=execution.id,
                platform_job_id="job-upd-4",
                idp_status="RUNNING",
                logs_content="",
            )


# ---------------------------------------------------------------------------
# _forward_platform_logs_to_splunk (lines 262-297)
# ---------------------------------------------------------------------------


class TestForwardPlatformLogsToSplunk:
    """Test _forward_platform_logs_to_splunk best-effort helper."""

    def test_skips_when_no_logs_content(self) -> None:
        """Returns immediately when logs_content is empty."""
        from executions.tasks import _forward_platform_logs_to_splunk

        with patch("services.splunk_utils.get_splunk_service") as mock_get:
            _forward_platform_logs_to_splunk(
                execution_id=1,
                platform_job_id="job-1",
                platform_type="aap",
                logs_content="",
            )
        mock_get.assert_not_called()

    def test_skips_when_splunk_not_configured(self) -> None:
        """Returns without sending when get_splunk_service returns None."""
        from executions.tasks import _forward_platform_logs_to_splunk

        with patch("services.splunk_utils.get_splunk_service", return_value=None):
            # Must not raise
            _forward_platform_logs_to_splunk(
                execution_id=1,
                platform_job_id="job-1",
                platform_type="aap",
                logs_content="some logs",
            )

    def test_sends_event_when_configured(self) -> None:
        """Calls send_event via async_to_sync when Splunk is configured."""
        from executions.tasks import _forward_platform_logs_to_splunk

        mock_splunk = MagicMock()
        mock_send = MagicMock()

        with patch("services.splunk_utils.get_splunk_service", return_value=mock_splunk):
            with patch("asgiref.sync.async_to_sync", return_value=mock_send):
                _forward_platform_logs_to_splunk(
                    execution_id=1,
                    platform_job_id="job-1",
                    platform_type="aap",
                    logs_content="step 1 complete",
                    correlation_id="corr-splunk",
                )

        mock_send.assert_called_once()

    def test_exception_is_swallowed(self) -> None:
        """Any exception during Splunk forwarding must not propagate."""
        from executions.tasks import _forward_platform_logs_to_splunk

        with patch("services.splunk_utils.get_splunk_service", side_effect=RuntimeError("splunk down")):
            # Must not raise
            _forward_platform_logs_to_splunk(
                execution_id=1,
                platform_job_id="job-1",
                platform_type="aap",
                logs_content="some logs",
            )


# ---------------------------------------------------------------------------
# poll_platform_job_status — terminal complete path (lines 452-467)
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusTerminal:
    """Test the terminal completion path of poll_platform_job_status."""

    @patch("executions.tasks._forward_platform_logs_to_splunk")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_returns_complete_outcome_when_terminal(
        self,
        mock_corr: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
        mock_splunk: MagicMock,
    ) -> None:
        """When logs_data.complete is True, returns outcome='complete' and calls Splunk forwarder."""
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "COMPLETED"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"content": "build done", "complete": True}
        )

        with patch("adapters.aap_adapter.AAPAdapter", return_value=mock_adapter):
            result = poll_platform_job_status(
                execution_id=10,
                platform_job_id="job-term-1",
                platform_type="aap",
            )

        assert result["outcome"] == "complete"
        assert result["status"] == "COMPLETED"
        mock_splunk.assert_called_once()

    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_returns_polling_outcome_when_not_terminal(
        self,
        mock_corr: MagicMock,
        mock_apply: MagicMock,
        mock_broadcast: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """When logs_data.complete is False, re-schedules and returns outcome='polling'."""
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING"})
        mock_adapter.get_job_logs = AsyncMock(
            return_value={"content": "building...", "complete": False}
        )

        with patch("adapters.aap_adapter.AAPAdapter", return_value=mock_adapter):
            result = poll_platform_job_status(
                execution_id=10,
                platform_job_id="job-poll-1",
                platform_type="aap",
            )

        assert result["outcome"] == "polling"
        mock_apply.assert_called_once()
