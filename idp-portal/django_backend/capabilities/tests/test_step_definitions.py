"""
Tests purs (sans DB) pour WorkflowStepDefinition et WorkflowStepDefinitionRegistry.
Story 83.3 — AC7 ; Story 84.3 — AC1, AC2
"""
import dataclasses

import pytest

from capabilities.step_definitions import (
    WorkflowStepDefinition,
    WorkflowStepDefinitionRegistry,
    workflow_step_registry,
)


class TestWorkflowStepDefinitionRegistry:

    def test_list_types_returns_six_step_types(self):
        """Story 84.3 (AC1) : schedule_execution ajouté → 6 types au total."""
        assert workflow_step_registry.list_types() == [
            'platform', 'service_call', 'gate', 'http_request', 'evaluation', 'schedule_execution'
        ]

    def test_get_platform_has_label(self):
        assert workflow_step_registry.get('platform').label == 'Exécuter'

    def test_get_platform_has_execution_category(self):
        assert workflow_step_registry.get('platform').category == 'execution'

    def test_get_platform_constraints_include_requires_integration(self):
        """Story 84.3 (AC2) : required_fields ajouté, requires_integration conservé."""
        constraints = workflow_step_registry.get('platform').constraints
        assert constraints['requires_integration'] is True
        assert 'required_fields' in constraints

    def test_get_platform_required_fields(self):
        """Story 84.3 (AC2) : platform.required_fields contient action_id."""
        rf = workflow_step_registry.get('platform').constraints['required_fields']
        assert isinstance(rf, list)
        assert len(rf) == 1
        assert rf[0]['field'] == 'action_id'
        assert 'message' in rf[0]

    def test_get_service_call_has_label(self):
        assert workflow_step_registry.get('service_call').label == 'Service'

    def test_get_service_call_has_integration_category(self):
        assert workflow_step_registry.get('service_call').category == 'integration'

    def test_get_service_call_constraints_include_requires_service_integration(self):
        """Story 84.3 (AC2) : required_fields ajouté, requires_service_integration conservé."""
        constraints = workflow_step_registry.get('service_call').constraints
        assert constraints['requires_service_integration'] is True
        assert 'required_fields' in constraints

    def test_get_service_call_required_fields(self):
        """Story 84.3 (AC2) : service_call.required_fields contient integration_type et operation."""
        rf = workflow_step_registry.get('service_call').constraints['required_fields']
        fields = [item['field'] for item in rf]
        assert 'integration_type' in fields
        assert 'operation' in fields

    def test_get_gate_has_label(self):
        assert workflow_step_registry.get('gate').label == 'Attendre'

    def test_get_gate_has_control_category(self):
        assert workflow_step_registry.get('gate').category == 'control'

    def test_get_gate_required_fields(self):
        """Story 84.3 (AC2) : gate.required_fields contient gate_type."""
        rf = workflow_step_registry.get('gate').constraints['required_fields']
        assert isinstance(rf, list)
        assert rf[0]['field'] == 'gate_type'

    def test_get_http_request_required_fields(self):
        """Story 84.3 (AC2) : http_request.required_fields contient url et method."""
        rf = workflow_step_registry.get('http_request').constraints['required_fields']
        fields = [item['field'] for item in rf]
        assert 'url' in fields
        assert 'method' in fields

    def test_get_evaluation_required_fields(self):
        """Story 84.3 (AC2) : evaluation.required_fields contient policy_id."""
        rf = workflow_step_registry.get('evaluation').constraints['required_fields']
        assert isinstance(rf, list)
        assert rf[0]['field'] == 'policy_id'

    def test_get_schedule_execution_is_registered(self):
        """Story 84.3 (AC1) : schedule_execution est dans le registre."""
        assert workflow_step_registry.is_registered('schedule_execution') is True

    def test_get_schedule_execution_label(self):
        """Story 84.3 (AC1) : label == 'Planifier'."""
        assert workflow_step_registry.get('schedule_execution').label == 'Planifier'

    def test_get_schedule_execution_category(self):
        """Story 84.3 (AC1) : category == 'scheduling'."""
        assert workflow_step_registry.get('schedule_execution').category == 'scheduling'

    def test_get_schedule_execution_required_fields(self):
        """Story 84.3 (AC2) : schedule_execution.required_fields contient action_id."""
        rf = workflow_step_registry.get('schedule_execution').constraints['required_fields']
        assert isinstance(rf, list)
        assert rf[0]['field'] == 'action_id'
        assert 'message' in rf[0]

    def test_all_types_have_required_fields_in_constraints(self):
        """Story 84.3 (AC2) : tous les types ont required_fields non vide dans constraints."""
        for code in workflow_step_registry.list_types():
            defn = workflow_step_registry.get(code)
            rf = defn.constraints.get('required_fields')
            assert rf is not None, f"{code}: required_fields manquant"
            assert isinstance(rf, list), f"{code}: required_fields doit être une liste"
            assert len(rf) >= 1, f"{code}: required_fields ne doit pas être vide"

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
