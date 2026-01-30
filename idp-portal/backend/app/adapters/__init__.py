"""Platform adapter factory and registry (Story 4.3, Task 5.3).

Provides factory function to get platform adapters based on platform type.
Uses Strategy Pattern for extensibility without modifying core engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.adapters.base_adapter import BaseAdapter, MockAdapter
from app.adapters.aap_adapter import AAPAdapter

if TYPE_CHECKING:
    from app.core.config import Settings

# Adapter registry: platform_type -> adapter class
_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "mock": MockAdapter,
    "aap": AAPAdapter,
    # "terraform": TerraformAdapter,  # Future
    # "github_actions": GitHubActionsAdapter,  # Future
    # "azure_devops": AzureDevOpsAdapter,  # Future
}


def get_platform_adapter(platform_type: str, base_url: str) -> BaseAdapter:
    """Factory function to get platform adapter (Story 4.3, Task 5.3).

    Creates appropriate adapter based on platform type using Strategy Pattern.

    Args:
        platform_type: Type of platform (e.g., "aap", "terraform", "mock")
        base_url: Base URL for platform API

    Returns:
        Configured BaseAdapter instance for the platform

    Raises:
        ValueError: If platform_type is not supported
    """
    adapter_class = _ADAPTER_REGISTRY.get(platform_type.lower())

    if adapter_class is None:
        supported = ", ".join(_ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"Plateforme non supportée: {platform_type}. "
            f"Plateformes disponibles: {supported}"
        )

    return adapter_class(platform_type=platform_type, base_url=base_url)


def register_adapter(platform_type: str, adapter_class: type[BaseAdapter]) -> None:
    """Register a new adapter type (for extensibility).

    Args:
        platform_type: Type identifier for the platform
        adapter_class: Adapter class implementing BaseAdapter
    """
    _ADAPTER_REGISTRY[platform_type.lower()] = adapter_class


__all__ = [
    "BaseAdapter",
    "MockAdapter",
    "AAPAdapter",
    "get_platform_adapter",
    "register_adapter",
]
