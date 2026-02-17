"""
GateEvaluator service for evaluating gate_conditions on WAITING ExecutionSteps.
Story 25.3: Evaluates conditions and determines if a step can transition WAITING → RUNNING.
"""
from typing import Any

import structlog
from django.utils import timezone

from core.middleware import get_correlation_id
from inventory.services import InventoryService, InventoryServiceError

logger = structlog.get_logger(__name__)


class GateEvaluator:
    """
    Evaluate gate_conditions for an ExecutionStep in WAITING status.

    Returns (all_satisfied, gate_status) where:
    - all_satisfied: True if ALL conditions are met
    - gate_status: dict with per-condition details and timeout info
    """

    def __init__(self) -> None:
        self.inventory_service = InventoryService()

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
        requires_approval = False
        if isinstance(env_config, dict):
            requires_maintenance_window = bool(env_config.get("requires_maintenance_window", False))
            requires_approval = bool(env_config.get("requires_approval", False))

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
            gate_type = condition.get('type')
            match gate_type:
                case 'maintenance_window':
                    # Story 25.4: if maintenance window is not required for this env, auto-satisfy.
                    if not requires_maintenance_window:
                        satisfied = True
                        context = {'reason': "Plage de maintenance non requise pour cet environnement"}
                    else:
                        satisfied, context = self._check_maintenance_window(step, condition)
                case 'approval_granted':
                    # Story 25.4: if approval is not required for this env, auto-satisfy.
                    # If required=true, the actual approval mechanism is handled by a separate flow (future story).
                    if not requires_approval:
                        satisfied = True
                        context = {'reason': "Approbation non requise pour cet environnement"}
                    else:
                        satisfied = False
                        context = {'reason': "Approbation requise mais mécanisme d'approbation non implémenté"}
                case _:
                    # Unsupported gate types are not satisfied (future stories)
                    satisfied = False
                    context = {'reason': f'Unsupported gate type: {gate_type}'}

            gate_status.append({
                'type': gate_type,
                'satisfied': satisfied,
                **context,
            })

            if not satisfied:
                all_satisfied = False

        return all_satisfied, {'gates': gate_status, 'timeout_triggered': False}

    def _check_maintenance_window(self, step: Any, condition: dict) -> tuple[bool, dict]:
        """
        Check that ALL execution targets are within their maintenance window.

        Args:
            step: ExecutionStep instance
            condition: gate_condition dict with type='maintenance_window'

        Returns:
            tuple[bool, dict]: (satisfied, context with reason/next_possible_at/details)
        """
        correlation_id = get_correlation_id()
        targets = step.execution.targets.all()

        if not targets.exists():
            logger.info(
                "gate_evaluator_no_targets",
                step_id=step.id,
                correlation_id=correlation_id,
            )
            return True, {'reason': 'No targets configured — condition satisfied by default'}

        all_in_window = True
        next_starts = []
        target_details = []

        for target in targets:
            try:
                window = self.inventory_service.get_next_maintenance_window(target.target_id)

                if window is None:
                    # Story 25.3 code review: No maintenance window defined → BLOCK by default (fail-safe)
                    # Rationale: maintenance_window gates are security controls for PROD changes.
                    # If inventory doesn't define a window, safer to block than to allow.
                    # This prevents accidental PROD executions outside maintenance hours.
                    all_in_window = False
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': False,
                        'reason': 'No maintenance window configured in inventory (blocked by default)',
                    })
                    continue

                if window.get('is_active'):
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': True,
                        'reason': 'Within maintenance window',
                    })
                else:
                    all_in_window = False
                    next_start = window.get('start')
                    if next_start:
                        next_starts.append(next_start)
                    target_details.append({
                        'target_id': target.target_id,
                        'target_name': target.target_name,
                        'is_active': False,
                        'reason': 'Outside maintenance window',
                        'next_start': next_start.isoformat() if next_start else None,
                    })

            except InventoryServiceError as e:
                logger.error(
                    "gate_evaluator_inventory_error",
                    step_id=step.id,
                    target_id=target.target_id,
                    error=str(e),
                    correlation_id=correlation_id,
                )
                # Inventory error → condition NOT satisfied (safe default)
                all_in_window = False
                target_details.append({
                    'target_id': target.target_id,
                    'target_name': target.target_name,
                    'is_active': False,
                    'reason': f'Inventory service error: {str(e)}',
                })

        context = {
            'reason': 'All targets in maintenance window' if all_in_window
                      else 'One or more targets outside maintenance window',
            'details': target_details,
        }

        if next_starts:
            context['next_possible_at'] = max(next_starts).isoformat()

        return all_in_window, context

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
