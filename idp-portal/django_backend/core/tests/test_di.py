"""
Tests unitaires pour core/di.py — Story 33.4 (DIP)

Vérifient :
- Les factories par défaut retournent les bons types de service.
- override_service() injecte la factory custom.
- reset_services() efface les overrides.
"""
from unittest.mock import MagicMock

import pytest

from core.di import (
    get_catalog_service,
    get_execution_service,
    get_inventory_service,
    get_profile_service,
    override_service,
    reset_services,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Garantit que le registry est vide avant et après chaque test."""
    reset_services()
    yield
    reset_services()


# ---------------------------------------------------------------------------
# Tests du fallback par défaut
# ---------------------------------------------------------------------------

def test_get_profile_service_default():
    from profiles.services import ProfileService
    svc = get_profile_service()
    assert isinstance(svc, ProfileService)


def test_get_execution_service_default():
    from executions.services import ExecutionService
    svc = get_execution_service()
    assert isinstance(svc, ExecutionService)


def test_get_catalog_service_default():
    from catalog.services import CatalogService
    svc = get_catalog_service()
    assert isinstance(svc, CatalogService)


def test_get_inventory_service_default():
    from inventory.services import InventoryService
    svc = get_inventory_service()
    assert isinstance(svc, InventoryService)


# ---------------------------------------------------------------------------
# Tests de l'override
# ---------------------------------------------------------------------------

def test_override_profile_service():
    mock_svc = MagicMock()
    override_service('profile_service', lambda: mock_svc)
    assert get_profile_service() is mock_svc


def test_override_execution_service():
    mock_svc = MagicMock()
    override_service('execution_service', lambda: mock_svc)
    assert get_execution_service() is mock_svc


def test_override_catalog_service():
    mock_svc = MagicMock()
    override_service('catalog_service', lambda: mock_svc)
    assert get_catalog_service() is mock_svc


def test_override_inventory_service():
    mock_svc = MagicMock()
    override_service('inventory_service', lambda: mock_svc)
    assert get_inventory_service() is mock_svc


# ---------------------------------------------------------------------------
# Tests de reset_services
# ---------------------------------------------------------------------------

def test_reset_clears_all_overrides():
    mock_svc = MagicMock()
    override_service('catalog_service', lambda: mock_svc)
    reset_services()
    from catalog.services import CatalogService
    svc = get_catalog_service()
    assert isinstance(svc, CatalogService)
    assert svc is not mock_svc


def test_override_factory_called_each_time():
    """Chaque appel au helper doit appeler la factory (pas de cache)."""
    call_count = 0

    def factory():
        nonlocal call_count
        call_count += 1
        return MagicMock()

    override_service('profile_service', factory)
    get_profile_service()
    get_profile_service()
    assert call_count == 2
