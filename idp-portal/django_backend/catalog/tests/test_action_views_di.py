"""
Tests d'injection de dépendances pour ActionViewSet — Story 33.4 (DIP)

Vérifient :
- Surcharge de _catalog_service_class dans les tests (AC3)
- La méthode get_catalog_service() retourne une instance du service injecté (AC3)
- Le fallback sur CatalogService par défaut (AC4 — rétrocompatibilité)
"""
from unittest.mock import MagicMock

import pytest


def test_action_viewset_injected_service():
    """AC3 : ActionViewSet accepte un service surchargé via _catalog_service_class."""
    mock_svc_class = MagicMock(return_value=MagicMock())
    from catalog.views.action_views import ActionViewSet
    view = ActionViewSet()
    view._catalog_service_class = mock_svc_class
    svc = view.get_catalog_service()
    mock_svc_class.assert_called_once()


def test_action_viewset_default_service():
    """AC4 : Sans surcharge, ActionViewSet utilise CatalogService par défaut."""
    from catalog.services import CatalogService
    from catalog.views.action_views import ActionViewSet
    view = ActionViewSet()
    svc = view.get_catalog_service()
    assert isinstance(svc, CatalogService)
