"""
Registry pattern for platform adapters (OCP — Open/Closed Principle).

Story 33.1: Replace if/elif chains with a registry so that new platforms
can be added without modifying adapters/__init__.py.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from adapters.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry mapping platform_type strings to factory callables.

    Each factory callable receives **kwargs and returns a BaseAdapter instance.
    Parameter validation (e.g. owner+repo for github_actions) stays inside
    the individual factory functions, not here.

    Note: Registrations happen at module import time (single-threaded). Dynamic
    registration at request time in a multi-threaded environment is not supported.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., BaseAdapter]] = {}

    def register(self, platform_type: str, factory: Callable[..., BaseAdapter]) -> None:
        """Register a factory function for a given platform type.

        Args:
            platform_type: Platform identifier string (e.g. 'aap').
            factory: Callable that accepts **kwargs and returns a BaseAdapter.

        Note:
            Re-registering an existing type replaces the previous factory and
            logs a warning to help detect accidental overwrites.
        """
        if platform_type in self._registry:
            logger.warning(
                "AdapterRegistry: overwriting existing factory for platform_type=%r",
                platform_type,
            )
        self._registry[platform_type] = factory

    def unregister(self, platform_type: str) -> None:
        """Remove a registered factory for the given platform type.

        Args:
            platform_type: Platform identifier string to remove.

        Raises:
            KeyError: If platform_type is not registered.
        """
        del self._registry[platform_type]

    def get(self, platform_type: str, **kwargs: Any) -> BaseAdapter:
        """Instantiate the adapter for the given platform type.

        Args:
            platform_type: Platform identifier string.
            **kwargs: Forwarded to the factory function.

        Returns:
            BaseAdapter instance.

        Raises:
            ValueError: If platform_type is not registered.
        """
        if platform_type not in self._registry:
            raise ValueError(f"Unsupported platform_type: {platform_type}")
        return self._registry[platform_type](**kwargs)

    def list_types(self) -> list[str]:
        """Return list of registered platform type identifiers.

        Returns types in insertion order (Python 3.7+ dict guarantee).
        """
        return list(self._registry.keys())


adapter_registry = AdapterRegistry()
