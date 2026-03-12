"""
Tests for Audit API correlation_id filter.

Story 27.8, AC5/AC8: 8 tests covering exact match, empty, not found,
combined filters, response format, pagination, CSV export, and case sensitivity.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory

from audit.views import AuditExecutionsView, AuditExportView
from core.models import AuditActionType, AuditEntityType, AuditLog


@pytest.fixture
def rf() -> APIRequestFactory:
    return APIRequestFactory()


def _create_audit_entry(
    user_id: str = "test_user",
    correlation_id: str | None = None,
    entity_id: int = 1,
    action_type: str = AuditActionType.EXECUTION_COMPLETED,
    environment: str = "prod",
) -> AuditLog:
    """Create an AuditLog entry for testing."""
    details = json.dumps({"action_id": 1, "environment": environment, "status": "COMPLETED"})
    return AuditLog.objects.create(
        user_id=user_id,
        action_type=action_type,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=entity_id,
        details=details,
        ip_address="127.0.0.1",
        correlation_id=correlation_id,
    )


def _make_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.is_authenticated = True
    user.id = "auditor"
    user.pk = "auditor"
    return user


def _get_audit(rf: APIRequestFactory, query_string: str = ""):
    """Make a GET request to AuditExecutionsView with auditor mock."""
    request = rf.get(f"/api/v1/audit/executions/?{query_string}")
    user = _make_user()
    # Force authentication by setting user on the request
    request.user = user
    request.auth = None
    # Use force_authenticate to bypass DRF permission checks
    from rest_framework.test import force_authenticate
    force_authenticate(request, user=user)
    view = AuditExecutionsView.as_view()
    with patch("audit.views.is_auditor_user", return_value=True):
        return view(request)


@pytest.mark.django_db
class TestAuditCorrelationIdFilter:
    """Test correlation_id filter on GET /audit/executions."""

    def test_filter_correlation_id_exact(self, rf: APIRequestFactory) -> None:
        """AC8 test 23: correlation_id=abc-123 -> returns only matching entries."""
        _create_audit_entry(correlation_id="abc-123", entity_id=1)
        _create_audit_entry(correlation_id="def-456", entity_id=2)
        _create_audit_entry(correlation_id="abc-123", entity_id=3)

        response = _get_audit(rf, "correlation_id=abc-123")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 2
        for entry in data:
            assert entry["correlation_id"] == "abc-123"

    def test_filter_correlation_id_empty(self, rf: APIRequestFactory) -> None:
        """AC8 test 24: correlation_id="" -> no filter applied."""
        _create_audit_entry(correlation_id="abc-123", entity_id=1)
        _create_audit_entry(correlation_id="def-456", entity_id=2)

        response = _get_audit(rf, "correlation_id=")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 2

    def test_filter_correlation_id_not_found(self, rf: APIRequestFactory) -> None:
        """AC8 test 25: non-existent correlation_id -> empty data."""
        _create_audit_entry(correlation_id="abc-123", entity_id=1)

        response = _get_audit(rf, "correlation_id=nonexistent-999")

        assert response.status_code == 200
        assert response.data["data"] == []

    def test_filter_correlation_id_with_other_filters(self, rf: APIRequestFactory) -> None:
        """AC8 test 26: correlation_id + user_id -> AND combination."""
        _create_audit_entry(user_id="alice", correlation_id="abc-123", entity_id=1)
        _create_audit_entry(user_id="bob", correlation_id="abc-123", entity_id=2)
        _create_audit_entry(user_id="alice", correlation_id="def-456", entity_id=3)

        response = _get_audit(rf, "correlation_id=abc-123&user_id=alice")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["user_id"] == "alice"
        assert data[0]["correlation_id"] == "abc-123"

    def test_response_includes_correlation_id(self, rf: APIRequestFactory) -> None:
        """AC8 test 27: each entry in data contains correlation_id field."""
        _create_audit_entry(correlation_id="uuid-test-001", entity_id=1)

        response = _get_audit(rf, "")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) >= 1
        assert "correlation_id" in data[0]
        assert data[0]["correlation_id"] == "uuid-test-001"

    def test_pagination_with_correlation_id(self, rf: APIRequestFactory) -> None:
        """AC8 test 28: 30 entries same correlation_id -> pagination works."""
        for i in range(30):
            _create_audit_entry(correlation_id="bulk-corr-id", entity_id=i + 1)

        response = _get_audit(rf, "correlation_id=bulk-corr-id&limit=10&offset=0")

        assert response.status_code == 200
        assert len(response.data["data"]) == 10
        assert response.data["pagination"]["total"] == 30
        assert response.data["pagination"]["total_pages"] == 3

    def test_correlation_id_case_sensitive(self, rf: APIRequestFactory) -> None:
        """AC8 test 30: ABC vs abc -> case-sensitive exact match."""
        _create_audit_entry(correlation_id="ABC-123", entity_id=1)
        _create_audit_entry(correlation_id="abc-123", entity_id=2)

        response = _get_audit(rf, "correlation_id=ABC-123")

        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["correlation_id"] == "ABC-123"


@pytest.mark.django_db
class TestAuditExportCorrelationId:
    """Test CSV export with correlation_id."""

    def test_export_csv_includes_correlation_id(self, rf: APIRequestFactory) -> None:
        """AC8 test 29: CSV export includes correlation_id column."""
        _create_audit_entry(correlation_id="export-corr-id", entity_id=1)

        request = rf.get("/api/v1/audit/export/?fmt=csv&correlation_id=export-corr-id")
        user = _make_user()
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=user)

        view = AuditExportView.as_view()
        with patch("audit.views.is_auditor_user", return_value=True):
            response = view(request)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        lines = content.strip().split("\n")
        # Header row should contain correlation_id
        header = lines[0]
        assert "correlation_id" in header
        # Data row should contain the correlation_id value
        if len(lines) > 1:
            assert "export-corr-id" in lines[1]
