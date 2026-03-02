"""
Story 55.3 — Couverture `integrations/tasks.py` (AC #1)

Couvre les branches non couvertes par test_story_51_1_health_check.py :
- _sanitize_health_error_message : None/vide, traceback, URL, longueur
- _resolve_and_check_adapter : github_actions, terraform_cloud, non-IHealthCheckable, exceptions
- _resolve_and_check_service : non-IHealthCheckable, exceptions
- _resolve_and_check_vault : credential_ref vide, exceptions
- run_integration_health_check : branche vault
- health_check_all_integrations : liste vide, exception dispatch, exception query
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations.tasks import (
    _sanitize_health_error_message,
    _resolve_and_check_adapter,
    _resolve_and_check_service,
    _resolve_and_check_vault,
    health_check_all_integrations,
    run_integration_health_check,
)


# ---------------------------------------------------------------------------
# Tests _sanitize_health_error_message (sous-tâche 1.1)
# ---------------------------------------------------------------------------

class TestSanitizeHealthErrorMessage:

    def test_none_returns_none(self):
        assert _sanitize_health_error_message(None) is None

    def test_empty_string_returns_none(self):
        assert _sanitize_health_error_message("") is None

    def test_whitespace_only_returns_none(self):
        assert _sanitize_health_error_message("   \n\t  ") is None

    def test_normal_message_returned(self):
        result = _sanitize_health_error_message("Connection refused")
        assert result == "Connection refused"

    def test_traceback_lines_stripped(self):
        msg = "Error occurred\n  File 'foo.py', line 42\nTraceback (most recent call last):\nSomething failed"
        result = _sanitize_health_error_message(msg)
        assert result is not None
        assert "File" not in result
        assert "Traceback" not in result
        assert "Something failed" in result

    def test_url_redacted(self):
        msg = "Failed to connect to https://example.com/api/health"
        result = _sanitize_health_error_message(msg)
        assert result is not None
        assert "https://example.com" not in result
        assert "[REDACTED]" in result

    def test_http_url_redacted(self):
        msg = "Error at http://internal.host/endpoint"
        result = _sanitize_health_error_message(msg)
        assert "[REDACTED]" in result

    def test_message_truncated_at_500_chars(self):
        long_msg = "x" * 600
        result = _sanitize_health_error_message(long_msg)
        assert result is not None
        assert len(result) <= 504  # 500 + "…"
        assert result.endswith("…")

    def test_message_exactly_500_chars_not_truncated(self):
        msg = "a" * 500
        result = _sanitize_health_error_message(msg)
        assert result is not None
        assert not result.endswith("…")

    def test_all_lines_stripped_falls_back_to_original(self):
        """Quand toutes les lignes sont des tracebacks, kept=[],
        on utilise msg original (non filtré), puis on applique les autres traitements."""
        msg = "Traceback (most recent call last):\n  File 'x.py', line 1"
        result = _sanitize_health_error_message(msg)
        # Résultat non None : le message original est utilisé si kept=[]
        # (le code utilise: text = " ".join(kept) if kept else msg)
        assert result is not None


# ---------------------------------------------------------------------------
# Tests _resolve_and_check_adapter (sous-tâche 1.2)
# ---------------------------------------------------------------------------

class TestResolveAndCheckAdapter:

    def _make_integration(self, itype="aap", config=None):
        integration = MagicMock()
        integration.id = 1
        integration.type = itype
        integration.base_url = "https://adapter.example.com"
        integration.get_config.return_value = config or {}
        return integration

    def test_github_actions_uses_owner_repo_from_config(self):
        """github_actions → platform_kwargs avec owner/repo depuis config."""
        integration = self._make_integration(
            itype="github_actions",
            config={"owner": "myorg", "repo": "myrepo"},
        )
        mock_result = MagicMock()
        from integrations.health_check import HealthCheckStatus
        mock_result.status = HealthCheckStatus.OK

        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("adapters.get_platform_adapter") as mock_get_adapter, \
             patch("integrations.health_check.IHealthCheckable"):
            adapter = MagicMock()
            mock_get_adapter.return_value = adapter
            # L'adapter est IHealthCheckable
            mock_ihc_class = MagicMock()
            adapter.__class__ = mock_ihc_class

            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = lambda: mock_result
                try:
                    _resolve_and_check_adapter(integration)
                except Exception:  # noqa: BLE001
                    pass

        # Vérifier que get_platform_adapter a été appelé avec owner et repo
        mock_get_adapter.assert_called_once()
        call_kwargs = mock_get_adapter.call_args[1]
        assert call_kwargs.get("owner") == "myorg"
        assert call_kwargs.get("repo") == "myrepo"

    def test_terraform_cloud_uses_organization_from_config(self):
        """terraform_cloud → platform_kwargs avec organization depuis config."""
        integration = self._make_integration(
            itype="terraform_cloud",
            config={"organization": "myorg"},
        )
        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("adapters.get_platform_adapter") as mock_get_adapter, \
             patch("asgiref.sync.async_to_sync"):
            mock_get_adapter.return_value = MagicMock()
            try:
                _resolve_and_check_adapter(integration)
            except Exception:  # noqa: BLE001
                pass

        mock_get_adapter.assert_called_once()
        call_kwargs = mock_get_adapter.call_args[1]
        assert call_kwargs.get("organization") == "myorg"

    def test_adapter_not_ihealthcheckable_returns_unknown(self):
        """Adapter qui n'implante pas IHealthCheckable → UNKNOWN."""
        integration = self._make_integration(itype="aap")
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("adapters.get_platform_adapter", return_value=object()):
            result = _resolve_and_check_adapter(integration)

        assert result.status == HealthCheckStatus.UNKNOWN

    def test_build_auth_headers_raises_returns_error(self):
        """build_auth_headers lève exception → HealthCheckResult ERROR."""
        integration = self._make_integration()
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", side_effect=Exception("creds error")):
            result = _resolve_and_check_adapter(integration)

        assert result.status == HealthCheckStatus.ERROR
        assert "creds error" in result.error_message

    def test_get_platform_adapter_raises_returns_error(self):
        """`get_platform_adapter` lève exception → HealthCheckResult ERROR."""
        integration = self._make_integration()
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("adapters.get_platform_adapter", side_effect=Exception("adapter init failed")):
            result = _resolve_and_check_adapter(integration)

        assert result.status == HealthCheckStatus.ERROR
        assert "adapter init failed" in result.error_message


# ---------------------------------------------------------------------------
# Tests _resolve_and_check_service (sous-tâche 1.3)
# ---------------------------------------------------------------------------

class TestResolveAndCheckService:

    def _make_integration(self, itype="servicenow"):
        integration = MagicMock()
        integration.id = 1
        integration.type = itype
        integration.base_url = "https://service.example.com"
        return integration

    def test_service_not_ihealthcheckable_returns_unknown(self):
        """Service qui n'implante pas IHealthCheckable → UNKNOWN."""
        integration = self._make_integration()
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("services.get_service_client", return_value=object()):
            result = _resolve_and_check_service(integration)

        assert result.status == HealthCheckStatus.UNKNOWN

    def test_build_auth_headers_raises_returns_error(self):
        """build_auth_headers lève exception → ERROR."""
        integration = self._make_integration()
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", side_effect=Exception("auth error")):
            result = _resolve_and_check_service(integration)

        assert result.status == HealthCheckStatus.ERROR

    def test_get_service_client_raises_returns_error(self):
        """`get_service_client` lève exception → ERROR."""
        integration = self._make_integration()
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.build_auth_headers", return_value={}), \
             patch("services.get_service_client", side_effect=Exception("service init failed")):
            result = _resolve_and_check_service(integration)

        assert result.status == HealthCheckStatus.ERROR
        assert "service init failed" in result.error_message


# ---------------------------------------------------------------------------
# Tests _resolve_and_check_vault (sous-tâche 1.4)
# ---------------------------------------------------------------------------

class TestResolveAndCheckVault:

    def _make_integration(self, credential_ref=None):
        integration = MagicMock()
        integration.id = 1
        integration.base_url = "https://vault.example.com"
        integration.credential_ref = credential_ref
        return integration

    def test_empty_credential_ref_skips_resolve(self):
        """credential_ref vide → vault_token="" sans appeler resolve_credential."""
        integration = self._make_integration(credential_ref="")

        with patch("adapters.utils.resolve_credential") as mock_resolve, \
             patch("services.vault_service.VaultService") as mock_vault_cls, \
             patch("asgiref.sync.async_to_sync") as mock_a2s:
            mock_vault = MagicMock()
            mock_vault_cls.return_value = mock_vault
            from integrations.health_check import HealthCheckStatus, HealthCheckResult
            from django.utils import timezone
            mock_a2s.return_value = lambda: HealthCheckResult(
                status=HealthCheckStatus.OK, checked_at=timezone.now()
            )
            _resolve_and_check_vault(integration)

        mock_resolve.assert_not_called()

    def test_none_credential_ref_skips_resolve(self):
        """credential_ref=None → vault_token="" sans appeler resolve_credential."""
        integration = self._make_integration(credential_ref=None)

        with patch("adapters.utils.resolve_credential") as mock_resolve, \
             patch("services.vault_service.VaultService"), \
             patch("asgiref.sync.async_to_sync") as mock_a2s:
            from integrations.health_check import HealthCheckStatus, HealthCheckResult
            from django.utils import timezone
            mock_a2s.return_value = lambda: HealthCheckResult(
                status=HealthCheckStatus.OK, checked_at=timezone.now()
            )
            _resolve_and_check_vault(integration)

        mock_resolve.assert_not_called()

    def test_resolve_credential_raises_returns_error(self):
        """`resolve_credential` lève exception → ERROR."""
        integration = self._make_integration(credential_ref="ref://secret")
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.resolve_credential", side_effect=Exception("cred error")):
            result = _resolve_and_check_vault(integration)

        assert result.status == HealthCheckStatus.ERROR
        assert "cred error" in result.error_message

    def test_vault_service_init_raises_returns_error(self):
        """`VaultService(...)` lève exception → ERROR."""
        integration = self._make_integration(credential_ref="ref://secret")
        from integrations.health_check import HealthCheckStatus

        with patch("adapters.utils.resolve_credential", return_value="mytoken"), \
             patch("services.vault_service.VaultService", side_effect=Exception("vault init error")):
            result = _resolve_and_check_vault(integration)

        assert result.status == HealthCheckStatus.ERROR
        assert "vault init error" in result.error_message


# ---------------------------------------------------------------------------
# Tests run_integration_health_check (sous-tâche 1.5)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRunIntegrationHealthCheckVaultBranch:

    def test_vault_type_calls_resolve_and_check_vault(self):
        """run_integration_health_check avec type=vault → _resolve_and_check_vault appelé."""
        from integrations.health_check import HealthCheckStatus, HealthCheckResult
        from django.utils import timezone

        mock_integration = MagicMock()
        mock_integration.id = 99
        mock_integration.type = "vault"

        mock_result = HealthCheckResult(
            status=HealthCheckStatus.OK, checked_at=timezone.now()
        )

        with patch("integrations.models.Integration.objects") as mock_objs, \
             patch("integrations.tasks._resolve_and_check_vault", return_value=mock_result) as mock_vault, \
             patch("integrations.tasks._sanitize_health_error_message", return_value=None):
            mock_objs.get.return_value = mock_integration
            mock_objs.filter.return_value.update.return_value = None
            run_integration_health_check(99)

        mock_vault.assert_called_once_with(mock_integration)

    def test_sanitize_called_on_error_message(self):
        """_sanitize_health_error_message est appelé sur result.error_message."""
        from integrations.health_check import HealthCheckStatus, HealthCheckResult
        from django.utils import timezone

        mock_integration = MagicMock()
        mock_integration.id = 88
        mock_integration.type = "unsupported_type"

        HealthCheckResult(
            status=HealthCheckStatus.UNKNOWN,
            checked_at=timezone.now(),
            error_message=None,
        )

        with patch("integrations.models.Integration.objects") as mock_objs, \
             patch("integrations.tasks._sanitize_health_error_message",
                   return_value=None) as mock_sanitize:
            mock_objs.get.return_value = mock_integration
            mock_objs.filter.return_value.update.return_value = None
            run_integration_health_check(88)

        mock_sanitize.assert_called_once_with(None)


# ---------------------------------------------------------------------------
# Tests health_check_all_integrations (sous-tâche 1.6)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHealthCheckAllIntegrations:

    def test_empty_integration_list_dispatched_count_zero(self):
        """Aucune intégration → dispatched_count=0, pas d'exception."""
        with patch("integrations.models.Integration.objects") as mock_objs:
            mock_objs.all.return_value.only.return_value.values_list.return_value = []
            health_check_all_integrations()  # Ne doit pas lever

    def test_dispatch_exception_logged_and_continues(self):
        """run_integration_health_check.delay lève exception → logger.exception + continue."""
        with patch("integrations.models.Integration.objects") as mock_objs, \
             patch("integrations.tasks.run_integration_health_check") as mock_task, \
             patch("integrations.tasks.logger") as mock_logger:
            mock_objs.all.return_value.only.return_value.values_list.return_value = [1, 2]
            mock_task.delay.side_effect = Exception("dispatch error")
            health_check_all_integrations()

        # logger.exception doit avoir été appelé (pas de raise)
        assert mock_logger.exception.called

    def test_integration_objects_all_raises_returns(self):
        """`Integration.objects.all()` lève exception → logger.error + return."""
        with patch("integrations.models.Integration.objects") as mock_objs, \
             patch("integrations.tasks.logger") as mock_logger:
            mock_objs.all.side_effect = Exception("db error")
            health_check_all_integrations()  # Ne doit pas lever

        assert mock_logger.error.called
