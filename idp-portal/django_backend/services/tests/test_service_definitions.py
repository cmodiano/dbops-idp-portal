"""
Story 82.3: Tests unitaires pour ServiceDefinition et ServiceDefinitionRegistry.

Vérifie l'enregistrement, le lookup, l'allowlist d'opérations, la détection
credential-free, et la dérivation de _SERVICE_TYPES pour le routing health check.
"""
from __future__ import annotations

import pytest

from services.definitions import ServiceDefinition, ServiceDefinitionRegistry, service_definition_registry


# ---------------------------------------------------------------------------
# Tests unitaires — ServiceDefinition (dataclass frozen)
# ---------------------------------------------------------------------------

class TestServiceDefinition:
    def test_frozen_dataclass_immutable(self) -> None:
        """ServiceDefinition est immuable (frozen=True)."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operations=frozenset({"op1"}),
            supports_health_check=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            defn.code = "modified"  # type: ignore[misc]

    def test_operations_is_frozenset(self) -> None:
        """Le champ operations est un frozenset."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operations=frozenset({"op1", "op2"}),
            supports_health_check=True,
        )
        assert isinstance(defn.operations, frozenset)


# ---------------------------------------------------------------------------
# Tests unitaires — ServiceDefinitionRegistry (registre isolé)
# ---------------------------------------------------------------------------

class TestServiceDefinitionRegistryIsolated:
    """Tests avec un registre frais pour éviter la pollution du singleton."""

    def _make_registry(self) -> ServiceDefinitionRegistry:
        reg = ServiceDefinitionRegistry()
        reg.register(ServiceDefinition(
            code="svc_a",
            display_name="Service A",
            requires_integration=True,
            operations=frozenset({"op1", "op2"}),
            supports_health_check=True,
        ))
        reg.register(ServiceDefinition(
            code="svc_b",
            display_name="Service B",
            requires_integration=False,
            operations=frozenset({"send"}),
            supports_health_check=False,
        ))
        return reg

    def test_register_and_get(self) -> None:
        reg = self._make_registry()
        defn = reg.get("svc_a")
        assert defn.code == "svc_a"
        assert defn.display_name == "Service A"

    def test_get_unknown_raises_key_error(self) -> None:
        reg = self._make_registry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_types_order(self) -> None:
        reg = self._make_registry()
        types = reg.list_types()
        assert types == ["svc_a", "svc_b"]

    def test_is_registered_true(self) -> None:
        reg = self._make_registry()
        assert reg.is_registered("svc_a") is True

    def test_is_registered_false(self) -> None:
        reg = self._make_registry()
        assert reg.is_registered("nonexistent") is False

    def test_get_allowed_operations_nominal(self) -> None:
        reg = self._make_registry()
        ops = reg.get_allowed_operations("svc_a")
        assert ops == frozenset({"op1", "op2"})

    def test_get_allowed_operations_unknown_raises_value_error(self) -> None:
        reg = self._make_registry()
        with pytest.raises(ValueError, match="Unknown integration_type"):
            reg.get_allowed_operations("unknown_service")

    def test_is_credential_free_requires_integration_false(self) -> None:
        """requires_integration=False → credential_free=True."""
        reg = self._make_registry()
        assert reg.is_credential_free("svc_b") is True

    def test_is_credential_free_requires_integration_true(self) -> None:
        """requires_integration=True → credential_free=False."""
        reg = self._make_registry()
        assert reg.is_credential_free("svc_a") is False

    def test_is_credential_free_unknown_returns_false(self) -> None:
        """Type inconnu → False (défaut sûr)."""
        reg = self._make_registry()
        assert reg.is_credential_free("nonexistent") is False


# ---------------------------------------------------------------------------
# Tests sur le singleton service_definition_registry (5 services enregistrés)
# ---------------------------------------------------------------------------

class TestServiceDefinitionRegistrySingleton:
    def test_list_types_contains_five_services(self) -> None:
        types = service_definition_registry.list_types()
        assert set(types) == {"vault", "splunk", "servicenow", "jira", "notification"}

    def test_list_types_length(self) -> None:
        assert len(service_definition_registry.list_types()) == 5

    def test_get_allowed_operations_servicenow(self) -> None:
        ops = service_definition_registry.get_allowed_operations("servicenow")
        assert "create_change" in ops
        assert "update_change" in ops
        assert "close_change" in ops
        assert "get_change_status" in ops
        assert "cancel_change" in ops

    def test_get_allowed_operations_vault(self) -> None:
        ops = service_definition_registry.get_allowed_operations("vault")
        assert "get_secret" in ops

    def test_get_allowed_operations_jira(self) -> None:
        ops = service_definition_registry.get_allowed_operations("jira")
        assert "create_issue" in ops
        assert "update_issue" in ops
        assert "get_issue" in ops

    def test_get_allowed_operations_notification(self) -> None:
        ops = service_definition_registry.get_allowed_operations("notification")
        assert "send_email" in ops
        assert "send_teams" in ops
        assert "notify_execution_event" in ops

    def test_get_allowed_operations_splunk_empty(self) -> None:
        """Splunk n'a pas d'opérations service_call (health check uniquement)."""
        ops = service_definition_registry.get_allowed_operations("splunk")
        assert ops == frozenset()

    def test_get_allowed_operations_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown integration_type"):
            service_definition_registry.get_allowed_operations("unknown_service")

    def test_is_credential_free_notification(self) -> None:
        assert service_definition_registry.is_credential_free("notification") is True

    def test_is_credential_free_servicenow(self) -> None:
        assert service_definition_registry.is_credential_free("servicenow") is False

    def test_is_credential_free_vault(self) -> None:
        assert service_definition_registry.is_credential_free("vault") is False

    def test_is_credential_free_unknown_returns_false(self) -> None:
        assert service_definition_registry.is_credential_free("nonexistent") is False

    def test_service_types_health_check_derivation(self) -> None:
        """La dérivation de _SERVICE_TYPES donne exactement servicenow, jira, splunk."""
        vault_type = "vault"
        derived = frozenset(
            code for code in service_definition_registry.list_types()
            if (
                service_definition_registry.get(code).supports_health_check
                and service_definition_registry.get(code).requires_integration
                and code != vault_type
            )
        )
        assert derived == {"servicenow", "jira", "splunk"}

    def test_vault_supports_health_check(self) -> None:
        defn = service_definition_registry.get("vault")
        assert defn.supports_health_check is True

    def test_notification_does_not_support_health_check(self) -> None:
        defn = service_definition_registry.get("notification")
        assert defn.supports_health_check is False

    def test_vault_requires_integration(self) -> None:
        defn = service_definition_registry.get("vault")
        assert defn.requires_integration is True
