"""
Tests smoke pour executions/app/handlers/ — Story 85.4.
"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_import_from_app_handlers_registry():
    """Vérifier que app.handlers.registry est accessible et les 4 handlers enregistrés."""
    from executions.app.handlers.registry import step_handler_registry
    assert step_handler_registry.is_registered('service_call')
    assert step_handler_registry.is_registered('http_request')
    assert step_handler_registry.is_registered('evaluation')
    assert step_handler_registry.is_registered('gate')
    assert not step_handler_registry.is_registered('platform')


def test_import_from_app_handlers_condition_evaluator():
    """Vérifier que StepConditionEvaluator est accessible depuis app.handlers."""
    from executions.app.handlers.condition_evaluator import StepConditionEvaluator
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


def test_shim_handlers_identity():
    """Vérifier que les shims step_handlers.* exposent les mêmes objets que app.handlers.*."""
    shim_targets = [
        ("executions.step_handlers.registry", "step_handler_registry", "executions.app.handlers.registry", "step_handler_registry"),
        ("executions.step_handlers.condition_evaluator", "StepConditionEvaluator", "executions.app.handlers.condition_evaluator", "StepConditionEvaluator"),
        ("executions.step_handlers.evaluation_handler", "EvaluationHandler", "executions.app.handlers.evaluation_handler", "EvaluationHandler"),
        ("executions.step_handlers.gate_handler", "GateHandler", "executions.app.handlers.gate_handler", "GateHandler"),
        ("executions.step_handlers.service_call_handler", "ServiceCallHandler", "executions.app.handlers.service_call_handler", "ServiceCallHandler"),
        ("executions.step_handlers.http_request_handler", "HttpRequestHandler", "executions.app.handlers.http_request_handler", "HttpRequestHandler"),
        ("executions.step_handlers.http_request_handler", "_is_private_ip_literal", "executions.app.handlers.http_request_handler", "_is_private_ip_literal"),
    ]
    import importlib
    for shim_mod, shim_sym, app_mod, app_sym in shim_targets:
        shim_m = importlib.import_module(shim_mod)
        app_m = importlib.import_module(app_mod)
        shim_obj = getattr(shim_m, shim_sym)
        app_obj = getattr(app_m, app_sym)
        assert shim_obj is app_obj, f"{shim_mod}.{shim_sym} is not {app_mod}.{app_sym}"
