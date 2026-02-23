"""
Tests for services/registry.py — ServiceRegistry (Story 33.1, AC: 1, 2, 4).
"""
from __future__ import annotations

from typing import Any

import pytest

from services.registry import ServiceRegistry, service_registry


# ---------------------------------------------------------------------------
# Helper — minimal mock service for testing
# ---------------------------------------------------------------------------

class _MockService:
    """Minimal concrete service for registry tests."""

    def __init__(self, **config: Any) -> None:
        self.config = config


def _mock_factory(**config: Any) -> _MockService:
    return _MockService(**config)


# ---------------------------------------------------------------------------
# ServiceRegistry unit tests
# ---------------------------------------------------------------------------

class TestServiceRegistry:
    """Unit tests for ServiceRegistry class."""

    def setup_method(self) -> None:
        """Create a fresh registry for each test."""
        self.registry = ServiceRegistry()

    def test_register_and_get_returns_correct_instance(self) -> None:
        """register() + get() returns the service produced by the factory."""
        self.registry.register("mock", _mock_factory)
        svc = self.registry.get("mock")
        assert isinstance(svc, _MockService)

    def test_get_unknown_type_raises_value_error(self) -> None:
        """get() with unregistered type raises ValueError with correct message."""
        with pytest.raises(ValueError, match=r"Unsupported service_type: 'unknown'"):
            self.registry.get("unknown")

    def test_error_message_includes_available_types(self) -> None:
        """ValueError message includes available service types."""
        self.registry.register("alpha", _mock_factory)
        with pytest.raises(ValueError, match="alpha"):
            self.registry.get("missing")

    def test_list_types_empty_registry(self) -> None:
        """list_types() on empty registry returns empty list."""
        assert self.registry.list_types() == []

    def test_list_types_returns_registered_keys(self) -> None:
        """list_types() returns all registered service types."""
        self.registry.register("svc_a", _mock_factory)
        self.registry.register("svc_b", _mock_factory)
        types = self.registry.list_types()
        assert "svc_a" in types
        assert "svc_b" in types
        assert len(types) == 2

    def test_register_overwrites_existing_type(self) -> None:
        """Re-registering a type replaces the factory."""
        call_log: list[str] = []

        def factory_v1(**kwargs: Any) -> _MockService:
            call_log.append("v1")
            return _MockService()

        def factory_v2(**kwargs: Any) -> _MockService:
            call_log.append("v2")
            return _MockService()

        self.registry.register("svc", factory_v1)
        self.registry.register("svc", factory_v2)
        self.registry.get("svc")
        assert call_log == ["v2"]

    def test_get_forwards_kwargs_to_factory(self) -> None:
        """get() forwards keyword arguments to the factory function."""
        self.registry.register("cfg", _mock_factory)
        svc = self.registry.get("cfg", base_url="http://x", timeout=30.0)
        assert isinstance(svc, _MockService)
        assert svc.config["base_url"] == "http://x"
        assert svc.config["timeout"] == 30.0

    def test_error_message_contains_service_type(self) -> None:
        """ValueError message contains the unknown service_type."""
        with pytest.raises(ValueError, match="'my_unknown_svc'"):
            self.registry.get("my_unknown_svc")


# ---------------------------------------------------------------------------
# Module-level service_registry integration tests (AC: 1, 3)
# ---------------------------------------------------------------------------

class TestModuleLevelServiceRegistry:
    """Tests for the module-level service_registry instance."""

    def test_module_registry_has_five_services(self) -> None:
        """Module-level registry has exactly the 5 standard services."""
        types = service_registry.list_types()
        assert "vault" in types
        assert "splunk" in types
        assert "servicenow" in types
        assert "jira" in types
        assert "notification" in types
        assert len(types) == 5

    def test_module_registry_resolves_vault(self) -> None:
        """service_registry.get('vault') returns a VaultService instance."""
        from services.vault_service import VaultService
        svc = service_registry.get(
            "vault",
            vault_addr="http://vault:8200",
            vault_token="test-token",
        )
        assert isinstance(svc, VaultService)

    def test_module_registry_resolves_splunk(self) -> None:
        """service_registry.get('splunk') returns a SplunkService instance."""
        from services.splunk_service import SplunkService
        svc = service_registry.get(
            "splunk",
            base_url="https://splunk.example.com:8088",
            auth_headers={"Authorization": "Splunk token"},
        )
        assert isinstance(svc, SplunkService)

    def test_module_registry_resolves_servicenow(self) -> None:
        """service_registry.get('servicenow') returns a ServiceNowService instance."""
        from services.servicenow_service import ServiceNowService
        svc = service_registry.get(
            "servicenow",
            base_url="https://instance.service-now.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(svc, ServiceNowService)

    def test_module_registry_resolves_jira(self) -> None:
        """service_registry.get('jira') returns a JiraService instance."""
        from services.jira_service import JiraService
        svc = service_registry.get(
            "jira",
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )
        assert isinstance(svc, JiraService)

    def test_module_registry_resolves_notification(self) -> None:
        """service_registry.get('notification') returns a NotificationService instance."""
        from services.notification_service import NotificationService
        svc = service_registry.get("notification")
        assert isinstance(svc, NotificationService)

    def test_module_registry_unknown_raises_value_error(self) -> None:
        """service_registry.get() with unknown type raises ValueError."""
        with pytest.raises(ValueError, match=r"Unsupported service_type: 'pagerduty'"):
            service_registry.get("pagerduty")


# ---------------------------------------------------------------------------
# Integration test — register mock service → public factory resolves it (AC: 1, 4)
# ---------------------------------------------------------------------------

class TestServiceRegistryIntegration:
    """Integration: register a mock service and verify public factory resolves it."""

    def test_public_factory_resolves_newly_registered_service(self) -> None:
        """get_service_client() resolves a newly registered mock service."""
        from services import get_service_client

        service_registry.register("mock_svc", _mock_factory)
        try:
            svc = get_service_client("mock_svc", base_url="http://mock")
            assert isinstance(svc, _MockService)
            assert svc.config["base_url"] == "http://mock"
        finally:
            # Restore original registry to avoid test pollution
            service_registry.unregister("mock_svc")
