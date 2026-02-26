"""
Registry pattern for platform adapters (OCP — Open/Closed Principle).

Story 33.1: Replace if/elif chains with a registry so that new platforms
can be added without modifying adapters/__init__.py.
Story 47.4: Add queue support so Celery queue resolution is derived from the
registry instead of a hardcoded PLATFORM_QUEUE_MAP.
"""
from __future__ import annotations

import structlog
from typing import Any, Callable

from adapters.base_adapter import BaseAdapter

logger = structlog.get_logger(__name__)


class AdapterRegistry:
    """Registry mapping platform_type strings to factory callables and Celery queues.

    Each factory callable receives **kwargs and returns a BaseAdapter instance.
    Parameter validation (e.g. owner+repo for github_actions) stays inside
    the individual factory functions, not here.

    Story 47.4: Each platform_type is also associated with a Celery queue name.
    By default, the queue name equals the platform_type. Use the `queue` parameter
    in register() to specify a different queue (e.g. tower→aap).

    Note: Registrations happen at module import time (single-threaded). Dynamic
    registration at request time in a multi-threaded environment is not supported.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., BaseAdapter]] = {}
        self._queue_map: dict[str, str] = {}  # platform_type → Celery queue name

    def register(
        self,
        platform_type: str,
        factory: Callable[..., BaseAdapter],
        queue: str | None = None,
    ) -> None:
        """Register a factory function and Celery queue for a given platform type.

        Args:
            platform_type: Platform identifier string (e.g. 'aap').
            factory: Callable that accepts **kwargs and returns a BaseAdapter.
            queue: Celery queue name for this platform. Defaults to platform_type.
                   Use an explicit value when multiple platforms share a queue
                   (e.g. tower shares the 'aap' queue).

        Note:
            Re-registering an existing type replaces the previous factory and
            logs a warning to help detect accidental overwrites.
        """
        if platform_type in self._registry:
            logger.warning(
                "adapter_registry_overwrite",
                platform_type=platform_type,
            )
        self._registry[platform_type] = factory
        self._queue_map[platform_type] = queue if queue is not None else platform_type

    def get_queue(self, platform_type: str) -> str:
        """Return the Celery queue name for the given platform type.

        Returns 'default' for unknown platform types so that unrecognised
        platforms fall back to the default queue without raising an exception.

        Args:
            platform_type: Platform identifier string.

        Returns:
            Celery queue name, or 'default' if platform_type is not registered.
        """
        return self._queue_map.get(platform_type, "default")

    def list_queues(self) -> list[str]:
        """Return unique Celery queue names in stable order.

        'default' is always included first (required for Beat tasks and
        trigger_platform_job fallback). Remaining queues are sorted alphabetically.

        Returns:
            List of queue names, e.g. ['default', 'aap', 'azure', 'github', 'terraform'].
        """
        unique = set(self._queue_map.values()) - {"default"}
        return ["default"] + sorted(unique)

    def unregister(self, platform_type: str) -> None:
        """Remove a registered factory for the given platform type.

        Args:
            platform_type: Platform identifier string to remove.

        Raises:
            KeyError: If platform_type is not registered.
        """
        del self._registry[platform_type]
        self._queue_map.pop(platform_type, None)  # Story 47.4: keep _queue_map in sync

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
