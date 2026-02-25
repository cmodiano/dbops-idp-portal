"""
Tests pour le stockage des paramètres d'exécution dans audit_details.

Story 43.2 — AC1–AC8 : 6 tests couvrant la sanitisation des paramètres
et leur inclusion dans les détails d'audit.
"""
from __future__ import annotations

from django.test import TestCase

from catalog.models import Action, ActionStatus
from core.models import AuditActionType, AuditLog
from executions.services import ExecutionService, _sanitize_parameters
from idp_auth.models import User
from integrations.models import Integration


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _last_audit(action_type: str) -> AuditLog:
    return AuditLog.objects.filter(action_type=action_type).order_by("id").last()


# ---------------------------------------------------------------------------
# T3.5 — Tests unitaires purs de _sanitize_parameters (sans DB)
# ---------------------------------------------------------------------------


class TestSanitizeParametersPure:
    """Tests unitaires directs de _sanitize_parameters — aucune DB requise."""

    def test_sanitize_removes_sensitive_keys(self):
        """T3.5 : les clés sensibles sont supprimées du dict."""
        params = {
            "db_name": "PROD01",
            "password": "super_secret",
            "api_key": "abc123",
            "token": "tok_xyz",
            "secret": "s3cr3t",
            "private_key": "-----BEGIN RSA-----",
            "credential": "cred_val",
            "_env_config": {"requires_approval": True},
            "target": "server1.example.com",
        }
        result = _sanitize_parameters(params)
        assert result is not None
        assert result == {"db_name": "PROD01", "target": "server1.example.com"}

    def test_sanitize_case_insensitive(self):
        """Les clés sensibles sont filtrées indépendamment de la casse."""
        params = {
            "Password": "x",
            "API_KEY": "y",
            "TOKEN": "t",
            "SECRET": "s",
            "PRIVATE_KEY": "pk",
            "CREDENTIAL": "cred",
            "_ENV_CONFIG": {"requires_approval": True},
            "valid_key": "z",
        }
        result = _sanitize_parameters(params)
        assert result == {"valid_key": "z"}

    def test_sanitize_returns_none_when_all_sensitive(self):
        """Retourne None si tous les champs sont sensibles."""
        params = {"password": "x", "secret": "y"}
        result = _sanitize_parameters(params)
        assert result is None

    def test_sanitize_returns_none_for_none_input(self):
        """Retourne None si parameters est None."""
        assert _sanitize_parameters(None) is None

    def test_sanitize_returns_none_for_empty_dict(self):
        """Retourne None si parameters est un dict vide."""
        assert _sanitize_parameters({}) is None

    def test_sanitize_recursive_nested_dict(self):
        """Filtrage récursif sur les valeurs dict imbriquées."""
        params = {
            "db_name": "PROD01",
            "nested": {
                "host": "db.example.com",
                "password": "inner_secret",
            },
        }
        result = _sanitize_parameters(params)
        assert result is not None
        assert result["db_name"] == "PROD01"
        assert result["nested"] == {"host": "db.example.com"}

    def test_sanitize_nested_all_sensitive_excluded(self):
        """Un dict imbriqué entièrement sensible est exclu du résultat (pas inclus comme None)."""
        params = {
            "db_name": "PROD01",
            "nested": {"password": "x", "secret": "y"},
        }
        result = _sanitize_parameters(params)
        # nested est entièrement sensible → clé exclue, pas incluse comme None
        assert result is not None
        assert result == {"db_name": "PROD01"}
        assert "nested" not in result

    def test_sanitize_list_of_dicts(self):
        """Les dicts dans une liste sont filtrés récursivement."""
        params = {
            "db_name": "PROD01",
            "servers": [
                {"host": "server1.example.com", "password": "secret1"},
                {"host": "server2.example.com", "api_key": "key2"},
                {"password": "x"},  # Regression: dict with only sensitive keys → excluded
                "plain_string_item",
            ],
        }
        result = _sanitize_parameters(params)
        assert result is not None
        assert result["db_name"] == "PROD01"
        assert result["servers"][0] == {"host": "server1.example.com"}
        assert result["servers"][1] == {"host": "server2.example.com"}
        assert result["servers"][2] == "plain_string_item"
        # Dict with only sensitive keys is removed, not included as None
        assert len(result["servers"]) == 3
        assert {"password": "x"} not in result["servers"]


# ---------------------------------------------------------------------------
# T3.1–T3.4, T3.6 — Tests d'intégration avec DB
# ---------------------------------------------------------------------------


class TestAuditDetailsParameters(TestCase):
    """Tests d'intégration : paramètres dans audit_details lors de la création d'exécution."""

    def setUp(self):
        self.user = User.objects.create(
            username="audit_param_user",
            display_name="Audit Param User",
            profile="DBA",
        )
        self.integration = Integration.objects.create(
            type="aap",
            name="Audit Param Integration",
            base_url="https://aap.example.com",
        )
        self.action = Action.objects.create(
            name="Audit Param Action",
            category="Patching",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration,
        )
        self.service = ExecutionService()

    # T3.1
    def test_audit_details_includes_parameters_on_submitted(self):
        """AC1 : EXECUTION_SUBMITTED contient details.parameters avec les params métier."""
        params = {"db_name": "PROD01", "target": "server1.example.com"}
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=params,
        )
        entry = _last_audit(AuditActionType.EXECUTION_SUBMITTED)
        assert entry is not None
        details = entry.get_details()
        assert details is not None
        assert "parameters" in details
        assert details["parameters"]["db_name"] == "PROD01"
        assert details["parameters"]["target"] == "server1.example.com"

    # T3.2
    def test_audit_details_includes_parameters_on_pending_approval(self):
        """AC2 : EXECUTION_PENDING_APPROVAL contient details.parameters."""
        params = {
            "db_name": "PROD02",
            "_env_config": {"requires_approval": True},
        }
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=params,
        )
        entry = _last_audit(AuditActionType.EXECUTION_PENDING_APPROVAL)
        assert entry is not None
        details = entry.get_details()
        assert details is not None
        assert "parameters" in details
        assert details["parameters"]["db_name"] == "PROD02"
        # _env_config doit être exclu
        assert "_env_config" not in details["parameters"]

    # T3.3
    def test_audit_details_excludes_sensitive_fields(self):
        """AC3 : aucun champ sensible ne doit apparaître dans details.parameters."""
        params = {
            "db_name": "PROD03",
            "password": "super_secret",
            "_env_config": {"requires_approval": False},
            "api_key": "abc123",
            "token": "tok_xyz",
            "private_key": "pk",
            "secret": "shhh",
            "credential": "cred",
        }
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=params,
        )
        entry = _last_audit(AuditActionType.EXECUTION_SUBMITTED)
        assert entry is not None
        details = entry.get_details()
        assert details is not None
        parameters = details.get("parameters", {})
        for sensitive_key in ("password", "_env_config", "api_key", "token", "private_key", "secret", "credential"):
            assert sensitive_key not in parameters, f"Clé sensible trouvée : {sensitive_key}"
        assert parameters.get("db_name") == "PROD03"

    # T3.4
    def test_audit_details_no_parameter_key_when_empty(self):
        """AC6 : si parameters est None ou vide après nettoyage, pas de clé 'parameters' dans details."""
        # Cas 1 : parameters = None
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=None,
        )
        entry_none = _last_audit(AuditActionType.EXECUTION_SUBMITTED)
        details_none = entry_none.get_details()
        assert "parameters" not in (details_none or {})

        # Cas 2 : parameters = uniquement des clés sensibles → vide après nettoyage
        params_all_sensitive = {"password": "x", "_env_config": {"requires_approval": False}}
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=params_all_sensitive,
        )
        entry_empty = _last_audit(AuditActionType.EXECUTION_SUBMITTED)
        details_empty = entry_empty.get_details()
        assert "parameters" not in (details_empty or {})

    # T3.6
    def test_audit_details_no_duplicate_workflow_step_parameters(self):
        """AC4 : workflow_step_parameters n'est pas dupliqué dans details.parameters."""
        wsp = {"step_1": {"db": "PROD04"}}
        params = {
            "db_name": "PROD04",
            "workflow_step_parameters": wsp,
        }
        self.service._create_execution_atomic(
            user=self.user,
            action=self.action,
            environment="production",
            parameters=params,
        )
        entry = _last_audit(AuditActionType.EXECUTION_SUBMITTED)
        assert entry is not None
        details = entry.get_details()
        assert details is not None
        # workflow_step_parameters doit être présent comme clé top-level (Story 4.12)
        assert "workflow_step_parameters" in details
        assert details["workflow_step_parameters"] == wsp
        # Mais pas dans details["parameters"]
        parameters = details.get("parameters", {})
        assert "workflow_step_parameters" not in parameters
