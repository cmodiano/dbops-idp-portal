"""
Story 82.3: Tests unitaires pour ServiceDefinition et ServiceDefinitionRegistry.
Story 82.7: Tests pour operation_labels et get_operation_label.
Story 83.4: Tests pour ServiceOperationDefinition + migration vers operation_defs.

Vérifie l'enregistrement, le lookup, l'allowlist d'opérations, la détection
credential-free, et la dérivation de _SERVICE_TYPES pour le routing health check.
"""
from __future__ import annotations

import dataclasses

import pytest

from services.definitions import ServiceDefinition, ServiceDefinitionRegistry, ServiceOperationDefinition, service_definition_registry


# ---------------------------------------------------------------------------
# Tests unitaires — ServiceOperationDefinition (Story 83.4)
# ---------------------------------------------------------------------------

class TestServiceOperationDefinition:
    def test_service_operation_definition_defaults(self) -> None:
        """input_schema, output_schema, ui_hints sont {} par défaut."""
        op = ServiceOperationDefinition(code="test_op", label="Test Op")
        assert op.input_schema == {}
        assert op.output_schema == {}
        assert op.ui_hints == {}

    def test_service_operation_definition_frozen(self) -> None:
        """ServiceOperationDefinition est immuable (frozen=True)."""
        op = ServiceOperationDefinition(code="test_op", label="Test Op")
        with pytest.raises(dataclasses.FrozenInstanceError):
            op.code = "modified"  # type: ignore[misc]

    def test_service_operation_definition_construction_with_values(self) -> None:
        """Construction avec toutes les valeurs."""
        op = ServiceOperationDefinition(
            code="create_change",
            label="Créer un change",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            ui_hints={"widget": "textarea"},
        )
        assert op.code == "create_change"
        assert op.label == "Créer un change"
        assert op.input_schema == {"type": "object"}
        assert op.output_schema == {"type": "object"}
        assert op.ui_hints == {"widget": "textarea"}


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
            operation_defs=(ServiceOperationDefinition(code="op1", label="Op 1"),),
            supports_health_check=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            defn.code = "modified"  # type: ignore[misc]

    def test_operation_defs_is_tuple(self) -> None:
        """Le champ operation_defs est un tuple."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operation_defs=(
                ServiceOperationDefinition(code="op1", label="Op 1"),
                ServiceOperationDefinition(code="op2", label="Op 2"),
            ),
            supports_health_check=True,
        )
        assert isinstance(defn.operation_defs, tuple)

    def test_service_definition_operations_property(self) -> None:
        """defn.operations retourne le frozenset des codes."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operation_defs=(
                ServiceOperationDefinition(code="op1", label="Op 1"),
                ServiceOperationDefinition(code="op2", label="Op 2"),
            ),
            supports_health_check=True,
        )
        assert defn.operations == frozenset({"op1", "op2"})
        assert isinstance(defn.operations, frozenset)

    def test_service_definition_operations_property_empty(self) -> None:
        """Sans operation_defs, operations retourne frozenset vide."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
        )
        assert defn.operations == frozenset()

    def test_service_definition_get_operation_label_from_defs(self) -> None:
        """get_operation_label retourne le label dérivé de operation_defs."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operation_defs=(
                ServiceOperationDefinition(code="op1", label="Mon opération"),
            ),
        )
        assert defn.get_operation_label("op1") == "Mon opération"

    def test_service_definition_get_operation_label_fallback(self) -> None:
        """get_operation_label retourne le code si absent."""
        defn = ServiceDefinition(
            code="test",
            display_name="Test",
            requires_integration=True,
            operation_defs=(
                ServiceOperationDefinition(code="op1", label="Op 1"),
            ),
        )
        assert defn.get_operation_label("op2") == "op2"


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
            operation_defs=(
                ServiceOperationDefinition(code="op1", label="Op 1"),
                ServiceOperationDefinition(code="op2", label="Op 2"),
            ),
            supports_health_check=True,
        ))
        reg.register(ServiceDefinition(
            code="svc_b",
            display_name="Service B",
            requires_integration=False,
            operation_defs=(
                ServiceOperationDefinition(code="send", label="Envoyer"),
            ),
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

    def test_get_operation_def_nominal(self) -> None:
        """get_operation_def retourne la bonne définition."""
        reg = self._make_registry()
        op = reg.get_operation_def("svc_a", "op1")
        assert op.code == "op1"
        assert op.label == "Op 1"

    def test_get_operation_def_unknown_operation_raises(self) -> None:
        """get_operation_def lève KeyError si operation_code inconnu."""
        reg = self._make_registry()
        with pytest.raises(KeyError):
            reg.get_operation_def("svc_a", "unknown_op")

    def test_get_operation_def_unknown_service_raises(self) -> None:
        """get_operation_def lève KeyError si service_code inconnu."""
        reg = self._make_registry()
        with pytest.raises(KeyError):
            reg.get_operation_def("unknown_service", "op1")


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

    def test_servicenow_has_five_operation_defs(self) -> None:
        """servicenow a exactement 5 ServiceOperationDefinition."""
        defn = service_definition_registry.get("servicenow")
        assert len(defn.operation_defs) == 5
        codes = {op.code for op in defn.operation_defs}
        assert codes == {"create_change", "update_change", "close_change", "get_change_status", "cancel_change"}

    def test_splunk_has_empty_operation_defs(self) -> None:
        """Splunk n'a pas d'opérations."""
        defn = service_definition_registry.get("splunk")
        assert defn.operation_defs == ()

    def test_get_operation_def_nominal(self) -> None:
        """get_operation_def retourne la bonne définition pour servicenow."""
        op = service_definition_registry.get_operation_def("servicenow", "create_change")
        assert op.code == "create_change"
        assert op.label == "Créer un change"

    def test_get_operation_def_unknown_raises(self) -> None:
        """get_operation_def lève KeyError si operation_code inconnu."""
        with pytest.raises(KeyError):
            service_definition_registry.get_operation_def("servicenow", "unknown_op")


# ---------------------------------------------------------------------------
# Tests labels FR sur le singleton service_definition_registry (Story 82.7 → 83.4)
# ---------------------------------------------------------------------------

class TestServiceDefinitionSingletonLabels:
    """Tests des labels FR dérivés de operation_defs."""

    def test_servicenow_create_change_label(self) -> None:
        defn = service_definition_registry.get("servicenow")
        assert defn.get_operation_label("create_change") == "Créer un change"

    def test_servicenow_update_change_label(self) -> None:
        defn = service_definition_registry.get("servicenow")
        assert defn.get_operation_label("update_change") == "Mettre à jour le change"

    def test_servicenow_close_change_label(self) -> None:
        defn = service_definition_registry.get("servicenow")
        assert defn.get_operation_label("close_change") == "Fermer le change"

    def test_servicenow_get_change_status_label(self) -> None:
        defn = service_definition_registry.get("servicenow")
        assert defn.get_operation_label("get_change_status") == "Statut du change"

    def test_servicenow_cancel_change_label(self) -> None:
        defn = service_definition_registry.get("servicenow")
        assert defn.get_operation_label("cancel_change") == "Annuler le change"

    def test_vault_get_secret_label(self) -> None:
        defn = service_definition_registry.get("vault")
        assert defn.get_operation_label("get_secret") == "Lire un secret"

    def test_jira_create_issue_label(self) -> None:
        defn = service_definition_registry.get("jira")
        assert defn.get_operation_label("create_issue") == "Créer un ticket"

    def test_jira_update_issue_label(self) -> None:
        defn = service_definition_registry.get("jira")
        assert defn.get_operation_label("update_issue") == "Mettre à jour le ticket"

    def test_jira_get_issue_label(self) -> None:
        defn = service_definition_registry.get("jira")
        assert defn.get_operation_label("get_issue") == "Lire le ticket"

    def test_notification_send_email_label(self) -> None:
        defn = service_definition_registry.get("notification")
        assert defn.get_operation_label("send_email") == "Envoyer un email"

    def test_notification_send_teams_label(self) -> None:
        defn = service_definition_registry.get("notification")
        assert defn.get_operation_label("send_teams") == "Envoyer un message Teams"

    def test_notification_notify_execution_event_label(self) -> None:
        defn = service_definition_registry.get("notification")
        assert defn.get_operation_label("notify_execution_event") == "Notifier un événement d'exécution"

    def test_splunk_has_no_operation_defs(self) -> None:
        """Splunk n'a pas d'opérations → operation_defs vide."""
        defn = service_definition_registry.get("splunk")
        assert defn.operation_defs == ()
        assert defn.operations == frozenset()
