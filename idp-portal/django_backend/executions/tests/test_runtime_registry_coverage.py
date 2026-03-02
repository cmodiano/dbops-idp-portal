"""
Tests de couverture pour executions/runtime_registry.py (Story 55).
Couvre les lignes manquantes :
  - 20    : TYPE_CHECKING import (non exécutable — ignoré)
  - 70-72 : corps de _workflow_runtime (ContainerWorkflowRuntime.run + log)
  - 82-85 : corps de _simulation_runtime (SimulationService + log)
"""
from unittest.mock import patch, MagicMock


class TestRuntimeRegistry:
    """Tests pour RuntimeRegistry."""

    def test_register_and_get(self):
        """register() + get() — cas nominal."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        factory = MagicMock()
        registry.register("mytype", factory)
        assert registry.get("mytype") is factory

    def test_get_unknown_returns_none(self):
        """get() pour un type non enregistré → None."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        assert registry.get("unknown") is None

    def test_register_overwrite_logs_warning(self):
        """register() avec un type déjà enregistré → logger.warning."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        factory1 = MagicMock()
        factory2 = MagicMock()

        with patch('executions.runtime_registry.logger') as mock_logger:
            registry.register("workflow", factory1)
            registry.register("workflow", factory2)
            mock_logger.warning.assert_called_once_with(
                "runtime_registry_overwrite", item_type="workflow"
            )

    def test_unregister(self):
        """unregister() retire un type enregistré."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        registry.register("mytype", MagicMock())
        registry.unregister("mytype")
        assert registry.get("mytype") is None

    def test_unregister_unknown_does_not_raise(self):
        """unregister() sur un type inconnu ne lève pas d'exception."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        registry.unregister("nonexistent")  # Ne doit pas lever

    def test_list_keys(self):
        """list_keys() retourne la liste des types enregistrés."""
        from executions.runtime_registry import RuntimeRegistry

        registry = RuntimeRegistry()
        registry.register("a", MagicMock())
        registry.register("b", MagicMock())
        keys = registry.list_keys()
        assert "a" in keys
        assert "b" in keys


class TestWorkflowRuntimeFactory:
    """Lignes 70-72 : corps de _workflow_runtime."""

    def test_workflow_runtime_calls_container_and_logs(self):
        """Lignes 70-72 : _workflow_runtime appelle ContainerWorkflowRuntime.run() et logger.info."""
        from executions.runtime_registry import runtime_registry

        # Récupérer la factory 'workflow' enregistrée par _register_defaults()
        factory = runtime_registry.get("workflow")
        assert factory is not None, "La factory 'workflow' doit être enregistrée"

        execution = MagicMock()
        execution.id = 99

        with patch('executions.runtime_registry.logger') as mock_logger, \
             patch('executions.container_workflow_runtime.ContainerWorkflowRuntime') as MockRuntime:
            mock_instance = MockRuntime.return_value
            mock_instance.run.return_value = None

            factory(execution, correlation_id="corr-workflow")

            MockRuntime.assert_called_once_with(execution)
            mock_instance.run.assert_called_once()
            mock_logger.info.assert_called_once_with(
                "container_workflow_execution_launched",
                execution_id=99,
                correlation_id="corr-workflow",
            )

    def test_workflow_runtime_without_correlation_id(self):
        """_workflow_runtime fonctionne sans correlation_id (paramètre optionnel)."""
        from executions.runtime_registry import runtime_registry

        factory = runtime_registry.get("workflow")
        execution = MagicMock()
        execution.id = 100

        with patch('executions.runtime_registry.logger'), \
             patch('executions.container_workflow_runtime.ContainerWorkflowRuntime') as MockRuntime:
            MockRuntime.return_value.run.return_value = None
            factory(execution)  # Sans correlation_id


class TestSimulationRuntimeFactory:
    """Lignes 82-85 : corps de _simulation_runtime."""

    def test_simulation_runtime_registers_when_setting_enabled(self):
        """Lignes 82-85 : SIMULATE_EXECUTION_DEV=True → 'simulation' enregistré."""
        from executions.runtime_registry import RuntimeRegistry, _register_defaults

        registry = RuntimeRegistry()

        with patch('executions.runtime_registry.runtime_registry', registry), \
             patch('django.conf.settings') as mock_settings:
            mock_settings.SIMULATE_EXECUTION_DEV = True

            with patch('executions.container_workflow_runtime.ContainerWorkflowRuntime'):
                _register_defaults()

            simulation_factory = registry.get("simulation")
            assert simulation_factory is not None

    def test_simulation_runtime_calls_service_and_logs(self):
        """Lignes 82-85 : _simulation_runtime appelle SimulationService et logger.info."""
        from executions.runtime_registry import RuntimeRegistry, _register_defaults

        registry = RuntimeRegistry()
        execution = MagicMock()
        execution.id = 77

        with patch('executions.runtime_registry.runtime_registry', registry), \
             patch('django.conf.settings') as mock_settings:
            mock_settings.SIMULATE_EXECUTION_DEV = True

            with patch('executions.container_workflow_runtime.ContainerWorkflowRuntime'):
                _register_defaults()

        simulation_factory = registry.get("simulation")
        assert simulation_factory is not None

        with patch('executions.runtime_registry.logger') as mock_logger, \
             patch('executions.simulation_service.SimulationService') as MockSim:
            simulation_factory(execution, correlation_id="corr-sim")

            MockSim.create_simulated_steps.assert_called_once_with(execution)
            MockSim.start_simulation.assert_called_once_with(execution)
            mock_logger.info.assert_called_once_with(
                "execution_simulation_started",
                execution_id=77,
                correlation_id="corr-sim",
            )

    def test_simulation_runtime_not_registered_when_setting_disabled(self):
        """SIMULATE_EXECUTION_DEV=False → 'simulation' non enregistré."""
        from executions.runtime_registry import RuntimeRegistry, _register_defaults

        registry = RuntimeRegistry()

        with patch('executions.runtime_registry.runtime_registry', registry), \
             patch('django.conf.settings') as mock_settings:
            mock_settings.SIMULATE_EXECUTION_DEV = False

            with patch('executions.container_workflow_runtime.ContainerWorkflowRuntime'):
                _register_defaults()

        assert registry.get("simulation") is None
