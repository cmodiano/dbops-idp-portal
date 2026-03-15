"""
Tests pour Story 47.4 — Résolution automatique des queues Celery depuis l'AdapterRegistry.

Covers:
- AC1: get_platform_queue() délègue à adapter_registry (plus de PLATFORM_QUEUE_MAP hardcodé)
- AC2/AC3: poll_platform_job_status.apply_async passe la bonne queue selon platform_type
- AC3: Un timeout sur une plateforme n'affecte pas les queues des autres (bulkhead)
- AC4: adapter_registry.get_queue() retourne 'default' pour une plateforme inconnue
- AC5: Non-régression (tests existants adaptés)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from adapters.registry import adapter_registry
from executions.tasks.polling import get_platform_queue, poll_platform_job_status


# ---------------------------------------------------------------------------
# Registry — résolution des queues par plateforme (AC1, AC2)
# ---------------------------------------------------------------------------


class TestAdapterRegistryQueues:
    """Vérifie que l'AdapterRegistry associe les bonnes queues aux plateformes."""

    def test_aap_queue(self) -> None:
        assert adapter_registry.get_queue("aap") == "aap"

    def test_tower_uses_aap_queue(self) -> None:
        """Tower est une variante d'AAP — même queue."""
        assert adapter_registry.get_queue("tower") == "aap"

    def test_azure_devops_queue(self) -> None:
        assert adapter_registry.get_queue("azure_devops") == "azure"

    def test_github_actions_queue(self) -> None:
        assert adapter_registry.get_queue("github_actions") == "github"

    def test_terraform_cloud_queue(self) -> None:
        assert adapter_registry.get_queue("terraform_cloud") == "terraform"

    def test_unknown_platform_defaults_to_default(self) -> None:
        """Plateforme inconnue → 'default' sans exception. AC4."""
        assert adapter_registry.get_queue("unknown_platform") == "default"

    def test_all_expected_platforms_registered(self) -> None:
        expected = {"aap", "tower", "azure_devops", "github_actions", "terraform_cloud"}
        assert expected.issubset(set(adapter_registry.list_types()))


# ---------------------------------------------------------------------------
# get_platform_queue() — wrapper public (AC1)
# ---------------------------------------------------------------------------


class TestGetPlatformQueue:
    """Vérifie que get_platform_queue() délègue correctement au registry."""

    def test_get_platform_queue_aap(self) -> None:
        assert get_platform_queue("aap") == "aap"

    def test_get_platform_queue_tower(self) -> None:
        assert get_platform_queue("tower") == "aap"

    def test_get_platform_queue_azure(self) -> None:
        assert get_platform_queue("azure_devops") == "azure"

    def test_get_platform_queue_github(self) -> None:
        assert get_platform_queue("github_actions") == "github"

    def test_get_platform_queue_terraform(self) -> None:
        assert get_platform_queue("terraform_cloud") == "terraform"

    def test_get_platform_queue_unknown(self) -> None:
        assert get_platform_queue("unknown_platform") == "default"


# ---------------------------------------------------------------------------
# list_queues() — commande management (AC4)
# ---------------------------------------------------------------------------


class TestListQueues:
    """Vérifie que list_queues() retourne les queues uniques avec 'default' en tête."""

    def test_default_always_included(self) -> None:
        queues = adapter_registry.list_queues()
        assert "default" in queues

    def test_default_is_first(self) -> None:
        queues = adapter_registry.list_queues()
        assert queues[0] == "default"

    def test_all_platform_queues_present(self) -> None:
        queues = adapter_registry.list_queues()
        assert "aap" in queues
        assert "azure" in queues
        assert "github" in queues
        assert "terraform" in queues

    def test_no_duplicates(self) -> None:
        queues = adapter_registry.list_queues()
        assert len(queues) == len(set(queues))

    def test_tower_aap_not_duplicated(self) -> None:
        """Tower et AAP partagent la queue 'aap' — elle ne doit apparaître qu'une fois."""
        queues = adapter_registry.list_queues()
        assert queues.count("aap") == 1




# ---------------------------------------------------------------------------
# poll_platform_job_status — queue dynamique sur erreur (AC2, AC3)
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
        """Plateforme inconnue → queue 'default' (pas d'exception). AC4."""
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
# Cohérence CELERY_TASK_ROUTES (settings) vs registry (AC5)
# ---------------------------------------------------------------------------


class TestCeleryTaskRoutesConsistency:
    """Vérifie que CELERY_TASK_ROUTES est cohérent avec le registry."""

    def test_celery_task_routes_no_shim_entries(self) -> None:
        """Shim task routes have been removed from CELERY_TASK_ROUTES."""
        from django.conf import settings

        removed_shim_tasks = [
            "executions.tasks.poll_aap_job_status",
            "executions.tasks.poll_tower_job_status",
            "executions.tasks.poll_azure_devops_run_status",
            "executions.tasks.poll_github_actions_run_status",
            "executions.tasks.poll_terraform_cloud_run_status",
        ]
        routes = getattr(settings, "CELERY_TASK_ROUTES", {})
        for task_name in removed_shim_tasks:
            assert task_name not in routes, (
                f"Shim task {task_name!r} should have been removed from CELERY_TASK_ROUTES"
            )

    def test_celery_task_routes_beat_tasks_on_default(self) -> None:
        """Les tasks Beat (gates, scheduled) restent sur la queue 'default'.

        Story 81: retry_workflow_step removed — legacy workflow decommissioned.
        """
        from django.conf import settings

        beat_tasks = [
            "executions.tasks.evaluate_waiting_gates",
            "executions.tasks.process_pending_scheduled_executions",
        ]
        routes = getattr(settings, "CELERY_TASK_ROUTES", {})
        for task_name in beat_tasks:
            assert task_name in routes, f"Task Beat {task_name!r} absente de CELERY_TASK_ROUTES"
            assert routes[task_name].get("queue") == "default", (
                f"{task_name} doit être sur 'default', "
                f"trouvé: '{routes[task_name].get('queue')}'"
            )


# ---------------------------------------------------------------------------
# Commande management celery_queues (AC4)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCeleryQueuesCommand:
    """Vérifie le comportement de la commande management celery_queues."""

    def test_command_outputs_default_queue(self) -> None:
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("celery_queues", stdout=out)
        output = out.getvalue().strip()
        assert "default" in output

    def test_command_comma_format_contains_all_queues(self) -> None:
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("celery_queues", format="comma", stdout=out)
        queues = out.getvalue().strip().split(",")
        assert "default" in queues
        assert "aap" in queues
        assert "azure" in queues
        assert "github" in queues
        assert "terraform" in queues

    def test_command_list_format_one_per_line(self) -> None:
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("celery_queues", format="list", stdout=out)
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        assert "default" in lines
        assert "aap" in lines

    def test_command_no_duplicates(self) -> None:
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("celery_queues", format="comma", stdout=out)
        queues = out.getvalue().strip().split(",")
        assert len(queues) == len(set(queues)), "Doublons détectés dans la sortie celery_queues"

    def test_command_has_help_text(self) -> None:
        """Command has useful help text for --help (Story 47.4 code review M2)."""
        from executions.management.commands.celery_queues import Command

        cmd = Command()
        assert "queue" in cmd.help.lower()
