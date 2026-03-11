"""
Tests pour l'export CSV de l'audit — Story 43.6.
Vérifie la colonne entity_type, les filtres globaux, et action_name depuis details.
"""
from __future__ import annotations

import csv
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from audit.views import AuditExportView
from core.models import AuditActionType, AuditEntityType, AuditLog


@pytest.fixture
def rf() -> APIRequestFactory:
    return APIRequestFactory()


def _create_audit_entry(
    entity_type: str = AuditEntityType.EXECUTION,
    action_type: str = AuditActionType.EXECUTION_COMPLETED,
    entity_id: int = 1,
    details: dict | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        user_id="42",
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details or {}),
        ip_address="127.0.0.1",
    )


def _export_csv(rf: APIRequestFactory, query_string: str = "") -> list[dict]:
    """Helper : GET /audit/export/?fmt=csv&... → retourne les lignes CSV parsées."""
    qs_part = f"&{query_string}" if query_string else ""
    request = rf.get(f"/api/v1/audit/export/?fmt=csv{qs_part}")
    user = MagicMock()
    user.is_authenticated = True
    request.user = user
    force_authenticate(request, user=user)
    view = AuditExportView.as_view()
    with patch("audit.views.is_auditor_user", return_value=True):
        response = view(request)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


@pytest.mark.django_db
class TestAuditExportCsv:

    def test_export_csv_includes_entity_type_column(self, rf):
        """AC2 : le CSV contient la colonne entity_type avec la valeur correcte."""
        _create_audit_entry(entity_type=AuditEntityType.EXECUTION, entity_id=1)
        rows = _export_csv(rf)
        assert len(rows) >= 1
        assert "entity_type" in rows[0]
        assert rows[0]["entity_type"] == AuditEntityType.EXECUTION

    def test_export_csv_filters_by_entity_type(self, rf):
        """AC1 : le filtre entity_type=action exclut les entrées execution."""
        _create_audit_entry(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=10,
        )
        _create_audit_entry(
            entity_type=AuditEntityType.EXECUTION,
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_id=1,
        )
        rows = _export_csv(rf, "entity_type=action")
        assert all(r["entity_type"] == AuditEntityType.ACTION for r in rows)
        assert len(rows) == 1

    def test_export_csv_action_name_from_details_for_non_execution(self, rf):
        """AC4 : pour une entrée non-exécution, action_name est pris depuis details."""
        _create_audit_entry(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_PUBLISHED,
            entity_id=5,
            details={"action_name": "Deploy Production"},
        )
        rows = _export_csv(rf, "entity_type=action")
        assert len(rows) == 1
        assert rows[0]["action_name"] == "Deploy Production"

    def test_export_csv_includes_action_type_column(self, rf):
        """AC3 : le CSV contient toujours la colonne action_type (inchangée)."""
        _create_audit_entry(entity_type=AuditEntityType.EXECUTION, action_type=AuditActionType.EXECUTION_COMPLETED, entity_id=1)
        rows = _export_csv(rf)
        assert len(rows) >= 1
        assert "action_type" in rows[0]
        assert rows[0]["action_type"] == AuditActionType.EXECUTION_COMPLETED

    def test_export_csv_execution_only_columns_empty_for_non_execution(self, rf):
        """AC5 : pour les entrées non-exécution, execution_id/action_id/environment/status/servicenow_change_id sont vides."""
        _create_audit_entry(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=7,
            details={"action_name": "Test Action"},
        )
        rows = _export_csv(rf, "entity_type=action")
        assert len(rows) == 1
        row = rows[0]
        assert not row["execution_id"]
        assert not row["action_id"]
        assert row["environment"] == ""
        assert row["status"] == ""
        assert row["servicenow_change_id"] == ""
