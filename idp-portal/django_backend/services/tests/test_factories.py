"""
Tests for service factory and platform adapter factory.

Story 27.9: Validate factories, backward compatibility, and correct
classification of platforms vs services.
"""
from __future__ import annotations

import pytest

from adapters import get_platform_adapter
from adapters.base_adapter import BaseAdapter
from services import SERVICE_TYPES, get_service_client
from services.jira_service import JiraService
from services.splunk_service import SplunkService
from services.vault_service import VaultService
from services.servicenow_service import ServiceNowService


# ---------------------------------------------------------------------------
# get_service_client factory tests (AC3)
# ---------------------------------------------------------------------------

class TestGetServiceClient:
    """Test services/__init__.py get_service_client() factory."""

    def test_vault_service_creation(self) -> None:
        """get_service_client('vault') returns VaultService instance."""
        svc = get_service_client(
            "vault",
            vault_addr="http://vault:8200",
            vault_token="test-token",
        )
        assert isinstance(svc, VaultService)
        assert svc.vault_addr == "http://vault:8200"

    def test_splunk_service_creation(self) -> None:
        """get_service_client('splunk') returns SplunkService instance."""
        svc = get_service_client(
            "splunk",
            base_url="https://splunk.example.com:8088",
            auth_headers={"Authorization": "Splunk test-token"},
        )
        assert isinstance(svc, SplunkService)
        assert svc.base_url == "https://splunk.example.com:8088"

    def test_servicenow_service_creation(self) -> None:
        """get_service_client('servicenow') returns ServiceNowService instance."""
        svc = get_service_client(
            "servicenow",
            base_url="https://instance.service-now.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(svc, ServiceNowService)
        assert svc.base_url == "https://instance.service-now.com"

    def test_jira_service_creation(self) -> None:
        """get_service_client('jira') returns JiraService instance."""
        svc = get_service_client(
            "jira",
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )
        assert isinstance(svc, JiraService)
        assert svc.base_url == "https://jira.example.com"

    def test_jira_service_creation_with_config(self) -> None:
        """get_service_client('jira') with custom timeout."""
        svc = get_service_client(
            "jira",
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
            timeout=60.0,
        )
        assert isinstance(svc, JiraService)
        assert svc.timeout == 60.0

    def test_unknown_service_type_raises_value_error(self) -> None:
        """get_service_client with unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported service_type: 'unknown'"):
            get_service_client("unknown")

    def test_service_types_registry(self) -> None:
        """SERVICE_TYPES contains all supported service types."""
        assert "vault" in SERVICE_TYPES
        assert "splunk" in SERVICE_TYPES
        assert "servicenow" in SERVICE_TYPES
        assert "jira" in SERVICE_TYPES
        assert "notification" in SERVICE_TYPES
        assert len(SERVICE_TYPES) == 5


# ---------------------------------------------------------------------------
# get_platform_adapter factory tests (AC3)
# ---------------------------------------------------------------------------

class TestGetPlatformAdapter:
    """Test adapters/__init__.py get_platform_adapter() factory."""

    def test_aap_adapter_creation(self) -> None:
        """get_platform_adapter('aap') returns BaseAdapter instance."""
        adapter = get_platform_adapter(
            platform_type="aap",
            base_url="https://aap.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, BaseAdapter)
        assert hasattr(adapter, "trigger")

    def test_tower_adapter_creation(self) -> None:
        """get_platform_adapter('tower') returns BaseAdapter instance."""
        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, BaseAdapter)

    def test_azure_devops_adapter_creation(self) -> None:
        """get_platform_adapter('azure_devops') returns BaseAdapter instance."""
        adapter = get_platform_adapter(
            platform_type="azure_devops",
            base_url="https://dev.azure.com/org",
            auth_headers={"Authorization": "Basic creds"},
        )
        assert isinstance(adapter, BaseAdapter)

    def test_github_actions_adapter_creation(self) -> None:
        """get_platform_adapter('github_actions') returns BaseAdapter with owner/repo."""
        adapter = get_platform_adapter(
            platform_type="github_actions",
            base_url="https://api.github.com",
            auth_headers={"Authorization": "Bearer token"},
            owner="myorg",
            repo="myrepo",
        )
        assert isinstance(adapter, BaseAdapter)

    def test_terraform_cloud_adapter_creation(self) -> None:
        """get_platform_adapter('terraform_cloud') returns BaseAdapter with organization."""
        adapter = get_platform_adapter(
            platform_type="terraform_cloud",
            base_url="https://app.terraform.io",
            auth_headers={"Authorization": "Bearer token"},
            organization="my-org",
        )
        assert isinstance(adapter, BaseAdapter)

    def test_unknown_platform_type_raises_value_error(self) -> None:
        """get_platform_adapter with unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported platform_type: jira"):
            get_platform_adapter(
                platform_type="jira",
                base_url="https://jira.example.com",
                auth_headers={},
            )

    def test_splunk_not_in_platform_adapters(self) -> None:
        """Splunk is a Service, NOT a Platform — should not be in get_platform_adapter."""
        with pytest.raises(ValueError, match="Unsupported platform_type"):
            get_platform_adapter(
                platform_type="splunk",
                base_url="https://splunk.example.com",
                auth_headers={},
            )


# ---------------------------------------------------------------------------
# Platform vs Service classification tests (AC1)
# ---------------------------------------------------------------------------

class TestPlatformServiceClassification:
    """Test that platforms and services are correctly classified."""

    def test_platforms_implement_base_adapter(self) -> None:
        """All platform adapters must implement BaseAdapter."""
        for platform_type in ("aap", "tower", "azure_devops"):
            adapter = get_platform_adapter(
                platform_type=platform_type,
                base_url="https://example.com",
                auth_headers={"Authorization": "Bearer x"},
            )
            assert isinstance(adapter, BaseAdapter), f"{platform_type} should be a BaseAdapter"
            assert hasattr(adapter, "trigger"), f"{platform_type} should have trigger()"
            assert hasattr(adapter, "get_status"), f"{platform_type} should have get_status()"
            assert hasattr(adapter, "get_job_logs"), f"{platform_type} should have get_job_logs()"
            assert hasattr(adapter, "cancel_execution"), f"{platform_type} should have cancel_execution()"

    def test_services_do_not_implement_base_adapter(self) -> None:
        """Services must NOT implement BaseAdapter."""
        splunk = SplunkService(
            base_url="https://splunk.example.com",
            auth_headers={"Authorization": "Splunk token"},
        )
        assert not isinstance(splunk, BaseAdapter)

        servicenow = ServiceNowService(
            base_url="https://instance.service-now.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert not isinstance(servicenow, BaseAdapter)

        jira = JiraService(
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )
        assert not isinstance(jira, BaseAdapter)


# ---------------------------------------------------------------------------
# Backward compatibility tests (AC4)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Test backward compatibility aliases work."""

    def test_splunk_adapter_alias_import(self) -> None:
        """SplunkAdapter alias still importable from services.splunk_service."""
        from services.splunk_service import SplunkAdapter
        assert SplunkAdapter is SplunkService

    def test_vault_service_importable_from_services(self) -> None:
        """VaultService importable from services.vault_service."""
        from services.vault_service import VaultService as VS
        assert VS is VaultService

    def test_vault_get_vault_service_importable(self) -> None:
        """get_vault_service() singleton importable from services.vault_service."""
        from services.vault_service import get_vault_service
        assert callable(get_vault_service)
