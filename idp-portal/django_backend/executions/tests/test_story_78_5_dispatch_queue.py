"""
Tests Story 78.5 — Dispatch par file au lieu de thread dans ContainerWorkflowRuntime

AC1 : ContainerWorkflowRuntime.run() n'instancie plus de threading.Thread — enqueue uniquement
AC2 : Orchestration worker : claim → execute → persist → enqueue next steps
AC3 : Comportement fonctionnel identique (séquentiel, gate, fan-out, on_error)
AC4 : Reprise après crash : état reconstruit depuis DB uniquement

Sections :
  1. Tests de run() enqueue-only (AC1)
  2. Tests du worker d'orchestration (AC2)
  3. Tests de _dispatch_command() handlers (AC2, AC3)
  4. Tests d'idempotence (AC4)
  5. Tests de crash recovery (AC4)
"""
import json
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
    WorkflowCommand,
    WorkflowCommandStatus,
)
from executions.services.runnable_steps import RunnableStepService
from executions.services.workflow_commands import WorkflowCommandService
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


def _make_execution(steps, status=ExecutionStatus.SUBMITTED):
    """Create an Execution with workflow steps."""
    action = _make_workflow_action(steps)
    return ExecutionFactory(action=action, status=status)


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
            "step_type": "evaluation",
            "on_success_step_ids": ["step-c"],
        },
        {
            "step_id": "step-c", "name": "Step C", "order": 3,
            "step_type": "evaluation",
        },
    ]


def _steps_with_gate():
    """2 steps with a gate: step-a → gate-step (WAITING) → step-c."""
    return [
        {
            "step_id": "step-a", "name": "Step A", "order": 1,
            "step_type": "evaluation",
            "on_success_step_ids": ["gate-step"],
        },
        {
            "step_id": "gate-step", "name": "Gate Step", "order": 2,
            "step_type": "gate",
            "gate_conditions": [{"type": "approval_granted"}],
            "on_success_step_ids": ["step-c"],
        },
        {
            "step_id": "step-c", "name": "Step C", "order": 3,
            "step_type": "evaluation",
        },
    ]


def _steps_with_fan_out():
    """Fan-out: step-a → [step-b1, step-b2] → step-c."""
    return [
        {
            "step_id": "step-a", "name": "Step A", "order": 1,
            "step_type": "evaluation",
            "on_success_step_ids": ["step-b1", "step-b2"],
        },
        {
            "step_id": "step-b1", "name": "Step B1", "order": 2,
            "step_type": "evaluation",
            "on_success_step_ids": ["step-c"],
        },
        {
            "step_id": "step-b2", "name": "Step B2", "order": 3,
            "step_type": "evaluation",
            "on_success_step_ids": ["step-c"],
        },
        {
            "step_id": "step-c", "name": "Step C", "order": 4,
            "step_type": "evaluation",
        },
    ]


def _steps_with_error_path():
    """Step with on_error: step-a (fails) → error-step."""
    return [
        {
            "step_id": "step-a", "name": "Step A", "order": 1,
            "step_type": "evaluation",
            "on_error_step_ids": ["error-step"],
        },
        {
            "step_id": "error-step", "name": "Error Handler", "order": 2,
            "step_type": "evaluation",
        },
    ]


def _make_command(execution=None, **kwargs):
    """Helper pour créer un WorkflowCommand en base."""
    if execution is None:
        execution = ExecutionFactory()
    created_at = kwargs.pop("created_at", None)
    defaults = {
        "execution": execution,
        "command_type": kwargs.pop("command_type", "approve"),
        "payload": kwargs.pop("payload", {}),
        "status": kwargs.pop("status", WorkflowCommandStatus.PENDING),
        "created_by": kwargs.pop("created_by", "test-user"),
    }
    defaults.update(kwargs)
    cmd = WorkflowCommand.objects.create(**defaults)
    if created_at is not None:
        WorkflowCommand.objects.filter(pk=cmd.pk).update(created_at=created_at)
        cmd.refresh_from_db()
    return cmd


# ===========================================================================
# 1. Tests de run() enqueue-only (AC1)
# ===========================================================================

@pytest.mark.django_db
class TestAC1RunEnqueueOnly:
    """AC1 : run() n'instancie plus de threading.Thread — enqueue root steps."""

    def test_run_creates_pending_execution_steps(self):
        """run() crée des ExecutionStep PENDING pour les root steps."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        # Execution should be RUNNING
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.RUNNING

        # Root step (step-a) should have a PENDING ExecutionStep
        exec_steps = ExecutionStep.objects.filter(execution=execution)
        assert exec_steps.count() == 1
        step_a = exec_steps.first()
        assert step_a.config_step_id == "step-a"
        assert step_a.status == ExecutionStepStatus.PENDING

    def test_run_enqueues_root_steps_to_runnable_queue(self):
        """run() enqueue les root steps dans RUNNABLE_STEPS."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        # Should have 1 runnable step
        runnables = RunnableStep.objects.filter(execution=execution)
        assert runnables.count() == 1
        assert runnables.first().execution_step.config_step_id == "step-a"

    def test_run_no_thread_created(self):
        """run() ne crée pas de threading.Thread pour les workflows avec step_id."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.container_workflow_runtime.threading.Thread') as mock_thread:
            runtime.run()
            mock_thread.assert_not_called()

    def test_run_cas_prevents_double_start(self):
        """run() n'enqueue pas si l'exécution est déjà RUNNING."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        # No steps enqueued
        assert RunnableStep.objects.filter(execution=execution).count() == 0

    def test_run_empty_workflow_marks_failed(self):
        """run() avec un workflow sans steps marque l'exécution FAILED."""
        execution = _make_execution([])

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED
        assert "no steps" in execution.error_message.lower()

    def test_run_fan_out_enqueues_single_root(self):
        """run() avec fan-out enqueue le seul root step (step-a)."""
        steps = _steps_with_fan_out()
        execution = _make_execution(steps)

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        runnables = RunnableStep.objects.filter(execution=execution)
        assert runnables.count() == 1
        assert runnables.first().execution_step.config_step_id == "step-a"


# ===========================================================================
# 2. Tests du worker d'orchestration (AC2)
# ===========================================================================

@pytest.mark.django_db
class TestAC2OrchestrationWorker:
    """AC2 : Orchestration worker claim → execute → persist → enqueue next."""

    def _setup_running_execution_with_pending_step(self, steps, step_id="step-a"):
        """Create a RUNNING execution with a PENDING step enqueued."""
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step_config = next(s for s in steps if s["step_id"] == step_id)
        step_type = step_config.get("step_type", "platform")

        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        db_step_type = ContainerWorkflowRuntime._STEP_TYPE_TO_DB_TYPE.get(
            step_type, ExecutionStepType.PLATFORM
        )

        exec_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name=step_config["name"],
            config_step_id=step_id,
            step_type=db_step_type,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(exec_step)
        return execution, exec_step

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_processes_single_step(self, mock_execute):
        """Worker claims and executes a single step."""
        mock_execute.return_value = {"status": ExecutionStatus.COMPLETED, "raw_output": {}}

        steps = _simple_sequential_steps()
        execution, exec_step = self._setup_running_execution_with_pending_step(steps)

        from executions.tasks.orchestration_worker import process_runnable_steps
        result = process_runnable_steps(batch_size=1)

        assert result["processed"] == 1
        exec_step.refresh_from_db()
        assert exec_step.status == ExecutionStepStatus.COMPLETED

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_enqueues_next_steps(self, mock_execute):
        """Worker enqueues next steps after completion."""
        mock_execute.return_value = {"status": ExecutionStatus.COMPLETED, "raw_output": {}}

        steps = _simple_sequential_steps()
        execution, _ = self._setup_running_execution_with_pending_step(steps)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        # Next step (step-b) should be enqueued
        runnables = RunnableStep.objects.filter(execution=execution)
        assert runnables.count() == 1
        assert runnables.first().execution_step.config_step_id == "step-b"

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_finalizes_execution_on_last_step(self, mock_execute):
        """Worker finalizes execution when no more steps to enqueue."""
        mock_execute.return_value = {"status": ExecutionStatus.COMPLETED, "raw_output": {}}

        # Single step workflow
        steps = [{"step_id": "only-step", "name": "Only Step", "order": 1, "step_type": "evaluation"}]
        execution, _ = self._setup_running_execution_with_pending_step(steps, step_id="only-step")

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_handles_step_failure(self, mock_execute):
        """Worker handles step failure and finalizes execution."""
        mock_execute.return_value = {"status": ExecutionStatus.FAILED, "raw_output": {}}

        steps = [{"step_id": "fail-step", "name": "Fail Step", "order": 1, "step_type": "evaluation"}]
        execution, exec_step = self._setup_running_execution_with_pending_step(steps, step_id="fail-step")

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        exec_step.refresh_from_db()
        assert exec_step.status == ExecutionStepStatus.FAILED

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

    @patch('executions.step_handlers.gate_handler.GateHandler.execute')
    def test_worker_gate_step_pauses(self, mock_execute):
        """Worker gate step sets WAITING and doesn't enqueue next steps."""
        mock_execute.return_value = {
            "waiting": True,
            "gate_output": {"gate_conditions": [{"type": "approval_granted", "satisfied": False}]},
        }

        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        # Create the gate step as PENDING
        exec_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=2,
            step_name="Gate Step",
            config_step_id="gate-step",
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(exec_step)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        exec_step.refresh_from_db()
        assert exec_step.status == ExecutionStepStatus.WAITING

        # No next steps should be enqueued (waiting for approve command)
        runnables = RunnableStep.objects.filter(execution=execution)
        assert runnables.count() == 0

        # Execution should still be RUNNING
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.RUNNING

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_error_path_routing(self, mock_execute):
        """Worker routes to error path on step failure with on_error_step_ids."""
        mock_execute.return_value = {"status": ExecutionStatus.FAILED, "raw_output": {}}

        steps = _steps_with_error_path()
        execution, _ = self._setup_running_execution_with_pending_step(steps)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        # Error step should be enqueued
        runnables = RunnableStep.objects.filter(execution=execution)
        assert runnables.count() == 1
        assert runnables.first().execution_step.config_step_id == "error-step"

    def test_worker_no_runnable_steps(self):
        """Worker returns 0 processed when no steps to claim."""
        from executions.tasks.orchestration_worker import process_runnable_steps
        result = process_runnable_steps(batch_size=5)
        assert result["processed"] == 0

    def test_worker_via_celery_apply(self):
        """Worker invoked via Celery .apply() (bind=True passes self)."""
        from executions.tasks.orchestration_worker import process_runnable_steps
        result = process_runnable_steps.apply(kwargs={"batch_size": 5})
        assert result.result["processed"] == 0

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_skips_non_running_execution(self, mock_execute):
        """Worker skips steps for executions that are no longer RUNNING."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        exec_step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Step A",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(exec_step)

        # Cancel execution before worker processes
        Execution.objects.filter(id=execution.id).update(status=ExecutionStatus.CANCELLED)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        # Step skipped (execution not RUNNING)
        mock_execute.assert_not_called()
        # Runnable step should be cleaned up
        assert RunnableStep.objects.filter(execution=execution).count() == 0


# ===========================================================================
# 3. Tests de _dispatch_command() handlers (AC2, AC3)
# ===========================================================================

@pytest.mark.django_db
class TestAC3DispatchCommandHandlers:
    """AC2/AC3 : _dispatch_command handlers approve/reject/cancel/timeout/resume."""

    def _make_waiting_step(self, execution):
        """Create a WAITING gate step."""
        return ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name="Gate Step",
            config_step_id="gate-step",
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
            started_at=timezone.now(),
        )

    def test_approve_step_waiting_to_completed(self):
        """approve: step WAITING → COMPLETED."""
        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = self._make_waiting_step(execution)

        cmd = _make_command(
            execution=execution,
            command_type="approve",
            payload={"step_id": step.id, "comment": "Approved"},
        )

        WorkflowCommandService._dispatch_command(cmd)

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED
        assert step.approval_comment == "Approved"

    def test_approve_enqueues_next_steps(self):
        """approve: enqueue on_success_step_ids."""
        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = self._make_waiting_step(execution)

        cmd = _make_command(
            execution=execution,
            command_type="approve",
            payload={"step_id": step.id},
        )

        WorkflowCommandService._dispatch_command(cmd)

        # step-c should be enqueued
        next_steps = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id="step-c",
        )
        assert next_steps.count() == 1
        assert next_steps.first().status == ExecutionStepStatus.PENDING

    def test_approve_idempotent_already_completed(self):
        """approve: step already COMPLETED → no error."""
        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Gate Step",
            config_step_id="gate-step", step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(), completed_at=timezone.now(),
        )

        cmd = _make_command(
            execution=execution,
            command_type="approve",
            payload={"step_id": step.id},
        )

        # Should not raise
        WorkflowCommandService._dispatch_command(cmd)
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED

    def test_reject_step_waiting_to_failed(self):
        """reject: step WAITING → FAILED."""
        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = self._make_waiting_step(execution)

        cmd = _make_command(
            execution=execution,
            command_type="reject",
            payload={"step_id": step.id, "comment": "Rejected"},
        )

        WorkflowCommandService._dispatch_command(cmd)

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert step.approval_comment == "Rejected"

    def test_reject_no_error_path_fails_execution(self):
        """reject: no on_error_step_ids → execution FAILED."""
        steps = _steps_with_gate()
        # Remove on_error_step_ids from gate step
        for s in steps:
            s.pop("on_error_step_ids", None)
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = self._make_waiting_step(execution)

        cmd = _make_command(
            execution=execution,
            command_type="reject",
            payload={"step_id": step.id},
        )

        WorkflowCommandService._dispatch_command(cmd)

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

    def test_cancel_execution_to_cancelled(self):
        """cancel: execution RUNNING → CANCELLED."""
        execution = ExecutionFactory(status=ExecutionStatus.RUNNING)

        cmd = _make_command(
            execution=execution,
            command_type="cancel",
            payload={},
        )

        WorkflowCommandService._dispatch_command(cmd)

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED

    def test_cancel_clears_pending_steps(self):
        """cancel: pending/waiting steps are cancelled."""
        execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        pending_step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Pending Step",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(pending_step)

        cmd = _make_command(
            execution=execution,
            command_type="cancel",
            payload={},
        )

        WorkflowCommandService._dispatch_command(cmd)

        pending_step.refresh_from_db()
        assert pending_step.status == ExecutionStepStatus.FAILED

        # Runnable steps should be cleared
        assert RunnableStep.objects.filter(execution=execution).count() == 0

    def test_cancel_idempotent_already_cancelled(self):
        """cancel: already CANCELLED → no error."""
        execution = ExecutionFactory(status=ExecutionStatus.CANCELLED)

        cmd = _make_command(
            execution=execution,
            command_type="cancel",
            payload={},
        )

        # Should not raise
        WorkflowCommandService._dispatch_command(cmd)
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED

    def test_timeout_step_waiting_to_failed(self):
        """timeout_signal: step WAITING → FAILED."""
        steps = _steps_with_gate()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)
        step = self._make_waiting_step(execution)

        cmd = _make_command(
            execution=execution,
            command_type="timeout_signal",
            payload={"step_id": step.id},
        )

        WorkflowCommandService._dispatch_command(cmd)

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert "timed out" in step.error_message.lower()

    def test_resume_signal_enqueues_steps(self):
        """resume_signal: enqueues specified step_ids."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        cmd = _make_command(
            execution=execution,
            command_type="resume_signal",
            payload={"step_ids": ["step-b"]},
        )

        WorkflowCommandService._dispatch_command(cmd)

        next_steps = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id="step-b",
        )
        assert next_steps.count() == 1
        assert next_steps.first().status == ExecutionStepStatus.PENDING


# ===========================================================================
# 4. Tests d'idempotence (AC4)
# ===========================================================================

@pytest.mark.django_db
class TestAC4Idempotence:
    """AC4 : Idempotence — command déjà processed → skip, step déjà COMPLETED → skip."""

    def test_command_already_processed_skipped(self):
        """process_pending_commands ne re-traite pas les commandes PROCESSED."""
        execution = ExecutionFactory()
        _make_command(
            execution=execution,
            status=WorkflowCommandStatus.PROCESSED,
        )

        count = WorkflowCommandService.process_pending_commands()
        assert count == 0

    def test_worker_skips_completed_step(self):
        """Worker skip les steps déjà COMPLETED."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        exec_step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Step A",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(), completed_at=timezone.now(),
        )
        RunnableStepService.enqueue(exec_step)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        # Processed (dequeued) but handler not called (skipped)
        assert RunnableStep.objects.filter(execution=execution).count() == 0

    def test_enqueue_next_step_idempotent(self):
        """_enqueue_next_steps ne crée pas de doublon si le step existe déjà."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        # Pre-create step-b as PENDING
        ExecutionStep.objects.create(
            execution=execution, step_order=2, step_name="Step B",
            config_step_id="step-b", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )

        from executions.tasks.orchestration_worker import _enqueue_next_steps
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        runtime = ContainerWorkflowRuntime(execution)

        step_config_by_id = {
            s["step_id"]: s for s in steps
        }
        count = _enqueue_next_steps(runtime, execution, ["step-b"], step_config_by_id)
        assert count == 0  # No new step created (already exists)


# ===========================================================================
# 5. Tests de crash recovery (AC4)
# ===========================================================================

@pytest.mark.django_db
class TestAC4CrashRecovery:
    """AC4 : Crash recovery — état reconstruit depuis DB."""

    def test_reclaim_expired_leases(self):
        """Expired leases are reclaimed for re-processing."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        exec_step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Step A",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )
        runnable = RunnableStepService.enqueue(exec_step)

        # Simulate a claimed step with expired lease
        expired_time = timezone.now() - timedelta(minutes=10)
        RunnableStep.objects.filter(id=runnable.id).update(
            claimed_at=expired_time,
            claimed_by="dead-worker",
            claimed_until=expired_time,
            attempt_no=1,
        )

        # Reclaim
        reclaimed = RunnableStepService.reclaim_expired_leases()
        assert reclaimed == 1

        # Step should be claimable again
        runnable.refresh_from_db()
        assert runnable.claimed_at is None
        assert runnable.claimed_by is None
        assert runnable.attempt_no == 1  # Preserved for tracking

    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_worker_reconstructs_step_outputs_from_db(self, mock_execute):
        """Worker reconstructs _step_outputs from completed steps in DB."""
        mock_execute.return_value = {"status": ExecutionStatus.COMPLETED, "raw_output": {"result": "done"}}

        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        # Simulate step-a already completed with output
        ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Step A",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(), completed_at=timezone.now(),
            output=json.dumps({"extracted_output": {"key": "value"}}),
        )

        # Create pending step-b
        exec_step = ExecutionStep.objects.create(
            execution=execution, step_order=2, step_name="Step B",
            config_step_id="step-b", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(exec_step)

        from executions.tasks.orchestration_worker import process_runnable_steps
        process_runnable_steps(batch_size=1)

        # Handler was called (step executed successfully)
        mock_execute.assert_called_once()

        exec_step.refresh_from_db()
        assert exec_step.status == ExecutionStepStatus.COMPLETED

    def test_claim_with_skip_locked_prevents_double_execution(self):
        """Two workers claiming the same step — only one succeeds."""
        steps = _simple_sequential_steps()
        execution = _make_execution(steps, status=ExecutionStatus.RUNNING)

        exec_step = ExecutionStep.objects.create(
            execution=execution, step_order=1, step_name="Step A",
            config_step_id="step-a", step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.PENDING,
        )
        RunnableStepService.enqueue(exec_step)

        # First claim
        claimed1 = RunnableStepService.claim_batch("worker-1", limit=1)
        assert len(claimed1) == 1

        # Second claim — should get nothing (skip locked)
        claimed2 = RunnableStepService.claim_batch("worker-2", limit=1)
        assert len(claimed2) == 0


# ===========================================================================
# Regression: existing 78.1-78.4 tests should still pass
# ===========================================================================

@pytest.mark.django_db
class TestRegression784:
    """Vérifier que les tests existants de 78.1–78.4 ne régressent pas."""

    def test_runnable_step_enqueue_idempotent(self):
        """RunnableStepService.enqueue() est idempotent (78.2)."""
        step = ExecutionStepFactory(status=ExecutionStepStatus.PENDING)
        r1 = RunnableStepService.enqueue(step)
        r2 = RunnableStepService.enqueue(step)
        assert r1 is not None
        assert r2 is None  # Duplicate → None

    def test_workflow_command_write(self):
        """WorkflowCommandService.write_command() crée une commande pending (78.4)."""
        execution = ExecutionFactory()
        cmd = WorkflowCommandService.write_command(
            execution.id, "approve", {"step_id": 123}, "user@test.com"
        )
        assert cmd.status == WorkflowCommandStatus.PENDING
        assert cmd.command_type == "approve"
        assert cmd.payload == {"step_id": 123}
