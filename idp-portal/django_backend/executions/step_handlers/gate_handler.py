"""
GateHandler — implémentation story 57.7

Handler pour les steps de type gate (ADR-007 §4e).
Crée un step WAITING avec gate_conditions ; réutilise GateEvaluator et Celery Beat existants.
"""
from __future__ import annotations

import structlog

from executions.models import Execution

logger = structlog.get_logger(__name__)


class GateHandler:
    """Handler pour les steps de type gate (ADR-007 §4e).

    Construit les gate_conditions depuis le step_config et retourne
    un dict signalant WAITING à _execute_handler_step().

    Types supportés :
    - gate_type: maintenance_window → condition {'type': 'maintenance_window'}
    - gate_type: approval           → condition {'type': 'approval_granted'} + context_from
    """

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        """
        Construit les gate_conditions et signale WAITING au runtime.

        Args:
            step_config: Définition du step (gate_type, timeout_hours, on_timeout, context_from, ...)
            resolved_params: Paramètres résolus via input_mapping (non utilisés pour les gates)
            execution: Instance Execution en cours
            step: Même dict que step_config (alias pour _execute_handler_step)
            correlation_id: ID de corrélation pour les logs

        Returns:
            dict: {'waiting': True, 'gate_conditions': [...], 'gate_output': {...}}
                  Interprété par _execute_handler_step() pour passer parent_step en WAITING.
        """
        gate_type = step_config.get('gate_type', 'maintenance_window')

        # Mapper gate_type → type de condition GateEvaluator
        condition_type_map = {
            'maintenance_window': 'maintenance_window',
            'approval': 'approval_granted',
        }
        condition_type = condition_type_map.get(gate_type, gate_type)

        # Construire la condition de base
        condition: dict = {'type': condition_type}

        # Timeout optionnel
        if 'timeout_hours' in step_config:
            condition['timeout_hours'] = step_config['timeout_hours']
            condition['on_timeout'] = step_config.get('on_timeout', 'FAIL')

        gate_conditions = [condition]

        # Construire l'output du step (sera stocké par _execute_handler_step)
        gate_output: dict = {'gate_conditions': gate_conditions}

        # Pour les gates approval : stocker context_from pour l'endpoint approve (story 57.8)
        context_from = step_config.get('context_from', [])
        if gate_type == 'approval' and context_from:
            gate_output['context_from'] = context_from
            logger.info(
                "gate_handler_approval_context",
                context_from=context_from,
                execution_id=execution.id,
                correlation_id=correlation_id,
            )

        logger.info(
            "gate_handler_waiting",
            gate_type=gate_type,
            condition_type=condition_type,
            has_timeout=('timeout_hours' in step_config),
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        return {
            'waiting': True,
            'gate_conditions': gate_conditions,
            'gate_output': gate_output,
        }
