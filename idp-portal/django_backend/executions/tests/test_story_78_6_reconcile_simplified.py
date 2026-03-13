"""
Tests Story 78.6 — Simplification du réconciliateur

AC1 : Le réconciliateur ne contient plus de logique d'exécution de handlers ni d'appel
      direct à _execute_workflow_steps(). Steps sans platform_job_id → reset PENDING + enqueue.
AC2 : Re-drive des commandes pending intégré dans le cycle de réconciliation.
AC3 : Aucune duplication de logique entre réconciliateur et worker — délégation via enqueue.
AC4 : Docstring du module documente les responsabilités post-simplification.

Sections :
  1. Tests re-drive commandes (AC2)
  2. Tests enqueue recovery — remplace resume inline (AC1, AC3)
  3. Tests reset+enqueue — remplace retry inline (AC1, AC3)
  4. Tests reattach poll inchangé
  5. Tests reconcile schedule step inchangé
  6. Tests parent-child cascade inchangé
  7. Tests finalisation (AC1, AC3)
  8. Tests docstring (AC4)
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStepType,
    RunnableStep,
)
from executions.tasks.reconcile import (
    _enqueue_recovery_steps,
    _reconcile_execution,
    _reset_and_enqueue_step,
    reconcile_stale_executions,
    STALE_THRESHOLD_MINUTES,
)
from tests.factories import ActionFactory, ExecutionFactory, ExecutionStepFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workflow_action(steps):
    """Create an Action with execution_steps (workflow definition)."""
    return ActionFactory(
        item_type='workflow',
        execution_steps=steps,
    )


def _make_execution(steps, status=ExecutionStatus.RUNNING, **kwargs):
    """Create an Execution with workflow steps."""
    action = _make_workflow_action(steps)
    return ExecutionFactory(action=action, status=status, **kwargs)


def _simple_sequential_steps():
    """3 sequential steps: step-a → step-b → step-c."""
    return [
        {
            "step_id": "step-a", "name": "Step A", "order": 1,
            "step_type": "evaluation",
            "on_success_step_ids": ["step-b"],
        },
        {
            "step_id": "step-b", "name": "Step B", "order": 2,
            "step_type": "service_call",
            "on_success_step_ids": ["step-c"],
        },
        {
            "step_id": "step-c", "name": "Step C", "order": 3,
            "step_type": "http_request",
        },
    ]


def _make_stale(execution):
    """Make an execution stale (older than threshold)."""
    stale_time = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES + 5)
    Execution.objects.filter(pk=execution.pk).update(
        updated_at=stale_time,
        created_at=stale_time,
    )
    execution.refresh_from_db()
    return execution


# ===========================================================================
# 1. Tests re-drive commandes (AC2)
# ===========================================================================

@pytest.mark.django_db
class TestAC2CommandRedrive:
    """AC2 : Le re-drive des commandes pending est intégré dans le cycle de réconciliation."""

    def test_reconcile_calls_process_pending_commands(self):
        """reconcile_stale_executions() appelle process_pending_commands() après reclaim."""
        with patch(
            "executions.services.workflow_commands.WorkflowCommandService.process_pending_commands",
            return_value=3,
        ) as mock_process, patch(
            "executions.services.runnable_steps.RunnableStepService.reclaim_expired_leases",
            return_value=0,
        ):
            result = reconcile_stale_executions()

        mock_process.assert_called_once()
        assert result["commands_redriven"] == 3

    def test_reconcile_redrive_error_graceful(self):
        """Si process_pending_commands lève une exception, le reconcile continue."""
        with patch(
            "executions.services.workflow_commands.WorkflowCommandService.process_pending_commands",
            side_effect=RuntimeError("DB error"),
        ), patch(
            "executions.services.runnable_steps.RunnableStepService.reclaim_expired_leases",
            return_value=0,
        ):
            result = reconcile_stale_executions()

        # Should complete without raising
        assert result["commands_redriven"] == 0

    def test_reconcile_result_includes_commands_redriven(self):
        """Le dict de retour contient la clé commands_redriven."""
        with patch(
            "executions.services.workflow_commands.WorkflowCommandService.process_pending_commands",
            return_value=0,
        ), patch(
            "executions.services.runnable_steps.RunnableStepService.reclaim_expired_leases",
            return_value=0,
        ):
            result = reconcile_stale_executions()

        assert "commands_redriven" in result
        assert result["commands_redriven"] == 0


# ===========================================================================
# 2. Tests enqueue recovery — remplace resume inline (AC1, AC3)
# ===========================================================================

@pytest.mark.django_db
class TestAC1AC3EnqueueRecovery:
    """AC1, AC3 : _enqueue_recovery_steps remplace _resume_container_workflow."""

    def test_enqueue_recovery_creates_pending_steps_and_enqueues(self):
        """Stale execution with COMPLETED step-a → enqueue step-b (not execute inline)."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        # step-a completed
        ExecutionStepFactory(
            execution=execution,
            config_step_id="step-a",
            step_name="Step A",
            step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.COMPLETED,
            step_order=1,
        )

        result = _enqueue_recovery_steps(execution)
        assert result == "reattached"

        # step-b should be PENDING in DB
        step_b = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id="step-b",
        ).first()
        assert step_b is not None
        assert step_b.status == ExecutionStepStatus.PENDING

        # step-b should be in RUNNABLE_STEPS queue
        runnable = RunnableStep.objects.filter(
            execution_step=step_b,
        ).first()
        assert runnable is not None

    def test_enqueue_recovery_no_execute_workflow_steps(self):
        """_enqueue_recovery_steps ne doit pas appeler _execute_workflow_steps."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        ExecutionStepFactory(
            execution=execution,
            config_step_id="step-a",
            step_name="Step A",
            step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.COMPLETED,
            step_order=1,
        )

        with patch(
            "executions.container_workflow_runtime.ContainerWorkflowRuntime._execute_workflow_steps"
        ) as mock_exec:
            _enqueue_recovery_steps(execution)
            mock_exec.assert_not_called()

    def test_enqueue_recovery_all_terminal_finalizes(self):
        """Tous les steps terminal, pas de next wave → exécution finalisée."""
        # 2-step workflow: step-a → step-b (both COMPLETED)
        steps = [
            {"step_id": "step-a", "name": "A", "order": 1, "step_type": "evaluation",
             "on_success_step_ids": ["step-b"]},
            {"step_id": "step-b", "name": "B", "order": 2, "step_type": "evaluation"},
        ]
        execution = _make_execution(steps)

        ExecutionStepFactory(
            execution=execution, config_step_id="step-a", step_name="A",
            step_type=ExecutionStepType.EVALUATION, status=ExecutionStepStatus.COMPLETED,
            step_order=1,
        )
        ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="B",
            step_type=ExecutionStepType.EVALUATION, status=ExecutionStepStatus.COMPLETED,
            step_order=2,
        )

        with patch(
            "executions.tasks.orchestration_worker._finalize_execution_if_done"
        ) as mock_finalize:
            result = _enqueue_recovery_steps(execution)

        assert result == "reattached"
        mock_finalize.assert_called_once_with(execution, ExecutionStatus.COMPLETED)

    def test_enqueue_recovery_no_completed_steps_raises(self):
        """Pas de steps COMPLETED → ValueError."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        with pytest.raises(ValueError, match="No COMPLETED steps found"):
            _enqueue_recovery_steps(execution)

    def test_reconcile_execution_no_running_steps_enqueues_recovery(self):
        """Execution RUNNING sans step RUNNING → _enqueue_recovery_steps est appelé."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        ExecutionStepFactory(
            execution=execution, config_step_id="step-a", step_name="Step A",
            step_type=ExecutionStepType.EVALUATION, status=ExecutionStepStatus.COMPLETED,
            step_order=1,
        )

        result = _reconcile_execution(execution)
        assert result == "reattached"

        # step-b should be enqueued
        step_b = ExecutionStep.objects.filter(
            execution=execution, config_step_id="step-b",
        ).first()
        assert step_b is not None
        assert step_b.status == ExecutionStepStatus.PENDING


# ===========================================================================
# 3. Tests reset+enqueue — remplace retry inline (AC1, AC3)
# ===========================================================================

@pytest.mark.django_db
class TestAC1AC3ResetAndEnqueue:
    """AC1, AC3 : _reset_and_enqueue_step remplace _retry_non_platform_step."""

    def test_reset_and_enqueue_resets_to_pending(self):
        """Step RUNNING sans platform_job_id → reset PENDING."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="Step B",
            step_type=ExecutionStepType.SERVICE_CALL, status=ExecutionStepStatus.RUNNING,
            step_order=2,
        )

        result = _reset_and_enqueue_step(step)
        assert result is True

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.PENDING
        assert step.error_message is None

    def test_reset_and_enqueue_creates_runnable_step(self):
        """Step reset → enqueued dans RUNNABLE_STEPS."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="Step B",
            step_type=ExecutionStepType.SERVICE_CALL, status=ExecutionStepStatus.RUNNING,
            step_order=2,
        )

        _reset_and_enqueue_step(step)

        runnable = RunnableStep.objects.filter(execution_step=step).first()
        assert runnable is not None
        assert runnable.execution_id == execution.id

    def test_reset_and_enqueue_no_handler_execution(self):
        """reset+enqueue ne doit PAS appeler de handler."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="Step B",
            step_type=ExecutionStepType.SERVICE_CALL, status=ExecutionStepStatus.RUNNING,
            step_order=2,
        )

        with patch("executions.step_handlers.service_call_handler.ServiceCallHandler") as mock_handler:
            _reset_and_enqueue_step(step)
            mock_handler.assert_not_called()

    def test_reset_and_enqueue_failure_marks_step_failed(self):
        """Si RunnableStepService.enqueue() lève une exception, le step est marqué FAILED."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="Step B",
            step_type=ExecutionStepType.SERVICE_CALL, status=ExecutionStepStatus.RUNNING,
            step_order=2,
        )

        with patch(
            "executions.services.runnable_steps.RunnableStepService.enqueue",
            side_effect=RuntimeError("Queue full"),
        ):
            result = _reset_and_enqueue_step(step)

        assert result is False
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert "Reset+enqueue failed" in (step.error_message or "")

    def test_reconcile_execution_running_step_no_platform_job_resets(self):
        """_reconcile_execution : step RUNNING service_call sans platform_job_id → reset+enqueue."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-b", step_name="Step B",
            step_type=ExecutionStepType.SERVICE_CALL, status=ExecutionStepStatus.RUNNING,
            step_order=2, platform_job_id=None,
        )

        result = _reconcile_execution(execution)
        assert result == "reattached"

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.PENDING

        # Should be in runnable queue
        assert RunnableStep.objects.filter(execution_step=step).exists()


# ===========================================================================
# 4. Tests reattach poll inchangé
# ===========================================================================

@pytest.mark.django_db
class TestReattachPollUnchanged:
    """Reattach poll pour platform steps avec platform_job_id reste inchangé."""

    def test_reattach_poll_step_running_with_platform_job_id(self):
        """Step RUNNING avec platform_job_id réel → _reattach_poll appelé."""
        steps = [
            {"step_id": "step-a", "name": "Step A", "order": 1, "step_type": "platform"},
        ]
        execution = _make_execution(steps)

        ExecutionStepFactory(
            execution=execution, config_step_id="step-a", step_name="Step A",
            step_type=ExecutionStepType.PLATFORM, status=ExecutionStepStatus.RUNNING,
            step_order=1, platform_job_id="job-123",
        )

        with patch("executions.tasks.reconcile._reattach_poll", return_value=True) as mock_poll:
            result = _reconcile_execution(execution)

        assert result == "reattached"
        mock_poll.assert_called_once()


# ===========================================================================
# 5. Tests reconcile schedule step inchangé
# ===========================================================================

@pytest.mark.django_db
class TestReconcileScheduleStepUnchanged:
    """_reconcile_schedule_step pour steps avec child execution ID reste inchangé."""

    def test_schedule_step_child_completed_syncs(self):
        """Step avec child execution ID, child COMPLETED → sync parent step."""
        steps = [
            {"step_id": "step-a", "name": "Step A", "order": 1, "step_type": "schedule_execution"},
        ]
        execution = _make_execution(steps)

        child = ExecutionFactory(
            parent_execution=execution,
            status=ExecutionStatus.COMPLETED,
            completed_at=timezone.now(),
        )

        step = ExecutionStepFactory(
            execution=execution, config_step_id="step-a", step_name="Step A",
            step_type=ExecutionStepType.PLATFORM, status=ExecutionStepStatus.RUNNING,
            step_order=1, platform_job_id=str(child.id),
        )

        result = _reconcile_execution(execution)
        assert result == "reattached"

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED


# ===========================================================================
# 6. Tests parent-child cascade inchangé
# ===========================================================================

@pytest.mark.django_db
class TestParentChildCascadeUnchanged:
    """Parent-child cascade : si parent reconcilié terminal, child marqué FAILED."""

    def test_child_cascade_failed_when_parent_failed(self):
        """Parent déjà FAILED → child stale marqué FAILED par cascade."""
        # Parent execution (already FAILED)
        parent_steps = _simple_sequential_steps()
        parent = _make_execution(parent_steps, status=ExecutionStatus.FAILED)

        # Child execution (stale RUNNING)
        child_steps = _simple_sequential_steps()
        child_action = _make_workflow_action(child_steps)
        child = ExecutionFactory(
            action=child_action, status=ExecutionStatus.RUNNING,
            parent_execution=parent,
        )
        _make_stale(child)

        with patch(
            "executions.services.workflow_commands.WorkflowCommandService.process_pending_commands",
            return_value=0,
        ), patch(
            "executions.services.runnable_steps.RunnableStepService.reclaim_expired_leases",
            return_value=0,
        ):
            result = reconcile_stale_executions()

        child.refresh_from_db()
        assert child.status == ExecutionStatus.FAILED
        assert result["failed"] >= 1


# ===========================================================================
# 7. Tests finalisation (AC1, AC3)
# ===========================================================================

@pytest.mark.django_db
class TestFinalization:
    """Tous steps terminal, pas de next wave → exécution finalisée via _finalize_execution_if_done."""

    def test_finalize_when_all_steps_done(self):
        """_enqueue_recovery_steps appelle _finalize_execution_if_done quand pas de next wave."""
        steps = [
            {"step_id": "step-a", "name": "A", "order": 1, "step_type": "evaluation"},
        ]
        execution = _make_execution(steps)

        ExecutionStepFactory(
            execution=execution, config_step_id="step-a", step_name="A",
            step_type=ExecutionStepType.EVALUATION, status=ExecutionStepStatus.COMPLETED,
            step_order=1,
        )

        # step-a has no on_success_step_ids → no next wave → finalize
        with patch(
            "executions.tasks.orchestration_worker._finalize_execution_if_done"
        ) as mock_finalize:
            _enqueue_recovery_steps(execution)

        mock_finalize.assert_called_once_with(execution, ExecutionStatus.COMPLETED)


# ===========================================================================
# 8. Tests docstring (AC4)
# ===========================================================================

class TestAC4Docstring:
    """AC4 : Le docstring du module documente les responsabilités post-simplification."""

    def test_docstring_contains_responsibilities(self):
        """Le docstring mentionne les responsabilités principales."""
        import executions.tasks.reconcile as mod
        docstring = mod.__doc__ or ""
        assert "Reclaim des leases" in docstring
        assert "Re-drive des commandes pending" in docstring
        assert "reset PENDING + enqueue" in docstring

    def test_docstring_contains_non_responsibilities(self):
        """Le docstring mentionne ce que le réconciliateur ne fait plus."""
        import executions.tasks.reconcile as mod
        docstring = mod.__doc__ or ""
        assert "ne fait plus" in docstring
        assert "_execute_workflow_steps" in docstring
        assert "ServiceCallHandler" in docstring

    def test_docstring_mentions_delegation_to_worker(self):
        """Le docstring mentionne la délégation au worker d'orchestration."""
        import executions.tasks.reconcile as mod
        docstring = mod.__doc__ or ""
        assert "worker d'orchestration" in docstring or "worker" in docstring.lower()
