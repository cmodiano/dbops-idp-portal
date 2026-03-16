"""
GateEvaluator service for evaluating gate_conditions on WAITING ExecutionSteps.
Story 25.3: Evaluates conditions and determines if a step can transition WAITING → RUNNING.
Story 82.5: Utilise gate_registry pour valider les types et déléguer via requires_manual_resolution.
Story 83.2: Orchestrateur pur — délègue l'évaluation à GateDefinition.evaluation_strategy.
"""
from typing import Any

import structlog
from django.utils import timezone

from core.middleware import get_correlation_id
from executions.gates.definitions import GateEvaluationContext
from executions.gates.registry import gate_registry
from inventory.services import InventoryService

logger = structlog.get_logger(__name__)


class GateEvaluator:
    """
    Evaluate gate_conditions for an ExecutionStep in WAITING status.

    Returns (all_satisfied, gate_status) where:
    - all_satisfied: True if ALL conditions are met
    - gate_status: dict with per-condition details and timeout info
    """

    def __init__(
        self,
        inventory_service: InventoryService | None = None,
    ) -> None:
        """
        Args:
            inventory_service: Optional InventoryService to inject (defaults to
                               a new InventoryService() for production use).
                               Pass a mock in tests to avoid DB access.
        """
        self.inventory_service = inventory_service or InventoryService()

    def evaluate(self, step: Any) -> tuple[bool, dict]:
        """
        Evaluate all gate_conditions for a WAITING ExecutionStep.

        Args:
            step: ExecutionStep instance in WAITING status

        Returns:
            tuple[bool, dict]:
                - bool: True if ALL conditions satisfied
                - dict: gate_status with details per condition
        """
        output = step.get_output()
        if not output or 'gate_conditions' not in output:
            logger.warning(
                "gate_evaluator_no_conditions",
                step_id=step.id,
                correlation_id=get_correlation_id(),
            )
            return True, {'gates': [], 'timeout_triggered': False}

        gate_conditions = output['gate_conditions']
        params = step.execution.get_parameters() if hasattr(step.execution, "get_parameters") else {}
        env_config = (params or {}).get("_env_config") if isinstance(params, dict) else None
        requires_maintenance_window = False
        if isinstance(env_config, dict):
            requires_maintenance_window = bool(env_config.get("requires_maintenance_window", False))

        # Validate gate_conditions schema (Story 25.3 code review fix: HIGH-4)
        if not isinstance(gate_conditions, list):
            logger.error(
                "gate_evaluator_invalid_schema_not_list",
                step_id=step.id,
                gate_conditions_type=type(gate_conditions).__name__,
                correlation_id=get_correlation_id(),
            )
            return False, {
                'gates': [],
                'timeout_triggered': False,
                'error': 'Invalid gate_conditions schema: expected list',
            }

        for idx, condition in enumerate(gate_conditions):
            if not isinstance(condition, dict):
                logger.error(
                    "gate_evaluator_invalid_condition_not_dict",
                    step_id=step.id,
                    condition_index=idx,
                    condition_type=type(condition).__name__,
                    correlation_id=get_correlation_id(),
                )
                return False, {
                    'gates': [],
                    'timeout_triggered': False,
                    'error': f'Invalid gate condition at index {idx}: expected dict',
                }
            if 'type' not in condition or not isinstance(condition['type'], str):
                logger.error(
                    "gate_evaluator_invalid_condition_no_type",
                    step_id=step.id,
                    condition_index=idx,
                    condition=condition,
                    correlation_id=get_correlation_id(),
                )
                return False, {
                    'gates': [],
                    'timeout_triggered': False,
                    'error': f'Invalid gate condition at index {idx}: missing or invalid type',
                }

        # Check timeout FIRST (any condition with timeout_hours)
        for condition in gate_conditions:
            if 'timeout_hours' in condition:
                timeout_triggered, timeout_action = self._check_timeout(step, condition)
                if timeout_triggered:
                    return False, {
                        'gates': [],
                        'timeout_triggered': True,
                        'action': timeout_action,
                        'timeout_hours': condition['timeout_hours'],
                    }

        # Evaluate each gate condition
        gate_status = []
        all_satisfied = True

        for condition in gate_conditions:
            # condition_type est la valeur runtime stockée par GateHandler (ex: 'approval_granted')
            condition_type = condition.get('type')

            # Valider via le registre (condition_type side) — Story 82.5
            try:
                definition = gate_registry.get_for_condition_type(condition_type)
            except KeyError:
                # Type véritablement inconnu du registre
                satisfied = False
                context = {'reason': f'Unsupported gate type: {condition_type}'}
                gate_status.append({'type': condition_type, 'satisfied': satisfied, **context})
                all_satisfied = False
                continue

            if definition.requires_manual_resolution:
                # Gates nécessitant résolution humaine (ex: approval_granted)
                # Jamais auto-satisfaits par le poll GateEvaluator.
                satisfied = False
                context = {'reason': "En attente d'approbation explicite"}
            elif definition.evaluation_strategy is not None:
                # Gate auto-évalué : déléguer à la stratégie (Story 83.2)
                ctx = GateEvaluationContext(
                    step=step,
                    condition=condition,
                    inventory_service=self.inventory_service,
                    requires_maintenance_window=requires_maintenance_window,
                )
                satisfied, context = definition.evaluation_strategy.evaluate(ctx)
            else:
                # Gate enregistré sans stratégie d'évaluation (comportement case _: préservé)
                satisfied = False
                context = {'reason': f'No evaluator implemented for: {condition_type}'}

            gate_status.append({
                **context,
                # Mandatory keys last: prevent strategy context from silently overriding them.
                'type': condition_type,
                'satisfied': satisfied,
            })

            if not satisfied:
                all_satisfied = False

        return all_satisfied, {'gates': gate_status, 'timeout_triggered': False}

    def _check_timeout(self, step: Any, condition: dict) -> tuple[bool, str | None]:
        """
        Check if timeout_hours has been exceeded for a WAITING step.

        Args:
            step: ExecutionStep instance
            condition: gate_condition dict containing timeout_hours and on_timeout

        Returns:
            tuple[bool, str | None]:
                - bool: True if timeout is triggered
                - str | None: 'FAILED' or 'SKIPPED' if triggered, None otherwise
        """
        timeout_hours = condition.get('timeout_hours')
        if not timeout_hours:
            return False, None

        elapsed_hours = (timezone.now() - step.created_at).total_seconds() / 3600

        if elapsed_hours > timeout_hours:
            on_timeout = condition.get('on_timeout', 'FAIL')
            timeout_action = 'FAILED' if on_timeout == 'FAIL' else 'SKIPPED'

            logger.info(
                "gate_evaluator_timeout_triggered",
                step_id=step.id,
                elapsed_hours=round(elapsed_hours, 2),
                timeout_hours=timeout_hours,
                on_timeout=on_timeout,
                timeout_action=timeout_action,
                correlation_id=get_correlation_id(),
            )

            return True, timeout_action

        return False, None
