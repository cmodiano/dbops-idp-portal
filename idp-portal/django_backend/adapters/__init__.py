"""
Adapter factory for platform integrations.

Story 27.1: AAPAdapter for Ansible Automation Platform.
Story 27.2: TowerAdapter for Ansible Tower / AWX.
Story 27.3: AzureDevOpsAdapter for Azure DevOps Pipelines.
"""
from __future__ import annotations

from adapters.base_adapter import BaseAdapter


def get_platform_adapter(
    platform_type: str,
    base_url: str,
    auth_headers: dict[str, str],
    timeout: float | None = None,
) -> BaseAdapter:
    """Factory to instantiate the correct adapter for a given platform type.

    Args:
        platform_type: Platform identifier ('aap', 'tower', or 'azure_devops').
        base_url: Platform base URL.
        auth_headers: Pre-built auth headers dict.
        timeout: Optional custom timeout.

    Returns:
        Adapter instance.

    Raises:
        ValueError: If platform_type is not supported.
    """
    kwargs: dict = {"base_url": base_url, "auth_headers": auth_headers}
    if timeout is not None:
        kwargs["timeout"] = timeout

    if platform_type == "aap":
        from adapters.aap_adapter import AAPAdapter
        return AAPAdapter(**kwargs)

    if platform_type == "tower":
        from adapters.tower_adapter import TowerAdapter
        return TowerAdapter(**kwargs)

    if platform_type == "azure_devops":
        from adapters.azure_devops_adapter import AzureDevOpsAdapter
        return AzureDevOpsAdapter(**kwargs)

    raise ValueError(f"Unsupported platform_type: {platform_type}")
