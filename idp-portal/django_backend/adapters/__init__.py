"""
Adapter factory for platform integrations.

Story 27.1: AAPAdapter for Ansible Automation Platform.
Story 27.2: TowerAdapter for Ansible Tower / AWX.
Story 27.3: AzureDevOpsAdapter for Azure DevOps Pipelines.
Story 27.4: GitHubActionsAdapter for GitHub Actions.
Story 27.5: TerraformCloudAdapter for Terraform Cloud.

Story 33.1: OCP — replaced if/elif chains with AdapterRegistry.
  New platforms are registered here; get_platform_adapter() delegates to
  the registry without any if/elif.
"""
from __future__ import annotations

from adapters.base_adapter import BaseAdapter
from adapters.registry import adapter_registry


# ---------------------------------------------------------------------------
# Factory functions — parameter validation stays here, not in the registry
# ---------------------------------------------------------------------------

def _factory_aap(base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs) -> BaseAdapter:
    from adapters.aap_adapter import AAPAdapter
    kw: dict = {"base_url": base_url, "auth_headers": auth_headers, **kwargs}
    if timeout is not None:
        kw["timeout"] = timeout
    return AAPAdapter(**kw)


def _factory_tower(base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs) -> BaseAdapter:
    from adapters.tower_adapter import TowerAdapter
    kw: dict = {"base_url": base_url, "auth_headers": auth_headers, **kwargs}
    if timeout is not None:
        kw["timeout"] = timeout
    return TowerAdapter(**kw)


def _factory_azure_devops(base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs) -> BaseAdapter:
    from adapters.azure_devops_adapter import AzureDevOpsAdapter
    kw: dict = {"base_url": base_url, "auth_headers": auth_headers, **kwargs}
    if timeout is not None:
        kw["timeout"] = timeout
    return AzureDevOpsAdapter(**kw)


def _factory_github_actions(base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs) -> BaseAdapter:
    if "owner" not in kwargs or "repo" not in kwargs:
        raise ValueError("github_actions platform requires 'owner' and 'repo' parameters")
    from adapters.github_actions_adapter import GitHubActionsAdapter
    kw: dict = {"base_url": base_url, "auth_headers": auth_headers, **kwargs}
    if timeout is not None:
        kw["timeout"] = timeout
    return GitHubActionsAdapter(**kw)


def _factory_terraform_cloud(base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs) -> BaseAdapter:
    if "organization" not in kwargs or not kwargs["organization"]:
        raise ValueError("terraform_cloud platform requires 'organization' parameter")
    from adapters.terraform_cloud_adapter import TerraformCloudAdapter
    kw: dict = {"base_url": base_url, "auth_headers": auth_headers, **kwargs}
    if timeout is not None:
        kw["timeout"] = timeout
    return TerraformCloudAdapter(**kw)


# ---------------------------------------------------------------------------
# Registration — add new platforms here, never touch get_platform_adapter()
# ---------------------------------------------------------------------------

adapter_registry.register("aap", _factory_aap)
adapter_registry.register("tower", _factory_tower)
adapter_registry.register("azure_devops", _factory_azure_devops)
adapter_registry.register("github_actions", _factory_github_actions)
adapter_registry.register("terraform_cloud", _factory_terraform_cloud)


# ---------------------------------------------------------------------------
# Public API — signature unchanged (backward-compatible)
# ---------------------------------------------------------------------------

# Re-exported for consumers who need to register custom adapters at runtime.
# Preferred over importing from adapters.registry directly.
__all__ = ["get_platform_adapter", "adapter_registry"]


def get_platform_adapter(
    platform_type: str,
    base_url: str,
    auth_headers: dict[str, str],
    timeout: float | None = None,
    **platform_kwargs,
) -> BaseAdapter:
    """Factory to instantiate the correct adapter for a given platform type.

    Delegates to adapter_registry — no if/elif.

    Args:
        platform_type: Platform identifier ('aap', 'tower', 'azure_devops',
            'github_actions', or 'terraform_cloud').
        base_url: Platform base URL.
        auth_headers: Pre-built auth headers dict.
        timeout: Optional custom timeout.
        **platform_kwargs: Platform-specific args (e.g. owner, repo for github_actions).

    Returns:
        Adapter instance.

    Raises:
        ValueError: If platform_type is not supported.
    """
    return adapter_registry.get(
        platform_type,
        base_url=base_url,
        auth_headers=auth_headers,
        timeout=timeout,
        **platform_kwargs,
    )
