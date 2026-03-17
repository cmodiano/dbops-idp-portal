"""
PlatformStepExecutor — Dispatch plateforme pour ContainerWorkflowRuntime (Story 88.5).

Responsabilité unique : exécuter un step de type 'platform' dans un workflow conteneurisé.
Extrait de ContainerWorkflowRuntime (SMELL-BE-01) selon le pattern SOLID-BE-2 (Story 34.7).

Note d'implémentation : les symboles patchables dans les tests (SimulationService,
trigger_platform_job, get_platform_queue, logger) sont accédés via le module
executions.container_workflow_runtime (comme dans le code d'origine) pour maintenir
la compatibilité avec les patches de tests existants.
"""
import threading
import time
from typing import Any, Callable, Dict, cast

import executions.container_workflow_runtime as _cwr_module

from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus, ExecutionStepType,
)
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from executions.domain.state_machine import assert_step_transition
from executions.container_workflow_runtime import (
    PLATFORM_ACTION_POLL_INTERVAL_SECONDS,
    PLATFORM_ACTION_MAX_WAIT_SECONDS,
    ParallelContext,
    _broadcast_step,
)

from django.db import transaction
from django.utils import timezone
from catalog.models import Action, ActionItemType, ActionStatus


class PlatformStepExecutor:
    """
    Exécuteur de steps de type 'platform' pour ContainerWorkflowRuntime.

    Responsabilité : validation de l'action référencée, création de l'exécution enfant,
    dispatch (simulation ou production), extraction des outputs.

    Instancié par ContainerWorkflowRuntime.__init__ et utilisé via délégation.
    Les références partagées (child_executions, step_outputs, locks) sont transmises
    par le constructeur et modifiées in-place pour garantir la thread-safety.
    """

    def __init__(
        self,
        execution: Execution,
        execution_service: ExecutionService,
        correlation_id: str | None,
        child_executions: list,
        step_outputs: dict,
        step_outputs_lock: threading.Lock,
        step_lock: threading.Lock,
        get_step_parameters: Callable,
    ):
        self.execution = execution
        self.execution_service = execution_service
        self.correlation_id = correlation_id
        self.child_executions = child_executions
        self._step_outputs = step_outputs
        self._step_outputs_lock = step_outputs_lock
        self._step_lock = step_lock
        self._get_step_parameters = get_step_parameters

    def _validate_and_load_referenced_action(
        self, step_def_order: int, referenced_action_id: Any, parent_step: ExecutionStep,
    ) -> Action | None:
        """
        Validate and load the referenced action for a platform step.

        Story 71.6: Extracted from _execute_platform_step (subtask 9.1).

        Returns:
            The Action instance, or None if validation/lookup failed (parent_step marked FAILED).
        """
        if not referenced_action_id:
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = f"Step {step_def_order} missing referenced_action_id"
            parent_step.set_output({"logs": f"[ERROR] Step {step_def_order} missing referenced_action_id"})
            parent_step.save()
            return None

        try:
            return cast(Action, Action.objects.select_related('integration').get(
                id=referenced_action_id, status=ActionStatus.PUBLISHED,
            ))
        except Action.DoesNotExist:
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = (
                f"Referenced action {referenced_action_id} not found or not published "
                f"for step {step_def_order}"
            )
            parent_step.set_output({"logs": f"[ERROR] Referenced action {referenced_action_id} not found or not published"})
            parent_step.save()
            _cwr_module.logger.error(
                "container_workflow_referenced_action_not_found",
                execution_id=self.execution.id,
                referenced_action_id=referenced_action_id,
                step_order=step_def_order,
                correlation_id=self.correlation_id,
            )
            return None

    def _create_child_execution(
        self,
        referenced_action: Action,
        child_params: dict,
        parent_step: ExecutionStep,
        parallel_context: ParallelContext | None,
    ) -> Execution:
        """
        Create a child execution and register it for cascade cancellation.

        Story 71.6: Extracted from _execute_platform_step (subtask 9.2).
        """
        exec_req = ExecutionRequest(
            user=self.execution.user,
            action=referenced_action,
            environment=self.execution.environment,
            parameters=child_params if child_params else None,
            parent_execution_id=self.execution.id,
            correlation_id=self.correlation_id,
        )
        child_execution: Execution = self.execution_service.create_execution(exec_req)
        if parallel_context is not None:
            with self._step_lock:
                self.child_executions.append(child_execution)
        else:
            self.child_executions.append(child_execution)

        parent_step.platform_job_id = str(child_execution.id)
        parent_step.save(update_fields=['platform_job_id'])
        return child_execution

    def _run_child_execution(self, child_execution: Execution, integration: Any = None) -> None:
        """
        Run the child execution (simulation or production fallback).

        Story 71.6: Extracted from _execute_platform_step (subtask 9.3).
        Story 77.3: Added integration parameter for real platform dispatch.

        Note: SimulationService, trigger_platform_job, get_platform_queue are accessed via
        _cwr_module to enable test patching via executions.container_workflow_runtime.
        """
        if _cwr_module.SimulationService.is_enabled():  # type: ignore[attr-defined]
            _cwr_module.SimulationService.create_simulated_steps(child_execution)  # type: ignore[attr-defined]
            try:
                _cwr_module.SimulationService._run_simulation(child_execution.id, force_success=True)  # type: ignore[attr-defined]
            except Exception as sim_error:  # noqa: BLE001 — catch-all-mark-failed
                _cwr_module.logger.error(
                    "container_workflow_simulation_failed",
                    child_execution_id=child_execution.id,
                    parent_execution_id=self.execution.id,
                    error=str(sim_error),
                    correlation_id=self.correlation_id,
                    exc_info=True,
                )
                now = timezone.now()
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.FAILED,
                    started_at=now,
                    completed_at=now,
                    error_message=f"Simulation failed: {sim_error}",
                )
        else:
            # Run the child execution via the real action path (Story 71.7).
            # For workflows, run_sync blocks until completion; for other types,
            # no runtime is registered — keep placeholder behavior.
            action = child_execution.action
            if action and action.item_type == ActionItemType.WORKFLOW:
                try:
                    # Import local pour éviter le cycle (platform_step_executor ← container_workflow_runtime ← platform_step_executor)  # noqa: PLC0415
                    from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
                    ContainerWorkflowRuntime(child_execution).run_sync()
                except Exception as run_err:  # noqa: BLE001
                    _cwr_module.logger.error(
                        "container_workflow_child_execution_run_failed",
                        child_execution_id=child_execution.id,
                        parent_execution_id=self.execution.id,
                        error=str(run_err),
                        correlation_id=self.correlation_id,
                        exc_info=True,
                    )
                    now = timezone.now()
                    Execution.objects.filter(id=child_execution.id).update(
                        status=ExecutionStatus.FAILED,
                        started_at=now,
                        completed_at=now,
                        error_message=str(run_err),
                    )
            else:
                # Story 77.3: Real dispatch for item_type='action' via platform job.
                if integration is None:
                    # AC2: No integration configured — mark child FAILED explicitly
                    now = timezone.now()
                    Execution.objects.filter(id=child_execution.id).update(
                        status=ExecutionStatus.FAILED,
                        started_at=now,
                        completed_at=now,
                        error_message="Action has no integration configured",
                    )
                    _cwr_module.logger.error(
                        "container_workflow_platform_action_no_integration",
                        child_execution_id=child_execution.id,
                        parent_execution_id=self.execution.id,
                        correlation_id=self.correlation_id,
                    )
                    return

                # AC1: Integration available — dispatch real platform job
                # Create an ExecutionStep on the child execution for the platform job tracker
                child_step = ExecutionStep.objects.create(
                    execution=child_execution,
                    step_order=1,
                    step_name="Platform Job",
                    step_type=ExecutionStepType.PLATFORM,
                    status=ExecutionStepStatus.RUNNING,
                    started_at=timezone.now(),
                )

                # Set child execution to RUNNING
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.RUNNING,
                    started_at=timezone.now(),
                )

                # Build trigger_kwargs from child execution parameters
                params = child_execution.get_parameters() or {}
                trigger_kwargs: dict = {"correlation_id": self.correlation_id}
                if params.get("template_id"):
                    trigger_kwargs["template_id"] = str(params["template_id"])
                if params.get("resource_type"):
                    trigger_kwargs["resource_type"] = params["resource_type"]
                if params.get("extra_vars"):
                    trigger_kwargs["extra_vars"] = params["extra_vars"]

                _cwr_module.trigger_platform_job.apply_async(  # type: ignore[attr-defined]
                    kwargs={
                        "execution_step_id": child_step.id,
                        "execution_id": child_execution.id,
                        "integration_id": integration.id,
                        "trigger_kwargs": trigger_kwargs,
                    },
                    queue=_cwr_module.get_platform_queue(integration.type),  # type: ignore[attr-defined]
                )

                _cwr_module.logger.info(
                    "container_workflow_platform_action_dispatched",
                    child_execution_id=child_execution.id,
                    parent_execution_id=self.execution.id,
                    integration_id=integration.id,
                    child_step_id=child_step.id,
                    correlation_id=self.correlation_id,
                )

                # Poll child_step.status until terminal or timeout (Task 4)
                elapsed = 0
                while elapsed < PLATFORM_ACTION_MAX_WAIT_SECONDS:
                    child_step.refresh_from_db()
                    if child_step.status in (
                        ExecutionStepStatus.COMPLETED,
                        ExecutionStepStatus.FAILED,
                    ):
                        break
                    time.sleep(PLATFORM_ACTION_POLL_INTERVAL_SECONDS)
                    elapsed += PLATFORM_ACTION_POLL_INTERVAL_SECONDS
                else:
                    # Timeout: mark step and execution as FAILED
                    ExecutionStep.objects.filter(id=child_step.id).update(
                        status=ExecutionStepStatus.FAILED,
                        completed_at=timezone.now(),
                        error_message="Platform action wait timeout",
                    )
                    child_step.refresh_from_db()
                    _cwr_module.logger.error(
                        "container_workflow_platform_action_timeout",
                        child_execution_id=child_execution.id,
                        parent_execution_id=self.execution.id,
                        elapsed=elapsed,
                        correlation_id=self.correlation_id,
                    )

                # Derive final child execution status from child_step.status
                final_exec_status = (
                    ExecutionStatus.COMPLETED
                    if child_step.status == ExecutionStepStatus.COMPLETED
                    else ExecutionStatus.FAILED
                )
                Execution.objects.filter(id=child_execution.id).update(
                    status=final_exec_status,
                    completed_at=timezone.now(),
                )
                child_execution.refresh_from_db()

    def execute_platform_step(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
        step_order_counter: int,
        parallel_context: ParallelContext | None = None,
    ) -> ExecutionStatus:
        """
        Execute a platform step: validate action, create child execution, run it, extract outputs.

        Story 71.6: Unified sequential/parallel + sub-operations extracted.
        Story 88.5: Extracted from ContainerWorkflowRuntime (SMELL-BE-01).
        """
        step_def_order = step.get('order', 0)
        step_order = parallel_context.step_order if parallel_context else step_order_counter

        # Story 71.7 AC#4: Transaction 1 — step creation + validation
        with transaction.atomic():
            parent_step = ExecutionStep.objects.create(
                execution=self.execution,
                step_order=step_order,
                step_name=step_name,
                config_step_id=step_id,
                step_type=ExecutionStepType.PLATFORM,
                status=ExecutionStepStatus.RUNNING,
                started_at=timezone.now(),
            )

            referenced_action = self._validate_and_load_referenced_action(
                step_def_order, step.get('referenced_action_id'), parent_step,
            )
            if referenced_action is None:
                _broadcast_step(self.execution.id, parent_step)
                return ExecutionStatus.FAILED

        _broadcast_step(self.execution.id, parent_step)  # RUNNING

        # Story 77.3: Extract integration pre-loaded via select_related
        integration = getattr(referenced_action, 'integration', None)

        # Pure computation outside transaction to minimize lock duration
        child_params = self._get_step_parameters(step)
        if resolved_params:
            child_params = {**child_params, **resolved_params}

        child_execution = None
        try:
            child_execution = self._create_child_execution(
                referenced_action, child_params, parent_step, parallel_context,
            )

            _cwr_module.logger.info(
                "container_workflow_child_execution_created",
                parent_execution_id=self.execution.id,
                child_execution_id=child_execution.id,
                referenced_action_id=referenced_action.id,
                referenced_action_name=referenced_action.name,
                step_order=step_def_order,
                has_step_params=bool(child_params),
                correlation_id=self.correlation_id,
            )

            # Execution runs OUTSIDE transaction (can be long-running)
            self._run_child_execution(child_execution, integration=integration)
            child_execution.refresh_from_db()

            # Story 71.7 AC#4: Transaction 2 — finalize parent_step after execution
            with transaction.atomic():
                final_step_status = (
                    ExecutionStepStatus.FAILED
                    if child_execution.status == ExecutionStatus.FAILED
                    else ExecutionStepStatus.COMPLETED
                )
                parent_step.status = final_step_status
                parent_step.completed_at = timezone.now()

                # Story 77.4: Enrich raw_output with real platform artifacts from child_step.
                # child_platform_output may contain: artifacts, job_status, platform_logs,
                # outputs, failed_tasks, changed_hosts, platform_job_id, etc.
                # Guard: only query for item_type=ACTION — _run_child_execution creates exactly
                # one PLATFORM tracking step in that case. For WORKFLOW items, the child
                # execution may have its own PLATFORM steps (from its internal workflow steps)
                # which must NOT be merged into the outer raw_output (AC3).
                if referenced_action.item_type == ActionItemType.ACTION:
                    child_platform_step = (
                        ExecutionStep.objects.filter(
                            execution=child_execution,
                            step_type=ExecutionStepType.PLATFORM,
                        )
                        .order_by('step_order')
                        .first()
                    )
                else:
                    child_platform_step = None
                child_platform_output = child_platform_step.get_output() if child_platform_step else {}

                raw_output = {
                    # Story 77.4: real platform data (artifacts, outputs, job_status, etc.) — merged first
                    **(child_platform_output or {}),
                    # Metadata fields — always present, take priority over any conflicting keys
                    'child_execution_id': child_execution.id,
                    'referenced_action_id': referenced_action.id,
                    'referenced_action_name': referenced_action.name,
                    'child_status': child_execution.status,
                    'parameters_injected': bool(child_params),
                }
                output_mapping = step.get('output_mapping', {})
                if output_mapping and not isinstance(output_mapping, dict):
                    _cwr_module.logger.warning(
                        "container_workflow_output_mapping_not_dict",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        output_mapping_type=type(output_mapping).__name__,
                        correlation_id=self.correlation_id,
                    )
                    output_mapping = {}
                extractor = _cwr_module.OutputExtractor()  # type: ignore[attr-defined]
                extracted = extractor.extract(raw_output, output_mapping)
                parent_step.set_output({
                    'raw_output': raw_output,
                    'extracted_output': extracted,
                    'status_context': {
                        'status': final_step_status,
                        'completed_at': parent_step.completed_at.isoformat(),
                    },
                })
                parent_step.save()

            _broadcast_step(self.execution.id, parent_step)  # COMPLETED or FAILED

            if step_id is not None:
                with self._step_outputs_lock:
                    self._step_outputs[step_id] = extracted

            return cast(ExecutionStatus, child_execution.status)
        except Exception as exc:  # noqa: BLE001
            # Story 71.7 AC#4: Atomic error handling for parent_step + child_execution
            with transaction.atomic():
                parent_step.status = ExecutionStepStatus.FAILED
                parent_step.completed_at = timezone.now()
                parent_step.error_message = f"Platform step failed: {exc}"
                parent_step.set_output({"logs": f"[ERROR] Platform step failed: {exc}"})
                parent_step.save()
                if child_execution is not None:
                    now = timezone.now()
                    Execution.objects.filter(id=child_execution.id).update(
                        status=ExecutionStatus.FAILED,
                        started_at=now,
                        completed_at=now,
                        error_message=str(exc),
                    )
            _broadcast_step(self.execution.id, parent_step)  # FAILED
            _cwr_module.logger.error(
                "container_workflow_platform_step_exception",
                execution_id=self.execution.id,
                step_def_order=step_def_order,
                correlation_id=self.correlation_id,
                error=str(exc),
                exc_info=True,
            )
            return ExecutionStatus.FAILED

    def execute_worker_platform_step(
        self,
        exec_step: ExecutionStep,
        step_config: dict,
        resolved_params: dict,
    ) -> ExecutionStatus:
        """
        Story 78.5: Execute a platform step using a pre-existing ExecutionStep.
        Story 88.5: Extracted from ContainerWorkflowRuntime (SMELL-BE-01).
        """
        step_id = step_config.get('step_id')
        referenced_action_id = step_config.get('referenced_action_id')

        referenced_action = self._validate_and_load_referenced_action(
            step_config.get('order', 0), referenced_action_id, exec_step,
        )
        if referenced_action is None:
            _broadcast_step(self.execution.id, exec_step)
            return ExecutionStatus.FAILED

        integration = getattr(referenced_action, 'integration', None)
        child_params = self._get_step_parameters(step_config)
        if resolved_params:
            child_params = {**child_params, **resolved_params}

        child_execution = None
        try:
            child_execution = self._create_child_execution(
                referenced_action, child_params, exec_step, None,
            )
            self._run_child_execution(child_execution, integration)
            child_execution.refresh_from_db()

            final_step_status = (
                ExecutionStepStatus.COMPLETED
                if child_execution.status == ExecutionStatus.COMPLETED
                else ExecutionStepStatus.FAILED
            )
            assert_step_transition(exec_step.status, final_step_status)
            exec_step.status = final_step_status
            exec_step.completed_at = timezone.now()

            # Extract and store output
            raw_output = {
                'child_execution_id': child_execution.id,
                'referenced_action_id': referenced_action.id,
                'referenced_action_name': referenced_action.name,
                'child_status': child_execution.status,
                'parameters_injected': bool(child_params),
            }
            output_mapping = step_config.get('output_mapping', {})
            if not isinstance(output_mapping, dict):
                output_mapping = {}
            extractor = _cwr_module.OutputExtractor()  # type: ignore[attr-defined]
            extracted = extractor.extract(raw_output, output_mapping)
            exec_step.set_output({
                'raw_output': raw_output,
                'extracted_output': extracted,
                'status_context': {
                    'status': final_step_status,
                    'completed_at': exec_step.completed_at.isoformat(),
                },
            })
            exec_step.save()
            _broadcast_step(self.execution.id, exec_step)

            if step_id is not None:
                with self._step_outputs_lock:
                    self._step_outputs[step_id] = extracted

            return cast(ExecutionStatus, child_execution.status)
        except Exception as exc:  # noqa: BLE001
            with transaction.atomic():
                assert_step_transition(exec_step.status, ExecutionStepStatus.FAILED)
                exec_step.status = ExecutionStepStatus.FAILED
                exec_step.completed_at = timezone.now()
                exec_step.error_message = f"Platform step failed: {exc}"
                exec_step.set_output({"logs": f"[ERROR] Platform step failed: {exc}"})
                exec_step.save()
                if child_execution is not None:
                    now = timezone.now()
                    Execution.objects.filter(id=child_execution.id).update(
                        status=ExecutionStatus.FAILED, started_at=now,
                        completed_at=now, error_message=str(exc),
                    )
            _broadcast_step(self.execution.id, exec_step)
            _cwr_module.logger.error(
                "worker_platform_step_exception",
                execution_id=self.execution.id,
                step_id=step_config.get('step_id'),
                error=str(exc),
                correlation_id=self.correlation_id,
                exc_info=True,
            )
            return ExecutionStatus.FAILED
