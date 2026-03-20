"""
GateHandler — Story 85.4 — Relocalisation vers app/handlers/.

Handler pour les steps de type gate (ADR-007 §4e).
Crée un step WAITING avec gate_conditions ; réutilise GateEvaluator et Celery Beat existants.
"""
from __future__ import annotations

import structlog

from executions.gates.registry import gate_registry
from executions.models import Execution

logger = structlog.get_logger(__name__)


class GateHandler:
    """Handler pour les steps de type gate (ADR-007 §4e).

    Construit les gate_conditions depuis le step_config et retourne
    un dict signalant WAITING à _execute_handler_step().

    Story 82.5: condition_type_map supprimé — gate_registry est la source de vérité.
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

        # Résoudre condition_type via le registre (Story 82.5)
        try:
            definition = gate_registry.get(gate_type)
            condition_type = definition.condition_type
        except KeyError:
            logger.warning(
                "gate_handler_unknown_gate_type",
                gate_type=gate_type,
                known_types=gate_registry.list_types(),
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
            condition_type = gate_type  # Fallback identique à l'ancien comportement
            definition = None

        # Construire la condition de base
        condition: dict = {'type': condition_type}

        # Timeout optionnel
        if 'timeout_hours' in step_config:
            condition['timeout_hours'] = step_config['timeout_hours']
            condition['on_timeout'] = step_config.get('on_timeout', 'FAIL')

        gate_conditions = [condition]

        # Construire l'output du step (sera stocké par _execute_handler_step)
        gate_output: dict = {'gate_conditions': gate_conditions}

        # Pour les gates à résolution manuelle : stocker context_from pour l'endpoint approve (story 57.8)
        # Utilise requires_manual_resolution du registre au lieu du literal 'approval' (Story 82.5 code review)
        context_from = step_config.get('context_from', [])
        if context_from and definition is not None and definition.requires_manual_resolution:
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
