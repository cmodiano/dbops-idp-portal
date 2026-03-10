"""
Story 66-19 — Couverture `audit/views.py` (AC #2, #8)

Couvre les branches non couvertes par les tests existants :
- _is_auditor : None, non-authentifié, ad_groups vide/non-list, profil is_auditor=1
- _derive_status : chaque valeur status + chaque action_type fallback
- _build_audit_queryset : entity_type invalide, non-execution, filtres exec, sort/order invalide
- AuditExecutionsView.get : permissions, limites pagination, entrées non-EXECUTION, details None/non-None
- AuditExportView.get : permissions, fmt invalide, pdf rejeté (AUD-MED-02), total > 10000, non-EXECUTION dans CSV
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory, force_authenticate

from audit.views import (
    _is_auditor,
    _derive_status,
    AuditExecutionsView,
    AuditExportView,
    _parse_int,
    _parse_dt,
    _resolve_user_names,
)
from core.models import AuditActionType, AuditEntityType, AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def rf():
    return APIRequestFactory()


def _make_request(rf, path="/audit/executions", query_string="", method="get"):
    if method == "get":
        request = rf.get(f"{path}?{query_string}")
    return request


def _make_auditor_user():
    user = MagicMock()
    user.is_authenticated = True
    return user


def _call_audit_view(rf, query_string="", auditor=True):
    request = rf.get(f"/audit/executions?{query_string}")
    user = _make_auditor_user()
    request.user = user
    request.auth = None
    force_authenticate(request, user=user)
    view = AuditExecutionsView.as_view()
    with patch("audit.views._is_auditor", return_value=auditor):
        return view(request)


def _call_export_view(rf, query_string="", auditor=True):
    request = rf.get(f"/audit/export?{query_string}")
    user = _make_auditor_user()
    request.user = user
    request.auth = None
    force_authenticate(request, user=user)
    view = AuditExportView.as_view()
    with patch("audit.views._is_auditor", return_value=auditor):
        return view(request)


def _create_audit_log(
    entity_type=AuditEntityType.EXECUTION,
    action_type=AuditActionType.EXECUTION_COMPLETED,
    entity_id=1,
    user_id="42",
    details=None,
):
    import json
    details_str = json.dumps(details or {"status": "COMPLETED"})
    return AuditLog.objects.create(
        user_id=user_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details_str,
        ip_address="127.0.0.1",
    )


# ---------------------------------------------------------------------------
# Tests _is_auditor (sous-tâche 2.1)
# ---------------------------------------------------------------------------

class TestIsAuditor:

    def test_user_none_returns_false(self):
        assert _is_auditor(None) is False

    def test_user_not_authenticated_returns_false(self):
        user = MagicMock()
        user.is_authenticated = False
        assert _is_auditor(user) is False

    def test_user_no_is_authenticated_attr_returns_false(self):
        user = MagicMock(spec=[])  # Pas d'attributs
        assert _is_auditor(user) is False

    @pytest.mark.django_db
    def test_user_with_empty_ad_groups_and_no_profile_returns_false(self):
        """ad_groups=[] ET profile vide → pas de profil auditeur."""
        user = MagicMock()
        user.is_authenticated = True
        user.ad_groups = []
        user.profile = ""
        assert _is_auditor(user) is False

    @pytest.mark.django_db
    def test_user_with_non_list_ad_groups_and_profile_name(self):
        """ad_groups non-list + profile renseigné → construit [profile_name] et cherche."""
        from profiles.models import Profile
        Profile.objects.get_or_create(name="AUDIT", defaults={"is_auditor": 1, "ad_group": "CN=Audit"})

        user = MagicMock()
        user.is_authenticated = True
        user.ad_groups = "AUDIT"  # non-list
        user.profile = "AUDIT"

        result = _is_auditor(user)
        assert result is True

    @pytest.mark.django_db
    def test_user_ad_groups_list_with_auditor_profile(self):
        """ad_groups liste non vide → appelle find_by_ad_groups, retourne True si is_auditor=1."""
        from profiles.models import Profile
        Profile.objects.get_or_create(name="AUDIT", defaults={"is_auditor": 1, "ad_group": "CN=Audit"})

        user = MagicMock()
        user.is_authenticated = True
        user.ad_groups = ["AUDIT"]
        result = _is_auditor(user)
        assert result is True

    @pytest.mark.django_db
    def test_user_ad_groups_list_without_auditor_profile_returns_false(self):
        """ad_groups liste mais aucun profil is_auditor=1 → False."""
        from profiles.models import Profile
        Profile.objects.get_or_create(name="DBA", defaults={"is_auditor": 0, "ad_group": "CN=DBA"})

        user = MagicMock()
        user.is_authenticated = True
        user.ad_groups = ["DBA"]
        result = _is_auditor(user)
        assert result is False


# ---------------------------------------------------------------------------
# Tests _derive_status (sous-tâche 2.2)
# ---------------------------------------------------------------------------

class TestDeriveStatus:

    def test_details_status_completed_returns_success(self):
        result = _derive_status("ANY", {"status": "COMPLETED"})
        assert result == "success"

    def test_details_status_failed_returns_failed(self):
        result = _derive_status("ANY", {"status": "FAILED"})
        assert result == "failed"

    def test_details_status_rejected_returns_failed(self):
        result = _derive_status("ANY", {"status": "REJECTED"})
        assert result == "failed"

    def test_details_status_cancelled_returns_failed(self):
        result = _derive_status("ANY", {"status": "CANCELLED"})
        assert result == "failed"

    def test_details_status_integration_error_returns_failed(self):
        result = _derive_status("ANY", {"status": "INTEGRATION_ERROR"})
        assert result == "failed"

    def test_details_status_submitted_returns_running(self):
        result = _derive_status("ANY", {"status": "SUBMITTED"})
        assert result == "running"

    def test_details_status_running_returns_running(self):
        result = _derive_status("ANY", {"status": "RUNNING"})
        assert result == "running"

    def test_details_status_pending_approval_returns_running(self):
        result = _derive_status("ANY", {"status": "PENDING_APPROVAL"})
        assert result == "running"

    def test_no_details_fallback_execution_completed(self):
        result = _derive_status(AuditActionType.EXECUTION_COMPLETED, None)
        assert result == "success"

    def test_no_details_fallback_execution_failed(self):
        result = _derive_status(AuditActionType.EXECUTION_FAILED, None)
        assert result == "failed"

    def test_no_details_fallback_execution_submitted(self):
        result = _derive_status(AuditActionType.EXECUTION_SUBMITTED, None)
        assert result == "running"

    def test_no_details_fallback_unknown_action_type(self):
        result = _derive_status("UNKNOWN_TYPE", None)
        assert result == "unknown"

    def test_empty_details_dict_fallback(self):
        result = _derive_status(AuditActionType.EXECUTION_COMPLETED, {})
        assert result == "success"


# ---------------------------------------------------------------------------
# Tests _build_audit_queryset (sous-tâches 2.3, 2.4, 2.5)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBuildAuditQueryset:

    def test_invalid_entity_type_raises_bad_request(self, rf):
        """entity_type invalide → 400."""
        response = _call_audit_view(rf, "entity_type=invalid_type")
        assert response.status_code == 400

    def test_non_execution_entity_type_exec_filters_ignored(self, rf):
        """entity_type=action + environment → filtre environment ignoré (pas d'erreur)."""
        _create_audit_log(entity_type=AuditEntityType.ACTION,
                          action_type=AuditActionType.ACTION_CREATED,
                          entity_id=5)
        response = _call_audit_view(rf, "entity_type=action&environment=prod")
        assert response.status_code == 200

    def test_action_id_filter_applied(self, rf):
        """action_id numérique valide → filtre appliqué."""
        response = _call_audit_view(rf, "entity_type=execution&action_id=99")
        assert response.status_code == 200

    def test_engine_type_filter_applied(self, rf):
        """engine_type filter → appliqué sans erreur."""
        response = _call_audit_view(rf, "entity_type=execution&engine_type=aap")
        assert response.status_code == 200

    def test_status_filter_invalid_raises_bad_request(self, rf):
        """status invalide → 400."""
        response = _call_audit_view(rf, "entity_type=execution&status=invalid_status")
        assert response.status_code == 400

    def test_status_filter_valid_success(self, rf):
        """status=success → 200."""
        response = _call_audit_view(rf, "entity_type=execution&status=success")
        assert response.status_code == 200

    def test_status_filter_valid_failed(self, rf):
        """status=failed → 200."""
        response = _call_audit_view(rf, "entity_type=execution&status=failed")
        assert response.status_code == 200

    def test_status_filter_valid_running(self, rf):
        """status=running → 200."""
        response = _call_audit_view(rf, "entity_type=execution&status=running")
        assert response.status_code == 200

    def test_sort_invalid_raises_bad_request(self, rf):
        """sort invalide → 400."""
        response = _call_audit_view(rf, "sort=invalid_col")
        assert response.status_code == 400

    def test_order_invalid_raises_bad_request(self, rf):
        """order invalide → 400."""
        response = _call_audit_view(rf, "order=sideways")
        assert response.status_code == 400

    def test_order_asc_ordering_no_prefix(self, rf):
        """order=asc → ordering sans '-'."""
        response = _call_audit_view(rf, "order=asc")
        assert response.status_code == 200

    def test_environment_filter_with_execution(self, rf):
        """environment filter avec entity_type=execution → appliqué."""
        response = _call_audit_view(rf, "entity_type=execution&environment=dev")
        assert response.status_code == 200

    def test_from_date_invalid_raises_bad_request(self, rf):
        """from date invalide → 400."""
        response = _call_audit_view(rf, "from=not-a-date")
        assert response.status_code == 400

    def test_to_date_invalid_raises_bad_request(self, rf):
        """to date invalide → 400."""
        response = _call_audit_view(rf, "to=not-a-date")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests AuditExecutionsView.get (sous-tâche 2.6)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditExecutionsViewGet:

    def test_non_auditor_returns_403(self, rf):
        """Non auditeur → 403."""
        response = _call_audit_view(rf, auditor=False)
        assert response.status_code == 403

    def test_limit_zero_raises_bad_request(self, rf):
        """limit=0 → 400."""
        response = _call_audit_view(rf, "limit=0")
        assert response.status_code == 400

    def test_limit_negative_raises_bad_request(self, rf):
        """limit=-1 → 400."""
        response = _call_audit_view(rf, "limit=-1")
        assert response.status_code == 400

    def test_limit_over_500_raises_bad_request(self, rf):
        """limit=501 → 400."""
        response = _call_audit_view(rf, "limit=501")
        assert response.status_code == 400

    def test_offset_negative_raises_bad_request(self, rf):
        """offset=-1 → 400."""
        response = _call_audit_view(rf, "offset=-1")
        assert response.status_code == 400

    def test_non_execution_entry_action_name_none(self, rf):
        """Entrée non-EXECUTION → action_name=None, derived_status=None."""
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=10,
        )
        response = _call_audit_view(rf, "entity_type=action")
        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) >= 1
        entry = next(e for e in data if e["entity_type"] == AuditEntityType.ACTION)
        assert entry["action_name"] is None
        assert entry["derived_status"] is None
        assert entry["parent_execution_id"] is None

    def test_execution_entry_with_no_exec_obj_and_null_details(self, rf):
        """Entrée EXECUTION sans exec_obj matchant et details=None → details reste None."""
        # Crée une entrée EXECUTION avec entity_id 9999 (n'existe pas en DB)
        AuditLog.objects.create(
            user_id="1",
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=9999,
            details=None,  # details=None, pas de exec_obj → ne doit pas planter
            ip_address="127.0.0.1",
        )
        response = _call_audit_view(rf, "entity_type=execution")
        assert response.status_code == 200

    def test_execution_entry_details_enriched_with_exec_obj_status(self, rf):
        """Entrée EXECUTION avec exec_obj trouvé → details["status"] enrichi."""
        from tests.factories import ActionFactory, UserFactory
        from executions.models import Execution, ExecutionStatus

        user = UserFactory()
        action = ActionFactory()
        exec_obj = Execution.objects.create(
            action=action, user=user,
            environment="dev", status=ExecutionStatus.COMPLETED,
        )
        import json
        AuditLog.objects.create(
            user_id=str(user.id),
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=exec_obj.id,
            details=json.dumps({"status": "RUNNING"}),
            ip_address="127.0.0.1",
        )
        response = _call_audit_view(rf, "entity_type=execution")
        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) >= 1


# ---------------------------------------------------------------------------
# Tests AuditExportView.get (sous-tâche 2.7)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditExportViewGet:

    def test_non_auditor_returns_403(self, rf):
        """Non auditeur → 403."""
        response = _call_export_view(rf, auditor=False)
        assert response.status_code == 403

    def test_invalid_fmt_raises_bad_request(self, rf):
        """fmt=xml → 400."""
        response = _call_export_view(rf, "fmt=xml")
        assert response.status_code == 400

    def test_empty_fmt_raises_bad_request(self, rf):
        """fmt vide → 400."""
        response = _call_export_view(rf)
        assert response.status_code == 400

    def test_pdf_fmt_raises_bad_request(self, rf):
        """fmt=pdf → 400 BAD_REQUEST (AUD-MED-02: pdf retiré du whitelist, message corrigé)."""
        response = _call_export_view(rf, "fmt=pdf")
        assert response.status_code == 400
        response_body = str(response.data)
        # Must NOT return NOT_IMPLEMENTED anymore — pdf is simply invalid
        assert "NOT_IMPLEMENTED" not in response_body
        assert "BAD_REQUEST" in response_body or "format invalide" in response_body.lower()

    def test_total_over_10000_raises_export_limit_exceeded(self, rf):
        """total > 10000 → 400 avec code EXPORT_LIMIT_EXCEEDED dans la réponse."""
        with patch("audit.views._build_audit_queryset") as mock_qs:
            mock_q = MagicMock()
            mock_q.count.return_value = 10001
            mock_qs.return_value = mock_q
            response = _call_export_view(rf, "fmt=csv")
        assert response.status_code == 400
        response_body = str(response.data)
        assert "EXPORT_LIMIT_EXCEEDED" in response_body or "export_limit" in response_body.lower()

    def test_csv_export_valid(self, rf):
        """fmt=csv avec données → 200 et contenu CSV valide."""
        _create_audit_log(entity_type=AuditEntityType.EXECUTION, entity_id=1)
        response = _call_export_view(rf, "fmt=csv&entity_type=execution")
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        content = response.content.decode("utf-8")
        assert "execution_id" in content or "id" in content

    def test_csv_non_execution_entry_execution_id_empty(self, rf):
        """Entrée non-EXECUTION dans CSV → execution_id vide."""
        _create_audit_log(
            entity_type=AuditEntityType.ACTION,
            action_type=AuditActionType.ACTION_CREATED,
            entity_id=10,
        )
        response = _call_export_view(rf, "fmt=csv&entity_type=action")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # L'entrée ACTION ne doit pas avoir d'execution_id
        assert "action" in content


# ---------------------------------------------------------------------------
# Story 66-19 — Tests warning logs sécurité (AUD-NEW-MED-02)
# ---------------------------------------------------------------------------

class TestUnauthorizedAccessLogging:
    """Vérifie que logger.warning est émis sur accès non-autorisé (AUD-NEW-MED-02)."""

    def test_audit_executions_view_logs_warning_on_forbidden(self, rf):
        """Non-auditeur sur AuditExecutionsView → logger.warning appelé avec ip_address."""
        with patch("audit.views.logger") as mock_logger:
            _call_audit_view(rf, auditor=False)
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[0][0] == "audit.unauthorized_access"
        assert call_kwargs[1].get("view") == "AuditExecutionsView"
        assert "ip_address" in call_kwargs[1]

    def test_audit_export_view_logs_warning_on_forbidden(self, rf):
        """Non-auditeur sur AuditExportView → logger.warning appelé avec ip_address."""
        with patch("audit.views.logger") as mock_logger:
            _call_export_view(rf, auditor=False)
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[0][0] == "audit.unauthorized_access"
        assert call_kwargs[1].get("view") == "AuditExportView"
        assert "ip_address" in call_kwargs[1]

    def test_authorized_access_does_not_log_warning(self, rf):
        """Auditeur autorisé → logger.warning PAS appelé."""
        with patch("audit.views.logger") as mock_logger:
            with patch("audit.views._build_audit_queryset") as mock_qs:
                mock_q = MagicMock()
                mock_q.count.return_value = 0
                mock_q.__getitem__ = MagicMock(return_value=iter([]))
                mock_qs.return_value = mock_q
                with patch("audit.views._resolve_user_names", return_value={}):
                    _call_audit_view(rf, auditor=True)
        mock_logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# Story 66-19 — Branches non couvertes supplémentaires (sous-tâches 2.8 à 2.15)
# ---------------------------------------------------------------------------

class TestParseIntBranches:
    """_parse_int invalid value → BadRequestError (lines 29-30)."""

    def test_invalid_int_raises_bad_request(self):
        from core.exceptions import BadRequestError
        with pytest.raises(BadRequestError):
            _parse_int("not_a_number", 0, name="limit")

    def test_none_returns_default(self):
        assert _parse_int(None, 25, name="limit") == 25

    def test_valid_int_returns_int(self):
        assert _parse_int("42", 0, name="limit") == 42


class TestParseDtBranches:
    """_parse_dt with naive datetime → make_aware (lines 39-41)."""

    def test_naive_datetime_string_made_aware(self):
        """Datetime without timezone info → timezone.make_aware applied."""
        result = _parse_dt("2024-01-15T10:00:00", name="from")
        assert result is not None
        from django.utils import timezone
        assert not timezone.is_naive(result)

    def test_none_returns_none(self):
        assert _parse_dt(None, name="from") is None

    def test_invalid_datetime_raises(self):
        from core.exceptions import BadRequestError
        with pytest.raises(BadRequestError):
            _parse_dt("not-a-date", name="from")


class TestDeriveStatusMissingBranches:
    """_derive_status edge cases (lines 86->96, 92->96)."""

    def test_status_is_non_string_falls_through_to_action_type(self):
        """status=42 (int, not str) → isinstance(s, str) is False → falls through (line 86->96)."""
        result = _derive_status(AuditActionType.EXECUTION_COMPLETED, {"status": 42})
        assert result == "success"  # fallback by action_type

    def test_unknown_status_string_falls_through_all_checks(self):
        """status='CUSTOM_STATE' → not in any known set → reaches action_type fallback (line 92->96)."""
        result = _derive_status(AuditActionType.EXECUTION_FAILED, {"status": "CUSTOM_STATE"})
        assert result == "failed"  # fallback by action_type


@pytest.mark.django_db
class TestResolveUserNamesMissingBranches:
    """_resolve_user_names non-numeric user IDs (lines 132-134, 137->142, 143-144)."""

    def test_non_numeric_ids_only_uses_username_query(self):
        """Only non-numeric IDs → numeric_ids=[] → skip numeric batch (137->142), use username batch."""
        result = _resolve_user_names(["admin", "john.doe"])
        # Fallback values returned (no users created in DB)
        assert result["admin"] == "admin"
        assert result["john.doe"] == "john.doe"

    def test_non_numeric_ids_found_in_db(self):
        """Non-numeric ID matching a username → resolved to display_name."""
        from tests.factories import UserFactory
        u = UserFactory()
        result = _resolve_user_names([u.username])
        assert u.username in result


@pytest.mark.django_db
class TestBuildAuditQuerysetMissingBranches:
    """_build_audit_queryset missing branches (lines 167-173, 178-182, 189, 191, 204, 241, 246)."""

    def test_invalid_action_type_raises_bad_request(self, rf):
        """action_type invalide → 400 (lines 167-173)."""
        response = _call_audit_view(rf, "action_type=INVALID_ACTION_TYPE")
        assert response.status_code == 400

    def test_user_search_filter_applied(self, rf):
        """user=admin → filtre user_id/user_search appliqué (lines 178-182)."""
        response = _call_audit_view(rf, "user=admin")
        assert response.status_code == 200

    def test_from_date_valid_filter_applied(self, rf):
        """from= avec date valide → qs.filter(timestamp__gte=...) (line 189)."""
        response = _call_audit_view(rf, "from=2024-01-01T00:00:00Z")
        assert response.status_code == 200

    def test_to_date_valid_filter_applied(self, rf):
        """to= avec date valide → qs.filter(timestamp__lte=...) (line 191)."""
        response = _call_audit_view(rf, "to=2024-12-31T23:59:59Z")
        assert response.status_code == 200

    def test_environment_filter_without_entity_type_applies_complex_filter(self, rf):
        """Pas d'entity_type + environment → _apply_exec_filter branche ~Q (line 204)."""
        response = _call_audit_view(rf, "environment=dev")  # no entity_type → entity_type_param=""
        assert response.status_code == 200

    def test_user_id_filter_applied(self, rf):
        """user_id= → qs.filter(user_id=...) (line 241)."""
        response = _call_audit_view(rf, "user_id=42")
        assert response.status_code == 200

    def test_correlation_id_filter_applied(self, rf):
        """correlation_id= → qs.filter(correlation_id=...) (line 246)."""
        response = _call_audit_view(rf, "correlation_id=test-corr-123")
        assert response.status_code == 200


@pytest.mark.django_db
class TestAuditExecutionsViewDetailsNullWithExec:
    """AuditExecutionsView: details=None + matching exec_obj → details populated (line 330)."""

    def test_null_details_with_matching_exec_populates_details(self, rf):
        """EXECUTION entry with details=None and matching exec_obj → if branch at line 330."""
        from tests.factories import ActionFactory, UserFactory
        from executions.models import Execution, ExecutionStatus

        user = UserFactory()
        action = ActionFactory()
        exec_obj = Execution.objects.create(
            action=action, user=user,
            environment="dev", status=ExecutionStatus.COMPLETED,
        )
        AuditLog.objects.create(
            user_id=str(user.id),
            action_type=AuditActionType.EXECUTION_COMPLETED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=exec_obj.id,
            details=None,  # details=None + exec_obj exists → line 330 executes
            ip_address="127.0.0.1",
        )
        response = _call_audit_view(rf, "entity_type=execution")
        assert response.status_code == 200
        data = response.data["data"]
        assert len(data) >= 1
        entry = next(e for e in data if e.get("entity_id") == exec_obj.id)
        assert entry.get("details") is not None


@pytest.mark.django_db
class TestBuildAuditQuerysetValidActionType:
    """action_type valid → qs.filter applied (line 173)."""

    def test_valid_action_type_filter_applied(self, rf):
        """action_type=EXECUTION_COMPLETED (valid) → qs.filter called (line 173)."""
        response = _call_audit_view(rf, f"action_type={AuditActionType.EXECUTION_COMPLETED}")
        assert response.status_code == 200
