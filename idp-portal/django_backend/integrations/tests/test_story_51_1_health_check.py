"""
Tests Story 51.1 — Modèle, IHealthCheckable, health_check() adapters/services, signal, tâche Celery.

Couvre :
- Sous-task 7.1 : Tests unitaires adapters (mock httpx.AsyncClient)
- Sous-task 7.2 : Tests unitaires services (mock HTTP)
- Sous-task 7.3 : Tests signal post_save (vérifier .delay() appelé)
- Sous-task 7.4 : Tests tâche Celery (mock adapter, vérifier mise à jour champs)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from integrations.health_check import (
    HealthCheckResult,
    HealthCheckStatus,
    IHealthCheckable,
)


# =============================================================================
# Sous-task 7.1 : Tests adapters health_check()
# =============================================================================


def _make_mock_client(status_code: int = 200, raise_exc: Exception | None = None):
    """Crée un mock httpx.AsyncClient qui retourne le status_code donné."""
    response = MagicMock()
    response.status_code = status_code
    if raise_exc:
        response.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    if raise_exc and not isinstance(raise_exc, httpx.HTTPStatusError):
        # Exception levée au niveau du client.get()
        mock_client.get = AsyncMock(side_effect=raise_exc)
    else:
        mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestAAPAdapterHealthCheck:
    """Tests pour AAPAdapter.health_check() — sous-task 3.1."""

    @pytest.fixture
    def adapter(self):
        from adapters.aap_adapter import AAPAdapter
        return AAPAdapter(
            base_url="https://aap.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter):
        """GET /api/v2/ping/ → 200 → HealthCheckStatus.OK."""
        mock_client = _make_mock_client(200)
        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None
        assert result.checked_at is not None
        mock_client.get.assert_called_once_with("https://aap.example.com/api/v2/ping/")

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, adapter):
        """Timeout → HealthCheckStatus.ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.TimeoutException("timeout"))
        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_health_check_http_error(self, adapter):
        """HTTP 401 → HealthCheckStatus.ERROR."""
        exc = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client = _make_mock_client(401, raise_exc=exc)
        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

    def test_aap_adapter_implements_ihealthcheckable(self, adapter):
        """AAPAdapter implémente IHealthCheckable."""
        from integrations.health_check import IHealthCheckable
        assert isinstance(adapter, IHealthCheckable)


class TestTowerAdapterHealthCheck:
    """Tests pour TowerAdapter.health_check() — sous-task 3.2."""

    @pytest.fixture
    def adapter(self):
        from adapters.tower_adapter import TowerAdapter
        return TowerAdapter(
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter):
        """GET /api/v2/ping/ → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, adapter):
        """Erreur de connexion → ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.ConnectError("refused"))
        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

    def test_tower_adapter_implements_ihealthcheckable(self, adapter):
        assert isinstance(adapter, IHealthCheckable)


class TestAzureDevOpsAdapterHealthCheck:
    """Tests pour AzureDevOpsAdapter.health_check() — sous-task 3.3."""

    @pytest.fixture
    def adapter(self):
        from adapters.azure_devops_adapter import AzureDevOpsAdapter
        return AzureDevOpsAdapter(
            base_url="https://dev.azure.com/myorg/myproject",
            auth_headers={"Authorization": "Basic cGF0OmVtcHR5"},
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter):
        """GET /_apis/?api-version=7.1 → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        mock_client.get.assert_called_once()
        call_url = mock_client.get.call_args[0][0]
        assert "/_apis/" in call_url

    @pytest.mark.asyncio
    async def test_health_check_error(self, adapter):
        """Erreur HTTP → ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.ConnectTimeout("timeout"))
        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_azure_devops_adapter_implements_ihealthcheckable(self, adapter):
        assert isinstance(adapter, IHealthCheckable)


class TestGitHubActionsAdapterHealthCheck:
    """Tests pour GitHubActionsAdapter.health_check() — sous-task 3.4."""

    @pytest.fixture
    def adapter(self):
        from adapters.github_actions_adapter import GitHubActionsAdapter
        return GitHubActionsAdapter(
            base_url="https://api.github.com",
            auth_headers={"Authorization": "Bearer ghp_test"},
            owner="myorg",
            repo="myrepo",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter):
        """GET https://api.github.com/ → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        mock_client.get.assert_called_once_with("https://api.github.com/")

    @pytest.mark.asyncio
    async def test_health_check_error(self, adapter):
        """Token invalide → ERROR."""
        exc = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client = _make_mock_client(401, raise_exc=exc)
        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_github_actions_adapter_implements_ihealthcheckable(self, adapter):
        assert isinstance(adapter, IHealthCheckable)


class TestTerraformCloudAdapterHealthCheck:
    """Tests pour TerraformCloudAdapter.health_check() — sous-task 3.5."""

    @pytest.fixture
    def adapter(self):
        from adapters.terraform_cloud_adapter import TerraformCloudAdapter
        return TerraformCloudAdapter(
            base_url="https://app.terraform.io/api/v2",
            auth_headers={"Authorization": "Bearer test-token"},
            organization="myorg",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter):
        """GET /api/v2/account/details → 200 → OK (endpoint authentifié, valide le token)."""
        mock_client = _make_mock_client(200)
        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        mock_client.get.assert_called_once()
        call_url = mock_client.get.call_args[0][0]
        assert "account/details" in call_url

    @pytest.mark.asyncio
    async def test_health_check_bad_token_returns_error(self, adapter):
        """Token invalide → HTTP 401 → ERROR (valide que l'endpoint est authentifié)."""
        exc = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client = _make_mock_client(401, raise_exc=exc)
        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_health_check_error(self, adapter):
        """Erreur réseau → ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.ConnectError("refused"))
        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_terraform_adapter_implements_ihealthcheckable(self, adapter):
        assert isinstance(adapter, IHealthCheckable)


# =============================================================================
# Sous-task 7.2 : Tests services health_check()
# =============================================================================


class TestVaultServiceHealthCheck:
    """Tests pour VaultService.health_check() — sous-task 4.1."""

    @pytest.fixture
    def vault_service(self):
        from services.vault_service import VaultService
        with patch.object(VaultService, '_authenticate_approle', return_value=None):
            svc = VaultService(
                vault_addr="https://vault.example.com",
                vault_token="test-token",
            )
        return svc

    @pytest.mark.asyncio
    async def test_health_check_ok_200(self, vault_service):
        """GET /v1/sys/health → 200 → OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(vault_service._session, "get", return_value=mock_response):
            result = await vault_service.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_health_check_ok_429_standby(self, vault_service):
        """GET /v1/sys/health → 429 (standby) → OK (vault HA accessible)."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.object(vault_service._session, "get", return_value=mock_response):
            result = await vault_service.health_check()

        assert result.status == HealthCheckStatus.OK

    @pytest.mark.asyncio
    async def test_health_check_error_503_sealed(self, vault_service):
        """GET /v1/sys/health → 503 (sealed) → ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(vault_service._session, "get", return_value=mock_response):
            result = await vault_service.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert "503" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, vault_service):
        """Erreur réseau → ERROR."""
        import requests
        with patch.object(
            vault_service._session, "get",
            side_effect=requests.ConnectionError("refused"),
        ):
            result = await vault_service.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

    def test_vault_service_implements_ihealthcheckable(self, vault_service):
        assert isinstance(vault_service, IHealthCheckable)


class TestServiceNowServiceHealthCheck:
    """Tests pour ServiceNowService.health_check() — sous-task 4.2."""

    @pytest.fixture
    def service(self):
        from services.servicenow_service import ServiceNowService
        return ServiceNowService(
            base_url="https://myinstance.service-now.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, service):
        """GET table API → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("services.servicenow_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None
        call_url = mock_client.get.call_args[0][0]
        assert "api/now/table" in call_url

    @pytest.mark.asyncio
    async def test_health_check_auth_error(self, service):
        """HTTP 401 → ERROR."""
        exc = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client = _make_mock_client(401, raise_exc=exc)
        with patch("services.servicenow_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_servicenow_implements_ihealthcheckable(self, service):
        assert isinstance(service, IHealthCheckable)


class TestJiraServiceHealthCheck:
    """Tests pour JiraService.health_check() — sous-task 4.3."""

    @pytest.fixture
    def service(self):
        from services.jira_service import JiraService
        return JiraService(
            base_url="https://myorg.atlassian.net",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, service):
        """GET /rest/api/2/serverInfo → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("services.jira_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.OK
        call_url = mock_client.get.call_args[0][0]
        assert "serverInfo" in call_url

    @pytest.mark.asyncio
    async def test_health_check_error(self, service):
        """Erreur réseau → ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.ConnectError("refused"))
        with patch("services.jira_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_jira_implements_ihealthcheckable(self, service):
        assert isinstance(service, IHealthCheckable)


class TestSplunkServiceHealthCheck:
    """Tests pour SplunkService.health_check() — sous-task 4.4."""

    @pytest.fixture
    def service(self):
        from services.splunk_service import SplunkService
        return SplunkService(
            base_url="https://splunk.example.com:8089",
            auth_headers={"Authorization": "Splunk test-token"},
        )

    @pytest.mark.asyncio
    async def test_health_check_ok(self, service):
        """GET /services/server/info → 200 → OK."""
        mock_client = _make_mock_client(200)
        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.OK
        call_url = mock_client.get.call_args[0][0]
        assert "server/info" in call_url

    @pytest.mark.asyncio
    async def test_health_check_error(self, service):
        """Timeout → ERROR."""
        mock_client = _make_mock_client(raise_exc=httpx.TimeoutException("timeout"))
        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.ERROR

    def test_splunk_implements_ihealthcheckable(self, service):
        assert isinstance(service, IHealthCheckable)


# =============================================================================
# Sous-task 7.3 : Tests signal post_save
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestIntegrationPostSaveSignal:
    """Tests du signal post_save → run_integration_health_check.delay — sous-task 6.1-6.3.

    Uses transaction=True so transaction.on_commit callbacks run (default TestCase rolls
    back and never commits, so on_commit would not execute).
    """

    def test_signal_fires_on_create(self, db):
        """Signal déclenche .delay() lors de Integration.save() (create)."""
        from integrations.models import Integration

        # L'import est local dans le signal : patcher directement integrations.tasks
        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            integration = Integration.objects.create(
                type="aap",
                name="Test AAP Signal",
                base_url="https://aap.example.com",
            )

        mock_task.delay.assert_called_once_with(integration.id)

    def test_signal_fires_on_update(self, db):
        """Signal déclenche .delay() lors de Integration.save() (update)."""
        from integrations.models import Integration

        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            integration = Integration.objects.create(
                type="aap",
                name="Test AAP Update",
                base_url="https://aap.example.com",
            )
            mock_task.delay.reset_mock()
            integration.name = "Test AAP Updated"
            integration.save()

        mock_task.delay.assert_called_once_with(integration.id)

    def test_signal_ignored_on_raw(self, db):
        """Signal ignoré si raw=True (fixtures/migrations)."""
        from integrations.models import Integration
        from integrations.signals import trigger_health_check_on_save

        calls = []

        def capture(*args, **kwargs):
            calls.append(kwargs)

        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            # Simuler raw=True
            trigger_health_check_on_save(
                sender=Integration,
                instance=MagicMock(id=999),
                created=True,
                raw=True,
            )

        mock_task.delay.assert_not_called()


# =============================================================================
# Sous-task 7.4 : Tests tâche Celery run_integration_health_check
# =============================================================================


@pytest.mark.django_db
class TestRunIntegrationHealthCheckTask:
    """Tests de la tâche Celery run_integration_health_check — sous-task 5.1-5.3."""

    def _create_integration(self, db, itype="aap", name="HC Test"):
        from integrations.models import Integration
        # Désactiver le signal pendant la création (import local dans le signal)
        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            integration = Integration.objects.create(
                type=itype,
                name=name,
                base_url="https://example.com",
                credential_ref="test-token",
            )
        return integration

    def test_task_updates_health_status_ok(self, db):
        """Tâche met à jour health_status=ok quand health_check retourne OK."""
        from integrations.models import HealthStatus
        from integrations.tasks import run_integration_health_check

        integration = self._create_integration(db)
        # Vérifier valeur initiale
        assert integration.health_status == HealthStatus.UNKNOWN

        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=ok_result):
            run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "ok"
        assert integration.health_checked_at is not None
        assert integration.health_error_message is None

    def test_task_updates_health_status_error(self, db):
        """Tâche met à jour health_status=error quand health_check retourne ERROR."""
        from integrations.tasks import run_integration_health_check

        integration = self._create_integration(db)

        error_result = HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=datetime.now(timezone.utc),
            error_message="Connection refused",
        )

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=error_result):
            run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "error"
        assert integration.health_error_message == "Connection refused"

    def test_task_integration_not_found(self, db):
        """Tâche termine sans erreur si l'intégration n'existe pas."""
        from integrations.tasks import run_integration_health_check
        # Ne doit pas lever d'exception
        run_integration_health_check(99999)

    def test_task_unknown_type_returns_unknown(self, db):
        """Types non supportés (inventory) retournent UNKNOWN."""
        from integrations.tasks import run_integration_health_check

        integration = self._create_integration(db, itype="inventory", name="HC Inventory")

        run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "unknown"

    def test_task_resolve_adapter_path_runs_real_helper(self, db):
        """Exercice _resolve_and_check_adapter via run_integration_health_check (sans patch)."""
        from integrations.tasks import run_integration_health_check
        from integrations.health_check import IHealthCheckable, HealthCheckResult, HealthCheckStatus

        integration = self._create_integration(db, itype="aap", name="HC AAP Real Path")
        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )
        mock_adapter = MagicMock(spec=IHealthCheckable)
        mock_adapter.health_check = AsyncMock(return_value=ok_result)

        with patch("adapters.get_platform_adapter", return_value=mock_adapter), \
             patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer x"}):
            run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "ok"

    def test_task_resolve_service_path_runs_real_helper(self, db):
        """Exercice _resolve_and_check_service via run_integration_health_check."""
        from integrations.tasks import run_integration_health_check
        from integrations.health_check import IHealthCheckable, HealthCheckResult, HealthCheckStatus

        integration = self._create_integration(db, itype="splunk", name="HC Splunk")
        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )
        mock_service = MagicMock(spec=IHealthCheckable)
        mock_service.health_check = AsyncMock(return_value=ok_result)

        with patch("services.get_service_client", return_value=mock_service), \
             patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Splunk x"}):
            run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "ok"

    def test_task_captures_unexpected_exception(self, db):
        """Exception inattendue → health_status=error, pas de raise."""
        from integrations.tasks import run_integration_health_check

        integration = self._create_integration(db)

        with patch(
            "integrations.tasks._resolve_and_check_adapter",
            side_effect=RuntimeError("unexpected!"),
        ):
            # Ne doit PAS lever
            run_integration_health_check(integration.id)

        integration.refresh_from_db()
        assert integration.health_status == "error"
        assert "unexpected!" in integration.health_error_message

    def test_task_uses_queryset_update_not_save(self, db):
        """La tâche utilise QuerySet.update() et ne déclenche pas le signal post_save récursivement."""
        from integrations.tasks import run_integration_health_check

        integration = self._create_integration(db)

        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )

        signal_delay_calls = []

        def capture_delay(integration_id):
            signal_delay_calls.append(integration_id)

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=ok_result):
            with patch("integrations.tasks.run_integration_health_check") as mock_task:
                mock_task.delay = capture_delay
                run_integration_health_check(integration.id)

        # Le signal post_save ne doit PAS se déclencher (on utilise .update(), pas .save())
        assert signal_delay_calls == [], f"Signal déclenché récursivement : {signal_delay_calls}"
        integration.refresh_from_db()
        assert integration.health_status == "ok"


# =============================================================================
# Tests modèle — champs santé
# =============================================================================


@pytest.mark.django_db
class TestIntegrationHealthFields:
    """Tests des champs santé sur le modèle Integration — AC #1, #2."""

    def test_health_fields_default_values(self, db):
        """Valeurs par défaut des champs health check."""
        from integrations.models import Integration, HealthStatus

        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            integration = Integration.objects.create(
                type="aap",
                name="HC Default Fields",
                base_url="https://aap.example.com",
            )

        assert integration.health_status == HealthStatus.UNKNOWN
        assert integration.health_checked_at is None
        assert integration.health_error_message is None

    def test_health_status_choices(self):
        """HealthStatus TextChoices contient ok/error/unknown."""
        from integrations.models import HealthStatus

        assert HealthStatus.OK == "ok"
        assert HealthStatus.ERROR == "error"
        assert HealthStatus.UNKNOWN == "unknown"

    def test_health_check_interface_is_abstract(self):
        """IHealthCheckable ne peut pas être instancié directement."""
        with pytest.raises(TypeError):
            IHealthCheckable()  # type: ignore[abstract]


# =============================================================================
# Tests résolution des alias de type — Code Review Fix M3
# =============================================================================


@pytest.mark.django_db
class TestTaskTypeAliasResolution:
    """Vérifie que les alias 'azuredevops' et 'terraform' sont correctement normalisés
    vers 'azure_devops' et 'terraform_cloud' avant le dispatch. (Code Review M3)"""

    def _create_integration(self, db, itype, name):
        from integrations.models import Integration
        with patch("integrations.tasks.run_integration_health_check") as mock_task:
            mock_task.delay = MagicMock()
            integration = Integration.objects.create(
                type=itype,
                name=name,
                base_url="https://example.com",
            )
        return integration

    def test_azuredevops_alias_dispatches_to_adapter(self, db):
        """Type 'azuredevops' est normalisé vers 'azure_devops' → dispatch vers adapter."""
        from integrations.tasks import run_integration_health_check, _ADAPTER_TYPES, _ADAPTER_TYPE_ALIASES

        integration = self._create_integration(db, "azuredevops", "HC AzureDevOps Alias")

        # Vérifier que l'alias existe dans la table
        assert "azuredevops" in _ADAPTER_TYPE_ALIASES
        assert _ADAPTER_TYPE_ALIASES["azuredevops"] == "azure_devops"
        assert "azure_devops" in _ADAPTER_TYPES

        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=ok_result) as mock_adapter_fn:
            run_integration_health_check(integration.id)

        # _resolve_and_check_adapter doit être appelé (pas la branche service ni UNKNOWN)
        mock_adapter_fn.assert_called_once_with(integration)

    def test_terraform_alias_dispatches_to_adapter(self, db):
        """Type 'terraform' est normalisé vers 'terraform_cloud' → dispatch vers adapter."""
        from integrations.tasks import run_integration_health_check, _ADAPTER_TYPES, _ADAPTER_TYPE_ALIASES

        integration = self._create_integration(db, "terraform", "HC Terraform Alias")

        assert "terraform" in _ADAPTER_TYPE_ALIASES
        assert _ADAPTER_TYPE_ALIASES["terraform"] == "terraform_cloud"
        assert "terraform_cloud" in _ADAPTER_TYPES

        ok_result = HealthCheckResult(
            status=HealthCheckStatus.OK,
            checked_at=datetime.now(timezone.utc),
        )

        with patch("integrations.tasks._resolve_and_check_adapter", return_value=ok_result) as mock_adapter_fn:
            run_integration_health_check(integration.id)

        mock_adapter_fn.assert_called_once_with(integration)
