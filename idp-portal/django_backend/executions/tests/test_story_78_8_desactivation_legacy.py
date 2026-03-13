"""
Tests Story 78.8 — Désactivation du runtime legacy en production.

AC1: Feature flag WORKFLOW_LEGACY_RUNTIME_ENABLED
AC2: Fallback thread-based bloqué quand flag=False
AC3: retry_workflow_step gardé par le flag
AC4: Non-régression — workflows queue-based fonctionnent normalement
"""
import structlog
import pytest
from unittest.mock import patch, MagicMock

from django.test import override_settings

from executions.exceptions import WorkflowLegacyDisabledError
from executions.models import (
    ExecutionStatus,
    RunnableStep,
)
from tests.factories import ActionFactory, ExecutionFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workflow_action(steps):
    """Create an Action with execution_steps (workflow definition)."""
    return ActionFactory(
        item_type='workflow',
        execution_steps=steps,
    )


def _make_execution(steps, status=ExecutionStatus.SUBMITTED):
    """Create an Execution with workflow steps."""
    action = _make_workflow_action(steps)
    return ExecutionFactory(action=action, status=status)


def _steps_with_step_id():
    """Steps with step_id — queue-based dispatch."""
    return [
        {
            "step_id": "step-a", "name": "Step A", "order": 1,
            "step_type": "evaluation",
            "on_success_step_ids": ["step-b"],
        },
        {
            "step_id": "step-b", "name": "Step B", "order": 2,
            "step_type": "evaluation",
        },
    ]


def _steps_without_step_id():
    """Steps without step_id — triggers legacy fallback."""
    return [
        {"name": "Step A", "order": 1, "step_type": "evaluation"},
        {"name": "Step B", "order": 2, "step_type": "evaluation"},
    ]


# ===========================================================================
# AC1 — Feature flag
# ===========================================================================

@pytest.mark.django_db
class TestAC1FeatureFlag:
    """AC1: Feature flag WORKFLOW_LEGACY_RUNTIME_ENABLED."""

    def test_flag_default_false_in_test_settings(self):
        """Flag is False by default in test settings."""
        from django.conf import settings
        assert settings.WORKFLOW_LEGACY_RUNTIME_ENABLED is False

    def test_exception_importable_and_inherits_runtime_error(self):
        """WorkflowLegacyDisabledError is importable and inherits RuntimeError."""
        assert issubclass(WorkflowLegacyDisabledError, RuntimeError)

    def test_exception_message(self):
        """Exception has explicit message about step_id requirement."""
        err = WorkflowLegacyDisabledError()
        assert "step_id" in str(err)


# ===========================================================================
# AC2 — Fallback thread-based bloqué
# ===========================================================================

@pytest.mark.django_db
class TestAC2FallbackBlocked:
    """AC2: Fallback thread-based bloqué quand WORKFLOW_LEGACY_RUNTIME_ENABLED=False."""

    def test_workflow_without_step_id_flag_false_raises(self):
        """Workflow sans step_id avec flag=False lève WorkflowLegacyDisabledError et marque FAILED."""
        steps = _steps_without_step_id()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)

        with pytest.raises(WorkflowLegacyDisabledError):
            runtime.run()

        # Execution must be FAILED, not stuck in RUNNING
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED
        assert execution.completed_at is not None
        assert "step_id" in execution.error_message

    def test_workflow_with_step_id_flag_false_enqueues(self):
        """Workflow AVEC step_id avec flag=False fonctionne normalement (enqueue)."""
        steps = _steps_with_step_id()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.RUNNING

        # Root step (step-a) should be enqueued in RUNNABLE_STEPS
        runnable = RunnableStep.objects.filter(execution=execution)
        assert runnable.count() == 1
        assert runnable.first().execution_step.config_step_id == "step-a"

    def test_workflow_without_step_id_flag_false_logs_blocked_event(self, caplog):
        """Le log structuré container_workflow_legacy_fallback_blocked est émis."""
        steps = _steps_without_step_id()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)

        with structlog.testing.capture_logs() as captured:
            with pytest.raises(WorkflowLegacyDisabledError):
                runtime.run()

        blocked_logs = [
            log for log in captured
            if log.get("event") == "container_workflow_legacy_fallback_blocked"
        ]
        assert len(blocked_logs) == 1
        assert blocked_logs[0]["execution_id"] == execution.id

    @override_settings(WORKFLOW_LEGACY_RUNTIME_ENABLED=True)
    @patch('threading.Thread')
    def test_workflow_without_step_id_flag_true_launches_thread(self, mock_thread_cls):
        """Workflow sans step_id avec flag=True lance le thread daemon (rollback)."""
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        steps = _steps_without_step_id()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        mock_thread_cls.assert_called_once()
        mock_thread_instance.start.assert_called_once()


# ===========================================================================
# AC3 — retry_workflow_step gardé par le flag
# ===========================================================================

@pytest.mark.django_db
class TestAC3RetryLegacyGuarded:
    """AC3: retry_workflow_step gardé par le feature flag."""

    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_flag_false_returns_error(self, _mock_cancelled):
        """retry_workflow_step avec flag=False retourne erreur sans instancier WorkflowRuntime."""
        from executions.tasks.retry import retry_workflow_step

        step = {"step_id": "step-x", "name": "Step X", "order": 1}

        # CELERY_TASK_ALWAYS_EAGER=True — .apply() runs synchronously with proper self binding
        result = retry_workflow_step.apply(
            args=[999, step, 2],
        )

        assert result.result['outcome'] == 'error'
        assert result.result['error_message'] == 'Legacy runtime disabled'

    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_flag_false_logs_disabled_event(self, _mock_cancelled):
        """Le log structuré legacy_retry_task_disabled est émis."""
        from executions.tasks.retry import retry_workflow_step

        step = {"step_id": "step-x", "name": "Step X", "order": 1}

        with structlog.testing.capture_logs() as captured:
            retry_workflow_step.apply(args=[999, step, 2])

        disabled_logs = [
            log for log in captured
            if log.get("event") == "legacy_retry_task_disabled"
        ]
        assert len(disabled_logs) == 1
        assert disabled_logs[0]["execution_id"] == 999

    @override_settings(WORKFLOW_LEGACY_RUNTIME_ENABLED=True)
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    @patch('executions.workflow_runtime.WorkflowRuntime')
    def test_retry_flag_true_proceeds(self, mock_runtime_cls, _mock_cancelled):
        """retry_workflow_step avec flag=True tente d'instancier WorkflowRuntime."""
        from executions.tasks.retry import retry_workflow_step

        steps = _steps_with_step_id()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        mock_runtime = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.outcome.value = 'success'
        mock_result.output = {}
        mock_runtime._execute_step.return_value = mock_result
        mock_runtime_cls.return_value = mock_runtime

        step = {"step_id": "step-a", "name": "Step A", "order": 1}

        result = retry_workflow_step.apply(
            args=[execution.id, step, 2],
        )

        assert result.result['outcome'] == 'success'
        mock_runtime_cls.assert_called_once()
