"""Tests unitaires pour la tâche trigger_platform_job (Story 47.2)."""
from unittest.mock import MagicMock, patch

import pytest

from executions.models import ExecutionStatus, ExecutionStepStatus
from tests.factories import (
    ExecutionFactory,
    ExecutionStepFactory,
    IntegrationFactory,
)


@pytest.mark.django_db
class TestTriggerPlatformJobTask:
    """Tests pour executions.tasks.trigger.trigger_platform_job."""

    @patch("executions.tasks.polling.poll_platform_job_status.apply_async")
    @patch("adapters.get_platform_adapter")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer test"})
    def test_trigger_success_stores_platform_job_id_and_schedules_poll(
        self, mock_auth, mock_get_adapter, mock_poll_async,
    ):
        """Trigger réussi → platform_job_id stocké + premier poll schedulé."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="aap", credential_ref="token123")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        mock_adapter = MagicMock()

        async def fake_trigger(**kwargs):
            return {"platform_job_id": "aap-42", "status": "SUBMITTED"}

        mock_adapter.trigger = fake_trigger
        mock_get_adapter.return_value = mock_adapter

        result = trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={"template_id": "5"},
        )

        assert result["outcome"] == "dispatched"
        assert result["platform_job_id"] == "aap-42"

        step.refresh_from_db()
        assert step.platform_job_id == "aap-42"

        mock_poll_async.assert_called_once()
        call_kwargs = mock_poll_async.call_args
        assert call_kwargs.kwargs["queue"] == "aap"

    @patch("executions.tasks.trigger.logger")
    @patch("adapters.get_platform_adapter")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer test"})
    def test_trigger_adapter_error_returns_error_outcome(self, mock_auth, mock_get_adapter, mock_logger):
        """Erreur adapter → outcome=error, log CRITICAL appelé, step marqué FAILED, pas d'exception non gérée."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="aap")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        mock_adapter = MagicMock()

        async def failing_trigger(**kwargs):
            raise RuntimeError("AAP timeout")

        mock_adapter.trigger = failing_trigger
        mock_get_adapter.return_value = mock_adapter

        result = trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={"template_id": "5"},
        )

        assert result["outcome"] == "error"
        assert "timeout" in result["error"]

        # AC5 : vérification du log CRITICAL sur erreur adapter
        mock_logger.critical.assert_called_once()
        assert mock_logger.critical.call_args.args[0] == "trigger_platform_job_failed"

        # Fix H2 : step doit être FAILED (plus jamais bloqué en RUNNING)
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED

    def test_trigger_integration_not_found_returns_error(self):
        """Integration inexistante → outcome=error sans exception non gérée."""
        from executions.tasks.trigger import trigger_platform_job

        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        result = trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=999999,  # inexistant
            trigger_kwargs={"template_id": "5"},
        )

        assert result["outcome"] == "error"
        assert "error" in result

    def test_trigger_execution_step_not_found_returns_error(self):
        """ExecutionStep inexistant → outcome=error sans exception non gérée."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="aap")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)

        result = trigger_platform_job(
            execution_step_id=999999,  # inexistant
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={"template_id": "5"},
        )

        assert result["outcome"] == "error"

    @patch("executions.tasks.polling.poll_platform_job_status.apply_async")
    @patch("adapters.get_platform_adapter")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer test"})
    def test_trigger_correct_queue_for_aap(self, mock_auth, mock_get_adapter, mock_poll_async):
        """Integration type=aap → poll schedulé sur queue 'aap'."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="aap")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        mock_adapter = MagicMock()

        async def fake_trigger(**kwargs):
            return {"platform_job_id": "aap-10"}

        mock_adapter.trigger = fake_trigger
        mock_get_adapter.return_value = mock_adapter

        trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={"template_id": "1"},
        )

        mock_poll_async.assert_called_once()
        assert mock_poll_async.call_args.kwargs["queue"] == "aap"

    @patch("executions.tasks.polling.poll_platform_job_status.apply_async")
    @patch("adapters.get_platform_adapter")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer test"})
    def test_trigger_correct_queue_for_azure_devops(self, mock_auth, mock_get_adapter, mock_poll_async):
        """Integration type=azure_devops → poll schedulé sur queue 'azure'."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="azure_devops")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        mock_adapter = MagicMock()

        async def fake_trigger(**kwargs):
            return {"platform_job_id": "ado-99"}

        mock_adapter.trigger = fake_trigger
        mock_get_adapter.return_value = mock_adapter

        trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={"template_id": "1"},
        )

        mock_poll_async.assert_called_once()
        assert mock_poll_async.call_args.kwargs["queue"] == "azure"

    @patch("executions.tasks.polling.poll_platform_job_status.apply_async")
    @patch("adapters.get_platform_adapter")
    @patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer test"})
    def test_trigger_no_platform_job_id_does_not_schedule_poll(
        self, mock_auth, mock_get_adapter, mock_poll_async,
    ):
        """Si adapter ne retourne pas de platform_job_id, pas de poll schedulé."""
        from executions.tasks.trigger import trigger_platform_job

        integration = IntegrationFactory.create(type="aap")
        execution = ExecutionFactory.create(status=ExecutionStatus.RUNNING)
        step = ExecutionStepFactory.create(
            execution=execution, status=ExecutionStepStatus.RUNNING,
        )

        mock_adapter = MagicMock()

        async def fake_trigger(**kwargs):
            return {}  # pas de platform_job_id

        mock_adapter.trigger = fake_trigger
        mock_get_adapter.return_value = mock_adapter

        result = trigger_platform_job(
            execution_step_id=step.id,
            execution_id=execution.id,
            integration_id=integration.id,
            trigger_kwargs={},
        )

        assert result["outcome"] == "dispatched"
        assert result["platform_job_id"] is None
        mock_poll_async.assert_not_called()
