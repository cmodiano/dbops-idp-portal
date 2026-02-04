"""
Tests for catalog API endpoints (DRF ViewSets).
Tests: GET /catalog/actions, GET /catalog/actions/{id}, GET /catalog/actions/{id}/stats
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from catalog.models import Action, Tag, ActionTag, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from executions.models import Execution, ExecutionStatus


@pytest.mark.django_db
class TestCatalogActionViewSet(TestCase):
    """Tests for CatalogActionViewSet (catalog endpoints)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user (optional for catalog endpoints)
        self.user = User.objects.create(
            username='testuser',
            profile='dba',
            is_staff=False
        )
        
        # Create test actions
        self.service = CatalogService()
        
        # Published action
        self.published_action_data = {
            'name': 'Published Action',
            'description': 'Published Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.PUBLISHED,
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
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')
    
    def test_retrieve_catalog_action_not_found(self):
        """Test GET /catalog/actions/{id} returns 404 for non-existent action."""
        response = self.client.get('/api/v1/catalog/actions/99999/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')
    
    def test_get_action_stats_no_executions(self):
        """Test GET /catalog/actions/{id}/stats returns None when no executions."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.published_action.id}/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsNone(response.data['data'])
    
    def test_get_action_stats_with_executions(self):
        """Test GET /catalog/actions/{id}/stats returns stats when executions exist."""
        # Create test execution
        Execution.objects.create(
            action=self.published_action,
            user=self.user,
            status=ExecutionStatus.COMPLETED,
            environment='DEV'
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
