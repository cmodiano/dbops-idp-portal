"""
Tests pour l'API d'audit globale avec filtres entity_type, action_type, user.

Story 43.1, AC1–AC9 : 9 tests couvrant les nouveaux filtres globaux.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from audit.views import AuditExecutionsView
from core.models import AuditActionType, AuditEntityType, AuditLog


@pytest.fixture
def rf() -> APIRequestFactory:
    return APIRequestFactory()


def _create_audit_log(
    entity_type: str = AuditEntityType.EXECUTION,
    action_type: str = AuditActionType.EXECUTION_COMPLETED,
    entity_id: int = 1,
    user_id: str = "42",
    details: dict | None = None,
) -> AuditLog:
    details_str = json.dumps(details or {"status": "COMPLETED"})
    return AuditLog.objects.create(
        user_id=user_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details_str,
        ip_address="127.0.0.1",
    )


def _get_audit(rf: APIRequestFactory, query_string: str = ""):
    """Effectue un GET sur AuditExecutionsView avec un auditeur mocké."""
    request = rf.get(f"/api/v1/audit/executions/?{query_string}")
    user = MagicMock()
    user.is_authenticated = True
    request.user = user
    request.auth = None
    force_authenticate(request, user=user)
    view = AuditExecutionsView.as_view()
    with patch("audit.views._is_auditor", return_value=True):
        return view(request)


@pytest.mark.django_db
class TestAuditGlobalFilters:
    """Tests pour les filtres globaux de l'API d'audit (Story 43.1)."""

    def test_audit_global_no_filter(self, rf: APIRequestFactory) -> None:
        """AC1 : sans filtre entity_type, retourne toutes les entrées (exécution + action)."""
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1)
        _create_audit_log(entity_type=AuditEntityType.ACTION, action_type=AuditActionType.ACTION_CREATED, entity_id=10)

        response = _get_audit(rf, "")

        assert response.status_code == 200
        data = response.data["data"]
        entity_types = {entry["entity_type"] for entry in data}
        assert AuditEntityType.EXECUTION in entity_types
        assert AuditEntityType.ACTION in entity_types
        assert len(data) == 2

    def test_audit_filter_entity_type_action(self, rf: APIRequestFactory) -> None:
        """AC2 : entity_type=action filtre correctement — uniquement les entrées action."""
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1)
        _create_audit_log(entity_type=AuditEntityType.ACTION, action_type=AuditActionType.ACTION_CREATED, entity_id=10)
        _create_audit_log(entity_type=AuditEntityType.ACTION, action_type=AuditActionType.ACTION_UPDATED, entity_id=11)

        response = _get_audit(rf, "entity_type=action")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 2
        for entry in data:
            assert entry["entity_type"] == AuditEntityType.ACTION

    def test_audit_filter_entity_type_execution_backward_compat(self, rf: APIRequestFactory) -> None:
        """AC3 : entity_type=execution = comportement actuel (rétro-compatibilité totale)."""
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1)
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=2)
        _create_audit_log(entity_type=AuditEntityType.ACTION, action_type=AuditActionType.ACTION_CREATED, entity_id=10)

        response = _get_audit(rf, "entity_type=execution")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 2
        for entry in data:
            assert entry["entity_type"] == AuditEntityType.EXECUTION

    def test_audit_filter_action_type(self, rf: APIRequestFactory) -> None:
        """AC4 : action_type=ACTION_PUBLISHED filtre correct sur le champ action_type."""
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_PUBLISHED,
            entity_id=10,
        )
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=11,
        )
        _create_audit_log(
            entity_type=AuditEntityType.EXECUTION,
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_id=1,
        )

        response = _get_audit(rf, "action_type=ACTION_PUBLISHED")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["action_type"] == AuditActionType.ACTION_PUBLISHED

    def test_audit_filter_user_by_username(self, rf: APIRequestFactory) -> None:
        """AC5 : user=john retourne les entrées des utilisateurs avec username 'john...'."""
        from idp_auth.models import User
        john = User.objects.create(username="johnsmith", display_name="John Smith")
        alice = User.objects.create(username="alice", display_name="Alice Dupont")

        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1, user_id=str(john.id))
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=2, user_id=str(alice.id))

        response = _get_audit(rf, "user=john")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["user_id"] == str(john.id)

    def test_audit_filter_user_by_display_name(self, rf: APIRequestFactory) -> None:
        """AC5 : user=Doe retourne les entrées des utilisateurs avec display_name contenant 'Doe'."""
        from idp_auth.models import User
        doe = User.objects.create(username="jdoe", display_name="Jane Doe")
        other = User.objects.create(username="other", display_name="Other Person")

        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1, user_id=str(doe.id))
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=2, user_id=str(other.id))

        response = _get_audit(rf, "user=Doe")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["user_id"] == str(doe.id)

    def test_audit_filter_combined_entity_action_user(self, rf: APIRequestFactory) -> None:
        """Combined filter: entity_type=action, action_type=ACTION_CREATED, user=john returns only matching entry."""
        from idp_auth.models import User
        john = User.objects.create(username="john", display_name="John Doe")
        alice = User.objects.create(username="alice", display_name="Alice")

        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=10,
            user_id=str(john.id),
        )
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_UPDATED,
            entity_id=11,
            user_id=str(john.id),
        )
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=12,
            user_id=str(alice.id),
        )
        _create_audit_log(
            entity_type=AuditEntityType.EXECUTION,
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_id=1,
            user_id=str(john.id),
        )

        response = _get_audit(rf, "entity_type=action&action_type=ACTION_CREATED&user=john")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["entity_type"] == AuditEntityType.ACTION
        assert data[0]["action_type"] == AuditActionType.ACTION_CREATED
        assert data[0]["user_id"] == str(john.id)

    def test_audit_filter_execution_only_ignored_for_non_exec(self, rf: APIRequestFactory) -> None:
        """AC6 : entity_type=action&environment=prod → filtre environment ignoré (pas de 400)."""
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=10,
        )

        response = _get_audit(rf, "entity_type=action&environment=prod")

        # Le filtre environment doit être ignoré silencieusement (pas d'erreur)
        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["entity_type"] == AuditEntityType.ACTION

    def test_audit_exec_only_filter_does_not_exclude_non_exec_entries(self, rf: APIRequestFactory) -> None:
        """AC6 : sans entity_type, un filtre execution-only (environment) ne doit pas
        exclure les entrées non-exécution — elles doivent rester présentes."""
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=999,
        )

        # Sans entity_type, environment=prod ne doit pas filtrer les entrées ACTION
        response = _get_audit(rf, "environment=prod")

        assert response.status_code == 200
        data = response.data["data"]
        action_entries = [e for e in data if e["entity_type"] == AuditEntityType.ACTION]
        assert len(action_entries) >= 1, (
            "Les entrées ACTION doivent rester présentes quand environment=prod "
            "est appliqué sans entity_type"
        )

    def test_audit_filter_entity_type_invalid(self, rf: APIRequestFactory) -> None:
        """AC : entity_type=foobar → 400 BadRequest."""
        response = _get_audit(rf, "entity_type=foobar")
        assert response.status_code == 400

    def test_audit_filter_action_type_invalid(self, rf: APIRequestFactory) -> None:
        """AC : action_type=FOOBAR → 400 BadRequest."""
        response = _get_audit(rf, "action_type=FOOBAR")
        assert response.status_code == 400
