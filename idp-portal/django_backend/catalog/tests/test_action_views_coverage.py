"""
Comprehensive coverage tests for catalog/views/action_views.py.

Target: ≥90% coverage of ActionViewSet.
Tests are organized by method group, each testing all major branches.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from django.db import IntegrityError

from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request as DRFRequest

from catalog.views.action_views import ActionViewSet
from tests.factories import UserFactory, ActionFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dbops_user():
    """Create a user with DBOPS profile."""
    return UserFactory(profile='DBOPS')


def _drf_request(factory_request, user):
    """Wrap a factory request as a DRF request with an authenticated user."""
    req = DRFRequest(factory_request)
    req.user = user
    return req


factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# TestGetSerializerClass
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetSerializerClass:
    """Tests for get_serializer_class method (lines 73-79)."""

    def test_create_action_returns_create_serializer(self):
        from catalog.serializers import ActionCreateSerializer
        view = ActionViewSet()
        view.action = 'create'
        assert view.get_serializer_class() is ActionCreateSerializer

    def test_list_action_returns_list_serializer(self):
        from catalog.serializers import ActionListSerializer
        view = ActionViewSet()
        view.action = 'list'
        assert view.get_serializer_class() is ActionListSerializer

    def test_other_action_returns_default_serializer(self):
        from catalog.serializers import ActionSerializer
        view = ActionViewSet()
        view.action = 'retrieve'
        assert view.get_serializer_class() is ActionSerializer

    def test_update_action_returns_default_serializer(self):
        from catalog.serializers import ActionSerializer
        view = ActionViewSet()
        view.action = 'update'
        assert view.get_serializer_class() is ActionSerializer


# ---------------------------------------------------------------------------
# TestGetQueryset
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetQueryset:
    """Tests for get_queryset method (lines 81-109)."""

    def _make_view(self, user, query_params=None, action_name='list'):
        """Build a configured ActionViewSet instance."""
        raw = factory.get('/admin/actions/', query_params or {})
        drf_req = DRFRequest(raw)
        drf_req.user = user
        view = ActionViewSet()
        view.request = drf_req
        view.action = action_name
        view.kwargs = {}
        return view

    def test_list_excludes_disabled_by_default(self):
        user = _make_dbops_user()
        ActionFactory(status='draft', created_by=user)
        ActionFactory(status='published', created_by=user)
        ActionFactory(status='disabled', created_by=user)
        view = self._make_view(user)
        qs = view.get_queryset()
        statuses = list(qs.values_list('status', flat=True))
        assert 'disabled' not in statuses

    def test_list_include_disabled_true(self):
        user = _make_dbops_user()
        ActionFactory(status='disabled', created_by=user)
        view = self._make_view(user, {'include_disabled': 'true'})
        qs = view.get_queryset()
        statuses = list(qs.values_list('status', flat=True))
        assert 'disabled' in statuses

    def test_list_status_filter(self):
        user = _make_dbops_user()
        ActionFactory(status='draft', created_by=user)
        ActionFactory(status='published', created_by=user)
        view = self._make_view(user, {'status': 'published'})
        qs = view.get_queryset()
        statuses = list(qs.values_list('status', flat=True))
        assert all(s == 'published' for s in statuses)

    def test_list_engine_filter(self):
        user = _make_dbops_user()
        ActionFactory(engine='Oracle', created_by=user)
        view = self._make_view(user, {'engine': 'Oracle'})
        qs = view.get_queryset()
        engines = list(qs.values_list('engine', flat=True))
        assert all(e == 'Oracle' for e in engines)

    def test_list_item_type_filter(self):
        user = _make_dbops_user()
        ActionFactory(item_type='action', created_by=user)
        ActionFactory(item_type='workflow', created_by=user)
        view = self._make_view(user, {'item_type': 'action'})
        qs = view.get_queryset()
        types = list(qs.values_list('item_type', flat=True))
        assert all(t == 'action' for t in types)

    def test_non_list_action_no_disabled_filter(self):
        """For retrieve/update, disabled should NOT be auto-filtered out."""
        user = _make_dbops_user()
        ActionFactory(status='disabled', created_by=user)
        view = self._make_view(user, action_name='retrieve')
        qs = view.get_queryset()
        statuses = list(qs.values_list('status', flat=True))
        assert 'disabled' in statuses

    def test_status_filter_overrides_default_exclude(self):
        """With explicit status filter set, disabled items matching that status appear."""
        user = _make_dbops_user()
        ActionFactory(status='disabled', created_by=user)
        view = self._make_view(user, {'status': 'disabled'})
        qs = view.get_queryset()
        statuses = list(qs.values_list('status', flat=True))
        assert 'disabled' in statuses


# ---------------------------------------------------------------------------
# TestCreate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreate:
    """Tests for create method (lines 111-134)."""

    def _patch_serializer_valid(self, validated_data=None):
        """Context manager: patch ActionCreateSerializer.is_valid to always succeed."""
        if validated_data is None:
            validated_data = {
                'name': 'Test Action',
                'engine': 'Oracle',
                'platform': 'AAP',
                'item_type': 'action',
            }
        from catalog.serializers import ActionCreateSerializer
        mock_ser = MagicMock()
        mock_ser.is_valid = MagicMock(return_value=True)
        mock_ser.validated_data = validated_data
        return patch.object(ActionCreateSerializer, '__new__', return_value=mock_ser)

    def test_create_success(self):
        user = _make_dbops_user()
        mock_action = MagicMock()
        mock_action.id = 1
        mock_svc = MagicMock()
        mock_svc.create_action.return_value = mock_action
        mock_svc.get_by_id.return_value = mock_action

        from catalog.serializers import ActionCreateSerializer, ActionSerializer
        validated = {'name': 'Test Action', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)), \
             patch.object(ActionSerializer, 'data', new_callable=lambda: property(lambda self: {'id': 1, 'name': 'Test Action'})):
            view = ActionViewSet.as_view({'post': 'create'})
            request = factory.post('/admin/actions/', {
                'name': 'Test Action',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request)

        assert response.status_code == 201
        assert 'data' in response.data

    def test_create_integrity_error_duplicate_name(self):
        user = _make_dbops_user()
        mock_svc = MagicMock()
        mock_svc.create_action.side_effect = IntegrityError('UK_ACTIONS_CATALOG_NAME')

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'Existing Action', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'post': 'create'})
            request = factory.post('/admin/actions/', {
                'name': 'Existing Action',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request)

        assert response.status_code == 400
        # DRFValidationError response has 'name' at top-level via exception handler
        assert 'name' in response.data.get('error', {}).get('details', response.data)

    def test_create_integrity_error_unique_name(self):
        """Also covers the UNIQUE + NAME branch."""
        user = _make_dbops_user()
        mock_svc = MagicMock()
        mock_svc.create_action.side_effect = IntegrityError('UNIQUE constraint failed: name')

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'Another Action', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'post': 'create'})
            request = factory.post('/admin/actions/', {
                'name': 'Another Action',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request)

        assert response.status_code == 400

    def test_create_integrity_error_reraise(self):
        """IntegrityError NOT about name should be re-raised (DRF returns 500)."""
        user = _make_dbops_user()
        mock_svc = MagicMock()
        mock_svc.create_action.side_effect = IntegrityError('FK constraint failed')

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'New Action', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'post': 'create'})
            request = factory.post('/admin/actions/', {
                'name': 'New Action',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request)

        # Custom exception handler returns 500 for unhandled IntegrityError
        assert response.status_code == 500

    def test_create_invalid_data_returns_400(self):
        user = _make_dbops_user()
        view = ActionViewSet.as_view({'post': 'create'})
        request = factory.post('/admin/actions/', {}, format='json')
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 400

    def test_create_unauthenticated_returns_403(self):
        view = ActionViewSet.as_view({'post': 'create'})
        request = factory.post('/admin/actions/', {}, format='json')
        response = view(request)
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# TestList
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestList:
    """Tests for list method (lines 136-146)."""

    def test_list_returns_paginated_response(self):
        user = _make_dbops_user()
        ActionFactory(status='published', created_by=user)
        ActionFactory(status='draft', created_by=user)

        view = ActionViewSet.as_view({'get': 'list'})
        request = factory.get('/admin/actions/')
        force_authenticate(request, user=user)
        response = view(request)

        assert response.status_code == 200

    def test_list_unauthenticated_returns_403(self):
        view = ActionViewSet.as_view({'get': 'list'})
        request = factory.get('/admin/actions/')
        response = view(request)
        assert response.status_code in (401, 403)

    def test_list_no_dbops_profile_returns_403(self):
        user = UserFactory(profile='DBA')
        view = ActionViewSet.as_view({'get': 'list'})
        request = factory.get('/admin/actions/')
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# TestRetrieve
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRetrieve:
    """Tests for retrieve method (lines 148-152)."""

    def test_retrieve_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)

        view = ActionViewSet.as_view({'get': 'retrieve'})
        request = factory.get(f'/admin/actions/{action_obj.id}/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_retrieve_not_found_returns_404(self):
        user = _make_dbops_user()
        view = ActionViewSet.as_view({'get': 'retrieve'})
        request = factory.get('/admin/actions/999999/')
        force_authenticate(request, user=user)
        response = view(request, pk=999999)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestUpdate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdate:
    """Tests for update method (lines 154-221)."""

    def _patch_update_serializer(self, validated_data=None):
        """Patch ActionCreateSerializer for update tests."""
        if validated_data is None:
            validated_data = {'name': 'Updated Name', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        from catalog.serializers import ActionCreateSerializer
        return (
            patch.object(ActionCreateSerializer, 'is_valid', return_value=True),
            patch.object(ActionCreateSerializer, 'validated_data',
                         new_callable=lambda: property(lambda self: validated_data)),
        )

    def test_update_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.update_action.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        from catalog.serializers import ActionCreateSerializer, ActionSerializer
        validated = {'name': 'Updated Name', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)), \
             patch.object(ActionSerializer, 'data', new_callable=lambda: property(lambda self: {'id': action_obj.id})):
            view = ActionViewSet.as_view({'put': 'update'})
            request = factory.put(f'/admin/actions/{action_obj.id}/', {
                'name': 'Updated Name',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_update_integrity_error_duplicate_name(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_action.side_effect = IntegrityError('UK_ACTIONS_CATALOG_NAME')

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'Existing', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'put': 'update'})
            request = factory.put(f'/admin/actions/{action_obj.id}/', {
                'name': 'Existing',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 400
        assert 'name' in response.data.get('error', {}).get('details', response.data)

    def test_update_integrity_error_reraise(self):
        """IntegrityError NOT about name should be re-raised (DRF returns 500)."""
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_action.side_effect = IntegrityError('FK error')

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'Something', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'put': 'update'})
            request = factory.put(f'/admin/actions/{action_obj.id}/', {
                'name': 'Something',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        # Custom exception handler returns 500 for unhandled IntegrityError
        assert response.status_code == 500

    def test_update_action_none_raises_not_found(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_action.return_value = None

        from catalog.serializers import ActionCreateSerializer
        validated = {'name': 'Something', 'engine': 'Oracle', 'platform': 'AAP', 'item_type': 'action'}
        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc), \
             patch.object(ActionCreateSerializer, 'is_valid', return_value=True), \
             patch.object(ActionCreateSerializer, 'validated_data', new_callable=lambda: property(lambda self: validated)):
            view = ActionViewSet.as_view({'put': 'update'})
            request = factory.put(f'/admin/actions/{action_obj.id}/', {
                'name': 'Something',
                'engine': 'Oracle',
                'platform': 'AAP',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404

    def test_update_with_business_rule_policy_id(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        view = ActionViewSet.as_view({'put': 'update'})
        request = factory.put(f'/admin/actions/{action_obj.id}/', {
            'business_rule_policy_id': None,
        }, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_update_xor_validation_both_brp_fields(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        view = ActionViewSet.as_view({'put': 'update'})
        request = factory.put(f'/admin/actions/{action_obj.id}/', {
            'business_rule_policy_id': 1,
            'business_rule_policies': [{'rule': 'test'}],
        }, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 400
        # The error is wrapped: response.data['error']['details']['business_rule_policies']
        details = response.data.get('error', {}).get('details', response.data)
        assert 'business_rule_policies' in details

    def test_update_inline_brp_validation_error(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        with patch('catalog.views.action_views.validate_business_rule_policies',
                   side_effect=ValueError('bad policy'), create=True), \
             patch('catalog.validators.validate_business_rule_policies',
                   side_effect=ValueError('bad policy')):
            view = ActionViewSet.as_view({'put': 'update'})
            request = factory.put(f'/admin/actions/{action_obj.id}/', {
                'business_rule_policies': [{'bad': 'data'}],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestUpdateTags
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateTags:
    """Tests for update_tags method (lines 223-257)."""

    def test_update_tags_with_tag_names(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.sync_tags.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_tags'})
            request = factory.put(f'/admin/actions/{action_obj.id}/tags/', {
                'tag_names': ['oracle', 'prod'],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data
        mock_svc.sync_tags.assert_called_once_with(action_obj.id, ['oracle', 'prod'])

    def test_update_tags_with_tag_ids(self):
        from catalog.models import Tag
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        tag = Tag.objects.create(name='my_tag')
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.sync_tags.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_tags'})
            request = factory.put(f'/admin/actions/{action_obj.id}/tags/', {
                'tag_ids': [tag.id],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200

    def test_update_tags_empty_tags(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.sync_tags.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_tags'})
            request = factory.put(f'/admin/actions/{action_obj.id}/tags/', {
                'tag_names': [],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        mock_svc.sync_tags.assert_called_once_with(action_obj.id, [])

    def test_update_tags_not_found(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.sync_tags.return_value = None

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_tags'})
            request = factory.put(f'/admin/actions/{action_obj.id}/tags/', {
                'tag_names': ['x'],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestUpdateStatus
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateStatus:
    """Tests for update_status method (lines 259-298)."""

    def test_update_status_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.update_status.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'patch': 'update_status'})
            request = factory.patch(f'/admin/actions/{action_obj.id}/status/', {
                'transition': 'publish',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_update_status_invalid_transition_error(self):
        from catalog.services import InvalidTransitionError
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_status.side_effect = InvalidTransitionError("Cannot publish")

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'patch': 'update_status'})
            request = factory.patch(f'/admin/actions/{action_obj.id}/status/', {
                'transition': 'publish',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        # InvalidStateError maps to HTTP 400 in custom_exception_handler
        assert response.status_code == 400
        assert response.data['error']['code'] == 'INVALID_STATE'

    def test_update_status_updated_action_none_raises_404(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_status.return_value = None

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'patch': 'update_status'})
            request = factory.patch(f'/admin/actions/{action_obj.id}/status/', {
                'transition': 'publish',
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404

    def test_update_status_invalid_data_returns_400(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        view = ActionViewSet.as_view({'patch': 'update_status'})
        request = factory.patch(f'/admin/actions/{action_obj.id}/status/', {}, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestUpdateExecutionSteps
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateExecutionSteps:
    """Tests for update_execution_steps method (lines 300-341)."""

    def test_update_execution_steps_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.update_execution_steps.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_execution_steps'})
            request = factory.put(f'/admin/actions/{action_obj.id}/execution-steps/', {
                'steps': [{'name': 'step1', 'type': 'vault'}],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_update_execution_steps_value_error(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_execution_steps.side_effect = ValueError("Only draft or disabled")

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_execution_steps'})
            request = factory.put(f'/admin/actions/{action_obj.id}/execution-steps/', {
                'steps': [],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        # InvalidStateError maps to HTTP 400 in custom_exception_handler
        assert response.status_code == 400
        assert response.data['error']['code'] == 'INVALID_STATE'

    def test_update_execution_steps_none_raises_404(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.update_execution_steps.return_value = None

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_execution_steps'})
            request = factory.put(f'/admin/actions/{action_obj.id}/execution-steps/', {
                'steps': [],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404

    def test_update_execution_steps_with_change_type_config(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        updated_mock = MagicMock()
        updated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.update_execution_steps.return_value = updated_mock
        mock_svc.get_by_id.return_value = updated_mock

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_execution_steps'})
            request = factory.put(f'/admin/actions/{action_obj.id}/execution-steps/', {
                'steps': [],
                'change_type_config': {'model': 'standard'},
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TestNameAvailable
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNameAvailable:
    """Tests for name_available method (lines 343-356)."""

    def test_name_available_no_name_param(self):
        user = _make_dbops_user()
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/')
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data['available'] is True

    def test_name_available_empty_name(self):
        user = _make_dbops_user()
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/', {'name': '   '})
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data['available'] is True

    def test_name_available_true(self):
        user = _make_dbops_user()
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/', {'name': 'NonExistentActionXYZ'})
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data['available'] is True

    def test_name_available_false(self):
        user = _make_dbops_user()
        _action_obj = ActionFactory(name='Unique Action Name', created_by=user)
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/', {'name': 'Unique Action Name'})
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data['available'] is False

    def test_name_available_with_valid_exclude_id(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(name='My Special Action', created_by=user)
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/', {
            'name': 'My Special Action',
            'exclude_id': str(action_obj.id),
        })
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        assert response.data['available'] is True

    def test_name_available_with_invalid_exclude_id(self):
        user = _make_dbops_user()
        ActionFactory(name='Another Action Z', created_by=user)
        view = ActionViewSet.as_view({'get': 'name_available'})
        request = factory.get('/admin/actions/name-available/', {
            'name': 'Another Action Z',
            'exclude_id': 'not-a-number',
        })
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == 200
        # Invalid exclude_id is silently ignored — name is taken
        assert response.data['available'] is False


# ---------------------------------------------------------------------------
# TestListEligibleForWorkflow
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestListEligibleForWorkflow:
    """Tests for list_eligible_for_workflow method (lines 358-367)."""

    def test_list_eligible_for_workflow(self):
        user = _make_dbops_user()
        ActionFactory(status='published', item_type='action', created_by=user)
        ActionFactory(status='draft', item_type='action', created_by=user)
        ActionFactory(status='published', item_type='workflow', created_by=user)

        view = ActionViewSet.as_view({'get': 'list_eligible_for_workflow'})
        request = factory.get('/admin/actions/eligible-for-workflow/')
        force_authenticate(request, user=user)
        response = view(request)

        assert response.status_code == 200
        assert 'data' in response.data
        # Only published actions (not workflows) should appear
        for item in response.data['data']:
            assert item['status'] == 'published'
            assert item['item_type'] == 'action'


# ---------------------------------------------------------------------------
# TestUpdateRemediationRules
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateRemediationRules:
    """Tests for update_remediation_rules method (lines 369-406)."""

    def test_update_remediation_rules_missing_returns_400(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_remediation_rules'})
            request = factory.put(f'/admin/actions/{action_obj.id}/remediation-rules/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        # BadRequestError maps to HTTP 400 in custom_exception_handler
        assert response.status_code == 400
        assert response.data['error']['code'] == 'BAD_REQUEST'

    def test_update_remediation_rules_non_draft_returns_400(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_remediation_rules'})
            request = factory.put(f'/admin/actions/{action_obj.id}/remediation-rules/', {
                'remediation_rules': {'on_failure': []},
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        # InvalidStateError maps to HTTP 400 in custom_exception_handler
        assert response.status_code == 400
        assert response.data['error']['code'] == 'INVALID_STATE'

    def test_update_remediation_rules_draft_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'update_remediation_rules'})
            request = factory.put(f'/admin/actions/{action_obj.id}/remediation-rules/', {
                'remediation_rules': {'on_failure': []},
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data


# ---------------------------------------------------------------------------
# TestUpdateBusinessRulePolicies
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateBusinessRulePolicies:
    """Tests for update_business_rule_policies method (lines 408-432)."""

    def test_update_business_rule_policies_none_clears(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        view = ActionViewSet.as_view({'put': 'update_business_rule_policies'})
        request = factory.put(f'/admin/actions/{action_obj.id}/business-rule-policies/', {}, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_update_business_rule_policies_valid(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        with patch('catalog.validators.validate_business_rule_policies', return_value=None):
            view = ActionViewSet.as_view({'put': 'update_business_rule_policies'})
            request = factory.put(f'/admin/actions/{action_obj.id}/business-rule-policies/', {
                'business_rule_policies': [{'rule': 'example'}],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200

    def test_update_business_rule_policies_validation_error(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)

        with patch('catalog.views.action_views.validate_business_rule_policies',
                   side_effect=ValueError('bad policy'), create=True), \
             patch('catalog.validators.validate_business_rule_policies',
                   side_effect=ValueError('bad policy')):
            view = ActionViewSet.as_view({'put': 'update_business_rule_policies'})
            request = factory.put(f'/admin/actions/{action_obj.id}/business-rule-policies/', {
                'business_rule_policies': [{'bad': 'data'}],
            }, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 400
        details = response.data.get('error', {}).get('details', response.data)
        assert 'business_rule_policies' in details


# ---------------------------------------------------------------------------
# TestDestroy
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDestroy:
    """Tests for destroy method (lines 434-448)."""

    def test_destroy_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.delete_action.return_value = True

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'delete': 'destroy'})
            request = factory.delete(f'/admin/actions/{action_obj.id}/')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 204

    def test_destroy_not_found(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='draft', created_by=user)
        mock_svc = MagicMock()
        mock_svc.delete_action.return_value = False

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'delete': 'destroy'})
            request = factory.delete(f'/admin/actions/{action_obj.id}/')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestDeactivate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeactivate:
    """Tests for deactivate method (lines 450-485)."""

    def test_deactivate_not_confirmed_with_affected_workflows(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        mock_svc = MagicMock()
        mock_svc.get_workflows_referencing_action.return_value = [{'id': 1, 'name': 'wf1'}]

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'deactivate'})
            request = factory.put(f'/admin/actions/{action_obj.id}/deactivate/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert response.data['status'] == 'requires_confirmation'
        assert 'affected_workflows' in response.data

    def test_deactivate_not_confirmed_no_workflows(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        deactivated_mock = MagicMock()
        deactivated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.get_workflows_referencing_action.return_value = []
        mock_svc.deactivate_action.return_value = {'action': deactivated_mock, 'deactivated_workflows': []}
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'deactivate'})
            request = factory.put(f'/admin/actions/{action_obj.id}/deactivate/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_deactivate_confirmed(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        deactivated_mock = MagicMock()
        deactivated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.deactivate_action.return_value = {'action': deactivated_mock, 'deactivated_workflows': []}
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'deactivate'})
            request = factory.put(
                f'/admin/actions/{action_obj.id}/deactivate/?confirmed=true',
                {'deletion_reason': 'No longer needed'},
                format='json'
            )
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data
        assert 'deactivated_workflows' in response.data

    def test_deactivate_result_none_raises_404(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)
        mock_svc = MagicMock()
        mock_svc.get_workflows_referencing_action.return_value = []
        mock_svc.deactivate_action.return_value = None

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'deactivate'})
            request = factory.put(f'/admin/actions/{action_obj.id}/deactivate/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestReactivate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReactivate:
    """Tests for reactivate method (lines 487-506)."""

    def test_reactivate_success(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='disabled', created_by=user)
        reactivated_mock = MagicMock()
        reactivated_mock.id = action_obj.id
        mock_svc = MagicMock()
        mock_svc.reactivate_action.return_value = reactivated_mock
        mock_svc.get_by_id.return_value = action_obj

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'reactivate'})
            request = factory.put(f'/admin/actions/{action_obj.id}/reactivate/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data

    def test_reactivate_none_raises_404(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='disabled', created_by=user)
        mock_svc = MagicMock()
        mock_svc.reactivate_action.return_value = None

        with patch.object(ActionViewSet, 'get_catalog_service', return_value=mock_svc):
            view = ActionViewSet.as_view({'put': 'reactivate'})
            request = factory.put(f'/admin/actions/{action_obj.id}/reactivate/', {}, format='json')
            force_authenticate(request, user=user)
            response = view(request, pk=action_obj.id)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestMutexRules
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMutexRules:
    """Tests for mutex_rules method (lines 508-573)."""

    def test_mutex_rules_get_list_empty(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)

        view = ActionViewSet.as_view({'get': 'mutex_rules'})
        request = factory.get(f'/admin/actions/{action_obj.id}/mutex/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 200
        assert 'data' in response.data
        assert response.data['data'] == []

    def test_mutex_rules_get_list_with_rules(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        ActionMutex.objects.create(action=action_a, incompatible_with=action_b, same_target=True)

        view = ActionViewSet.as_view({'get': 'mutex_rules'})
        request = factory.get(f'/admin/actions/{action_a.id}/mutex/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id)

        assert response.status_code == 200
        assert len(response.data['data']) == 1

    def test_mutex_rules_post_create_with_symmetric(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)

        view = ActionViewSet.as_view({'post': 'mutex_rules'})
        request = factory.post(f'/admin/actions/{action_a.id}/mutex/', {
            'incompatible_with_id': action_b.id,
            'same_target': True,
        }, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id)

        assert response.status_code == 201
        assert 'data' in response.data
        # Should have created symmetric rule too
        assert ActionMutex.objects.count() == 2

    def test_mutex_rules_post_symmetric_already_exists(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        # Pre-create the symmetric rule
        ActionMutex.objects.create(action=action_b, incompatible_with=action_a, same_target=True)

        view = ActionViewSet.as_view({'post': 'mutex_rules'})
        request = factory.post(f'/admin/actions/{action_a.id}/mutex/', {
            'incompatible_with_id': action_b.id,
            'same_target': True,
        }, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id)

        assert response.status_code == 201
        # Should NOT have created another symmetric rule (already exists)
        assert ActionMutex.objects.count() == 2

    def test_mutex_rules_post_invalid_data_returns_400(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)

        view = ActionViewSet.as_view({'post': 'mutex_rules'})
        request = factory.post(f'/admin/actions/{action_obj.id}/mutex/', {}, format='json')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id)

        assert response.status_code == 400

    def test_mutex_rules_get_includes_both_directions(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        action_c = ActionFactory(status='published', created_by=user)
        # A → B
        ActionMutex.objects.create(action=action_a, incompatible_with=action_b, same_target=True)
        # C → A
        ActionMutex.objects.create(action=action_c, incompatible_with=action_a, same_target=True)

        view = ActionViewSet.as_view({'get': 'mutex_rules'})
        request = factory.get(f'/admin/actions/{action_a.id}/mutex/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id)

        assert response.status_code == 200
        assert len(response.data['data']) == 2


# ---------------------------------------------------------------------------
# TestDeleteMutexRule
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeleteMutexRule:
    """Tests for delete_mutex_rule method (lines 575-631)."""

    def test_delete_mutex_rule_not_found_returns_404(self):
        user = _make_dbops_user()
        action_obj = ActionFactory(status='published', created_by=user)

        view = ActionViewSet.as_view({'delete': 'delete_mutex_rule'})
        request = factory.delete(f'/admin/actions/{action_obj.id}/mutex/999999/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_obj.id, rule_id='999999')

        assert response.status_code == 404

    def test_delete_mutex_rule_wrong_action_returns_404(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        action_c = ActionFactory(status='published', created_by=user)
        rule = ActionMutex.objects.create(action=action_b, incompatible_with=action_c, same_target=True)

        view = ActionViewSet.as_view({'delete': 'delete_mutex_rule'})
        request = factory.delete(f'/admin/actions/{action_a.id}/mutex/{rule.id}/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id, rule_id=str(rule.id))

        assert response.status_code == 404

    def test_delete_mutex_rule_success_deletes_symmetric(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        rule_ab = ActionMutex.objects.create(action=action_a, incompatible_with=action_b, same_target=True)
        _rule_ba = ActionMutex.objects.create(action=action_b, incompatible_with=action_a, same_target=True)

        assert ActionMutex.objects.count() == 2

        view = ActionViewSet.as_view({'delete': 'delete_mutex_rule'})
        request = factory.delete(f'/admin/actions/{action_a.id}/mutex/{rule_ab.id}/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id, rule_id=str(rule_ab.id))

        assert response.status_code == 204
        assert ActionMutex.objects.count() == 0

    def test_delete_mutex_rule_success_no_symmetric(self):
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        rule_ab = ActionMutex.objects.create(action=action_a, incompatible_with=action_b, same_target=True)

        assert ActionMutex.objects.count() == 1

        view = ActionViewSet.as_view({'delete': 'delete_mutex_rule'})
        request = factory.delete(f'/admin/actions/{action_a.id}/mutex/{rule_ab.id}/')
        force_authenticate(request, user=user)
        response = view(request, pk=action_a.id, rule_id=str(rule_ab.id))

        assert response.status_code == 204
        assert ActionMutex.objects.count() == 0

    def test_delete_mutex_rule_multiple_symmetric_rules(self):
        """When multiple symmetric rules exist, a warning is logged but all are deleted."""
        from catalog.models import ActionMutex
        user = _make_dbops_user()
        action_a = ActionFactory(status='published', created_by=user)
        action_b = ActionFactory(status='published', created_by=user)
        rule_ab = ActionMutex.objects.create(action=action_a, incompatible_with=action_b, same_target=True)
        _rule_ba = ActionMutex.objects.create(action=action_b, incompatible_with=action_a, same_target=True)

        # Simulate the "multiple symmetric" warning branch by patching the queryset count
        original_filter = ActionMutex.objects.filter

        def patched_filter(**kwargs):
            qs = original_filter(**kwargs)
            # If filtering for symmetric rules, mock count() > 1
            action_id_val = kwargs.get('action_id')
            incompatible_with_val = kwargs.get('incompatible_with')
            if action_id_val == action_b.id and incompatible_with_val == action_a:
                mock_qs = MagicMock(wraps=qs)
                mock_qs.count.return_value = 2
                mock_qs.exists.return_value = True
                mock_qs.delete.return_value = (2, {})
                return mock_qs
            return qs

        with patch.object(ActionMutex.objects.__class__, 'filter', side_effect=patched_filter):
            view = ActionViewSet.as_view({'delete': 'delete_mutex_rule'})
            request = factory.delete(f'/admin/actions/{action_a.id}/mutex/{rule_ab.id}/')
            force_authenticate(request, user=user)
            response = view(request, pk=action_a.id, rule_id=str(rule_ab.id))

        assert response.status_code == 204
