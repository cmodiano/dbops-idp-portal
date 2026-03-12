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

import threading
import structlog
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, NamedTuple, Union, cast

from django.db import close_old_connections, transaction
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
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.utils import sanitize_audit_changes
from core.middleware import get_correlation_id
from executions.output_extractor import OutputExtractor
from executions.template_resolver import StepTemplateResolver
from executions.utils.workflow_parsing import get_workflow_entry_step_ids
from executions.step_handlers.condition_evaluator import StepConditionEvaluator
from executions.step_handlers.service_call_handler import ServiceCallHandler
from executions.step_handlers.http_request_handler import HttpRequestHandler
from executions.step_handlers.evaluation_handler import EvaluationHandler
from executions.step_handlers.gate_handler import GateHandler

logger = structlog.get_logger(__name__)


def _broadcast_step(execution_id: int, step: ExecutionStep) -> None:
    """Broadcast step_update via WebSocket (best-effort, never interrupts runtime)."""
    try:
        from executions.utils.websocket_broadcast import broadcast_step_update  # noqa: PLC0415
        broadcast_step_update(execution_id, step)
    except Exception as e:  # noqa: BLE001 — best-effort: must not interrupt workflow execution
        logger.debug("broadcast_step_update_failed", execution_id=execution_id, step_id=step.id, error=str(e))


def _broadcast_terminal(execution: Execution) -> None:
    """Broadcast execution_complete or execution_failed via WebSocket (best-effort)."""
    try:
        from channels.layers import get_channel_layer  # noqa: PLC0415
        from asgiref.sync import async_to_sync  # noqa: PLC0415

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        event_type = (
            "execution_complete" if execution.status == ExecutionStatus.COMPLETED
            else "execution_failed"
        )
        async_to_sync(channel_layer.group_send)(
            f"execution_{execution.id}",
            {
                "type": event_type,
                "data": {
                    "execution_id": execution.id,
                    "status": execution.status,
                    "finished": (
                        execution.completed_at.isoformat()
                        if execution.completed_at else None
                    ),
                },
            },
        )
    except Exception as e:  # noqa: BLE001 — best-effort: must not interrupt workflow execution
        logger.debug("broadcast_terminal_failed", execution_id=execution.id, error=str(e))


class ParallelContext(NamedTuple):
    """Thread-safe context for parallel step execution (Story 71.6)."""
    step_order: int

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

    ServiceNow change management (ADR-007 Story 57.10):
    ServiceNow change creation is no longer handled by a pre-hook.
    It must be defined as an explicit step in the workflow's execution_steps:

        {
            "step_id": "create-change",
            "step_type": "service_call",
            "name": "Créer change ServiceNow",
            "integration_type": "servicenow",
            "operation": "create_change",
            "condition": {"environment_in": ["production", "pre-production"]},
            "input_mapping": {
                "short_description": "IDP Portal — {{ execution.action_name }}",
                "change_model_code": "MDL001",
                "change_type": "normal"
            },
            "output_mapping": {
                "change_number": "$.number",
                "sys_id": "$.sys_id"
            }
        }

    The change number is then available as steps['create-change']['change_number']
    for subsequent steps (e.g., close-change via operation: close_change).
    """

    # Mapping step_type string → ExecutionStepType enum (ADR-007 §3d)
    # Story 67.2: 'parallel_group' supprimé — le parallélisme est géré via fan-out explicite
    # (on_success_step_ids / on_error_step_ids avec 2+ cibles)
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
        # Story 72.1: In Celery (e.g. resume_container_workflow_from_gate), get_correlation_id()
        # returns None — use execution.correlation_id for audit consistency.
        self.correlation_id = get_correlation_id() or execution.correlation_id or None
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

        # Thread-safety pour _step_outputs et _step_order_counter (Story 65.2)
        self._step_outputs_lock = threading.Lock()
        self._step_lock = threading.Lock()

        # Lookup step_id → step dict pour résolution des next_step_ids (Story 67.2)
        self._step_lookup_by_id: dict[str, dict] = {
            s['step_id']: s
            for s in self.workflow_steps
            if s.get('step_id')
        }
        # Story 67.4: Vague initiale pour resume après gate (fan-out parallèle)
        self._initial_wave: list[str] | None = None

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
        steps = sorted(steps, key=lambda s: s.get('order', 0))

        return steps

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
        """Cancel all running/submitted child executions (cascade cancellation).

        Story 71.7 AC#2: CAS pattern instead of read-modify-write to prevent
        overwriting a COMPLETED status with CANCELLED.
        """
        cancellable_statuses = [ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING]
        for child in self.child_executions:
            updated = Execution.objects.filter(
                id=child.id,
                status__in=cancellable_statuses,
            ).update(
                status=ExecutionStatus.CANCELLED,
                completed_at=timezone.now(),
            )
            if updated > 0:
                logger.info(
                    "container_workflow_child_cancelled",
                    parent_execution_id=self.execution.id,
                    child_execution_id=child.id,
                    correlation_id=self.correlation_id,
                )

    def _has_approval_notification_configured(self) -> bool:
        """Vérifie si au moins un canal a on_approval_required dans ses conditions."""
        config = self.action.notification_config or {}
        for ch in config.get("channels", []):
            if ch.get("enabled") and "on_approval_required" in (ch.get("conditions") or []):
                return True
        return False

    def _schedule_approval_notification(self) -> None:
        """Story 57.8: Envoie notification on_approval_required via on_commit."""
        try:
            from services.notification_service import NotificationService

            _execution = self.execution
            _action = self.action
            _correlation_id = self.correlation_id

            def _send() -> None:
                try:
                    notif = NotificationService()
                    notif.notify_execution_event(
                        execution=_execution,
                        action=_action,
                        event="on_approval_required",
                        correlation_id=_correlation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "approval_notification_failed",
                        execution_id=_execution.id,
                        error=str(exc),
                        correlation_id=_correlation_id,
                    )

            transaction.on_commit(_send)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "approval_notification_setup_failed",
                execution_id=self.execution.id,
                error=str(exc),
                correlation_id=self.correlation_id,
            )

    def _execute_step(
        self,
        step: Dict[str, Any],
        parallel_context: ParallelContext | None = None,
    ) -> ExecutionStatus:
        """
        Execute a single container workflow step.

        Orchestrates: input_mapping resolution → condition evaluation →
        step_type dispatch → output_mapping extraction (ADR-007 §3d).

        Story 71.6: Unified sequential/parallel — parallel_context provides pre-allocated
        step_order and enables thread-safe _step_outputs snapshot.

        Args:
            step: Step dict from workflow definition
            parallel_context: If not None, step runs in a thread (pre-allocated order, lock-based reads)

        Returns:
            ExecutionStatus of the step (COMPLETED for SKIPPED steps)
        """
        # Story 72.3: step_name = nom lisible, jamais UUID (step_id)
        step_name = step.get('name') or f"Étape {step.get('order', 0)}"
        step_id = step.get('step_id')
        step_type = step.get('step_type') or 'platform'  # ADR-007 §3d

        if parallel_context is None:
            self._step_order_counter += 1
            self._transition_count += 1
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
            # Parallel: snapshot under lock to avoid concurrent modification
            # Sequential: direct read — no concurrent writer (BFS single-step)
            if parallel_context is not None:
                with self._step_outputs_lock:
                    step_outputs_snapshot = dict(self._step_outputs)
            else:
                step_outputs_snapshot = self._step_outputs
            resolver = StepTemplateResolver(
                step_outputs_snapshot,
                execution_context={
                    'action_name': getattr(self.action, 'name', ''),
                    'environment': self.execution.environment,
                    'execution_id': self.execution.id,
                },
            )
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
            step_order=parallel_context.step_order if parallel_context else step.get('order', 0),
            step_name=step_name,
            step_type=step_type,
            correlation_id=self.correlation_id,
        )

        # Évaluer la condition (ADR-007 §6)
        condition_evaluator = StepConditionEvaluator()
        if not condition_evaluator.should_execute(step, self.execution):
            return self._create_skipped_step(step_name, step_id, step_type, parallel_context)

        # Dispatcher selon step_type (ADR-007 §3d)
        handler: Union[
            ServiceCallHandler, HttpRequestHandler, EvaluationHandler, GateHandler
        ]
        match step_type:
            case 'platform':
                return self._execute_platform_step(step, resolved_params, step_name, step_id, parallel_context)
            case 'service_call':
                handler = ServiceCallHandler()
            case 'http_request':
                handler = HttpRequestHandler()
            case 'evaluation':
                handler = EvaluationHandler()
            case 'gate':
                handler = GateHandler()
            case _:
                if parallel_context is not None:
                    logger.error(
                        "container_workflow_parallel_unknown_step_type",
                        step_type=step_type,
                        execution_id=self.execution.id,
                        correlation_id=self.correlation_id,
                    )
                    return ExecutionStatus.FAILED
                raise ValueError(f"Unknown step_type: {step_type!r}")

        return self._execute_handler_step(step, resolved_params, step_name, step_id, step_type, handler, parallel_context)

    def _get_next_step_ids(self, step: dict, outcome: ExecutionStatus) -> list[str]:
        """Retourne les step_id cibles selon l'outcome, avec rétrocompat singulier.

        Si aucun champ de routing n'est présent (ancien mode linéaire), retourne
        le step suivant par ordre (rétrocompat workflows sans routing explicite).

        Story 67.2 — AC1, AC2, AC7.
        """
        if outcome == ExecutionStatus.COMPLETED:
            # Opt out of linear fallback only if step defines explicit success routing.
            # Steps with only on_error_step_ids must use linear fallback on success.
            # Note: on_success_step_id (singular) is legacy; no active code uses it (RC-02).
            has_routing = 'on_success_step_ids' in step
            if not has_routing:
                # Mode linéaire sans routing explicite — fallback sur step suivant par ordre
                return self._get_linear_next_step_ids(step)
            ids = step.get('on_success_step_ids')
            return ids or []
        else:  # FAILED, CANCELLED, etc.
            ids = step.get('on_error_step_ids')
            return ids or []

    def _get_linear_next_step_ids(self, step: dict) -> list[str]:
        """Retourne le step suivant par ordre (mode linéaire sans routing explicite).

        Rétrocompatibilité pour les workflows créés avant le support multi-cibles.
        """
        current_order = step.get('order', 0)
        next_steps = [
            s for s in self.workflow_steps
            if s.get('order', 0) > current_order and s.get('step_id')
        ]
        if next_steps:
            next_step = min(next_steps, key=lambda s: s.get('order', 0))
            return [next_step['step_id']]
        return []  # exit point

    def _apply_join_policy(
        self,
        wave_steps: list[dict],
        results: dict[str, tuple[ExecutionStatus, list[str]]],
    ) -> list[str]:
        """
        Construit la prochaine vague en appliquant join_policy pour les steps convergents.

        Pour chaque step cible candidat :
        - Si 1 seul prédécesseur dans la vague → inclus inconditionnellement
        - Si 2+ prédécesseurs dans la vague → apply join_policy du step cible (défaut all_success)

        Limitation connue : join_policy s'applique uniquement aux prédécesseurs de la vague COURANTE.
        Les convergences cross-waves (prédécesseurs dans des vagues BFS différentes) ne sont pas
        gérées dans cette story.

        Story 67.3 — AC: #1, #5, #6, #7, #8.
        Story 67.8 — all_failed (tous les prédécesseurs en échec) | one_failed (au moins un en échec).

        Note : join_policy n'est évaluée que si le step cible a 2+ prédécesseurs dans la vague courante.
        Si 1 seul prédécesseur, le step est inclus inconditionnellement (politique ignorée).
        """
        # Build: target_step_id → [(source_step_id, source_outcome)]
        # Considère TOUS les targets possibles de la vague (success ET error paths)
        target_preds: dict[str, list[tuple[str, ExecutionStatus]]] = {}
        for step in wave_steps:
            sid = step.get('step_id', '')
            if not sid:
                continue
            status, _ = results.get(sid, (ExecutionStatus.FAILED, []))
            all_targets: set[str] = set()
            for t in (step.get('on_success_step_ids') or []):
                if t:
                    all_targets.add(t)
            for t in (step.get('on_error_step_ids') or []):
                if t:
                    all_targets.add(t)
            for target_id in all_targets:
                target_preds.setdefault(target_id, []).append((sid, status))

        # Collecter les candidats : union déduplicée des next_ids per-branch (déjà routés)
        candidate_ids: list[str] = []
        for _, (_, next_ids) in results.items():
            for nid in next_ids:
                if nid not in candidate_ids:
                    candidate_ids.append(nid)

        # Appliquer join_policy pour chaque candidat
        result: list[str] = []
        for target_id in candidate_ids:
            preds = target_preds.get(target_id, [])
            if len(preds) <= 1:
                # Prédécesseur unique → inclure sans condition
                result.append(target_id)
                continue

            target_step = self._step_lookup_by_id.get(target_id)
            join_policy = (target_step or {}).get('join_policy', 'all_success')
            pred_statuses = [s for _, s in preds]

            if join_policy == 'all_success':
                if all(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                    result.append(target_id)
            elif join_policy == 'one_success':
                if any(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                    result.append(target_id)
            elif join_policy == 'all_done':
                # Tous terminés par définition dans le contexte fan-out
                result.append(target_id)
            elif join_policy == 'all_failed':
                # Story 67.8: D runs only if ALL predecessors failed
                if all(s == ExecutionStatus.FAILED for s in pred_statuses):
                    result.append(target_id)
            elif join_policy == 'one_failed':
                # Story 67.8: D runs if at least one predecessor failed
                if any(s == ExecutionStatus.FAILED for s in pred_statuses):
                    result.append(target_id)
            else:
                # Politique inconnue → all_success par défaut (défensif)
                if all(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                    result.append(target_id)

        return result

    def _execute_fan_out(
        self, step_ids: list[str]
    ) -> tuple[ExecutionStatus, list[str]]:
        """
        Exécute plusieurs steps en parallèle (fan-out) via ThreadPoolExecutor.

        Retourne (statut_global, liste_next_step_ids_combinée_déduplicée).

        Story 67.2 — AC1, AC2, AC3, AC4.
        """
        from django.conf import settings  # noqa: PLC0415

        sub_steps: list[dict] = []
        for sid in step_ids:
            sub_step = self._step_lookup_by_id.get(sid)
            if sub_step is None:
                logger.error(
                    "container_workflow_fan_out_step_not_found",
                    execution_id=self.execution.id,
                    step_id=sid,
                    correlation_id=self.correlation_id,
                )
                return ExecutionStatus.FAILED, []
            sub_steps.append(sub_step)

        # Pré-allouer step_order et incrémenter transition_count (thread-safe)
        pre_allocated: dict[str, int] = {}
        with self._step_lock:
            for sub_step in sub_steps:
                self._step_order_counter += 1
                pre_allocated[sub_step['step_id']] = self._step_order_counter
            self._transition_count += len(sub_steps)

        if self._transition_count > MAX_STEP_TRANSITIONS:
            logger.error(
                "container_workflow_loop_detected_fan_out",
                execution_id=self.execution.id,
                transition_count=self._transition_count,
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.FAILED, []

        max_workers = getattr(settings, 'PARALLEL_GROUP_MAX_WORKERS', 5)
        step_timeout = getattr(settings, 'PARALLEL_GROUP_STEP_TIMEOUT_S', 300)

        logger.info(
            "container_workflow_fan_out_starting",
            execution_id=self.execution.id,
            step_ids=step_ids,
            max_workers=max_workers,
            correlation_id=self.correlation_id,
        )

        results: dict[str, tuple[ExecutionStatus, list[str]]] = {}

        def execute_sub_step(sub_step: dict) -> tuple[str, ExecutionStatus]:
            """Exécute un step dans un thread worker (DB connection isolée)."""
            close_old_connections()
            sub_step_id = sub_step.get('step_id', '')
            allocated_order = pre_allocated[sub_step_id]
            status = self._execute_step(sub_step, ParallelContext(step_order=allocated_order))
            return sub_step_id, status

        from concurrent.futures import TimeoutError as FutureTimeoutError  # noqa: PLC0415
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_step = {
                executor.submit(execute_sub_step, sub_step): sub_step
                for sub_step in sub_steps
            }
            try:
                for future in as_completed(future_to_step, timeout=step_timeout):
                    try:
                        sub_step_id, status = future.result()
                        sub_step = self._step_lookup_by_id[sub_step_id]
                        next_ids = self._get_next_step_ids(sub_step, status)
                        results[sub_step_id] = (status, next_ids)
                    except Exception as exc:  # noqa: BLE001
                        failed_step = future_to_step[future]
                        failed_id = failed_step.get('step_id', '?')
                        logger.error(
                            "container_workflow_fan_out_sub_step_exception",
                            execution_id=self.execution.id,
                            sub_step_id=failed_id,
                            error=str(exc),
                            correlation_id=self.correlation_id,
                            exc_info=True,
                        )
                        results[failed_id] = (ExecutionStatus.FAILED, [])
            except FutureTimeoutError:
                # One or more sub-steps exceeded step_timeout — mark remaining as FAILED.
                # The executor context manager will call shutdown(cancel_futures=True) on exit.
                pending_ids = [
                    s.get('step_id', '?') for f, s in future_to_step.items() if not f.done()
                ]
                logger.error(
                    "container_workflow_fan_out_timeout",
                    execution_id=self.execution.id,
                    timeout_s=step_timeout,
                    pending_step_ids=pending_ids,
                    correlation_id=self.correlation_id,
                )
                for pending_id in pending_ids:
                    results[pending_id] = (ExecutionStatus.FAILED, [])

        # Phase 1 limitation: gate steps returning RUNNING inside a fan-out are treated
        # as FAILED (they cannot pause the fan-out — ThreadPoolExecutor has already joined).
        # Full gate support in fan-out is deferred to a future story.

        # CANCELLED prioritaire sur tout
        if any(s == ExecutionStatus.CANCELLED for s, _ in results.values()):
            return ExecutionStatus.CANCELLED, []

        # Story 67.3 : routage par branche indépendant + join_policy configurable
        combined_next = self._apply_join_policy(sub_steps, results)

        if not combined_next and any(s == ExecutionStatus.FAILED for s, _ in results.values()):
            return ExecutionStatus.FAILED, []

        logger.info(
            "container_workflow_fan_out_finished",
            execution_id=self.execution.id,
            step_ids=step_ids,
            next_step_ids=combined_next,
            correlation_id=self.correlation_id,
        )

        return ExecutionStatus.COMPLETED, combined_next

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
            parent_step.save()
            return None

        try:
            return cast(Action, Action.objects.get(id=referenced_action_id, status=ActionStatus.PUBLISHED))
        except Action.DoesNotExist:
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = (
                f"Referenced action {referenced_action_id} not found or not published "
                f"for step {step_def_order}"
            )
            parent_step.save()
            logger.error(
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

    def _run_child_execution(self, child_execution: Execution) -> None:
        """
        Run the child execution (simulation or production fallback).

        Story 71.6: Extracted from _execute_platform_step (subtask 9.3).
        """
        if SimulationService.is_enabled():
            SimulationService.create_simulated_steps(child_execution)
            try:
                SimulationService._run_simulation(child_execution.id, force_success=True)
            except Exception as sim_error:  # noqa: BLE001 — catch-all-mark-failed
                logger.error(
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
            if action and action.item_type == "workflow":
                try:
                    ContainerWorkflowRuntime(child_execution).run_sync()
                except Exception as run_err:  # noqa: BLE001
                    logger.error(
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
                # No runtime for item_type='action' — placeholder: mark completed
                now = timezone.now()
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.COMPLETED,
                    started_at=now,
                    completed_at=now,
                )

    def _extract_and_store_output(
        self, step_id: str, parent_step: ExecutionStep, output_mapping: Any,
    ) -> None:
        """
        Extract output from a completed step and store in _step_outputs (thread-safe).

        Story 71.6: Extracted from _execute_platform_step (subtask 9.4).
        """
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
        with self._step_outputs_lock:
            self._step_outputs[step_id] = extracted

    def _execute_platform_step(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
        parallel_context: ParallelContext | None = None,
    ) -> ExecutionStatus:
        """
        Execute a platform step: validate action, create child execution, run it, extract outputs.

        Story 71.6: Unified sequential/parallel + sub-operations extracted.
        """
        step_def_order = step.get('order', 0)
        step_order = parallel_context.step_order if parallel_context else self._step_order_counter

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

        # Pure computation outside transaction to minimize lock duration
        child_params = self._get_step_parameters(step)
        if resolved_params:
            child_params = {**child_params, **resolved_params}

        child_execution = None
        try:
            child_execution = self._create_child_execution(
                referenced_action, child_params, parent_step, parallel_context,
            )

            logger.info(
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
            self._run_child_execution(child_execution)
            child_execution.refresh_from_db()

            # Story 71.7 AC#4: Transaction 2 — finalize parent_step after execution
            with transaction.atomic():
                parent_step.status = (
                    ExecutionStepStatus.FAILED
                    if child_execution.status == ExecutionStatus.FAILED
                    else ExecutionStepStatus.COMPLETED
                )
                parent_step.completed_at = timezone.now()
                parent_step.set_output({
                    'child_execution_id': child_execution.id,
                    'referenced_action_id': referenced_action.id,
                    'referenced_action_name': referenced_action.name,
                    'child_status': child_execution.status,
                    'parameters_injected': bool(child_params),
                })
                parent_step.save()

            _broadcast_step(self.execution.id, parent_step)  # COMPLETED or FAILED

            if step_id is not None:
                self._extract_and_store_output(step_id, parent_step, step.get('output_mapping', {}))

            return cast(ExecutionStatus, child_execution.status)
        except Exception as exc:  # noqa: BLE001
            # Story 71.7 AC#4: Atomic error handling for parent_step + child_execution
            with transaction.atomic():
                parent_step.status = ExecutionStepStatus.FAILED
                parent_step.completed_at = timezone.now()
                parent_step.error_message = f"Platform step failed: {exc}"
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
            logger.error(
                "container_workflow_platform_step_exception",
                execution_id=self.execution.id,
                step_def_order=step_def_order,
                correlation_id=self.correlation_id,
                error=str(exc),
                exc_info=True,
            )
            return ExecutionStatus.FAILED

    def _create_skipped_step(
        self,
        step_name: str,
        step_id: str | None,
        step_type: str,
        parallel_context: ParallelContext | None = None,
    ) -> ExecutionStatus:
        """
        Crée un ExecutionStep SKIPPED et met à jour _step_outputs (ADR-007 §6).

        Story 71.6: Unified sequential/parallel via optional parallel_context.

        Returns:
            ExecutionStatus.COMPLETED — le runtime continue au step suivant.
        """
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)
        step_order = parallel_context.step_order if parallel_context else self._step_order_counter

        now = timezone.now()
        ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            config_step_id=step_id,
            step_type=db_step_type,
            status=ExecutionStepStatus.SKIPPED,
            started_at=now,
            completed_at=now,
        )

        if step_id is not None:
            with self._step_outputs_lock:
                self._step_outputs[step_id] = {}

        logger.info(
            "container_workflow_step_skipped",
            execution_id=self.execution.id,
            step_id=step_id,
            step_name=step_name,
            step_type=step_type,
            correlation_id=self.correlation_id,
        )
        return ExecutionStatus.COMPLETED

    def _handle_gate_waiting(
        self, result: dict, parent_step: ExecutionStep, step_name: str, step_id: str | None,
    ) -> ExecutionStatus:
        """
        Handle WAITING protocol for gate steps: set output, broadcast, notify.

        Story 71.6: Extracted from _execute_handler_step (subtask 10.1).

        Returns:
            ExecutionStatus.RUNNING — sentinel to pause the BFS loop.
        """
        gate_output = dict(result.get('gate_output', {}))
        gate_conditions = gate_output.get('gate_conditions', [])
        # Story 72.3: ajouter gate_type pour affichage timeline (Approbation / Fenêtre maintenance)
        if gate_conditions and isinstance(gate_conditions[0], dict):
            cond_type = gate_conditions[0].get('type', '')
            gate_output['gate_type'] = (
                'approval' if cond_type == 'approval_granted' else 'maintenance_window'
            )
        parent_step.set_output(gate_output)
        parent_step.status = ExecutionStepStatus.WAITING
        parent_step.save()

        _broadcast_step(self.execution.id, parent_step)  # WAITING

        logger.info(
            "container_workflow_gate_step_waiting",
            step_name=step_name,
            step_id=step_id,
            execution_id=self.execution.id,
            correlation_id=self.correlation_id,
        )
        is_approval_gate = any(
            isinstance(c, dict) and c.get('type') == 'approval_granted'
            for c in gate_conditions
        )
        if is_approval_gate:
            if self._has_approval_notification_configured():
                self._schedule_approval_notification()
            try:
                from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
                WorkflowEventService.emit_approval_requested(self.execution.id, parent_step)
            except Exception as e:  # noqa: BLE001 — best-effort: must not fail runtime
                logger.error(
                    "container_workflow_emit_approval_requested_failed",
                    execution_id=self.execution.id,
                    step_id=parent_step.id,
                    step_name=parent_step.step_name,
                    correlation_id=self.correlation_id,
                    error=str(e),
                    exc_info=True,
                )
        return ExecutionStatus.RUNNING

    def _finalize_handler_step(
        self,
        result: Any,
        parent_step: ExecutionStep,
        step_id: str | None,
        output_mapping: Any,
    ) -> ExecutionStatus:
        """
        Extract output and finalize handler step status.

        Story 71.6: Extracted from _execute_handler_step (subtask 10.2).
        """
        if step_id is not None:
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
            if isinstance(result, dict) and 'raw_output' in result:
                raw_output = result.get('raw_output', {}) or {}
            else:
                raw_output = result if isinstance(result, dict) else {}
            extracted = extractor.extract(raw_output, output_mapping)
            with self._step_outputs_lock:
                self._step_outputs[step_id] = extracted

        # Fail-closed: missing/invalid handler_status → FAILED
        result_execution_status = ExecutionStatus.FAILED
        if isinstance(result, dict):
            handler_status = result.get('status')
            if isinstance(handler_status, ExecutionStatus):
                result_execution_status = handler_status

        parent_step.status = (
            ExecutionStepStatus.FAILED
            if result_execution_status == ExecutionStatus.FAILED
            else ExecutionStepStatus.COMPLETED
        )
        parent_step.completed_at = timezone.now()
        parent_step.save()
        _broadcast_step(self.execution.id, parent_step)  # COMPLETED or FAILED
        return result_execution_status

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
        parallel_context: ParallelContext | None = None,
    ) -> ExecutionStatus:
        """
        Wrapper générique pour les handlers non-platform (ADR-007 §3d).

        Story 71.6: Unified sequential/parallel + sub-operations extracted.
        """
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)
        step_order = parallel_context.step_order if parallel_context else self._step_order_counter

        parent_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            config_step_id=step_id,
            step_type=db_step_type,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )
        _broadcast_step(self.execution.id, parent_step)  # RUNNING

        try:
            result = handler.execute(
                step_config=step,
                resolved_params=resolved_params,
                execution=self.execution,
                step=step,
                correlation_id=self.correlation_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "container_workflow_handler_exception",
                step_name=step_name,
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.save()
            _broadcast_step(self.execution.id, parent_step)  # FAILED
            return ExecutionStatus.FAILED

        # Protocole WAITING pour gate steps (story 57.7)
        if isinstance(result, dict) and result.get('waiting'):
            if parallel_context is not None:
                logger.warning(
                    "container_workflow_parallel_gate_not_supported",
                    step_name=step_name,
                    execution_id=self.execution.id,
                    correlation_id=self.correlation_id,
                )
                parent_step.status = ExecutionStepStatus.FAILED
                parent_step.completed_at = timezone.now()
                parent_step.save()
                _broadcast_step(self.execution.id, parent_step)  # FAILED
                return ExecutionStatus.FAILED
            return self._handle_gate_waiting(result, parent_step, step_name, step_id)

        return self._finalize_handler_step(result, parent_step, step_id, step.get('output_mapping', {}))

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

        # CAS transition SUBMITTED→RUNNING to prevent double-start (Story 71.7 AC#3)
        updated = Execution.objects.filter(
            id=self.execution.id,
            status=ExecutionStatus.SUBMITTED,
        ).update(
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )
        if updated == 0:
            logger.warning(
                "container_workflow_already_started",
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            return
        self.execution.refresh_from_db(fields=['status', 'started_at'])

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
        thread = threading.Thread(
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

        # CAS transition SUBMITTED→RUNNING to prevent double-start (Story 71.7 AC#3)
        updated = Execution.objects.filter(
            id=self.execution.id,
            status=ExecutionStatus.SUBMITTED,
        ).update(
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )
        if updated == 0:
            # Allow proceeding if already RUNNING (test scenario / resume)
            self.execution.refresh_from_db(fields=['status', 'started_at'])
            if self.execution.status != ExecutionStatus.RUNNING:
                logger.warning(
                    "container_workflow_already_started",
                    execution_id=self.execution.id,
                    correlation_id=self.correlation_id,
                )
                return ExecutionStatus.FAILED
        else:
            self.execution.refresh_from_db(fields=['status', 'started_at'])

        if not self.workflow_steps:
            self.execution.status = ExecutionStatus.FAILED
            self.execution.completed_at = timezone.now()
            self.execution.error_message = "Workflow has no steps"
            self.execution.save(update_fields=['status', 'completed_at', 'error_message'])
            return ExecutionStatus.FAILED

        return self._execute_workflow_steps()

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
            # Réinitialiser le lookup step_id → step (Story 67.2)
            self._step_lookup_by_id = {
                s['step_id']: s for s in self.workflow_steps if s.get('step_id')
            }

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
            # Story 71.7 AC#7: CAS pattern to avoid overwriting terminal status
            try:
                updated = Execution.objects.filter(
                    id=execution_id,
                ).exclude(
                    status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
                ).update(
                    status=ExecutionStatus.FAILED,
                    completed_at=timezone.now(),
                    error_message=f"Workflow thread error: {e}",
                )
                if updated > 0:
                    logger.info(
                        "container_workflow_thread_error_marked_failed",
                        execution_id=execution_id,
                        correlation_id=self.correlation_id,
                    )
            except Exception as _:  # noqa: BLE001 — best-effort-non-critical: cleanup after thread error must not raise
                logger.error("container_workflow_thread_cleanup_failed", execution_id=execution_id, exc_info=True)
        finally:
            close_old_connections()

    def _determine_initial_wave(self) -> list[str] | None:
        """
        Determine the initial wave of step IDs for BFS-wave traversal (Story 71.6).

        Returns:
            List of step IDs for the first wave, or None if fallback to
            sequential execution is needed (legacy steps without step_id).
        """
        # Story 67.4: Vague initiale explicite (resume après gate avec on_success_step_ids)
        initial_wave = getattr(self, '_initial_wave', None)
        if initial_wave:
            return [s for s in initial_wave if s in self._step_lookup_by_id]

        # Démarrer par les steps d'entrée (aucune connexion entrante), pas min(order).
        # Fixe le cas où une étape d'approbation ajoutée au début a un order élevé.
        entry_ids = get_workflow_entry_step_ids(self.workflow_steps)
        if entry_ids:
            current_wave = [s for s in entry_ids if s in self._step_lookup_by_id]
        else:
            # Fallback: pas d'entrée (cycle?) — min order
            first_step = min(self.workflow_steps, key=lambda s: s.get('order', 0))
            first_step_id = first_step.get('step_id')
            current_wave = [first_step_id] if first_step_id else []

        return current_wave if current_wave else None

    def _execute_workflow_steps(self) -> ExecutionStatus:
        """
        Execute workflow steps via BFS-wave graph traversal (Story 67.2).

        Supports sequential execution (1 step per wave) and parallel fan-out
        (2+ steps per wave via on_success_step_ids / on_error_step_ids).

        Returns:
            Final ExecutionStatus of the parent workflow
        """
        final_status = ExecutionStatus.COMPLETED
        _failed_step_name: str | None = None

        if not self.workflow_steps:
            # Boucle vide → COMPLETED (cohérent avec l'ancien comportement while skipé)
            # Note: run_sync() / run() vérifient déjà les steps vides avant d'appeler cette méthode
            return ExecutionStatus.COMPLETED

        # Story 67.4 / 71.6: Déterminer la vague initiale
        current_wave = self._determine_initial_wave()
        if current_wave is None:
            # Rétrocompat : step sans step_id → exécution séquentielle par ordre
            return self._execute_workflow_steps_sequential()

        while current_wave:
            # Check cancellation avant chaque vague (AC4)
            if self._check_cancelled():
                logger.info(
                    "container_workflow_cancelled",
                    execution_id=self.execution.id,
                    current_wave=current_wave,
                    correlation_id=self.correlation_id,
                )
                self._cancel_child_executions()
                final_status = ExecutionStatus.CANCELLED
                break

            if len(current_wave) == 1:
                # Exécution séquentielle (optimisation — évite un ThreadPoolExecutor inutile)
                step_id = current_wave[0]
                step = self._step_lookup_by_id.get(step_id)
                if not step:
                    logger.error(
                        "container_workflow_step_not_found",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        correlation_id=self.correlation_id,
                    )
                    final_status = ExecutionStatus.FAILED
                    break

                child_status = self._execute_step(step)

                # Story 57.7: Gate step en WAITING — l'exécution reste RUNNING
                # Celery Beat reprendra via resume_container_workflow_from_gate
                if child_status == ExecutionStatus.RUNNING:
                    logger.info(
                        "container_workflow_paused_on_gate",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        correlation_id=self.correlation_id,
                    )
                    return ExecutionStatus.RUNNING

                if child_status == ExecutionStatus.CANCELLED:
                    logger.info(
                        "container_workflow_step_cancelled",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        correlation_id=self.correlation_id,
                    )
                    final_status = ExecutionStatus.CANCELLED
                    break

                next_ids = self._get_next_step_ids(step, child_status)

                if child_status == ExecutionStatus.FAILED:
                    if not next_ids:
                        _failed_step_name = step.get('name') or f"order {step.get('order', '?')}"
                        logger.warning(
                            "container_workflow_step_failed",
                            execution_id=self.execution.id,
                            step_id=step_id,
                            step_name=_failed_step_name,
                            correlation_id=self.correlation_id,
                        )
                        final_status = ExecutionStatus.FAILED
                        break
                    # On_error routing : continuer avec les next_ids

                current_wave = list(dict.fromkeys(next_ids))  # dédupliquer ordre préservé

            else:
                # Fan-out : plusieurs steps en parallèle (AC1, AC2, AC3)
                wave_status, next_ids = self._execute_fan_out(current_wave)

                # Note: _execute_fan_out() ne retourne jamais RUNNING actuellement
                # (gate WAITING en fan-out → FAILED dans _execute_handler_step).
                # Cette garde est défensive pour les évolutions futures (gates dans fan-out).
                if wave_status == ExecutionStatus.RUNNING:
                    return ExecutionStatus.RUNNING

                if wave_status == ExecutionStatus.CANCELLED:
                    self._cancel_child_executions()
                    final_status = ExecutionStatus.CANCELLED
                    break

                if wave_status == ExecutionStatus.FAILED:
                    final_status = ExecutionStatus.FAILED
                    break

                current_wave = list(dict.fromkeys(next_ids))  # dédupliquer ordre préservé

        return self._finalize_workflow_execution(final_status, _failed_step_name)

    def _finalize_workflow_execution(
        self, final_status: ExecutionStatus, failed_step_name: str | None = None,
    ) -> ExecutionStatus:
        """
        Persist final execution status, audit trail, and log completion.

        Story 71.6 code review: extracted to eliminate duplication between
        _execute_workflow_steps and _execute_workflow_steps_sequential.
        """
        completed_at = timezone.now()
        update_fields: dict[str, Any] = {
            'status': final_status,
            'completed_at': completed_at,
        }
        if final_status == ExecutionStatus.FAILED:
            step_info = f" (step: {failed_step_name})" if failed_step_name else ""
            update_fields['error_message'] = f"Workflow failed: a referenced action failed{step_info}"

        audit_action_type = {
            ExecutionStatus.COMPLETED: AuditActionType.EXECUTION_COMPLETED,
            ExecutionStatus.FAILED: AuditActionType.EXECUTION_FAILED,
            ExecutionStatus.CANCELLED: AuditActionType.EXECUTION_CANCELLED,
        }.get(final_status, AuditActionType.EXECUTION_FAILED)

        # Story 71.7 AC#1: Atomic update + audit to prevent inconsistent state
        # CAS guard: do not overwrite a terminal status set by _run_workflow_loop error handler
        with transaction.atomic():
            updated = Execution.objects.filter(
                id=self.execution.id,
            ).exclude(
                status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
            ).update(**update_fields)
            if updated == 0:
                self.execution.refresh_from_db(fields=['status', 'completed_at'])
                logger.warning(
                    "container_workflow_finalize_already_terminal",
                    execution_id=self.execution.id,
                    target_status=final_status,
                    actual_status=self.execution.status,
                    correlation_id=self.correlation_id,
                )
                return cast(ExecutionStatus, self.execution.status)
            old_status = self.execution.status
            changes = sanitize_audit_changes({'status': {'old': old_status, 'new': final_status}})
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
                    'changes': changes,
                },
                correlation_id=self.correlation_id,
            )

        # Sync in-memory object after commit (values are known, no refresh needed)
        self.execution.status = final_status
        self.execution.completed_at = completed_at

        _broadcast_terminal(self.execution)

        logger.info(
            "container_workflow_execution_finished",
            execution_id=self.execution.id,
            final_status=final_status,
            child_count=len(self.child_executions),
            correlation_id=self.correlation_id,
        )

        return final_status

    def _execute_workflow_steps_sequential(self) -> ExecutionStatus:
        """
        Fallback séquentiel par ordre pour les workflows avec steps sans step_id.

        Rétrocompatibilité : les anciens workflows dont certains steps n'ont pas
        de step_id utilisent cet exécuteur linéaire simple.
        """
        final_status = ExecutionStatus.COMPLETED
        _failed_step_name: str | None = None

        for step in self.workflow_steps:
            if self._check_cancelled():
                logger.info(
                    "container_workflow_cancelled",
                    execution_id=self.execution.id,
                    correlation_id=self.correlation_id,
                )
                self._cancel_child_executions()
                final_status = ExecutionStatus.CANCELLED
                break

            child_status = self._execute_step(step)

            if child_status == ExecutionStatus.RUNNING:
                return ExecutionStatus.RUNNING

            if child_status == ExecutionStatus.FAILED:
                _failed_step_name = step.get('name') or f"order {step.get('order', '?')}"
                final_status = ExecutionStatus.FAILED
                break

            if child_status == ExecutionStatus.CANCELLED:
                final_status = ExecutionStatus.CANCELLED
                break

        return self._finalize_workflow_execution(final_status, _failed_step_name)
