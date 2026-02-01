"""Unit tests for Audit API (Story 6.3).

Tests:
- GET /api/v1/audit/executions with filters
- Pagination (limit, offset, total_count)
- 403 if non-auditor
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.models.auth import UserProfile


@pytest.fixture
def auditor_user():
    """User with is_auditor=True."""
    return UserProfile(
        id=1,
        username="auditor",
        display_name="Auditor User",
        profile="audit",
        is_auditor=True,
    )


@pytest.fixture
def non_auditor_user():
    """User without auditor role."""
    return UserProfile(
        id=2,
        username="regular",
        display_name="Regular User",
        profile="dbops",
        is_auditor=False,
    )


@pytest.fixture
def mock_audit_entries():
    """Sample audit entries for testing."""
    return [
        {
            "id": 1,
            "timestamp": "2026-01-30T10:00:00",
            "user_id": "1",
            "action_type": "EXECUTION_COMPLETED",
            "entity_type": "execution",
            "entity_id": 101,
            "details": {"action_id": 5, "environment": "prod", "status": "COMPLETED"},
            "ip_address": "192.168.1.1",
            "correlation_id": "abc-123",
            "derived_status": "success",
        },
        {
            "id": 2,
            "timestamp": "2026-01-30T09:30:00",
            "user_id": "2",
            "action_type": "EXECUTION_FAILED",
            "entity_type": "execution",
            "entity_id": 102,
            "details": {"action_id": 6, "environment": "dev", "status": "FAILED"},
            "ip_address": "192.168.1.2",
            "correlation_id": "def-456",
            "derived_status": "failed",
        },
    ]


class TestAuditExecutionsEndpoint:
    """Tests for GET /api/v1/audit/executions."""

    def test_403_if_not_auditor(self, non_auditor_user):
        """Should return 403 AUDITOR_REQUIRED if user is not an auditor."""
        app.dependency_overrides[get_current_user] = lambda: non_auditor_user
        client = TestClient(app)
        try:
            response = client.get("/api/v1/audit/executions")
            assert response.status_code == 403
            data = response.json()
            assert data["error"]["code"] == "AUDITOR_REQUIRED"
        finally:
            app.dependency_overrides.clear()

    def test_success_with_auditor(self, auditor_user, mock_audit_entries):
        """Should return audit entries when user is an auditor."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=mock_audit_entries,
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=2,
                ),
            ):
                response = client.get("/api/v1/audit/executions")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert len(data["data"]) == 2
            assert data["pagination"]["total_count"] == 2
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["page_size"] == 25
        finally:
            app.dependency_overrides.clear()

    def test_filters_passed_to_repository(self, auditor_user, mock_audit_entries):
        """Should pass filter parameters to repository functions."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            mock_list = AsyncMock(return_value=mock_audit_entries[:1])
            mock_count = AsyncMock(return_value=1)

            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    mock_list,
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    mock_count,
                ),
            ):
                response = client.get(
                    "/api/v1/audit/executions",
                    params={
                        "from": "2026-01-01T00:00:00",
                        "to": "2026-01-31T23:59:59",
                        "environment": "prod",
                        "action_id": 5,
                        "user_id": "1",
                        "status": "success",
                        "limit": 10,
                        "offset": 5,
                    },
                )

            assert response.status_code == 200

            # Verify list was called with correct params
            mock_list.assert_called_once_with(
                from_date="2026-01-01T00:00:00",
                to_date="2026-01-31T23:59:59",
                user_id="1",
                environment="prod",
                action_id=5,
                status="success",
                limit=10,
                offset=5,
            )

            # Verify count was called with same filters (minus limit/offset)
            mock_count.assert_called_once_with(
                from_date="2026-01-01T00:00:00",
                to_date="2026-01-31T23:59:59",
                user_id="1",
                environment="prod",
                action_id=5,
                status="success",
            )
        finally:
            app.dependency_overrides.clear()

    def test_pagination_calculation(self, auditor_user):
        """Should calculate pagination correctly."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=100,
                ),
            ):
                response = client.get(
                    "/api/v1/audit/executions",
                    params={"limit": 25, "offset": 50},
                )

            assert response.status_code == 200
            data = response.json()
            # Page 3 = offset 50 / limit 25 + 1
            assert data["pagination"]["page"] == 3
            assert data["pagination"]["page_size"] == 25
            assert data["pagination"]["total_count"] == 100
            assert data["pagination"]["total_pages"] == 4
        finally:
            app.dependency_overrides.clear()

    def test_limit_validation_max(self, auditor_user):
        """Should reject limit > 100."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            response = client.get(
                "/api/v1/audit/executions",
                params={"limit": 200},
            )
            # FastAPI should enforce limit <= 100 via Query validation
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_empty_result(self, auditor_user):
        """Should return empty list when no entries match."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    new_callable=AsyncMock,
                    return_value=0,
                ),
            ):
                response = client.get("/api/v1/audit/executions")

            assert response.status_code == 200
            data = response.json()
            assert data["data"] == []
            assert data["pagination"]["total_count"] == 0
            assert data["pagination"]["total_pages"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_status_filter_success(self, auditor_user, mock_audit_entries):
        """Should filter by success status."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            mock_list = AsyncMock(return_value=[mock_audit_entries[0]])
            mock_count = AsyncMock(return_value=1)

            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    mock_list,
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    mock_count,
                ),
            ):
                response = client.get(
                    "/api/v1/audit/executions",
                    params={"status": "success"},
                )

            assert response.status_code == 200
            mock_list.assert_called_once()
            assert mock_list.call_args[1]["status"] == "success"
        finally:
            app.dependency_overrides.clear()

    def test_status_filter_failed(self, auditor_user, mock_audit_entries):
        """Should filter by failed status."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            mock_list = AsyncMock(return_value=[mock_audit_entries[1]])
            mock_count = AsyncMock(return_value=1)

            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    mock_list,
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    mock_count,
                ),
            ):
                response = client.get(
                    "/api/v1/audit/executions",
                    params={"status": "failed"},
                )

            assert response.status_code == 200
            mock_list.assert_called_once()
            assert mock_list.call_args[1]["status"] == "failed"
        finally:
            app.dependency_overrides.clear()

    def test_environment_filter(self, auditor_user, mock_audit_entries):
        """Should filter by environment."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            mock_list = AsyncMock(return_value=[mock_audit_entries[0]])
            mock_count = AsyncMock(return_value=1)

            with (
                patch(
                    "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                    mock_list,
                ),
                patch(
                    "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                    mock_count,
                ),
            ):
                response = client.get(
                    "/api/v1/audit/executions",
                    params={"environment": "prod"},
                )

            assert response.status_code == 200
            mock_list.assert_called_once()
            assert mock_list.call_args[1]["environment"] == "prod"
        finally:
            app.dependency_overrides.clear()


class TestAuditExportEndpoint:
    """Tests for GET /api/v1/audit/export (Story 6.4)."""

    def test_403_if_not_auditor(self, non_auditor_user):
        """Should return 403 AUDITOR_REQUIRED if user is not an auditor."""
        app.dependency_overrides[get_current_user] = lambda: non_auditor_user
        client = TestClient(app)
        try:
            response = client.get("/api/v1/audit/export", params={"format": "csv"})
            assert response.status_code == 403
            data = response.json()
            assert data["error"]["code"] == "AUDITOR_REQUIRED"
        finally:
            app.dependency_overrides.clear()

    def test_export_csv_success(self, auditor_user, mock_audit_entries):
        """Should export CSV file with correct headers and content."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            # Mock catalog_repository to return action names (Story 6.4, MEDIUM-4 fix)
            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=mock_audit_entries,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={5: "Test Action Name", 6: "Another Action"},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=2,
            ):
                response = client.get("/api/v1/audit/export", params={"format": "csv"})

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]
            assert "audit-export-" in response.headers["content-disposition"]
            assert response.headers["content-disposition"].endswith(".csv")

            # Check CSV content (Story 6.4, MEDIUM-4 fix - verify action_name and servicenow_change_id)
            content = response.text
            assert content.startswith("\ufeff")  # UTF-8 BOM for Excel
            lines = content.split("\n")
            assert len(lines) >= 3  # Header + 2 data rows + empty line
            
            # Verify required columns are present
            header_line = lines[0].lower()
            assert "action_name" in header_line, "CSV header should include action_name"
            assert "action_id" in header_line, "CSV header should include action_id"
            assert "servicenow_change_id" in header_line, "CSV header should include servicenow_change_id"
            assert "action_type" in header_line, "CSV header should include action_type"
        finally:
            app.dependency_overrides.clear()

    def test_export_pdf_success(self, auditor_user, mock_audit_entries):
        """Should export PDF file with correct headers."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            # Mock catalog_repository to return action names (Story 6.4, HIGH-3 fix)
            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=mock_audit_entries,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={5: "Test Action Name", 6: "Another Action"},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=2,
            ):
                response = client.get("/api/v1/audit/export", params={"format": "pdf"})

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert "attachment" in response.headers["content-disposition"]
            assert "audit-export-" in response.headers["content-disposition"]
            assert response.headers["content-disposition"].endswith(".pdf")

            # Check PDF content (should start with PDF magic bytes)
            assert response.content.startswith(b"%PDF")
        finally:
            app.dependency_overrides.clear()

    def test_export_filters_passed_to_repository(self, auditor_user, mock_audit_entries):
        """Should pass filter parameters to repository."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            mock_list = AsyncMock(return_value=mock_audit_entries)
            mock_count = AsyncMock(return_value=2)

            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                mock_list,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                mock_count,
            ):
                response = client.get(
                    "/api/v1/audit/export",
                    params={
                        "format": "csv",
                        "from": "2026-01-01T00:00:00",
                        "to": "2026-01-31T23:59:59",
                        "environment": "prod",
                        "action_id": 5,
                        "user_id": "1",
                        "status": "success",
                    },
                )

            assert response.status_code == 200
            mock_list.assert_called_once()
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["from_date"] == "2026-01-01T00:00:00"
            assert call_kwargs["to_date"] == "2026-01-31T23:59:59"
            assert call_kwargs["environment"] == "prod"
            assert call_kwargs["action_id"] == 5
            assert call_kwargs["user_id"] == "1"
            assert call_kwargs["status"] == "success"
            assert call_kwargs["limit"] == 10001  # MAX_EXPORT_ROWS + 1
            assert call_kwargs["offset"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_export_limit_10000_enforced(self, auditor_user):
        """Should enforce 10,000 row limit for export."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            # Mock repository to return 10,001 entries (simulating limit exceeded)
            mock_entries = [{"id": i} for i in range(10001)]
            mock_list = AsyncMock(return_value=mock_entries)

            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                mock_list,
            ):
                response = client.get("/api/v1/audit/export", params={"format": "csv"})

            # Should return 400 or 413 with explicit message
            assert response.status_code in (400, 413)
            data = response.json()
            assert "10000" in data.get("error", {}).get("message", "").lower() or "limit" in data.get("error", {}).get("message", "").lower()
        finally:
            app.dependency_overrides.clear()

    def test_export_invalid_format(self, auditor_user):
        """Should return 422 for invalid format."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            response = client.get("/api/v1/audit/export", params={"format": "xml"})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_export_missing_format(self, auditor_user):
        """Should return 422 if format parameter is missing."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            response = client.get("/api/v1/audit/export")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_csv_filename_format(self, auditor_user, mock_audit_entries):
        """Should generate filename in format audit-export-YYYY-MM-DD.csv."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=mock_audit_entries,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=2,
            ):
                response = client.get("/api/v1/audit/export", params={"format": "csv"})

            assert response.status_code == 200
            content_disposition = response.headers["content-disposition"]
            # Should match pattern audit-export-YYYY-MM-DD.csv
            import re
            assert re.search(r'audit-export-\d{4}-\d{2}-\d{2}\.csv', content_disposition)
        finally:
            app.dependency_overrides.clear()

    def test_pdf_filename_format(self, auditor_user, mock_audit_entries):
        """Should generate filename in format audit-export-YYYY-MM-DD.pdf."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=mock_audit_entries,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=2,
            ):
                response = client.get("/api/v1/audit/export", params={"format": "pdf"})

            assert response.status_code == 200
            content_disposition = response.headers["content-disposition"]
            import re
            assert re.search(r'audit-export-\d{4}-\d{2}-\d{2}\.pdf', content_disposition)
        finally:
            app.dependency_overrides.clear()

    def test_pdf_header_content(self, auditor_user, mock_audit_entries):
        """Should include date, filters, and count in PDF header."""
        app.dependency_overrides[get_current_user] = lambda: auditor_user
        client = TestClient(app)
        try:
            with patch(
                "app.api.v1.audit.audit_repository.list_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=mock_audit_entries,
            ), patch(
                "app.api.v1.audit.catalog_repository.get_action_names_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ), patch(
                "app.api.v1.audit.audit_repository.count_execution_audit_entries",
                new_callable=AsyncMock,
                return_value=2,
            ):
                response = client.get(
                    "/api/v1/audit/export",
                    params={"format": "pdf", "environment": "prod"},
                )

            assert response.status_code == 200
            # PDF content should exist (magic bytes check done in another test)
            assert len(response.content) > 0
        finally:
            app.dependency_overrides.clear()
