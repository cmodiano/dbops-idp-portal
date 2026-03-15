"""
Tests purs (sans DB) pour WorkflowStepDefinition et WorkflowStepDefinitionRegistry.
Story 83.3 — AC7
"""
import dataclasses

import pytest

from capabilities.step_definitions import (
    WorkflowStepDefinition,
    WorkflowStepDefinitionRegistry,
    workflow_step_registry,
)


class TestWorkflowStepDefinitionRegistry:

    def test_list_types_returns_three_step_types(self):
        assert workflow_step_registry.list_types() == ['platform', 'service_call', 'gate']

    def test_get_platform_has_label(self):
        assert workflow_step_registry.get('platform').label == 'Exécuter'

    def test_get_platform_has_execution_category(self):
        assert workflow_step_registry.get('platform').category == 'execution'

    def test_get_platform_has_requires_integration_constraint(self):
        assert workflow_step_registry.get('platform').constraints == {'requires_integration': True}

    def test_get_service_call_has_label(self):
        assert workflow_step_registry.get('service_call').label == 'Service'

    def test_get_service_call_has_integration_category(self):
        assert workflow_step_registry.get('service_call').category == 'integration'

    def test_get_service_call_has_requires_service_integration_constraint(self):
        assert workflow_step_registry.get('service_call').constraints == {'requires_service_integration': True}

    def test_get_gate_has_label(self):
        assert workflow_step_registry.get('gate').label == 'Attendre'

    def test_get_gate_has_control_category(self):
        assert workflow_step_registry.get('gate').category == 'control'

    def test_get_gate_has_empty_constraints(self):
        assert workflow_step_registry.get('gate').constraints == {}

    def test_is_registered_known_code(self):
        assert workflow_step_registry.is_registered('platform') is True

    def test_is_registered_unknown_code(self):
        assert workflow_step_registry.is_registered('unknown') is False

    def test_get_unknown_raises_key_error(self):
        with pytest.raises(KeyError):
            workflow_step_registry.get('unknown')


class TestWorkflowStepDefinitionIsolated:
    """Tests sur un registre isolé pour ne pas dépendre du registre global."""

    def test_register_and_get(self):
        registry = WorkflowStepDefinitionRegistry()
        defn = WorkflowStepDefinition(code='test', label='Test', category='testing')
        registry.register(defn)
        assert registry.get('test') is defn

    def test_list_types_preserves_insertion_order(self):
        registry = WorkflowStepDefinitionRegistry()
        registry.register(WorkflowStepDefinition(code='c', label='C', category='cat'))
        registry.register(WorkflowStepDefinition(code='a', label='A', category='cat'))
        registry.register(WorkflowStepDefinition(code='b', label='B', category='cat'))
        assert registry.list_types() == ['c', 'a', 'b']

    def test_is_registered_returns_false_when_empty(self):
        registry = WorkflowStepDefinitionRegistry()
        assert registry.is_registered('anything') is False

    def test_definition_is_frozen(self):
        defn = WorkflowStepDefinition(code='x', label='X', category='cat')
        with pytest.raises(dataclasses.FrozenInstanceError):
            defn.code = 'y'  # type: ignore[misc]

    def test_default_config_schema_is_empty_dict(self):
        defn = WorkflowStepDefinition(code='x', label='X', category='cat')
        assert defn.config_schema == {}

    def test_default_constraints_is_empty_dict(self):
        defn = WorkflowStepDefinition(code='x', label='X', category='cat')
        assert defn.constraints == {}


class TestVariantsBuilder:
    """Story 83-6, AC1/AC2/AC6 — variants_builder sur WorkflowStepDefinition."""

    def test_gate_has_variants_builder(self):
        """AC6.1 : gate possède un variants_builder non-None."""
        assert workflow_step_registry.get('gate').variants_builder is not None

    def test_platform_has_no_variants_builder(self):
        """AC6.1 : platform n'a pas de variants_builder."""
        assert workflow_step_registry.get('platform').variants_builder is None

    def test_service_call_has_no_variants_builder(self):
        """AC6.1 : service_call n'a pas de variants_builder."""
        assert workflow_step_registry.get('service_call').variants_builder is None

    def test_default_variants_builder_is_none(self):
        """AC1.3 : une WorkflowStepDefinition créée sans variants_builder a variants_builder is None."""
        defn = WorkflowStepDefinition(code='x', label='X', category='cat')
        assert defn.variants_builder is None
