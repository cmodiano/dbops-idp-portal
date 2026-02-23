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
# Test 5 — Shim backward-compat : poll_aap_job_status délègue
# ---------------------------------------------------------------------------


class TestPollAapShimDelegates:
    """AC3: Le shim poll_aap_job_status délègue à poll_platform_job_status."""

    @patch("executions.tasks.polling.poll_platform_job_status")
    def test_aap_shim_delegates_with_correct_platform_type(
        self, mock_generic: MagicMock
    ) -> None:
        """poll_aap_job_status transmet platform_type='aap' et les kwargs traduits.

        Patch sur executions.tasks.polling.poll_platform_job_status car le shim
        appelle la fonction par référence locale dans ce module.
        """
        from executions.tasks import poll_aap_job_status

        mock_generic.return_value = {"outcome": "complete", "status": "COMPLETED"}

        poll_aap_job_status(
            execution_id=10,
            platform_job_id="job-shim-1",
            resource_type="workflow_job",
            base_url="https://aap.example.com",
            credential_ref="token123",
            retry_count=0,
            ssl_verify=False,
        )

        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args[1]
        assert call_kwargs["platform_type"] == "aap"
        assert call_kwargs["adapter_kwargs"]["ssl_verify"] is False
        assert call_kwargs["poll_kwargs"]["resource_type"] == "workflow_job"


# ---------------------------------------------------------------------------
# Test 6 — Shims GitHub Actions et Terraform Cloud (AC3, M3 fix)
# ---------------------------------------------------------------------------


class TestPollGitHubActionsShimDelegates:
    """AC3: Le shim poll_github_actions_run_status délègue avec owner/repo dans adapter_kwargs."""

    @patch("executions.tasks.polling.poll_platform_job_status")
    def test_github_shim_delegates_with_owner_repo(
        self, mock_generic: MagicMock
    ) -> None:
        """poll_github_actions_run_status transmet owner/repo dans adapter_kwargs."""
        from executions.tasks import poll_github_actions_run_status

        mock_generic.return_value = {"outcome": "polling", "status": "RUNNING"}

        poll_github_actions_run_status(
            execution_id=20,
            platform_job_id="run-gh-1",
            owner="my-org",
            repo="my-repo",
            base_url="https://api.github.com",
            credential_ref="ghp_token",
            retry_count=0,
        )

        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args[1]
        assert call_kwargs["platform_type"] == "github_actions"
        assert call_kwargs["auth_flow"] == "token"
        assert call_kwargs["adapter_kwargs"]["owner"] == "my-org"
        assert call_kwargs["adapter_kwargs"]["repo"] == "my-repo"
        assert call_kwargs["poll_kwargs"] == {}


class TestPollTerraformCloudShimDelegates:
    """AC3: Le shim poll_terraform_cloud_run_status délègue avec organization dans adapter_kwargs."""

    @patch("executions.tasks.polling.poll_platform_job_status")
    def test_terraform_shim_delegates_with_organization(
        self, mock_generic: MagicMock
    ) -> None:
        """poll_terraform_cloud_run_status transmet organization dans adapter_kwargs."""
        from executions.tasks import poll_terraform_cloud_run_status

        mock_generic.return_value = {"outcome": "complete", "status": "COMPLETED"}

        poll_terraform_cloud_run_status(
            execution_id=30,
            platform_job_id="run-tf-1",
            organization="my-org",
            base_url="https://app.terraform.io",
            credential_ref="tf_token",
            retry_count=2,
        )

        mock_generic.assert_called_once()
        call_kwargs = mock_generic.call_args[1]
        assert call_kwargs["platform_type"] == "terraform_cloud"
        assert call_kwargs["auth_flow"] == "token"
        assert call_kwargs["adapter_kwargs"]["organization"] == "my-org"
        assert call_kwargs["poll_kwargs"] == {}
        assert call_kwargs["retry_count"] == 2
