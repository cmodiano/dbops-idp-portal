"""
Registry pattern for service clients (OCP — Open/Closed Principle).

Story 33.1: Replace if/elif chains with a registry so that new services
can be added without modifying services/__init__.py.
"""
from __future__ import annotations

import structlog
from typing import Any, Callable

logger = structlog.get_logger(__name__)


class ServiceRegistry:
    """Registry mapping service_type strings to factory callables.

    Each factory callable receives **config kwargs and returns a service instance.

    Note: Registrations happen at module import time (single-threaded). Dynamic
    registration at request time in a multi-threaded environment is not supported.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Any]] = {}

    def register(self, service_type: str, factory: Callable[..., Any]) -> None:
        """Register a factory function for a given service type.

        Args:
            service_type: Service identifier string (e.g. 'vault').
            factory: Callable that accepts **config kwargs and returns a service instance.

        Note:
            Re-registering an existing type replaces the previous factory and
            logs a warning to help detect accidental overwrites.
        """
        if service_type in self._registry:
            logger.warning(
                "service_registry_overwrite",
                service_type=service_type,
            )
        self._registry[service_type] = factory

    def unregister(self, service_type: str) -> None:
        """Remove a registered factory for the given service type.

        Args:
            service_type: Service identifier string to remove.

        Raises:
            KeyError: If service_type is not registered.
        """
        del self._registry[service_type]

    def get(self, service_type: str, **config: Any) -> Any:
        """Instantiate the service client for the given service type.

        Args:
            service_type: Service identifier string.
            **config: Forwarded to the factory function.

        Returns:
            Service client instance.

        Raises:
            ValueError: If service_type is not registered.
        """
        if service_type not in self._registry:
            available = list(self._registry.keys())
            raise ValueError(
                f"Unsupported service_type: '{service_type}'. Available: {available}"
            )
        return self._registry[service_type](**config)

    def list_types(self) -> list[str]:
        """Return list of registered service type identifiers.

        Returns types in insertion order (Python 3.7+ dict guarantee).
        """
        return list(self._registry.keys())


service_registry = ServiceRegistry()
