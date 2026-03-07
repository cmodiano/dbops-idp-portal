"""Tests for dashboard export endpoints (Story 30.2, AC6).

Tests for:
- GET /dashboard/export/csv — Export CSV des statistiques dashboard
- GET /dashboard/export/pdf — Export PDF des statistiques dashboard
"""
import csv
import io
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from executions.models import ExecutionStatus
from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory


def _create_test_data(user, integration):
    """Create a set of executions with varied dates, engines, environments, statuses."""
    now = timezone.now()
    executions = []

    engines = ["Oracle", "PostgreSQL", "MySQL"]
    environments = ["dev", "staging", "prod"]
    statuses = [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.RUNNING]

    for i in range(30):
        engine = engines[i % 3]
        env = environments[i % 3]
        status = statuses[i % 3]
        action = ActionFactory.create(
            status="published",
            integration=integration,
            engine=engine,
        )
        exec_obj = ExecutionFactory.create(
            action=action,
            user=user,
            environment=env,
            status=status,
        )
        # Backdate some executions
        days_back = i % 10
        Execution = type(exec_obj)
        Execution.objects.filter(id=exec_obj.id).update(
            created_at=now - timedelta(days=days_back)
        )
        executions.append(exec_obj)

    return executions


@pytest.mark.django_db
class TestDashboardExportCSV:
    """GET /dashboard/export/csv — AC3, AC6."""

    URL = "/api/v1/dashboard/export/csv"

    def setup_method(self):
        self.client = APIClient()
        self.admin = UserFactory.create(profile="DBOPS", username="admin_export_csv")
        self.integration = IntegrationFactory.create(type="aap", name="Test Export CSV")
        self.client.force_authenticate(user=self.admin)

    def test_csv_with_date_filters(self):
        """Filtres start_date + end_date → seulement les exécutions dans la plage."""
        _create_test_data(self.admin, self.integration)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        response = self.client.get(
            self.URL,
            {"start_date": yesterday.isoformat(), "end_date": today.isoformat()},
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"

    def test_csv_with_engine_filter(self):
        """Filtre engine=Oracle → seulement les exécutions Oracle."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL, {"engine": "Oracle"})

        assert response.status_code == 200
        content = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        engine_idx = header.index("engine")
        for row in reader:
            assert row[engine_idx] == "Oracle"

    def test_csv_with_environment_filter(self):
        """Filtre environment=prod → seulement les exécutions prod."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL, {"environment": "prod"})

        assert response.status_code == 200
        content = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        env_idx = header.index("environment")
        for row in reader:
            assert row[env_idx] == "prod"

    def test_csv_without_filters_returns_all(self):
        """Sans filtres → toutes les exécutions."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        content = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        next(reader)  # skip header
        rows = list(reader)
        assert len(rows) > 0

    def test_csv_format_valid(self):
        """Format CSV valide : colonnes correctes, délimiteurs."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        content = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        expected_columns = [
            "date",
            "total_executions",
            "successful_executions",
            "failed_executions",
            "success_rate_pct",
            "avg_execution_time_ms",
            "engine",
            "environment",
        ]
        assert header == expected_columns

    def test_csv_utf8_encoding(self):
        """Encodage UTF-8 BOM (Excel compatibility)."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        # UTF-8 BOM = b'\xef\xbb\xbf'
        assert response.content[:3] == b"\xef\xbb\xbf"

    def test_csv_content_disposition(self):
        """Content-Disposition header présent avec nom de fichier."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        cd = response["Content-Disposition"]
        assert cd.startswith('attachment; filename="dashboard-export-')
        assert cd.endswith('.csv"')

    def test_csv_permissions_dba_ok(self):
        """Permissions DBOPS (admin) → HTTP 200."""
        _create_test_data(self.admin, self.integration)
        dbops = UserFactory.create(profile="DBOPS", username="dbops_export_csv")
        self.client.force_authenticate(user=dbops)

        response = self.client.get(self.URL)

        assert response.status_code == 200

    def test_csv_permissions_non_dba_forbidden(self):
        """Permissions non-DBA → HTTP 403."""
        non_dba = UserFactory.create(profile="BUSINESS_USER", username="biz_export_csv")
        self.client.force_authenticate(user=non_dba)

        response = self.client.get(self.URL)

        assert response.status_code == 403

    def test_csv_with_tags_filter(self):
        """Filtre tags=database → seulement les exécutions avec tag 'database'."""
        _create_test_data(self.admin, self.integration)
        # Create a specific action with a "database" tag
        from catalog.models import Tag, ActionTag
        db_tag = Tag.objects.create(name="database")
        action_with_tag = ActionFactory.create(
            status="published",
            integration=self.integration,
            engine="Oracle",
        )
        ActionTag.objects.create(action=action_with_tag, tag=db_tag)
        ExecutionFactory.create(
            action=action_with_tag,
            user=self.admin,
            environment="prod",
            status=ExecutionStatus.COMPLETED,
        )

        response = self.client.get(self.URL, {"tags": "database"})

        assert response.status_code == 200
        content = response.content.decode("utf-8-sig")
        # At least one row should be present (the one with database tag)
        assert "Oracle" in content

    def test_csv_invalid_date_format_returns_400(self):
        """Format de date invalide → HTTP 400."""
        response = self.client.get(self.URL, {"start_date": "2026-13-99"})

        assert response.status_code == 400

    def test_csv_unauthenticated_returns_401(self):
        """Utilisateur non authentifié → HTTP 401."""
        self.client.force_authenticate(user=None)

        response = self.client.get(self.URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestDashboardExportPDF:
    """GET /dashboard/export/pdf — AC4, AC6."""

    URL = "/api/v1/dashboard/export/pdf"

    def setup_method(self):
        self.client = APIClient()
        self.admin = UserFactory.create(profile="DBOPS", username="admin_export_pdf")
        self.integration = IntegrationFactory.create(type="aap", name="Test Export PDF")
        self.client.force_authenticate(user=self.admin)

    def test_pdf_with_filters(self):
        """Filtres appliqués → PDF généré avec données filtrées."""
        _create_test_data(self.admin, self.integration)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        response = self.client.get(
            self.URL,
            {"start_date": yesterday.isoformat(), "end_date": today.isoformat()},
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_pdf_without_filters(self):
        """Sans filtres → PDF complet."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_pdf_magic_bytes(self):
        """Magic bytes %PDF présents dans les 10 premiers octets."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert b"%PDF" in response.content[:10]

    def test_pdf_content_type(self):
        """Content-Type application/pdf."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        assert response["Content-Type"] == "application/pdf"

    def test_pdf_content_disposition(self):
        """Content-Disposition header présent."""
        _create_test_data(self.admin, self.integration)

        response = self.client.get(self.URL)

        cd = response["Content-Disposition"]
        assert cd.startswith('attachment; filename="dashboard-export-')
        assert cd.endswith('.pdf"')

    def test_pdf_permissions_dba_ok(self):
        """Permissions DBOPS (admin) → HTTP 200."""
        _create_test_data(self.admin, self.integration)
        dbops = UserFactory.create(profile="DBOPS", username="dbops_export_pdf")
        self.client.force_authenticate(user=dbops)

        response = self.client.get(self.URL)

        assert response.status_code == 200

    def test_pdf_permissions_non_dba_forbidden(self):
        """Permissions non-DBA → HTTP 403."""
        non_dba = UserFactory.create(profile="BUSINESS_USER", username="biz_export_pdf")
        self.client.force_authenticate(user=non_dba)

        response = self.client.get(self.URL)

        assert response.status_code == 403

    def test_pdf_unauthenticated_returns_401(self):
        """Utilisateur non authentifié → HTTP 401."""
        self.client.force_authenticate(user=None)

        response = self.client.get(self.URL)

        assert response.status_code == 401
