"""
Tests for Story 47.1 — Queues Celery dédiées par plateforme (bulkhead pattern).

Covers:
- AC1: PLATFORM_QUEUE_MAP défini dans polling.py avec tous les types de plateformes
- AC2/AC3: poll_platform_job_status.apply_async passe la bonne queue selon platform_type
- AC3: Un timeout sur une plateforme n'affecte pas les queues des autres (bulkhead)
- AC5: Non-régression (tests existants non impactés)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

from executions.tasks.polling import PLATFORM_QUEUE_MAP, poll_platform_job_status
from executions.tasks import (
    poll_aap_job_status,
    poll_tower_job_status,
    poll_azure_devops_run_status,
    poll_github_actions_run_status,
    poll_terraform_cloud_run_status,
)


# ---------------------------------------------------------------------------
# PLATFORM_QUEUE_MAP — structure et couverture des plateformes (AC1)
# ---------------------------------------------------------------------------


class TestPlatformQueueMap:
    """Vérifie que PLATFORM_QUEUE_MAP couvre toutes les plateformes attendues."""

    def test_map_defined(self) -> None:
        assert isinstance(PLATFORM_QUEUE_MAP, dict)

    def test_aap_queue(self) -> None:
        assert PLATFORM_QUEUE_MAP['aap'] == 'aap'

    def test_tower_uses_aap_queue(self) -> None:
        """Tower est une variante d'AAP — même queue acceptable."""
        assert PLATFORM_QUEUE_MAP['tower'] == 'aap'

    def test_azure_devops_queue(self) -> None:
        assert PLATFORM_QUEUE_MAP['azure_devops'] == 'azure'

    def test_github_actions_queue(self) -> None:
        assert PLATFORM_QUEUE_MAP['github_actions'] == 'github'

    def test_terraform_cloud_queue(self) -> None:
        assert PLATFORM_QUEUE_MAP['terraform_cloud'] == 'terraform'

    def test_all_expected_platforms_present(self) -> None:
        expected = {'aap', 'tower', 'azure_devops', 'github_actions', 'terraform_cloud'}
        assert expected.issubset(set(PLATFORM_QUEUE_MAP.keys()))

    def test_unknown_platform_defaults_to_default(self) -> None:
        """get() avec plateforme inconnue → 'default' (pas d'exception). AC3."""
        assert PLATFORM_QUEUE_MAP.get('unknown_platform', 'default') == 'default'


# ---------------------------------------------------------------------------
# Task 4.1 — poll_aap_job_status.apply_async appelé avec queue='aap' (AC1)
# ---------------------------------------------------------------------------


class TestShimQueueRouting:
    """Vérifie que les shims backward-compat déclenchent apply_async avec la bonne queue.

    Le shim poll_aap_job_status délègue à poll_platform_job_status (appel direct,
    sans apply_async). Lors du re-schedule interne, c'est poll_platform_job_status
    qui appelle apply_async avec queue=PLATFORM_QUEUE_MAP[platform_type].
    """

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_poll_aap_reschedule_uses_aap_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        """poll_aap_job_status → re-schedule dans queue 'aap'."""
        with patch("adapters.aap_adapter.AAPAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("aap timeout")

            result = poll_aap_job_status(
                execution_id=1,
                platform_job_id="job-aap-1",
                retry_count=0,
            )

        assert result["outcome"] == "error"
        mock_apply.assert_called_once()
        assert mock_apply.call_args[1]["queue"] == "aap"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_poll_tower_reschedule_uses_aap_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        """Tower utilise la même queue qu'AAP (variante compatible)."""
        with patch("adapters.tower_adapter.TowerAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("tower error")

            poll_tower_job_status(
                execution_id=2,
                platform_job_id="job-tower-1",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "aap"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_poll_azure_reschedule_uses_azure_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("azure timeout 45s")

            poll_azure_devops_run_status(
                execution_id=3,
                platform_job_id="run-azure-1",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "azure"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_poll_github_reschedule_uses_github_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.github_actions_adapter.GitHubActionsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("github error")

            poll_github_actions_run_status(
                execution_id=4,
                platform_job_id="run-gh-1",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "github"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_poll_terraform_reschedule_uses_terraform_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.terraform_cloud_adapter.TerraformCloudAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("terraform error")

            poll_terraform_cloud_run_status(
                execution_id=5,
                platform_job_id="run-tf-1",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "terraform"


# ---------------------------------------------------------------------------
# Task 4.2 — poll_platform_job_status.apply_async avec queue dynamique (AC3)
# ---------------------------------------------------------------------------


class TestPollPlatformQueueOnError:
    """Vérifie que apply_async utilise la bonne queue lors du re-schedule sur erreur."""

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_error_reschedule_aap_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.aap_adapter.AAPAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("aap timeout")

            poll_platform_job_status(
                execution_id=10,
                platform_job_id="job-aap-1",
                platform_type="aap",
                retry_count=0,
            )

        mock_apply.assert_called_once()
        assert mock_apply.call_args[1]["queue"] == "aap"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_error_reschedule_azure_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("azure timeout 45s")

            poll_platform_job_status(
                execution_id=11,
                platform_job_id="run-azure-1",
                platform_type="azure_devops",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "azure"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_error_reschedule_github_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.github_actions_adapter.GitHubActionsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("github error")

            poll_platform_job_status(
                execution_id=12,
                platform_job_id="run-gh-1",
                platform_type="github_actions",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "github"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_error_reschedule_terraform_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.terraform_cloud_adapter.TerraformCloudAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("terraform error")

            poll_platform_job_status(
                execution_id=13,
                platform_job_id="run-tf-1",
                platform_type="terraform_cloud",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "terraform"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_error_reschedule_tower_uses_aap_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        with patch("adapters.tower_adapter.TowerAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("tower error")

            poll_platform_job_status(
                execution_id=14,
                platform_job_id="job-tower-1",
                platform_type="tower",
                retry_count=0,
            )

        assert mock_apply.call_args[1]["queue"] == "aap"

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_unknown_platform_type_uses_default_queue(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        """Task 4.3 — Plateforme inconnue → queue 'default' (pas d'exception). AC3.

        get_platform_adapter lève une exception pour un type inconnu ; celle-ci est
        attrapée par le bloc except de poll_platform_job_status, qui re-schedule
        avec queue='default' (PLATFORM_QUEUE_MAP.get('unknown_platform', 'default')).
        """
        poll_platform_job_status(
            execution_id=99,
            platform_job_id="job-unknown-1",
            platform_type="unknown_platform",
            retry_count=0,
        )

        mock_apply.assert_called_once()
        assert mock_apply.call_args[1]["queue"] == "default"


# ---------------------------------------------------------------------------
# Re-schedule normal (poll non-terminal) — queue correcte (AC3)
# ---------------------------------------------------------------------------


class TestPollPlatformQueueOnSuccess:
    """Vérifie que apply_async utilise la bonne queue lors du re-schedule normal."""

    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_reschedule_aap_queue_on_polling(
        self,
        mock_corr: MagicMock,
        mock_apply: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ) -> None:
        """Re-schedule normal (RUNNING) sur AAP → queue 'aap'."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING"})
        mock_adapter.get_job_logs = AsyncMock(return_value={"content": "log", "complete": False})

        with patch("adapters.aap_adapter.AAPAdapter", return_value=mock_adapter):
            result = poll_platform_job_status(
                execution_id=20,
                platform_job_id="job-aap-1",
                platform_type="aap",
                retry_count=0,
            )

        assert result["outcome"] == "polling"
        mock_apply.assert_called_once()
        assert mock_apply.call_args[1]["queue"] == "aap"

    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks._update_execution_from_poll")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_reschedule_azure_queue_on_polling(
        self,
        mock_corr: MagicMock,
        mock_apply: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ) -> None:
        """Re-schedule normal sur Azure DevOps → queue 'azure' (bulkhead validé)."""
        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={"status": "RUNNING"})
        mock_adapter.get_job_logs = AsyncMock(return_value={"content": "log", "complete": False})

        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter", return_value=mock_adapter):
            result = poll_platform_job_status(
                execution_id=21,
                platform_job_id="run-azure-1",
                platform_type="azure_devops",
                retry_count=0,
            )

        assert result["outcome"] == "polling"
        assert mock_apply.call_args[1]["queue"] == "azure"


# ---------------------------------------------------------------------------
# Bulkhead — isolation inter-plateforme (AC3)
# ---------------------------------------------------------------------------


class TestBulkheadIsolation:
    """Vérifie que le timeout d'Azure n'interfère pas avec la queue 'aap'."""

    @patch("executions.tasks.poll_platform_job_status.apply_async")
    @patch("executions.tasks.get_correlation_id", return_value="test-corr")
    def test_azure_timeout_uses_azure_queue_not_aap(
        self, mock_corr: MagicMock, mock_apply: MagicMock
    ) -> None:
        """Un timeout Azure → queue 'azure', distincte de 'aap', 'github', 'terraform'."""
        with patch("adapters.azure_devops_adapter.AzureDevOpsAdapter") as MockAdapter:
            MockAdapter.side_effect = Exception("azure 45s timeout")

            poll_platform_job_status(
                execution_id=30,
                platform_job_id="run-azure-timeout",
                platform_type="azure_devops",
                retry_count=5,
            )

        queue_used = mock_apply.call_args[1]["queue"]
        assert queue_used == "azure"
        assert queue_used != "aap"
        assert queue_used != "github"
        assert queue_used != "terraform"
        assert queue_used != "default"


# ---------------------------------------------------------------------------
# Cohérence CELERY_TASK_ROUTES (settings) vs PLATFORM_QUEUE_MAP (polling) (LOW#7)
# ---------------------------------------------------------------------------


class TestCeleryTaskRoutesConsistency:
    """Vérifie que CELERY_TASK_ROUTES dans settings.py est cohérent avec
    PLATFORM_QUEUE_MAP dans polling.py — les deux mécanismes de routing doivent
    produire les mêmes queues pour les shims nommés.
    """

    def test_celery_task_routes_shims_match_platform_queue_map(self) -> None:
        """CELERY_TASK_ROUTES[shim] doit pointer vers la même queue que PLATFORM_QUEUE_MAP."""
        from django.conf import settings

        expected_shim_routes = {
            'executions.tasks.poll_aap_job_status': PLATFORM_QUEUE_MAP['aap'],
            'executions.tasks.poll_tower_job_status': PLATFORM_QUEUE_MAP['tower'],
            'executions.tasks.poll_azure_devops_run_status': PLATFORM_QUEUE_MAP['azure_devops'],
            'executions.tasks.poll_github_actions_run_status': PLATFORM_QUEUE_MAP['github_actions'],
            'executions.tasks.poll_terraform_cloud_run_status': PLATFORM_QUEUE_MAP['terraform_cloud'],
        }
        routes = getattr(settings, 'CELERY_TASK_ROUTES', {})
        for task_name, expected_queue in expected_shim_routes.items():
            assert task_name in routes, f"Task {task_name!r} absente de CELERY_TASK_ROUTES"
            actual_queue = routes[task_name].get('queue')
            assert actual_queue == expected_queue, (
                f"{task_name}: CELERY_TASK_ROUTES='{actual_queue}' "
                f"!= PLATFORM_QUEUE_MAP='{expected_queue}'"
            )

    def test_celery_task_routes_beat_tasks_on_default(self) -> None:
        """Les tasks Beat (retry, gates, scheduled) restent sur la queue 'default'."""
        from django.conf import settings

        beat_tasks = [
            'executions.tasks.retry_workflow_step',
            'executions.tasks.evaluate_waiting_gates',
            'executions.tasks.process_pending_scheduled_executions',
        ]
        routes = getattr(settings, 'CELERY_TASK_ROUTES', {})
        for task_name in beat_tasks:
            assert task_name in routes, f"Task Beat {task_name!r} absente de CELERY_TASK_ROUTES"
            assert routes[task_name].get('queue') == 'default', (
                f"{task_name} doit être sur 'default', "
                f"trouvé: '{routes[task_name].get('queue')}'"
            )
