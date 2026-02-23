"""
Tests d'injection de dépendances pour ActionViewSet — Story 33.4 (DIP) + Story 34.1 (AC1)

Vérifient :
- Surcharge de _catalog_service_class dans les tests (AC3)
- La méthode get_catalog_service() retourne une instance du service injecté (AC3)
- Le fallback sur CatalogService par défaut (AC4 — rétrocompatibilité)
- Story 34.1 AC1 : destroy/deactivate/reactivate utilisent get_catalog_service()
"""
from unittest.mock import MagicMock, patch

import pytest


def test_action_viewset_injected_service():
    """AC3 : ActionViewSet accepte un service surchargé via _catalog_service_class."""
    mock_svc_class = MagicMock(return_value=MagicMock())
    from catalog.views.action_views import ActionViewSet
    view = ActionViewSet()
    view._catalog_service_class = mock_svc_class
    view.get_catalog_service()
    mock_svc_class.assert_called_once()


def test_action_viewset_default_service():
    """AC4 : Sans surcharge, ActionViewSet utilise CatalogService par défaut."""
    from catalog.services import CatalogService
    from catalog.views.action_views import ActionViewSet
    view = ActionViewSet()
    svc = view.get_catalog_service()
    assert isinstance(svc, CatalogService)


# ─── Story 34.1 AC1 : destroy/deactivate/reactivate utilisent get_catalog_service() ───


@pytest.mark.django_db
def test_destroy_uses_get_catalog_service():
    """Story 34.1 AC1 : destroy() délègue au service injecté via get_catalog_service()."""
    from catalog.views.action_views import ActionViewSet
    from catalog.models import Action
    from tests.factories import UserFactory
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request as DRFRequest

    user = UserFactory(profile='dbops')
    action_obj = Action.objects.create(name='DI Test Destroy', status='draft', created_by=user)

    mock_svc = MagicMock()
    mock_svc.delete_action.return_value = True
    mock_svc_class = MagicMock(return_value=mock_svc)

    view = ActionViewSet()
    view._catalog_service_class = mock_svc_class

    factory = APIRequestFactory()
    request = factory.delete(f'/admin/actions/{action_obj.id}/')
    drf_request = DRFRequest(request)
    drf_request.user = user

    with patch.object(view, 'get_object', return_value=action_obj):
        response = view.destroy(drf_request)

    mock_svc_class.assert_called_once()
    mock_svc.delete_action.assert_called_once_with(action_obj.id, user=user)
    assert response.status_code == 204


@pytest.mark.django_db
def test_deactivate_uses_get_catalog_service():
    """Story 34.1 AC1 : deactivate() délègue au service injecté via get_catalog_service()."""
    from catalog.views.action_views import ActionViewSet
    from catalog.models import Action
    from tests.factories import UserFactory
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request as DRFRequest

    user = UserFactory(profile='dbops')
    action_obj = Action.objects.create(name='DI Test Deactivate', status='published', created_by=user)

    mock_svc = MagicMock()
    mock_svc.get_workflows_referencing_action.return_value = []
    deactivated_action = MagicMock()
    deactivated_action.id = action_obj.id
    mock_svc.deactivate_action.return_value = {'action': deactivated_action, 'deactivated_workflows': []}
    mock_svc.get_by_id.return_value = action_obj
    mock_svc_class = MagicMock(return_value=mock_svc)

    view = ActionViewSet()
    view._catalog_service_class = mock_svc_class

    factory = APIRequestFactory()
    request = factory.put(f'/admin/actions/{action_obj.id}/deactivate/?confirmed=true')
    drf_request = DRFRequest(request)
    drf_request.user = user

    with patch.object(view, 'get_object', return_value=action_obj):
        response = view.deactivate(drf_request, pk=action_obj.id)

    mock_svc_class.assert_called_once()
    mock_svc.deactivate_action.assert_called_once()
    assert response.status_code == 200


@pytest.mark.django_db
def test_reactivate_uses_get_catalog_service():
    """Story 34.1 AC1 : reactivate() délègue au service injecté via get_catalog_service()."""
    from catalog.views.action_views import ActionViewSet
    from catalog.models import Action
    from tests.factories import UserFactory
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request as DRFRequest

    user = UserFactory(profile='dbops')
    action_obj = Action.objects.create(name='DI Test Reactivate', status='disabled', created_by=user)

    mock_svc = MagicMock()
    reactivated = MagicMock()
    reactivated.id = action_obj.id
    mock_svc.reactivate_action.return_value = reactivated
    mock_svc.get_by_id.return_value = action_obj
    mock_svc_class = MagicMock(return_value=mock_svc)

    view = ActionViewSet()
    view._catalog_service_class = mock_svc_class

    factory = APIRequestFactory()
    request = factory.put(f'/admin/actions/{action_obj.id}/reactivate/')
    drf_request = DRFRequest(request)
    drf_request.user = user

    with patch.object(view, 'get_object', return_value=action_obj):
        response = view.reactivate(drf_request, pk=action_obj.id)

    mock_svc_class.assert_called_once()
    mock_svc.reactivate_action.assert_called_once_with(action_obj.id, user=user)
    assert response.status_code == 200
