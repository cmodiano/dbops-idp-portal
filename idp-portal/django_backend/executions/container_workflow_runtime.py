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
from typing import Dict, Any, List, Union, cast

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
        step_name = step.get('name') or step.get('step_id') or f"Step {step_order}"
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
        # Note : lecture sans lock — pas de writer concurrent en mode séquentiel (BFS-wave garantit
        # qu'un seul step est actif à la fois). Contraste avec _execute_step_for_parallel qui
        # prend un snapshot sous _step_outputs_lock.
        input_mapping = step.get('input_mapping', {})
        resolved_params: dict = {}
        if input_mapping and isinstance(input_mapping, dict):
            resolver = StepTemplateResolver(
                self._step_outputs,
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

    def _get_next_step_ids(self, step: dict, outcome: ExecutionStatus) -> list[str]:
        """Retourne les step_id cibles selon l'outcome, avec rétrocompat singulier.

        Si aucun champ de routing n'est présent (ancien mode linéaire), retourne
        le step suivant par ordre (rétrocompat workflows sans routing explicite).

        Story 67.2 — AC1, AC2, AC7.
        """
        if outcome == ExecutionStatus.COMPLETED:
            has_routing = 'on_success_step_ids' in step or 'on_success_step_id' in step
            if not has_routing:
                # Mode linéaire sans routing explicite — fallback sur step suivant par ordre
                return self._get_linear_next_step_ids(step)
            ids = step.get('on_success_step_ids')
            if ids is None:
                v = step.get('on_success_step_id')
                ids = [v] if v else []
            return ids or []
        else:  # FAILED, CANCELLED, etc.
            ids = step.get('on_error_step_ids')
            if ids is None:
                v = step.get('on_error_step_id')
                ids = [v] if v else []
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
            if sv := step.get('on_success_step_id'):
                all_targets.add(sv)
            for t in (step.get('on_error_step_ids') or []):
                if t:
                    all_targets.add(t)
            if ev := step.get('on_error_step_id'):
                all_targets.add(ev)
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
            status = self._execute_step_for_parallel(sub_step, allocated_order)
            return sub_step_id, status

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_step = {
                executor.submit(execute_sub_step, sub_step): sub_step
                for sub_step in sub_steps
            }
            for future in as_completed(future_to_step):
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

    def _execute_step_for_parallel(self, step: Dict[str, Any], step_order: int) -> ExecutionStatus:
        """
        Version thread-safe de _execute_step pour exécution dans ThreadPoolExecutor.

        Identique à _execute_step mais avec step_order explicite (pré-alloué).
        Protège les écritures dans _step_outputs avec _step_outputs_lock.

        Story 65.2 — AC4, AC7.
        """
        step_name = step.get('name') or step.get('step_id') or f"Step {step_order}"
        step_id = step.get('step_id')
        step_type = step.get('step_type') or 'platform'

        # Résoudre les input_mapping depuis _step_outputs
        # Snapshot under lock to avoid "dictionary changed size during iteration" from sibling workers
        input_mapping = step.get('input_mapping', {})
        resolved_params: dict = {}
        if input_mapping and isinstance(input_mapping, dict):
            with self._step_outputs_lock:
                step_outputs_snapshot = dict(self._step_outputs)
            resolver = StepTemplateResolver(
                step_outputs_snapshot,
                execution_context={
                    'action_name': getattr(self.action, 'name', ''),
                    'environment': self.execution.environment,
                    'execution_id': self.execution.id,
                },
            )
            resolved_params = resolver.resolve(input_mapping)

        logger.info(
            "container_workflow_parallel_sub_step_starting",
            execution_id=self.execution.id,
            step_order=step_order,
            step_name=step_name,
            step_type=step_type,
            correlation_id=self.correlation_id,
        )

        # Évaluer la condition
        condition_evaluator = StepConditionEvaluator()
        if not condition_evaluator.should_execute(step, self.execution):
            return self._create_skipped_step_for_parallel(step_name, step_id, step_type, step_order)

        # Dispatch selon step_type avec step_order pré-alloué
        handler: ServiceCallHandler | HttpRequestHandler | EvaluationHandler | GateHandler
        match step_type:
            case 'platform':
                return self._execute_platform_step_for_parallel(
                    step, resolved_params, step_name, step_id, step_order
                )
            case 'service_call':
                handler = ServiceCallHandler()
            case 'http_request':
                handler = HttpRequestHandler()
            case 'evaluation':
                handler = EvaluationHandler()
            case 'gate':
                handler = GateHandler()
            case _:
                logger.error(
                    "container_workflow_parallel_unknown_step_type",
                    step_type=step_type,
                    execution_id=self.execution.id,
                    correlation_id=self.correlation_id,
                )
                return ExecutionStatus.FAILED

        return self._execute_handler_step_for_parallel(
            step, resolved_params, step_name, step_id, step_type, handler, step_order
        )

    def _create_skipped_step_for_parallel(
        self,
        step_name: str,
        step_id: str | None,
        step_type: str,
        step_order: int,
    ) -> ExecutionStatus:
        """Version de _create_skipped_step avec step_order explicite (thread-safe)."""
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)
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
        return ExecutionStatus.COMPLETED

    def _execute_platform_step_for_parallel(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
        step_order: int,
    ) -> ExecutionStatus:
        """Version thread-safe de _execute_platform_step avec step_order pré-alloué."""
        step_def_order = step.get('order', 0)
        referenced_action_id = step.get('referenced_action_id')

        parent_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            config_step_id=step_id,
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        if not referenced_action_id:
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = f"Step {step_def_order} missing referenced_action_id"
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
                f"for step {step_def_order}"
            )
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.error_message = error_msg
            parent_step.save()
            logger.error(
                "container_workflow_referenced_action_not_found",
                execution_id=self.execution.id,
                referenced_action_id=referenced_action_id,
                step_order=step_def_order,
                correlation_id=self.correlation_id,
            )
            return ExecutionStatus.FAILED

        child_params = self._get_step_parameters(step)
        if resolved_params:
            child_params = {**child_params, **resolved_params}

        from executions.dtos import ExecutionRequest as _ExecReq  # noqa: PLC0415
        exec_req = _ExecReq(
            user=self.execution.user,
            action=referenced_action,
            environment=self.execution.environment,
            parameters=child_params if child_params else None,
            parent_execution_id=self.execution.id,
            correlation_id=self.correlation_id,
        )
        child_execution = None
        try:
            child_execution = self.execution_service.create_execution(exec_req)
            with self._step_lock:  # Thread-safe append (Story 65.2)
                self.child_executions.append(child_execution)

            parent_step.platform_job_id = str(child_execution.id)
            parent_step.save(update_fields=['platform_job_id'])

            if SimulationService.is_enabled():
                SimulationService.create_simulated_steps(child_execution)
                try:
                    SimulationService._run_simulation(child_execution.id, force_success=True)
                except Exception as sim_error:  # noqa: BLE001
                    logger.error(
                        "container_workflow_simulation_failed",
                        child_execution_id=child_execution.id,
                        parent_execution_id=self.execution.id,
                        error=str(sim_error),
                        correlation_id=self.correlation_id,
                        exc_info=True,
                    )
                    Execution.objects.filter(id=child_execution.id).update(
                        status=ExecutionStatus.FAILED,
                        completed_at=timezone.now(),
                        error_message=f"Simulation failed: {sim_error}",
                    )
            else:
                now = timezone.now()
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.COMPLETED,
                    started_at=now,
                    completed_at=now,
                )

            child_execution.refresh_from_db()

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

            if step_id is not None:
                output_mapping = step.get('output_mapping', {})
                if not isinstance(output_mapping, dict):
                    output_mapping = {}
                extractor = OutputExtractor()
                raw_output = parent_step.get_output() or {}
                extracted = extractor.extract(raw_output, output_mapping)
                with self._step_outputs_lock:
                    self._step_outputs[step_id] = extracted

            return cast(ExecutionStatus, child_execution.status)
        except Exception as exc:  # noqa: BLE001
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
            logger.error(
                "container_workflow_platform_step_exception",
                execution_id=self.execution.id,
                step_def_order=step_def_order,
                correlation_id=self.correlation_id,
                error=str(exc),
                exc_info=True,
            )
            return ExecutionStatus.FAILED

    def _execute_handler_step_for_parallel(
        self,
        step: Dict[str, Any],
        resolved_params: dict,
        step_name: str,
        step_id: str | None,
        step_type: str,
        handler: Union[
            ServiceCallHandler, HttpRequestHandler, EvaluationHandler, GateHandler
        ],
        step_order: int,
    ) -> ExecutionStatus:
        """Version thread-safe de _execute_handler_step avec step_order pré-alloué."""
        db_step_type = self._STEP_TYPE_TO_DB_TYPE.get(step_type, ExecutionStepType.PLATFORM)

        parent_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            config_step_id=step_id,
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
            return ExecutionStatus.FAILED

        # Gate WAITING dans un fan-out : limité en Phase 1 → FAILED
        # Les gate steps ne peuvent pas suspendre un fan-out (ThreadPoolExecutor déjà joiné).
        # Traitement complet des gates dans les fan-outs différé aux stories suivantes.
        if isinstance(result, dict) and result.get('waiting'):
            logger.warning(
                "container_workflow_parallel_gate_not_supported",
                step_name=step_name,
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            parent_step.status = ExecutionStepStatus.FAILED
            parent_step.completed_at = timezone.now()
            parent_step.save()
            return ExecutionStatus.FAILED

        if step_id is not None:
            output_mapping = step.get('output_mapping', {})
            if not isinstance(output_mapping, dict):
                output_mapping = {}
            extractor = OutputExtractor()
            if isinstance(result, dict) and 'raw_output' in result:
                raw_output = result.get('raw_output', {}) or {}
            else:
                raw_output = result if isinstance(result, dict) else {}
            extracted = extractor.extract(raw_output, output_mapping)
            with self._step_outputs_lock:
                self._step_outputs[step_id] = extracted

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
            config_step_id=step_id,
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
                # Mark child as FAILED explicitly before refresh (started_at for duration display)
                now = timezone.now()
                Execution.objects.filter(id=child_execution.id).update(
                    status=ExecutionStatus.FAILED,
                    started_at=now,
                    completed_at=now,
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
            with self._step_outputs_lock:
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
            config_step_id=step_id,
            step_type=db_step_type,
            status=ExecutionStepStatus.SKIPPED,
            started_at=now,
            completed_at=now,
        )

        # _step_outputs[step_id] = {} pour que les steps suivants obtiennent null
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
            config_step_id=step_id,
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
            # Do not re-raise: return FAILED so _execute_workflow_steps can finalize
            # (mark parent FAILED, audit, return terminal status) instead of bypassing
            return ExecutionStatus.FAILED

        # Protocole WAITING pour gate steps (story 57.7)
        # DOIT précéder l'output_mapping ET le fail-closed :
        # - évite que le gate soit marqué FAILED (fail-closed)
        # - évite que le dict gate {'waiting', 'gate_conditions', ...} pollue _step_outputs
        if isinstance(result, dict) and result.get('waiting'):
            gate_output = result.get('gate_output', {})
            gate_conditions = gate_output.get('gate_conditions', [])
            parent_step.set_output(gate_output)
            parent_step.status = ExecutionStepStatus.WAITING
            # NE PAS SET completed_at — step est en attente
            parent_step.save()

            # Story 58.3: broadcast step_update pour que la vue d'exécution s'actualise en temps réel
            from executions.utils.websocket_broadcast import broadcast_step_update  # noqa: PLC0415
            broadcast_step_update(self.execution.id, parent_step)

            logger.info(
                "container_workflow_gate_step_waiting",
                step_name=step_name,
                step_id=step_id,
                execution_id=self.execution.id,
                correlation_id=self.correlation_id,
            )
            # Story 57.8: Notification approbation requise (on_approval_required)
            is_approval_gate = any(
                isinstance(c, dict) and c.get('type') == 'approval_granted'
                for c in gate_conditions
            )
            if is_approval_gate:
                if self._has_approval_notification_configured():
                    self._schedule_approval_notification()
                # V113: Durable APPROVAL_REQUESTED event — UI catch-up on reconnect
                from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
                WorkflowEventService.emit_approval_requested(
                    self.execution.id, parent_step,
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
            with self._step_outputs_lock:
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

        # Story 67.4: Vague initiale explicite (resume après gate avec on_success_step_ids)
        initial_wave = getattr(self, '_initial_wave', None)
        if initial_wave:
            current_wave = [s for s in initial_wave if s in self._step_lookup_by_id]
        else:
            # Démarrer par le step d'ordre minimum
            first_step = min(self.workflow_steps, key=lambda s: s.get('order', 0))
            first_step_id = first_step.get('step_id')
            if not first_step_id:
                # Rétrocompat : step sans step_id → exécution séquentielle par ordre
                return self._execute_workflow_steps_sequential()
            current_wave = [first_step_id]

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
                # (gate WAITING en fan-out → FAILED dans _execute_handler_step_for_parallel).
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

        # Update parent execution final status (use queryset.update for reliable thread saves)
        update_fields = {
            'status': final_status,
            'completed_at': timezone.now(),
        }
        if final_status == ExecutionStatus.FAILED:
            step_info = f" (step: {_failed_step_name})" if _failed_step_name else ""
            update_fields['error_message'] = f"Workflow failed: a referenced action failed{step_info}"
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

        # Update parent execution final status
        update_fields = {
            'status': final_status,
            'completed_at': timezone.now(),
        }
        if final_status == ExecutionStatus.FAILED:
            step_info = f" (step: {_failed_step_name})" if _failed_step_name else ""
            update_fields['error_message'] = f"Workflow failed: a referenced action failed{step_info}"
        Execution.objects.filter(id=self.execution.id).update(**update_fields)
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
