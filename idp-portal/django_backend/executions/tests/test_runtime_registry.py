"""
Tests pour RuntimeRegistry — Story 34.4 (SOLID-BE-7).

Couvre :
- Enregistrement / récupération / liste des clés
- Dispatch via launch_workflow() pour item_type='workflow'
- Dispatch via launch_workflow() pour item_type='simulation'
- Clé inconnue → aucune exception (retour silencieux)
- Remplacement temporaire d'un runtime pour isoler les tests
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.runtime_registry import RuntimeRegistry


# ---------------------------------------------------------------------------
# Tests unitaires du registry (sans Django DB)
# ---------------------------------------------------------------------------


class TestRuntimeRegistryUnit:
    """Tests unitaires de la classe RuntimeRegistry (pas de DB)."""

    def setup_method(self) -> None:
        self.registry = RuntimeRegistry()

    def test_register_and_get(self) -> None:
        factory = MagicMock()
        self.registry.register("workflow", factory)
        assert self.registry.get("workflow") is factory

    def test_get_unknown_key_returns_none(self) -> None:
        assert self.registry.get("unknown_type") is None

    def test_list_keys(self) -> None:
        self.registry.register("workflow", MagicMock())
        self.registry.register("simulation", MagicMock())
        assert set(self.registry.list_keys()) == {"workflow", "simulation"}

    def test_unregister(self) -> None:
        self.registry.register("workflow", MagicMock())
        self.registry.unregister("workflow")
        assert self.registry.get("workflow") is None

    def test_unregister_unknown_key_is_noop(self) -> None:
        self.registry.unregister("nonexistent")  # should not raise

    def test_overwrite_logs_warning(self) -> None:
        from unittest.mock import patch
        import executions.runtime_registry as rr_module

        self.registry.register("workflow", MagicMock())
        with patch.object(rr_module.logger, "warning") as mock_warn:
            self.registry.register("workflow", MagicMock())
        mock_warn.assert_called_once_with("runtime_registry_overwrite", item_type="workflow")


# ---------------------------------------------------------------------------
# Tests via launch_workflow() (AC1)
# ---------------------------------------------------------------------------


class TestLaunchWorkflowViaRegistry:
    """
    Vérifient que launch_workflow() dispatche via RuntimeRegistry.
    On utilise un registry de test isolé du registry global.
    """

    def _make_execution(self, item_type: str) -> MagicMock:
        action = MagicMock()
        action.item_type = item_type
        execution = MagicMock()
        execution.action = action
        execution.id = 99
        return execution

    def test_runtime_registry_workflow(self) -> None:
        """launch_workflow() avec item_type='workflow' appelle la factory enregistrée."""
        from executions.runtime_registry import runtime_registry
        from executions.services import ExecutionService

        mock_workflow_runtime = MagicMock()
        original = runtime_registry.get("workflow")
        try:
            runtime_registry.register("workflow", mock_workflow_runtime)
            execution = self._make_execution("workflow")
            ExecutionService.launch_workflow(execution, correlation_id="test-corr")
            mock_workflow_runtime.assert_called_once_with(execution, correlation_id="test-corr")
        finally:
            # Restaurer le runtime d'origine
            if original is not None:
                runtime_registry.register("workflow", original)
            else:
                runtime_registry.unregister("workflow")

    def test_runtime_registry_simulation(self) -> None:
        """launch_workflow() avec item_type='simulation' appelle la factory enregistrée."""
        from executions.runtime_registry import runtime_registry
        from executions.services import ExecutionService

        mock_sim_runtime = MagicMock()
        original = runtime_registry.get("simulation")
        try:
            runtime_registry.register("simulation", mock_sim_runtime)
            execution = self._make_execution("simulation")
            ExecutionService.launch_workflow(execution, correlation_id="sim-corr")
            mock_sim_runtime.assert_called_once_with(execution, correlation_id="sim-corr")
        finally:
            if original is not None:
                runtime_registry.register("simulation", original)
            else:
                runtime_registry.unregister("simulation")

    def test_runtime_registry_unknown_key(self) -> None:
        """launch_workflow() avec clé inconnue → pas d'exception, retour silencieux."""
        from executions.services import ExecutionService

        execution = self._make_execution("unknown_item_type_xyz")
        # Should not raise
        ExecutionService.launch_workflow(execution)

    def test_launch_workflow_no_action(self) -> None:
        """launch_workflow() sans action attachée → retour immédiat sans exception."""
        from executions.services import ExecutionService

        execution = MagicMock()
        execution.action = None
        # Should not raise
        ExecutionService.launch_workflow(execution)


# ---------------------------------------------------------------------------
# Test du module global (vérification import)
# ---------------------------------------------------------------------------


def test_global_runtime_registry_has_workflow_key() -> None:
    """Le registry global contient au moins 'workflow' après import du module."""
    from executions.runtime_registry import runtime_registry
    assert "workflow" in runtime_registry.list_keys()


@pytest.mark.django_db
def test_register_defaults_simulation_when_flag_enabled(settings) -> None:  # type: ignore[no-untyped-def]
    """_register_defaults() enregistre 'simulation' quand SIMULATE_EXECUTION_DEV=True."""
    from executions.runtime_registry import RuntimeRegistry, _register_defaults

    settings.SIMULATE_EXECUTION_DEV = True
    isolated = RuntimeRegistry()
    with patch("executions.runtime_registry.runtime_registry", isolated):
        _register_defaults()

    assert "workflow" in isolated.list_keys()
    assert "simulation" in isolated.list_keys()


@pytest.mark.django_db
def test_register_defaults_no_simulation_by_default(settings) -> None:  # type: ignore[no-untyped-def]
    """Par défaut (SIMULATE_EXECUTION_DEV=False), 'simulation' n'est pas enregistré."""
    from executions.runtime_registry import RuntimeRegistry, _register_defaults

    settings.SIMULATE_EXECUTION_DEV = False
    isolated = RuntimeRegistry()
    with patch("executions.runtime_registry.runtime_registry", isolated):
        _register_defaults()

    assert "workflow" in isolated.list_keys()
    assert "simulation" not in isolated.list_keys()
