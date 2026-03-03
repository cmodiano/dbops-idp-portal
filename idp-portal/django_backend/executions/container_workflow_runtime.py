"""
Container Workflow Runtime Engine - Story 20.6 (Tasks 3.1–3.5)

Orchestrates execution of container workflows: workflows whose steps reference
other actions (via referenced_action_id). Each step creates a child execution
(with parent_execution_id) for full traceability, cancellation cascade, and
log aggregation.

Integrates with the existing WorkflowRuntime (Story 16.3) by reusing loop
detection, state management, and audit trail patterns.

Architecture:
- ContainerWorkflowRuntime: Orchestrator for container workflows
- Reuses WorkflowExecutionState from workflow_runtime for state tracking
- Uses ExecutionService.create_execution for child executions
- Supports workflow_step_parameters injection (Story 4.12)
"""
# Responsabilité : Runtime des workflows conteneur (exécutions enfants, cascade annulation,
# loop detection, intégration ServiceNow) — volume justifié par la complexité inhérente
# à l'orchestration async multi-étapes (Story 35.4 AC3).

import structlog
from threading import Thread
from typing import Dict, Any, List, Union, cast

from django.db import close_old_connections
from django.utils import timezone

from catalog.models import Action, ActionStatus
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
    ExecutionStepType,
)
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from executions.simulation_service import SimulationService
from executions.cancellation_cache import is_cancelled
from core.exceptions import ServiceUnavailableError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from executions.output_extractor import OutputExtractor
from executions.template_resolver import StepTemplateResolver
from executions.step_handlers.condition_evaluator import StepConditionEvaluator
from executions.step_handlers.service_call_handler import ServiceCallHandler
from executions.step_handlers.http_request_handler import HttpRequestHandler
from executions.step_handlers.evaluation_handler import EvaluationHandler
from executions.step_handlers.gate_handler import GateHandler

logger = structlog.get_logger(__name__)

# Maximum number of step transitions to prevent infinite loops
MAX_STEP_TRANSITIONS = 100


class ContainerWorkflowRuntime:
    """
    Runtime engine for container workflows (Story 20.6).

    A container workflow is an Action with item_type='workflow' whose
    execution_steps reference other actions. Each referenced action is
    executed as a child execution with parent_execution_id linking back
    to the workflow's parent execution.

    Implements:
    - AC1: Sequential execution of referenced actions in step order
    - AC2: Child executions with parent_execution_id for traceability
    - AC3: workflow_step_parameters injection (Story 4.12)
    - AC4: Failure/cancellation propagation
    """

    # Mapping step_type string → ExecutionStepType enum (ADR-007 §3d)
    _STEP_TYPE_TO_DB_TYPE: dict[str, ExecutionStepType] = {
        'platform': ExecutionStepType.PLATFORM,
        'service_call': ExecutionStepType.SERVICE_CALL,
        'http_request': ExecutionStepType.HTTP_REQUEST,
        'evaluation': ExecutionStepType.EVALUATION,
        'gate': ExecutionStepType.GATE,
    }

    def __init__(
        self,
        execution: Execution,
        execution_service: ExecutionService | None = None,
    ):
        """
        Initialize container workflow runtime.

        Args:
            execution:         The parent Execution instance (workflow)
            execution_service: Optional ExecutionService to inject (defaults to
                               a new ExecutionService() for production use).
                               Pass a mock in tests to avoid DB access.
        """
        self.execution = execution
        self.action = execution.action
        self.correlation_id = get_correlation_id()
        self.execution_service = execution_service or ExecutionService()

        # Load workflow steps from action's execution_steps
        self.workflow_steps = self._load_workflow_steps()

        # Track child executions for cascade cancellation
        self.child_executions: List[Execution] = []

        # Step counter for ExecutionStep records on the parent
        self._step_order_counter = 0

        # Transition counter for loop detection
        self._transition_count = 0

        # Contexte partagé des outputs de steps (ADR-007 §3a)
        self._step_outputs: dict[str, dict] = {}

        logger.info(
            "container_workflow_runtime_initialized",
            execution_id=self.execution.id,
            action_id=self.action.id,
            action_name=self.action.name,
            step_count=len(self.workflow_steps),
            correlation_id=self.correlation_id,
        )

    def _load_workflow_steps(self) -> List[Dict[str, Any]]:
        """Load and sort workflow steps from action's execution_steps."""
        steps = self.action.execution_steps or []
        if not isinstance(steps, list):
            logger.warning(
                "container_workflow_steps_invalid_format",
                execution_id=self.execution.id,
                action_id=self.action.id,
                correlation_id=self.correlation_id,
            )
            return []
        # Sort by order
        return sorted(steps, key=lambda s: s.get('order', 0))

    def _get_step_parameters(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get parameters for a workflow step (Story 4.12 AC5 / Story 20.6 AC3).

        Merges workflow_step_parameters[step_order] with global workflow
        parameters to build the child execution's parameter set.

        Args:
            step: Step dict with 'order' key

        Returns:
            Dict of parameters for the child execution
        """
        params = self.execution.get_parameters() or {}

        # Global parameters (excluding internal keys)
        global_params = {
            k: v for k, v in params.items()
            if k not in ('workflow_step_parameters', '_env_config')
        }

        # Step-specific parameters (Story 4.12)
        wsp = params.get("workflow_step_parameters")
        step_params: dict[str, object] = {}
        if isinstance(wsp, dict):
            order_key = str(step.get("order", ""))
            step_entry = wsp.get(order_key)
            if isinstance(step_entry, dict):
                step_params = step_entry.get("parameters") or {}

        # Merge: step params override global params
        merged = {**global_params, **step_params}
        return merged

    def _check_cancelled(self) -> bool:
        """Check if the parent workflow execution has been cancelled."""
        return is_cancelled(self.execution.id)

    def _cancel_child_executions(self) -> None:
        """Cancel all running/submitted child executions (cascade cancellation)."""
        cancellable_statuses = [ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING]
        for child in self.child_executions:
            child.refresh_from_db(fields=['status'])
            if child.status in cancellable_statuses:
                child.status = ExecutionStatus.CANCELLED
                child.completed_at = timezone.now()
                child.save(update_fields=['status', 'completed_at'])

                logger.info(
                    "container_workflow_child_cancelled",
                    parent_execution_id=self.execution.id,
                    child_execution_id=child.id,
                    correlation_id=self.correlation_id,
                )

    def _execute_step(self, step: Dict[str, Any]) -> ExecutionStatus:
        """
        Execute a single container workflow step.

        Orchestrates: input_mapping resolution → condition evaluation →
        step_type dispatch → output_mapping extraction (ADR-007 §3d).

        Args:
            step: Step dict from workflow definition

        Returns:
            ExecutionStatus of the step (COMPLETED for SKIPPED steps)
        """
        step_order = step.get('order', 0)
        step_name = step.get('name') or f"Step {step_order}"
        step_id = step.get('step_id')
        step_type = step.get('step_type') or 'platform'  # ADR-007 §3d, coalesce null/"" to platform

        self._step_order_counter += 1
        self._transition_count += 1

        # Loop detection
        if self._transition_count > MAX_STEP_TRANSITIONS:
            logger.error(
                "container_workflow_loop_detected",
                execution_id=self.execution.id,
                transition_count=self._transition_count,
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.FAILED

        # Résoudre les input_mapping depuis _step_outputs (ADR-007 §3b)
        input_mapping = step.get('input_mapping', {})
        resolved_params: dict = {}
        if input_mapping and isinstance(input_mapping, dict):
            resolver = StepTemplateResolver(self._step_outputs)
            resolved_params = resolver.resolve(input_mapping)
        elif input_mapping and not isinstance(input_mapping, dict):
            logger.warning(
                "container_workflow_input_mapping_not_dict",
                step_id=step_id,
                input_type=type(input_mapping).__name__,
                correlation_id=self.correlation_id,
            )

        logger.info(
            "container_workflow_step_starting",
            execution_id=self.execution.id,
            step_order=step_order,
            step_name=step_name,
            step_type=step_type,
            correlation_id=self.correlation_id,
        )

        # Évaluer la condition (ADR-007 §6)
        condition_evaluator = StepConditionEvaluator()
        if not condition_evaluator.should_execute(step, self.execution):
            return self._create_skipped_step(step_name, step_id, step_type)

        # Dispatcher selon step_type (ADR-007 §3d)
        handler: Union[
            ServiceCallHandler, HttpRequestHandler, EvaluationHandler, GateHandler
        ]
        match step_type:
            case 'platform':
                return self._execute_platform_step(step, resolved_params, step_name, step_id)
            case 'service_call':
                handler = ServiceCallHandler()
            case 'http_request':
                handler = HttpRequestHandler()
            case 'evaluation':
                handler = EvaluationHandler()
            case 'gate':
                handler = GateHandler()
            case _:
                raise ValueError(f"Unknown step_type: {step_type!r}")

        return self._execute_handler_step(step, resolved_params, step_name, step_id, step_type, handler)

    def _execute_platform_step(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
    ) -> ExecutionStatus:
        """
        Logique platform extraite de _execute_step() (ADR-007 §3d).

        Crée une child execution, exécute, met à jour _step_outputs.
        """
        step_order = step.get('order', 0)
        referenced_action_id = step.get('referenced_action_id')

        # Create a tracking step on the parent execution
        parent_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=self._step_order_counter,
            step_name=step_name,
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Validate referenced action
        if not referenced_action_id:
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = f"Step {step_order} missing referenced_action_id"
            parent_step.save()
            return ExecutionStatus.FAILED

        try:
            referenced_action = Action.objects.get(
                id=referenced_action_id,
                status=ActionStatus.PUBLISHED,
            )
        except Action.DoesNotExist:
            error_msg = (
                f"Referenced action {referenced_action_id} not found or not published "
                f"for step {step_order}"
            )
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = error_msg
            parent_step.save()

            logger.error(
                "container_workflow_referenced_action_not_found",
                execution_id=self.execution.id,
                referenced_action_id=referenced_action_id,
                step_order=step_order,
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.FAILED

        # Build child execution parameters (AC3: inject workflow_step_parameters)
        child_params = self._get_step_parameters(step)

        # Fusionner les resolved_params dans child_params (AC5)
        if resolved_params:
            child_params = {**child_params, **resolved_params}

        # Create child execution
        exec_req = ExecutionRequest(
            user=self.execution.user,
            action=referenced_action,
            environment=self.execution.environment,
            parameters=child_params if child_params else None,
            parent_execution_id=self.execution.id,
            correlation_id=self.correlation_id,
        )
        child_execution = self.execution_service.create_execution(exec_req)
        self.child_executions.append(child_execution)

        # Link parent step to child execution
        parent_step.platform_job_id = str(child_execution.id)
        parent_step.save(update_fields=['platform_job_id'])

        logger.info(
            "container_workflow_child_execution_created",
            parent_execution_id=self.execution.id,
            child_execution_id=child_execution.id,
            referenced_action_id=referenced_action.id,
            referenced_action_name=referenced_action.name,
            step_order=step_order,
            has_step_params=bool(child_params),
            correlation_id=self.correlation_id,
        )

        # Execute child: simulation mode creates steps with progressive logs,
        # production mode would use platform adapter (pending).
        # Story 19.6: Create ExecutionSteps for child so drawer can display timeline.
        if SimulationService.is_enabled():
            SimulationService.create_simulated_steps(child_execution)
            # Run simulation synchronously (we're already in a background thread).
            # force_success=True: parent workflow controls the outcome, not random failure.
            # HIGH-2: Wrap simulation in try-except to handle failures explicitly
            try:
                SimulationService._run_simulation(child_execution.id, force_success=True)
            except Exception as sim_error:  # noqa: BLE001 — catch-all-mark-failed: simulation failure marks child FAILED, parent continues
                logger.error(
                    "container_workflow_simulation_failed",
                    child_execution_id=child_execution.id,
                    parent_execution_id=self.execution.id,
                    error=str(sim_error),
                    error_type=type(sim_error).__name__,
                    correlation_id=self.correlation_id,
                    exc_info=True,
                )
                # Mark child as FAILED explicitly before refresh
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.FAILED,
                    completed_at=timezone.now(),
                    error_message=f"Simulation failed: {sim_error}",
                )
        else:
            # Non-simulation fallback: mark child as completed directly
            # MEDIUM-1: Add structured logging for production fallback
            logger.info(
                "container_workflow_child_no_simulation",
                child_execution_id=child_execution.id,
                parent_execution_id=self.execution.id,
                referenced_action_id=referenced_action.id,
                correlation_id=self.correlation_id,
                message="Simulation disabled — using direct status update fallback",
            )
            now = timezone.now()
            Execution.objects.filter(id=child_execution.id).update(
                status=ExecutionStatus.COMPLETED,
                started_at=now,
                completed_at=now,
            )

        # Refresh in-memory object for downstream status check (after all updates)
        child_execution.refresh_from_db()

        # Update parent step to reflect child outcome
        parent_step.status = ExecutionStepStatus.COMPLETED
        parent_step.completed_at = timezone.now()
        parent_step.set_output({
            'child_execution_id': child_execution.id,
            'referenced_action_id': referenced_action.id,
            'referenced_action_name': referenced_action.name,
            'child_status': child_execution.status,
            'parameters_injected': bool(child_params),
        })
        parent_step.save()

        # Extraire les outputs via output_mapping (ADR-007 §3c)
        if step_id is not None:
            output_mapping = step.get('output_mapping', {})
            if not isinstance(output_mapping, dict):
                logger.warning(
                    "container_workflow_output_mapping_not_dict",
                    execution_id=self.execution.id,
                    step_id=step_id,
                    output_mapping_type=type(output_mapping).__name__,
                    correlation_id=self.correlation_id,
                )
                output_mapping = {}
            extractor = OutputExtractor()
            raw_output = parent_step.get_output() or {}
            extracted = extractor.extract(raw_output, output_mapping)
            self._step_outputs[step_id] = extracted
            if extracted:
                logger.info(
                    "container_workflow_step_output_extracted",
                    execution_id=self.execution.id,
                    step_id=step_id,
                    extracted_keys=list(extracted.keys()),
                    correlation_id=self.correlation_id,
                )

        return cast(ExecutionStatus, child_execution.status)

    def _create_skipped_step(
        self,
        step_name: str,
        step_id: str | None,
        step_type: str,
    ) -> ExecutionStatus:
        """
        Crée un ExecutionStep SKIPPED et met à jour _step_outputs (ADR-007 §6).

        Returns:
            ExecutionStatus.COMPLETED — le runtime continue au step suivant.
        """
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)

        now = timezone.now()
        ExecutionStep.objects.create(
            execution=self.execution,
            step_order=self._step_order_counter,
            step_name=step_name,
            step_type=db_step_type,
            status=ExecutionStepStatus.SKIPPED,
            started_at=now,
            completed_at=now,
        )

        # _step_outputs[step_id] = {} pour que les steps suivants obtiennent null
        if step_id is not None:
            self._step_outputs[step_id] = {}

        logger.info(
            "container_workflow_step_skipped",
            execution_id=self.execution.id,
            step_id=step_id,
            step_name=step_name,
            step_type=step_type,
            correlation_id=self.correlation_id,
        )
        # Traité comme SUCCESS par le runtime (continue au step suivant)
        return ExecutionStatus.COMPLETED

    def _execute_handler_step(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
        step_type: str,
        handler: Union[
            ServiceCallHandler, HttpRequestHandler, EvaluationHandler, GateHandler
        ],
    ) -> ExecutionStatus:
        """
        Wrapper générique pour les handlers non-platform (ADR-007 §3d).

        Story 57.3: les handlers lèvent NotImplementedError.
        Stories 57.4–57.7: les handlers retournent {'status': ..., 'raw_output': ...}.
        """
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)

        parent_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=self._step_order_counter,
            step_name=step_name,
            step_type=db_step_type,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        try:
            result = handler.execute(
                step_config=step,
                resolved_params=resolved_params,
                execution=self.execution,
                step=step,
                correlation_id=self.correlation_id,
            )
        except Exception as _e:
            logger.exception(
                "container_workflow_handler_exception",
                step_name=step_name,
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.save()
            raise

        # Protocole WAITING pour gate steps (story 57.7)
        # DOIT précéder l'output_mapping ET le fail-closed :
        # - évite que le gate soit marqué FAILED (fail-closed)
        # - évite que le dict gate {'waiting', 'gate_conditions', ...} pollue _step_outputs
        if isinstance(result, dict) and result.get('waiting'):
            gate_output = result.get('gate_output', {})
            parent_step.set_output(gate_output)
            parent_step.status = ExecutionStepStatus.WAITING
            # NE PAS SET completed_at — step est en attente
            parent_step.save()
            logger.info(
                "container_workflow_gate_step_waiting",
                step_name=step_name,
                step_id=step_id,
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.RUNNING  # Sentinel : boucle doit s'arrêter

        # Extraction output_mapping pour les handlers non-gate (même pattern que platform)
        if step_id is not None:
            output_mapping = step.get('output_mapping', {})
            if not isinstance(output_mapping, dict):
                logger.warning(
                    "container_workflow_output_mapping_not_dict",
                    execution_id=self.execution.id,
                    step_id=step_id,
                    output_mapping_type=type(output_mapping).__name__,
                    correlation_id=self.correlation_id,
                )
                output_mapping = {}
            extractor = OutputExtractor()
            # Handlers peuvent retourner envelope {raw_output: ...} ou dict brut
            if isinstance(result, dict) and 'raw_output' in result:
                raw_output = result.get('raw_output', {}) or {}
            else:
                raw_output = result if isinstance(result, dict) else {}
            extracted = extractor.extract(raw_output, output_mapping)
            self._step_outputs[step_id] = extracted

        # Lire le statut retourné par le handler (ADR-007 §3d — contrat 57.4–57.7)
        # Les handlers retournent {'status': ExecutionStatus, 'raw_output': dict}
        # Fail-closed: missing/invalid handler_status → FAILED
        result_execution_status = ExecutionStatus.FAILED
        if isinstance(result, dict):
            handler_status = result.get('status')
            if isinstance(handler_status, ExecutionStatus):
                result_execution_status = handler_status

        final_step_status = (
            ExecutionStepStatus.FAILED
            if result_execution_status == ExecutionStatus.FAILED
            else ExecutionStepStatus.COMPLETED
        )
        parent_step.status = final_step_status
        parent_step.completed_at = timezone.now()
        parent_step.save()

        return result_execution_status

    def run(self) -> None:
        """
        Start the container workflow execution asynchronously.

        Sets the execution to RUNNING and launches the workflow loop in a
        background daemon thread so the HTTP response returns immediately
        with the execution_id. The frontend can then poll / subscribe via
        WebSocket to follow real-time progress.
        """
        logger.info(
            "container_workflow_execution_starting",
            execution_id=self.execution.id,
            action_id=self.action.id,
            action_name=self.action.name,
            step_count=len(self.workflow_steps),
            correlation_id=self.correlation_id,
        )

        # Story 31.6: Create ServiceNow change if required before RUNNING
        try:
            self._create_servicenow_change_if_required(self.execution.environment)
        except Exception as exc:  # noqa: BLE001 — catch-all-mark-failed: ServiceNow failure marks execution FAILED
            logger.error(
                "execution_servicenow_change_failed",
                execution_id=self.execution.id,
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
            )
            self.execution.status = ExecutionStatus.FAILED
            self.execution.error_message = f"Échec de la création du changement ServiceNow : {exc}"
            self.execution.completed_at = timezone.now()
            self.execution.save(update_fields=['status', 'error_message', 'completed_at'])
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_FAILED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={'reason': 'servicenow_change_creation_failed', 'error': str(exc)},
                correlation_id=self.correlation_id,
            )
            return

        # Update parent to RUNNING immediately (visible to frontend)
        self.execution.status = ExecutionStatus.RUNNING
        self.execution.started_at = timezone.now()
        self.execution.save(update_fields=['status', 'started_at'])

        if not self.workflow_steps:
            logger.error(
                "container_workflow_empty",
                execution_id=self.execution.id,
                action_id=self.action.id,
                correlation_id=self.correlation_id,
            )
            self.execution.status = ExecutionStatus.FAILED
            self.execution.completed_at = timezone.now()
            self.execution.error_message = "Workflow has no steps"
            self.execution.save(update_fields=['status', 'completed_at', 'error_message'])
            return

        # Launch background thread for step-by-step execution
        thread = Thread(
            target=self._run_workflow_loop,
            args=(self.execution.id,),
            daemon=True,
        )
        thread.start()
        logger.info(
            "container_workflow_thread_started",
            execution_id=self.execution.id,
            correlation_id=self.correlation_id,
        )

    def run_sync(self) -> ExecutionStatus:
        """
        Execute the container workflow synchronously (for tests only).

        Identical to run() but blocks until completion. Do NOT use in
        production request handlers — use run() instead.
        """
        logger.info(
            "container_workflow_execution_starting_sync",
            execution_id=self.execution.id,
            action_id=self.action.id,
            step_count=len(self.workflow_steps),
            correlation_id=self.correlation_id,
        )

        # Story 31.6: Create ServiceNow change if required before RUNNING
        try:
            self._create_servicenow_change_if_required(self.execution.environment)
        except Exception as exc:  # noqa: BLE001 — catch-all-mark-failed: ServiceNow failure marks execution FAILED
            logger.error(
                "execution_servicenow_change_failed",
                execution_id=self.execution.id,
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
            )
            self.execution.status = ExecutionStatus.FAILED
            self.execution.error_message = f"Échec de la création du changement ServiceNow : {exc}"
            self.execution.completed_at = timezone.now()
            self.execution.save(update_fields=['status', 'error_message', 'completed_at'])
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_FAILED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={'reason': 'servicenow_change_creation_failed', 'error': str(exc)},
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.FAILED

        self.execution.status = ExecutionStatus.RUNNING
        self.execution.started_at = timezone.now()
        self.execution.save(update_fields=['status', 'started_at'])

        if not self.workflow_steps:
            self.execution.status = ExecutionStatus.FAILED
            self.execution.completed_at = timezone.now()
            self.execution.error_message = "Workflow has no steps"
            self.execution.save(update_fields=['status', 'completed_at', 'error_message'])
            return ExecutionStatus.FAILED

        return self._execute_workflow_steps()

    def _create_servicenow_change_if_required(self, environment: str) -> None:
        """
        Story 31.6 (Partie B): Create a ServiceNow change before RUNNING if required.

        Logic:
        1. Check change_type_config[env].required == True
        2. Resolve ServiceNow integration (gate_config or fallback)
        3. Call ServiceNowService.create_change()
        4. Store change number in execution.servicenow_change_id

        Raises:
            ServiceUnavailableError: if no ServiceNow integration is available when required,
                or if create_change() fails
        """
        from adapters.utils import build_auth_headers
        from services.servicenow_service import ServiceNowService
        from integrations.services import IntegrationService

        change_type_config = self.action.change_type_config or {}
        env_config = change_type_config.get(environment, {})

        if not isinstance(env_config, dict) or not env_config.get('required'):
            return  # No change required for this environment

        # Resolve ServiceNow integration
        gate_config = self.action.gate_config or {}
        servicenow_integration_id = gate_config.get('servicenow_change', {}).get('integration_id')

        integration_service = IntegrationService()

        integration = None
        if servicenow_integration_id:
            integration = integration_service.get_by_id(servicenow_integration_id)
            if not integration or integration.type != 'servicenow':
                logger.warning(
                    "servicenow_gate_integration_not_found",
                    integration_id=servicenow_integration_id,
                    execution_id=self.execution.id,
                )
                integration = None

        if not integration:
            # Fallback: first available servicenow integration
            integration = integration_service.get_by_type('servicenow')

        if not integration:
            logger.warning(
                "servicenow_no_integration_found_skipping",
                execution_id=self.execution.id,
                environment=environment,
            )
            # env_config['required'] is truthy here; missing integration is a hard failure
            raise ServiceUnavailableError(
                code="SERVICENOW_INTEGRATION_MISSING",
                message=(
                    f"ServiceNow change is required for environment {environment!r} but no "
                    "ServiceNow integration is configured or available. Configure an integration in "
                    "Admin > Intégrations and select it in the action's gate config."
                ),
                details={"execution_id": self.execution.id, "environment": environment},
            )

        auth_headers = build_auth_headers(integration, get_correlation_id())
        svc = ServiceNowService(base_url=integration.base_url, auth_headers=auth_headers)
        change_result = svc.create_change(
            change_model_code=env_config.get('change_model_code') or env_config.get('template_id'),
            change_type=env_config.get('change_type'),
            short_description=f"IDP Portal — {self.action.name}",
            description=f"Exécution automatisée {self.execution.id} (env: {environment})",
        )
        change_number = change_result["number"]

        # Store change number
        self.execution.servicenow_change_id = change_number
        self.execution.save(update_fields=['servicenow_change_id'])

        logger.info(
            "servicenow_change_created",
            change_number=change_number,
            execution_id=self.execution.id,
            environment=environment,
            integration_id=integration.id,
        )

    def _run_workflow_loop(self, execution_id: int) -> None:
        """Background workflow execution loop (runs in a daemon thread)."""
        try:
            close_old_connections()

            # Re-load execution from DB in this thread's connection
            self.execution = Execution.objects.select_related('action').get(id=execution_id)
            self.action = self.execution.action
            self.workflow_steps = self._load_workflow_steps()
            self.child_executions = []
            self._step_order_counter = 0
            self._transition_count = 0
            self._step_outputs = {}

            self._execute_workflow_steps()

        except Exception as e:  # noqa: BLE001 — catch-all-mark-failed: ensures parent execution is marked FAILED on any error
            # Catch-all: ensure the parent execution is marked as FAILED
            logger.error(
                "container_workflow_thread_error",
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
            )
            try:
                execution = Execution.objects.get(id=execution_id)
                if execution.status not in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
                    execution.status = ExecutionStatus.FAILED
                    execution.completed_at = timezone.now()
                    execution.error_message = f"Workflow thread error: {e}"
                    execution.save(update_fields=['status', 'completed_at', 'error_message'])
            except Exception as _:  # noqa: BLE001 — best-effort-non-critical: cleanup after thread error must not raise
                logger.error("container_workflow_thread_cleanup_failed", execution_id=execution_id, exc_info=True)
        finally:
            close_old_connections()

    def _execute_workflow_steps(self) -> ExecutionStatus:
        """
        Execute workflow steps sequentially (shared by async thread and sync mode).

        Returns:
            Final ExecutionStatus of the parent workflow
        """
        final_status = ExecutionStatus.COMPLETED

        for step in self.workflow_steps:
            # Check cancellation before each step (AC4)
            if self._check_cancelled():
                logger.info(
                    "container_workflow_cancelled",
                    execution_id=self.execution.id,
                    step_order=step.get('order', 0),
                    correlation_id=self.correlation_id,
                )
                self._cancel_child_executions()
                final_status = ExecutionStatus.CANCELLED
                break

            # Execute step (creates child execution)
            child_status = self._execute_step(step)

            # Story 57.7: Gate step en WAITING — l'exécution reste RUNNING
            # Celery Beat reprendra via resume_container_workflow_from_gate
            if child_status == ExecutionStatus.RUNNING:
                logger.info(
                    "container_workflow_paused_on_gate",
                    execution_id=self.execution.id,
                    step_order=step.get('order', 0),
                    correlation_id=self.correlation_id,
                )
                return ExecutionStatus.RUNNING

            # AC4: Propagate failure — stop on first failure
            if child_status == ExecutionStatus.FAILED:
                logger.warning(
                    "container_workflow_step_failed",
                    execution_id=self.execution.id,
                    step_order=step.get('order', 0),
                    child_status=child_status,
                    correlation_id=self.correlation_id,
                )
                final_status = ExecutionStatus.FAILED
                break

            if child_status == ExecutionStatus.CANCELLED:
                logger.info(
                    "container_workflow_step_cancelled",
                    execution_id=self.execution.id,
                    step_order=step.get('order', 0),
                    correlation_id=self.correlation_id,
                )
                final_status = ExecutionStatus.CANCELLED
                break

        # Update parent execution final status (use queryset.update for reliable thread saves)
        update_fields = {
            'status': final_status,
            'completed_at': timezone.now(),
        }
        if final_status == ExecutionStatus.FAILED:
            update_fields['error_message'] = "Workflow failed: a referenced action failed"
        Execution.objects.filter(id=self.execution.id).update(**update_fields)
        # Sync in-memory
        self.execution.status = final_status
        self.execution.completed_at = update_fields['completed_at']  # type: ignore[assignment]

        # Audit trail
        audit_action_type = {
            ExecutionStatus.COMPLETED: AuditActionType.EXECUTION_COMPLETED,
            ExecutionStatus.FAILED: AuditActionType.EXECUTION_FAILED,
            ExecutionStatus.CANCELLED: AuditActionType.EXECUTION_CANCELLED,
        }.get(final_status, AuditActionType.EXECUTION_FAILED)

        AuditService.create_entry(
            user_id=str(self.execution.user_id),
            action_type=audit_action_type,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=self.execution.id,
            details={
                'action_id': self.action.id,
                'action_name': self.action.name,
                'workflow_type': 'container',
                'step_count': len(self.workflow_steps),
                'child_execution_ids': [c.id for c in self.child_executions],
                'final_status': final_status,
            },
            correlation_id=self.correlation_id,
        )

        logger.info(
            "container_workflow_execution_finished",
            execution_id=self.execution.id,
            final_status=final_status,
            child_count=len(self.child_executions),
            correlation_id=self.correlation_id,
        )

        return final_status
