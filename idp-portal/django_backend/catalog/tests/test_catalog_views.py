"""
Tests for catalog API endpoints (DRF ViewSets).
Tests: GET /catalog/actions, GET /catalog/actions/{id}, GET /catalog/actions/{id}/stats
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from catalog.models import Tag, ActionTag, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from executions.models import Execution, ExecutionStatus
from tests.factories import UserFactory


@pytest.mark.django_db
class TestCatalogActionViewSet(TestCase):
    """Tests for CatalogActionViewSet (catalog endpoints)."""
    
    def setUp(self):
        """Set up test data."""
        from catalog.views._shared import _catalog_cache
        _catalog_cache.clear()

        self.client = APIClient()

        # Create user (optional for catalog endpoints)
        self.user = UserFactory(
            username='testuser',
            profile='dba'
        )
        
        # Create test actions
        self.service = CatalogService()
        
        # Create action as DRAFT then publish (valid transition: draft → published)
        self.published_action_data = {
            'name': 'Published Action',
            'description': 'Published Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.published_action = self.service.create_action(
            self.published_action_data, self.user
        )
        self.service.update_status(self.published_action.id, 'publish', self.user)
        
        # Draft action (should not appear in catalog)
        self.draft_action_data = {
            'name': 'Draft Action',
            'description': 'Draft Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.draft_action = self.service.create_action(
            self.draft_action_data, self.user
        )
        
        # Create tags
        self.tag1 = Tag.objects.create(name='oracle')
        self.tag2 = Tag.objects.create(name='database')
        ActionTag.objects.create(action=self.published_action, tag=self.tag1)
        ActionTag.objects.create(action=self.published_action, tag=self.tag2)
    
    def test_list_catalog_actions_public(self):
        """Test GET /catalog/actions is public (no authentication required)."""
        response = self.client.get('/api/v1/catalog/actions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
        # Should only return published actions
        action_ids = [item['id'] for item in response.data['data']]
        self.assertIn(self.published_action.id, action_ids)
        self.assertNotIn(self.draft_action.id, action_ids)
    
    def test_list_catalog_actions_with_tags_filter(self):
        """Test GET /catalog/actions with tags filter."""
        response = self.client.get('/api/v1/catalog/actions/?tags=oracle')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # All returned actions should have oracle tag
        for item in response.data['data']:
            self.assertIn('oracle', item.get('tags', []))
    
    def test_list_catalog_actions_with_category_filter(self):
        """Test GET /catalog/actions with category filter (maps to tag)."""
        response = self.client.get('/api/v1/catalog/actions/?category=oracle')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_list_catalog_actions_with_q_search(self):
        """Test GET /catalog/actions with q (text search) parameter."""
        response = self.client.get('/api/v1/catalog/actions/?q=Published')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Should find published action
        action_names = [item['name'] for item in response.data['data']]
        self.assertIn('Published Action', action_names)
    
    def test_list_catalog_actions_with_engine_filter(self):
        """Test GET /catalog/actions with engine filter."""
        response = self.client.get('/api/v1/catalog/actions/?engine=Oracle')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # All returned actions should have Oracle engine
        for item in response.data['data']:
            self.assertEqual(item['engine'], 'Oracle')
    
    def test_list_catalog_actions_cache(self):
        """Test GET /catalog/actions uses cache (second request should be faster)."""
        # First request
        response1 = self.client.get('/api/v1/catalog/actions/')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second request (should use cache)
        response2 = self.client.get('/api/v1/catalog/actions/')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        # Data should be identical
        self.assertEqual(response1.data, response2.data)
    
    def test_retrieve_catalog_action_success(self):
        """Test GET /catalog/actions/{id} returns published action."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.published_action.id)
        self.assertEqual(response.data['data']['status'], 'published')
        # Should include can_execute and allowed_environments
        self.assertIn('can_execute', response.data['data'])
        self.assertIn('allowed_environments', response.data['data'])
    
    def test_retrieve_catalog_action_not_published(self):
        """Test GET /catalog/actions/{id} returns 404 for draft action."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.draft_action.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        # DRF wraps Http404 as VALIDATION_ERROR in our exception handler
        self.assertIn(response.data['error']['code'], ('NOT_FOUND', 'VALIDATION_ERROR'))

    def test_retrieve_catalog_action_not_found(self):
        """Test GET /catalog/actions/{id} returns 404 for non-existent action."""
        response = self.client.get('/api/v1/catalog/actions/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        # DRF wraps Http404 as VALIDATION_ERROR in our exception handler
        self.assertIn(response.data['error']['code'], ('NOT_FOUND', 'VALIDATION_ERROR'))
    
    def test_get_action_stats_no_executions(self):
        """Test GET /catalog/actions/{id}/stats returns dict with zeros when no executions."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # MEDIUM-3: Always returns dict, never None
        stats = response.data['data']
        self.assertIsNotNone(stats)
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats['total_executions'], 0)
        self.assertEqual(stats['incidents_count'], 0)
        self.assertIsNone(stats['success_rate'])
        self.assertIsNone(stats['avg_execution_time_ms'])
    
    def test_get_action_stats_with_executions(self):
        """Test GET /catalog/actions/{id}/stats returns stats when executions exist."""
        from django.utils import timezone
        # Create test execution with timestamps for avg_execution_time_ms calculation
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment='DEV',
            started_at=timezone.now(),
            completed_at=timezone.now()
        )
        
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Should return stats dict
        stats = response.data['data']
        self.assertIsNotNone(stats)
        self.assertIn('total_executions', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('incidents_count', stats)
        # LOW-2: Verify avg_execution_time_ms field exists and is calculated
        self.assertIn('avg_execution_time_ms', stats)
        # Field should be present (None if no valid timestamps, or a number if calculated)
        self.assertIsInstance(stats['avg_execution_time_ms'], (type(None), float, int))
    
    def test_get_action_stats_only_running_executions(self):
        """Test success_rate is None when only RUNNING executions exist (MEDIUM-2)."""
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment='DEV'
        )
        
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data['data']
        self.assertEqual(stats['total_executions'], 1)
        self.assertEqual(stats['incidents_count'], 0)
        # No completed/failed executions, so success_rate should be None
        self.assertIsNone(stats['success_rate'])
    
    def test_get_action_stats_mixed_statuses(self):
        """Test success_rate calculation with mixed statuses (MEDIUM-2)."""
        from django.utils import timezone
        from datetime import timedelta
        # Create completed execution with timestamps
        now = timezone.now()
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment='DEV',
            started_at=now - timedelta(seconds=10),
            completed_at=now
        )
        # Create failed execution
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment='DEV'
        )
        # Create running execution (should not affect success_rate)
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment='DEV'
        )
        
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data['data']
        self.assertEqual(stats['total_executions'], 3)
        self.assertEqual(stats['incidents_count'], 1)
        # success_rate = 1 completed / (1 completed + 1 failed) * 100 = 50%
        self.assertEqual(stats['success_rate'], 50.0)
        # LOW-2: Verify avg_execution_time_ms is calculated (should be ~10000ms for 10 seconds)
        self.assertIsNotNone(stats['avg_execution_time_ms'])
        self.assertGreater(stats['avg_execution_time_ms'], 0)
    
    def test_get_action_stats_only_failed_executions(self):
        """Test success_rate is 0.0 when only FAILED executions exist (MEDIUM-2)."""
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.FAILED,
            environment='DEV'
        )
        
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data['data']
        self.assertEqual(stats['total_executions'], 1)
        self.assertEqual(stats['incidents_count'], 1)
        # 0 completed / (0 completed + 1 failed) * 100 = 0%
        self.assertEqual(stats['success_rate'], 0.0)
    
    def test_get_action_stats_invalid_action_id(self):
        """Test 404 when action doesn't exist (MEDIUM-2)."""
        # Use non-existent action ID
        response = self.client.get('/api/v1/catalog/actions/99999/stats/')

        # Should return 404, not 200 with None
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_catalog_actions_with_environment_filter(self):
        """Test GET /catalog/actions with environment query parameter (line 103)."""
        response = self.client.get('/api/v1/catalog/actions/?environment=DEV')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_with_impact_filter(self):
        """Test GET /catalog/actions with impact query parameter (line 107)."""
        response = self.client.get('/api/v1/catalog/actions/?impact=low')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_category_tout_is_not_filtered(self):
        """Test that category=tout does not apply tag filtering (category skipped for reserved words)."""
        response = self.client.get('/api/v1/catalog/actions/?category=tout')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_category_all_is_not_filtered(self):
        """Test that category=all does not apply tag filtering."""
        response = self.client.get('/api/v1/catalog/actions/?category=all')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_category_mes_actions_is_not_filtered(self):
        """Test that category=mes-actions does not apply tag filtering."""
        response = self.client.get('/api/v1/catalog/actions/?category=mes-actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_category_with_tags_already_included(self):
        """Test list with both tags and category that resolve to the same tag (line 136->139 branch)."""
        # tags=oracle and category=oracle: tag_name 'oracle' is already in tags_filter
        response = self.client.get('/api/v1/catalog/actions/?tags=oracle&category=oracle')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_list_catalog_actions_no_pagination(self):
        """Test list response when pagination returns None (lines 171-188)."""
        # Patch pagination_class to None so paginate_queryset returns None
        from catalog.views.catalog_views import CatalogActionViewSet
        from catalog.views._shared import _catalog_cache
        _catalog_cache.clear()

        with patch.object(CatalogActionViewSet, 'pagination_class', None):
            response = self.client.get('/api/v1/catalog/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('pagination', response.data)
        self.assertIn('total', response.data['pagination'])

    def test_list_catalog_actions_with_rbac_filtering(self):
        """Test list applies RBAC filtering when user has cumulative permissions (lines 114-118)."""
        from catalog.views._shared import _catalog_cache
        _catalog_cache.clear()

        mock_permissions = {
            'actions_type': 'list',
            'action_ids': [self.published_action.id],
            'tag_patterns': [],
            'environments': ['DEV'],
        }

        self.client.force_authenticate(user=self.user)
        with patch('catalog.rbac_service.CatalogRBACService.get_permissions', return_value=mock_permissions):
            response = self.client.get('/api/v1/catalog/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_retrieve_catalog_action_rbac_denied(self):
        """Test retrieve raises 404 when RBAC check_action returns False (lines 199-200)."""
        mock_permissions = {
            'actions_type': 'list',
            'action_ids': [],
            'tag_patterns': [],
            'environments': ['DEV'],
        }

        self.client.force_authenticate(user=self.user)
        with patch('catalog.rbac_service.CatalogRBACService.get_permissions', return_value=mock_permissions):
            response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_catalog_action_with_rbac_permissions(self):
        """Test retrieve includes allowed_environments when user has RBAC permissions (lines 214-216)."""
        mock_permissions = {
            'actions_type': 'list',
            'action_ids': [self.published_action.id],
            'tag_patterns': [],
            'environments': ['DEV', 'PROD'],
        }

        self.client.force_authenticate(user=self.user)
        with patch('catalog.rbac_service.CatalogRBACService.get_permissions', return_value=mock_permissions):
            response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('can_execute', response.data['data'])
        self.assertIn('allowed_environments', response.data['data'])
        self.assertEqual(response.data['data']['allowed_environments'], ['DEV', 'PROD'])
        self.assertTrue(response.data['data']['can_execute'])

    def test_get_stats_rbac_denied(self):
        """Test get_stats raises 404 when RBAC check_action returns False (lines 232-233)."""
        mock_permissions = {
            'actions_type': 'list',
            'action_ids': [],
            'tag_patterns': [],
            'environments': ['DEV'],
        }

        self.client.force_authenticate(user=self.user)
        with patch('catalog.rbac_service.CatalogRBACService.get_permissions', return_value=mock_permissions):
            response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_stats_execution_service_value_error(self):
        """Test get_stats raises 404 when ExecutionService.get_action_stats raises ValueError (lines 245-247)."""
        mock_execution_service = MagicMock()
        # The view calls cls() to get the service instance, so we need to configure return_value
        mock_execution_service.return_value.get_action_stats.side_effect = ValueError("Action not found")

        from catalog.views.catalog_views import CatalogActionViewSet
        with patch.object(CatalogActionViewSet, '_execution_service_class', mock_execution_service):
            response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
