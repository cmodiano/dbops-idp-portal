"""
Tests for Story 30.7 — Polling max retries, gate timeout, and cache documentation.

Covers:
- RACE-1: MAX_POLLING_RETRIES for all 5 polling tasks
- CELERY-3: asyncio.run() usage (implicit — tasks work correctly)
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
