"""
RuntimeRegistry — dispatch de runtime d'exécution (Story 34.4, SOLID-BE-7).

Remplace le if/elif sur item_type dans launch_workflow().
OCP : enregistrer un nouveau runtime ne nécessite pas de modifier ExecutionService.

Registries existants du projet (référence) :
  - services/registry.py       → ServiceRegistry
  - adapters/registry.py       → AdapterRegistry
  - executions/interpreters/registry.py → OutputInterpreterRegistry
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

import structlog

if TYPE_CHECKING:
    from executions.models import Execution

logger = structlog.get_logger(__name__)


class RuntimeRegistry:
    """
    Registry de runtimes d'exécution.

    Associe item_type (str) à une factory callable(execution, correlation_id=None).
    Enregistrement via register(), dispatch via get().

    Note action standard : item_type == "action" n'a pas de runtime propre —
    launch_workflow() retourne silencieusement quand get() renvoie None.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register(self, item_type: str, factory: Callable) -> None:
        """Enregistrer une factory pour item_type."""
        with self._lock:
            if item_type in self._registry:
                logger.warning("runtime_registry_overwrite", item_type=item_type)
            self._registry[item_type] = factory

    def unregister(self, item_type: str) -> None:
        """Retirer un runtime (utilitaire de test)."""
        with self._lock:
            self._registry.pop(item_type, None)

    def get(self, item_type: str) -> Callable | None:
        """Retourner la factory ou None si non enregistrée."""
        return self._registry.get(item_type)

    def list_keys(self) -> list[str]:
        """Lister les item_types enregistrés."""
        with self._lock:
            return list(self._registry.keys())


runtime_registry = RuntimeRegistry()


def _register_defaults() -> None:
    """Enregistrer les runtimes par défaut au chargement du module."""
    from django.conf import settings  # noqa: PLC0415

    def _workflow_runtime(execution: Execution, correlation_id: str | None = None) -> None:
        from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
        ContainerWorkflowRuntime(execution).run()
        logger.info(
            "container_workflow_execution_launched",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

    runtime_registry.register("workflow", _workflow_runtime)

    if getattr(settings, "SIMULATE_EXECUTION_DEV", False):
        def _simulation_runtime(execution: Execution, correlation_id: str | None = None) -> None:
            from executions.simulation_service import SimulationService  # noqa: PLC0415
            SimulationService.create_simulated_steps(execution)
            SimulationService.start_simulation(execution)
            logger.info(
                "execution_simulation_started",
                execution_id=execution.id,
                correlation_id=correlation_id,
            )

        runtime_registry.register("simulation", _simulation_runtime)


_register_defaults()
