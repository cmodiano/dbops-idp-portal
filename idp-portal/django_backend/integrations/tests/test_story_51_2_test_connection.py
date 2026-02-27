"""
Tests Story 51.2 — Endpoint POST /api/v1/admin/integrations/{id}/test-connection/

Couvre :
- Task 3.2 : test_connection_ok (mock dispatch → OK, vérifie réponse + update BD)
- Task 3.3 : test_connection_error (mock dispatch → ERROR)
- Task 3.4 : test_connection_unknown (mock dispatch → UNKNOWN)
- Task 3.5 : test_connection_not_found (pk inexistant → 404)
- Task 3.6 : test_connection_requires_auth (sans auth → 401/403)
- Task 3.7 : test_audit (vérifie AuditService.create_entry appelé avec les bons paramètres)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from rest_framework.test import APIClient

from integrations.health_check import HealthCheckResult, HealthCheckStatus


def _make_result(status: HealthCheckStatus, error_message: str | None = None) -> HealthCheckResult:
    """Helper pour créer un HealthCheckResult."""
    return HealthCheckResult(
        status=status,
        checked_at=datetime.now(dt_timezone.utc),
        error_message=error_message,
    )


def _create_integration(itype: str = "aap", name: str = "Test Integration"):
    """Crée une intégration en patchant le signal post_save."""
    from integrations.models import Integration

    with patch("integrations.tasks.run_integration_health_check"):
        integration = Integration.objects.create(
            type=itype,
            name=name,
            base_url="https://example.com",
            credential_ref="test-token",
        )
    return integration


@pytest.mark.django_db
class TestTestConnectionEndpoint:
    """Tests de l'endpoint POST /admin/integrations/{id}/test-connection/."""

    def setup_method(self):
        """Initialise le client API et crée les utilisateurs de test."""
        from idp_auth.models import User

        self.client = APIClient()

        self.dbops_user = User.objects.create(
            username="dbops_user_51_2",
            profile="dbops",
        )
        self.regular_user = User.objects.create(
            username="regular_user_51_2",
            profile="dba_applicatif",
        )

    def _url(self, integration_id) -> str:
        return f"/api/v1/admin/integrations/{integration_id}/test-connection/"

    # -------------------------------------------------------------------------
    # Task 3.2 — Cas OK
    # -------------------------------------------------------------------------

    def test_test_connection_ok(self, db):
        """Mock dispatch → OK : réponse 200 avec status=ok + BD mise à jour."""
        integration = _create_integration()
        mock_result = _make_result(HealthCheckStatus.OK)

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=mock_result), \
             patch("integrations.views.AuditService.create_entry"):
            response = self.client.post(self._url(integration.id))

        assert response.status_code == 200
        data = response.data["data"]
        assert data["status"] == "ok"
        assert data["message"] is None
        assert data["checked_at"] is not None

        # Vérifier mise à jour BD
        integration.refresh_from_db()
        assert integration.health_status == "ok"
        assert integration.health_error_message is None
        assert integration.health_checked_at is not None

    # -------------------------------------------------------------------------
    # Task 3.3 — Cas ERROR
    # -------------------------------------------------------------------------

    def test_test_connection_error(self, db):
        """Mock dispatch → ERROR : réponse 200 avec status=error + message d'erreur."""
        integration = _create_integration()
        mock_result = _make_result(HealthCheckStatus.ERROR, error_message="Connection refused")

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=mock_result), \
             patch("integrations.views.AuditService.create_entry"):
            response = self.client.post(self._url(integration.id))

        assert response.status_code == 200
        data = response.data["data"]
        assert data["status"] == "error"
        assert data["message"] == "Connection refused"

        integration.refresh_from_db()
        assert integration.health_status == "error"
        assert integration.health_error_message == "Connection refused"

    # -------------------------------------------------------------------------
    # Task 3.4 — Cas UNKNOWN (type non reconnu)
    # -------------------------------------------------------------------------

    def test_test_connection_unknown(self, db):
        """Type non géré → UNKNOWN : réponse 200 avec status=unknown."""
        integration = _create_integration(itype="unknown_type", name="Unknown Integration")

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.views.AuditService.create_entry"):
            response = self.client.post(self._url(integration.id))

        assert response.status_code == 200
        data = response.data["data"]
        assert data["status"] == "unknown"

        integration.refresh_from_db()
        assert integration.health_status == "unknown"

    # -------------------------------------------------------------------------
    # Task 3.5 — 404 si intégration introuvable
    # -------------------------------------------------------------------------

    def test_test_connection_not_found(self, db):
        """pk inexistant → 404 NotFoundError."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.post(self._url(99999))
        assert response.status_code == 404

    def test_test_connection_invalid_pk(self, db):
        """pk non numérique → 404 NotFoundError."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.post(self._url("not-a-number"))
        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Task 3.6 — Authentification requise
    # -------------------------------------------------------------------------

    def test_test_connection_requires_auth(self, db):
        """Sans authentification → 401 ou 403."""
        integration = _create_integration()
        response = self.client.post(self._url(integration.id))
        assert response.status_code in (401, 403)

    def test_test_connection_forbidden_non_dbops(self, db):
        """Utilisateur non-DBOPS → 403 Forbidden."""
        integration = _create_integration()
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self._url(integration.id))
        assert response.status_code == 403

    # -------------------------------------------------------------------------
    # Task 3.7 — Audit
    # -------------------------------------------------------------------------

    def test_test_connection_audit_logged(self, db):
        """AuditService.create_entry appelé avec les bons paramètres."""
        from core.models import AuditActionType, AuditEntityType

        integration = _create_integration()
        mock_result = _make_result(HealthCheckStatus.OK)

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=mock_result), \
             patch("integrations.views.AuditService.create_entry") as mock_audit:
            self.client.post(self._url(integration.id))

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs if mock_audit.call_args.kwargs else mock_audit.call_args[1]

        assert call_kwargs["action_type"] == AuditActionType.INTEGRATION_HEALTH_CHECK_TESTED
        assert call_kwargs["entity_type"] == AuditEntityType.INTEGRATION
        assert call_kwargs["entity_id"] == integration.id
        assert call_kwargs["details"]["status"] == "ok"
        assert call_kwargs["details"]["error_message"] is None
        assert "checked_at" in call_kwargs["details"]

    def test_test_connection_audit_logged_on_error(self, db):
        """AuditService.create_entry appelé avec status=error quand le health check échoue."""
        from core.models import AuditActionType

        integration = _create_integration()
        mock_result = _make_result(HealthCheckStatus.ERROR, error_message="Timeout")

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=mock_result), \
             patch("integrations.views.AuditService.create_entry") as mock_audit:
            self.client.post(self._url(integration.id))

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs if mock_audit.call_args.kwargs else mock_audit.call_args[1]
        assert call_kwargs["action_type"] == AuditActionType.INTEGRATION_HEALTH_CHECK_TESTED
        assert call_kwargs["details"]["status"] == "error"
        assert call_kwargs["details"]["error_message"] == "Timeout"

    def test_test_connection_dispatch_exception_returns_error(self, db):
        """Si le dispatch lève une exception, on logge et on retourne status=error."""
        integration = _create_integration()

        self.client.force_authenticate(user=self.dbops_user)

        with patch("integrations.tasks._resolve_and_check_adapter", side_effect=RuntimeError("Broker down")), \
             patch("integrations.views.logger") as mock_logger, \
             patch("integrations.views.AuditService.create_entry"):
            response = self.client.post(self._url(integration.id))

        assert response.status_code == 200
        data = response.data["data"]
        assert data["status"] == "error"
        assert "Broker down" in (data.get("message") or "")

        mock_logger.exception.assert_called_once_with(
            "test_connection_dispatch_error",
            integration_id=integration.id,
            error="Broker down",
            error_type="RuntimeError",
        )
