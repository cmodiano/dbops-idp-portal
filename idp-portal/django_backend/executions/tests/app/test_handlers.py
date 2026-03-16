"""
Tests smoke pour executions/app/handlers/ — Story 85.4.
"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_import_from_app_handlers_registry():
    """Vérifier que app.handlers.registry est accessible et les 4 handlers enregistrés."""
    from executions.app.handlers.registry import StepHandlerRegistry, step_handler_registry
    assert StepHandlerRegistry is not None
    assert step_handler_registry.is_registered('service_call')
    assert step_handler_registry.is_registered('http_request')
    assert step_handler_registry.is_registered('evaluation')
    assert step_handler_registry.is_registered('gate')
    assert not step_handler_registry.is_registered('platform')


def test_import_from_app_handlers_condition_evaluator():
    """Vérifier que StepConditionEvaluator est accessible depuis app.handlers."""
    from executions.app.handlers.condition_evaluator import StepConditionEvaluator
    assert StepConditionEvaluator is not None
    evaluator = StepConditionEvaluator()
    mock_execution = MagicMock()
    mock_execution.environment = 'production'
    # Vérifie que la logique est intacte : step sans condition → should_execute = True
    assert evaluator.should_execute({}, mock_execution) is True
    # Vérifie la logique environment_in : environnement non dans la liste → should_execute = False
    step_with_condition = {'condition': {'environment_in': ['staging']}}
    assert evaluator.should_execute(step_with_condition, mock_execution) is False
    # Vérifie la logique environment_in : environnement dans la liste → should_execute = True
    step_matching = {'condition': {'environment_in': ['production', 'staging']}}
    assert evaluator.should_execute(step_matching, mock_execution) is True


def test_shim_step_handlers_registry_still_works():
    """Vérifier que le shim step_handlers.registry fonctionne (rétrocompatibilité)."""
    from executions.step_handlers.registry import step_handler_registry
    from executions.app.handlers.registry import step_handler_registry as app_registry
    # Le shim doit exposer le même objet singleton
    assert step_handler_registry is app_registry


def test_shim_condition_evaluator_still_works():
    """Vérifier que le shim step_handlers.condition_evaluator fonctionne."""
    from executions.step_handlers.condition_evaluator import StepConditionEvaluator
    from executions.app.handlers.condition_evaluator import StepConditionEvaluator as AppStepConditionEvaluator
    assert StepConditionEvaluator is AppStepConditionEvaluator


def test_shim_evaluation_handler_still_works():
    """Vérifier que le shim step_handlers.evaluation_handler fonctionne."""
    from executions.step_handlers.evaluation_handler import EvaluationHandler
    from executions.app.handlers.evaluation_handler import EvaluationHandler as AppEvaluationHandler
    assert EvaluationHandler is AppEvaluationHandler


def test_shim_gate_handler_still_works():
    """Vérifier que le shim step_handlers.gate_handler fonctionne."""
    from executions.step_handlers.gate_handler import GateHandler
    from executions.app.handlers.gate_handler import GateHandler as AppGateHandler
    assert GateHandler is AppGateHandler


def test_shim_service_call_handler_still_works():
    """Vérifier que le shim step_handlers.service_call_handler fonctionne."""
    from executions.step_handlers.service_call_handler import ServiceCallHandler
    from executions.app.handlers.service_call_handler import ServiceCallHandler as AppServiceCallHandler
    assert ServiceCallHandler is AppServiceCallHandler


def test_shim_http_request_handler_still_works():
    """Vérifier que le shim step_handlers.http_request_handler fonctionne (incl. _is_private_ip_literal)."""
    from executions.step_handlers.http_request_handler import HttpRequestHandler, _is_private_ip_literal
    from executions.app.handlers.http_request_handler import HttpRequestHandler as AppHttpRequestHandler
    from executions.app.handlers.http_request_handler import _is_private_ip_literal as app_fn
    assert HttpRequestHandler is AppHttpRequestHandler
    assert _is_private_ip_literal is app_fn
