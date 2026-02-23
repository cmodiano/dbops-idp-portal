"""
Tests for adapters/registry.py — AdapterRegistry (Story 33.1, AC: 1, 2, 4).
"""
from __future__ import annotations


import pytest

from adapters.base_adapter import BaseAdapter
from adapters.registry import AdapterRegistry, adapter_registry


# ---------------------------------------------------------------------------
# Helper — minimal concrete BaseAdapter for testing
# ---------------------------------------------------------------------------

class _MockAdapter(BaseAdapter):
    """Minimal concrete adapter for registry tests."""

    async def trigger(self, **kwargs) -> dict:  # type: ignore[override]
        return {}

    async def get_status(self, platform_job_id: str, **kwargs) -> dict:  # type: ignore[override]
        return {}

    async def get_job_logs(self, platform_job_id: str, **kwargs) -> dict:  # type: ignore[override]
        return {}

    async def cancel_execution(self, platform_job_id: str, **kwargs) -> None:  # type: ignore[override]
        pass


def _mock_factory(**kwargs) -> _MockAdapter:
    return _MockAdapter()


# ---------------------------------------------------------------------------
# AdapterRegistry unit tests
# ---------------------------------------------------------------------------

class TestAdapterRegistry:
    """Unit tests for AdapterRegistry class."""

    def setup_method(self) -> None:
        """Create a fresh registry for each test."""
        self.registry = AdapterRegistry()

    def test_register_and_get_returns_correct_instance(self) -> None:
        """register() + get() returns the adapter produced by the factory."""
        self.registry.register("mock", _mock_factory)
        adapter = self.registry.get("mock")
        assert isinstance(adapter, _MockAdapter)
        assert isinstance(adapter, BaseAdapter)

    def test_get_unknown_type_raises_value_error(self) -> None:
        """get() with unregistered type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported platform_type: unknown"):
            self.registry.get("unknown")

    def test_list_types_empty_registry(self) -> None:
        """list_types() on empty registry returns empty list."""
        assert self.registry.list_types() == []

    def test_list_types_returns_registered_keys(self) -> None:
        """list_types() returns all registered platform types."""
        self.registry.register("alpha", _mock_factory)
        self.registry.register("beta", _mock_factory)
        types = self.registry.list_types()
        assert "alpha" in types
        assert "beta" in types
        assert len(types) == 2

    def test_register_overwrites_existing_type(self) -> None:
        """Re-registering a type replaces the factory."""
        call_log: list[str] = []

        def factory_v1(**kwargs) -> _MockAdapter:
            call_log.append("v1")
            return _MockAdapter()

        def factory_v2(**kwargs) -> _MockAdapter:
            call_log.append("v2")
            return _MockAdapter()

        self.registry.register("platform", factory_v1)
        self.registry.register("platform", factory_v2)
        self.registry.get("platform")
        assert call_log == ["v2"]

    def test_get_forwards_kwargs_to_factory(self) -> None:
        """get() forwards keyword arguments to the factory function."""
        received: dict = {}

        def capturing_factory(**kwargs) -> _MockAdapter:
            received.update(kwargs)
            return _MockAdapter()

        self.registry.register("cap", capturing_factory)
        self.registry.get("cap", base_url="http://x", auth_headers={"k": "v"})
        assert received["base_url"] == "http://x"
        assert received["auth_headers"] == {"k": "v"}

    def test_error_message_contains_platform_type(self) -> None:
        """ValueError message contains the unknown platform_type."""
        with pytest.raises(ValueError, match="gitlab_ci"):
            self.registry.get("gitlab_ci")


# ---------------------------------------------------------------------------
# Module-level adapter_registry integration tests (AC: 1, 3)
# ---------------------------------------------------------------------------

class TestModuleLevelAdapterRegistry:
    """Tests for the module-level adapter_registry instance."""

    def test_module_registry_has_five_platforms(self) -> None:
        """Module-level registry has exactly the 5 standard platforms."""
        types = adapter_registry.list_types()
        assert "aap" in types
        assert "tower" in types
        assert "azure_devops" in types
        assert "github_actions" in types
        assert "terraform_cloud" in types
        assert len(types) == 5

    def test_module_registry_resolves_aap(self) -> None:
        """adapter_registry.get('aap') returns a BaseAdapter instance."""
        adapter = adapter_registry.get(
            "aap",
            base_url="https://aap.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, BaseAdapter)

    def test_module_registry_resolves_tower(self) -> None:
        """adapter_registry.get('tower') returns a BaseAdapter instance."""
        adapter = adapter_registry.get(
            "tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, BaseAdapter)

    def test_module_registry_resolves_azure_devops(self) -> None:
        """adapter_registry.get('azure_devops') returns a BaseAdapter instance."""
        adapter = adapter_registry.get(
            "azure_devops",
            base_url="https://dev.azure.com/org",
            auth_headers={"Authorization": "Basic creds"},
        )
        assert isinstance(adapter, BaseAdapter)

    def test_module_registry_resolves_github_actions(self) -> None:
        """adapter_registry.get('github_actions') with owner+repo returns BaseAdapter."""
        adapter = adapter_registry.get(
            "github_actions",
            base_url="https://api.github.com",
            auth_headers={"Authorization": "Bearer token"},
            owner="myorg",
            repo="myrepo",
        )
        assert isinstance(adapter, BaseAdapter)

    def test_module_registry_resolves_terraform_cloud(self) -> None:
        """adapter_registry.get('terraform_cloud') with organization returns BaseAdapter."""
        adapter = adapter_registry.get(
            "terraform_cloud",
            base_url="https://app.terraform.io",
            auth_headers={"Authorization": "Bearer token"},
            organization="my-org",
        )
        assert isinstance(adapter, BaseAdapter)

    def test_module_registry_unknown_raises_value_error(self) -> None:
        """adapter_registry.get() with unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported platform_type: gitlab_ci"):
            adapter_registry.get("gitlab_ci")


# ---------------------------------------------------------------------------
# Integration test — register mock adapter → public factory resolves it (AC: 1, 4)
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    """Integration: register a mock adapter and verify public factory resolves it."""

    def test_public_factory_resolves_newly_registered_adapter(self) -> None:
        """get_platform_adapter() resolves a newly registered mock platform."""
        from adapters import get_platform_adapter

        adapter_registry.register("mock_platform", _mock_factory)
        try:
            adapter = get_platform_adapter(
                platform_type="mock_platform",
                base_url="https://mock.example.com",
                auth_headers={},
            )
            assert isinstance(adapter, _MockAdapter)
        finally:
            # Restore original registry to avoid test pollution
            adapter_registry.unregister("mock_platform")
