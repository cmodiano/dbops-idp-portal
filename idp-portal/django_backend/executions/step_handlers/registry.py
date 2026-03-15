"""
Story 84.1: StepHandlerRegistry — registre centralisé des handlers de step types.

Pattern identique à GateDefinitionRegistry (executions/gates/registry.py) et
WorkflowStepDefinitionRegistry (capabilities/step_definitions.py).

Note : 'platform' est ABSENT volontairement de ce registre.
Il est géré par ContainerWorkflowRuntime._execute_platform_step() qui crée
des child executions — logique différente du protocole handler.execute().
"""
from __future__ import annotations

from executions.step_handlers.service_call_handler import ServiceCallHandler
from executions.step_handlers.http_request_handler import HttpRequestHandler
from executions.step_handlers.evaluation_handler import EvaluationHandler
from executions.step_handlers.gate_handler import GateHandler


class StepHandlerRegistry:
    """Registre singleton des classes handler par step_type.

    Permet d'enregistrer un handler par step_type et de le récupérer par code.
    Rend le dispatch des step types extensible par déclaration (Epic 84, R1).
    """

    def __init__(self) -> None:
        self._registry: dict[str, type] = {}

    def register(self, step_type: str, handler_class: type) -> None:
        """Enregistre une classe handler pour un step_type donné.

        Un ré-enregistrement du même step_type remplace le handler existant.
        """
        self._registry[step_type] = handler_class

    def get(self, step_type: str) -> type | None:
        """Retourne la classe handler pour un step_type, ou None si inconnu."""
        return self._registry.get(step_type)

    def list_types(self) -> list[str]:
        """Retourne les step_types enregistrés dans l'ordre d'insertion."""
        return list(self._registry)

    def is_registered(self, step_type: str) -> bool:
        """True si step_type est enregistré."""
        return step_type in self._registry


step_handler_registry = StepHandlerRegistry()

# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement des 4 handlers existants — source de vérité centralisée (Story 84.1)
# 'platform' est absent : géré par _execute_platform_step() (child executions)
# ─────────────────────────────────────────────────────────────────────────────

step_handler_registry.register('service_call', ServiceCallHandler)
step_handler_registry.register('http_request', HttpRequestHandler)
step_handler_registry.register('evaluation', EvaluationHandler)
step_handler_registry.register('gate', GateHandler)
