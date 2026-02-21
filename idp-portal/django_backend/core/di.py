"""
Dependency Injection helpers — Story 33.4 (DIP)

Provides factory functions for the main services (Profile, Execution, Catalog,
Inventory) and a lightweight override registry for tests.

Usage
-----
Production code (e.g. inside a DRF ViewSet) calls the helper directly:

    from core.di import get_catalog_service
    svc = get_catalog_service()

Tests can override any factory without monkey-patching imports:

    from core.di import override_service, reset_services
    override_service('catalog_service', lambda: MockCatalogService())
    # ... run test ...
    reset_services()

Design choice (Option A — see ADR adr-006)
-----------------------------------------
- No external DI framework (over-engineering).
- No ``override_settings(SERVICES=...)`` — bypasses type-checking.
- All imports are lazy (inside function body) to avoid circular imports.
"""
from __future__ import annotations

from typing import Callable

# ---------------------------------------------------------------------------
# Internal registry — maps service name → zero-argument factory callable.
# Empty in production; populated by tests via override_service().
# ---------------------------------------------------------------------------
_service_registry: dict[str, Callable] = {}


# ---------------------------------------------------------------------------
# Public factory helpers
# ---------------------------------------------------------------------------

def get_profile_service():
    """Return a ProfileService instance (overridable in tests)."""
    factory = _service_registry.get('profile_service')
    if factory:
        return factory()
    from profiles.services import ProfileService  # noqa: PLC0415
    return ProfileService()


def get_execution_service():
    """Return an ExecutionService instance (overridable in tests)."""
    factory = _service_registry.get('execution_service')
    if factory:
        return factory()
    from executions.services import ExecutionService  # noqa: PLC0415
    return ExecutionService()


def get_catalog_service():
    """Return a CatalogService instance (overridable in tests)."""
    factory = _service_registry.get('catalog_service')
    if factory:
        return factory()
    from catalog.services import CatalogService  # noqa: PLC0415
    return CatalogService()


def get_inventory_service():
    """Return an InventoryService instance (overridable in tests)."""
    factory = _service_registry.get('inventory_service')
    if factory:
        return factory()
    from inventory.services import InventoryService  # noqa: PLC0415
    return InventoryService()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def override_service(name: str, factory: Callable) -> None:
    """
    Register a custom factory for *name* (used in test setUp / fixture).

    Args:
        name:    Service key — one of:
                 'profile_service', 'execution_service',
                 'catalog_service', 'inventory_service'.
        factory: Zero-argument callable returning the desired mock/stub.

    Example::

        override_service('catalog_service', lambda: MockCatalogService())
    """
    _service_registry[name] = factory


def reset_services() -> None:
    """
    Clear all service overrides (call in test tearDown / fixture finalizer).
    """
    _service_registry.clear()
