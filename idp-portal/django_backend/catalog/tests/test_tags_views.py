"""
Tests for tags API endpoints (DRF ViewSets).
Tests: GET /tags, GET /catalog/tags
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from catalog.models import Action, Tag, ActionTag, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService


@pytest.mark.django_db
class TestTagViewSet(TestCase):
    """Tests for TagViewSet (tags endpoints)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create(
            username='testuser',
            profile='dba'
        )
        
        # Create tags
        self.tag1 = Tag.objects.create(name='oracle')
        self.tag2 = Tag.objects.create(name='database')
        self.tag3 = Tag.objects.create(name='patching')
        
        # Create published action with tags
        self.service = CatalogService()
        self.action_data = {
            'name': 'Test Action',
            'description': 'Test Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.PUBLISHED,
            'item_type': ActionItemType.ACTION,
        }
        self.action = self.service.create_action(self.action_data, self.user)
        self.service.update_status(self.action.id, 'publish', self.user)
        
        # Add tags to action
        ActionTag.objects.create(action=self.action, tag=self.tag1)
        ActionTag.objects.create(action=self.action, tag=self.tag2)
    
    def test_list_tags_public(self):
        """Test GET /tags is public (no authentication required)."""
        response = self.client.get('/api/v1/tags/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
        # Should return all tags
        tag_names = [tag['name'] for tag in response.data['data']]
        self.assertIn('oracle', tag_names)
        self.assertIn('database', tag_names)
        self.assertIn('patching', tag_names)
    
    def test_list_tags_format(self):
        """Test GET /tags returns correct format."""
        response = self.client.get('/api/v1/tags/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Each tag should have id, name, created_at
        for tag in response.data['data']:
            self.assertIn('id', tag)
            self.assertIn('name', tag)
            self.assertIn('created_at', tag)
    
    def test_list_catalog_tags_public(self):
        """Test GET /catalog/tags is public (no authentication required)."""
        response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_list_catalog_tags_format(self):
        """Test GET /catalog/tags returns correct format."""
        response = self.client.get('/api/v1/catalog/tags/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Each tag should have name and action_count (when implemented)
        for tag in response.data['data']:
            self.assertIn('name', tag)
            # TODO: action_count will be added when implementation is complete
