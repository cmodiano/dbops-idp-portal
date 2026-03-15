"""
Tests unitaires pour StepHandlerRegistry — Story 84.1 (AC6).

Couvre :
- Enregistrement et lookup d'un handler (T4.2)
- get() sur type inconnu retourne None (T4.3)
- list_types() et is_registered() (T4.4)
- Les 4 handlers sont bien accessibles depuis step_handler_registry (T4.5)
"""
from __future__ import annotations


from executions.step_handlers.registry import StepHandlerRegistry, step_handler_registry
from executions.step_handlers.service_call_handler import ServiceCallHandler
from executions.step_handlers.http_request_handler import HttpRequestHandler
from executions.step_handlers.evaluation_handler import EvaluationHandler
from executions.step_handlers.gate_handler import GateHandler


# ---------------------------------------------------------------------------
# StepHandlerRegistry — tests unitaires isolés
# ---------------------------------------------------------------------------

class TestStepHandlerRegistryRegisterAndGet:
    """T4.2 — Enregistrement et lookup d'un handler."""

    def test_register_and_get_returns_handler_class(self):
        registry = StepHandlerRegistry()

        class FakeHandler:
            pass

        registry.register('fake_type', FakeHandler)
        assert registry.get('fake_type') is FakeHandler

    def test_reregister_same_type_replaces_handler(self):
        registry = StepHandlerRegistry()

        class HandlerV1:
            pass

        class HandlerV2:
            pass

        registry.register('my_type', HandlerV1)
        registry.register('my_type', HandlerV2)
        assert registry.get('my_type') is HandlerV2

    def test_get_instantiated_handler_is_callable(self):
        registry = StepHandlerRegistry()

        class FakeHandler:
            pass

        registry.register('fake_type', FakeHandler)
        handler_class = registry.get('fake_type')
        assert handler_class is not None
        instance = handler_class()
        assert isinstance(instance, FakeHandler)


class TestStepHandlerRegistryGetUnknownType:
    """T4.3 — get() sur type inconnu retourne None."""

    def test_get_unknown_type_returns_none(self):
        registry = StepHandlerRegistry()
        assert registry.get('nonexistent_type') is None

    def test_get_on_empty_registry_returns_none(self):
        registry = StepHandlerRegistry()
        assert registry.get('platform') is None


class TestStepHandlerRegistryListTypesAndIsRegistered:
    """T4.4 — list_types() et is_registered()."""

    def test_list_types_empty_registry(self):
        registry = StepHandlerRegistry()
        assert registry.list_types() == []

    def test_list_types_preserves_insertion_order(self):
        registry = StepHandlerRegistry()

        class H1:
            pass

        class H2:
            pass

        class H3:
            pass

        registry.register('alpha', H1)
        registry.register('beta', H2)
        registry.register('gamma', H3)
        assert registry.list_types() == ['alpha', 'beta', 'gamma']

    def test_is_registered_returns_true_for_known_type(self):
        registry = StepHandlerRegistry()

        class FakeHandler:
            pass

        registry.register('my_type', FakeHandler)
        assert registry.is_registered('my_type') is True

    def test_is_registered_returns_false_for_unknown_type(self):
        registry = StepHandlerRegistry()
        assert registry.is_registered('unknown') is False

    def test_is_registered_returns_false_on_empty_registry(self):
        registry = StepHandlerRegistry()
        assert registry.is_registered('platform') is False


# ---------------------------------------------------------------------------
# step_handler_registry singleton — vérification des 4 handlers (T4.5)
# ---------------------------------------------------------------------------

class TestStepHandlerRegistrySingleton:
    """T4.5 — Les 4 handlers sont bien accessibles depuis step_handler_registry."""

    def test_service_call_handler_registered(self):
        assert step_handler_registry.get('service_call') is ServiceCallHandler

    def test_http_request_handler_registered(self):
        assert step_handler_registry.get('http_request') is HttpRequestHandler

    def test_evaluation_handler_registered(self):
        assert step_handler_registry.get('evaluation') is EvaluationHandler

    def test_gate_handler_registered(self):
        assert step_handler_registry.get('gate') is GateHandler

    def test_platform_not_registered(self):
        """'platform' est géré par _execute_platform_step — pas dans le registre."""
        assert step_handler_registry.get('platform') is None
        assert step_handler_registry.is_registered('platform') is False

    def test_all_four_types_in_list_types(self):
        types = step_handler_registry.list_types()
        assert 'service_call' in types
        assert 'http_request' in types
        assert 'evaluation' in types
        assert 'gate' in types

    def test_all_four_handlers_are_registered(self):
        assert step_handler_registry.is_registered('service_call') is True
        assert step_handler_registry.is_registered('http_request') is True
        assert step_handler_registry.is_registered('evaluation') is True
        assert step_handler_registry.is_registered('gate') is True

    def test_singleton_has_at_least_the_four_base_types(self):
        """Les 4 handlers de base sont toujours présents (d'autres stories peuvent en ajouter)."""
        types = set(step_handler_registry.list_types())
        assert {'service_call', 'http_request', 'evaluation', 'gate'}.issubset(types)
