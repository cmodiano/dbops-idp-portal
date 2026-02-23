"""
Tests for admin API endpoints (DRF ViewSets).
Tests: POST /admin/actions, GET /admin/actions, GET /admin/actions/{id}, PUT /admin/actions/{id}, etc.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from catalog.models import Tag, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from tests.factories import UserFactory


@pytest.mark.django_db
class TestAdminActionViewSet(TestCase):
    """Tests for ActionViewSet (admin endpoints)."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create reference data (required for serializer validation)
        RefEngine.objects.get_or_create(code='Oracle', defaults={'label': 'Oracle', 'display_order': 1})
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        # Create DBOPS user
        self.dbops_user = UserFactory(
            username='dbops_user',
            profile='dbops'
        )

        # Create non-DBOPS user
        self.regular_user = UserFactory(
            username='regular_user',
            profile='dba'
        )

        # Create test action
        self.service = CatalogService()
        self.action_data = {
            'name': 'Test Action',
            'description': 'Test Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.action = self.service.create_action(self.action_data, self.dbops_user)

        # Create tags
        self.tag1 = Tag.objects.create(name='oracle')
        self.tag2 = Tag.objects.create(name='database')

    def test_create_action_requires_authentication(self):
        """Test POST /admin/actions requires authentication."""
        response = self.client.post('/api/v1/admin/actions/', self.action_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_action_requires_dbops_profile(self):
        """Test POST /admin/actions requires DBOPS profile."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/api/v1/admin/actions/', self.action_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_action_success(self):
        """Test POST /admin/actions creates action successfully."""
        self.client.force_authenticate(user=self.dbops_user)
        new_action_data = {
            'name': 'New Action',
            'description': 'New Description',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action',
        }
        response = self.client.post('/api/v1/admin/actions/', new_action_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['name'], 'New Action')
        self.assertEqual(response.data['data']['engine'], 'Oracle')

    def test_list_actions_requires_authentication(self):
        """Test GET /admin/actions requires authentication."""
        response = self.client.get('/api/v1/admin/actions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_actions_success(self):
        """Test GET /admin/actions returns list with pagination."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('pagination', response.data)
        self.assertIsInstance(response.data['data'], list)
        self.assertEqual(response.data['pagination']['page'], 1)
        self.assertEqual(response.data['pagination']['page_size'], 25)

    def test_list_actions_with_filters(self):
        """Test GET /admin/actions with filters (status, engine, item_type)."""
        self.client.force_authenticate(user=self.dbops_user)

        # Filter by status
        response = self.client.get('/api/v1/admin/actions/?status=draft')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item['status'] == 'draft' for item in response.data['data']))

        # Filter by engine
        response = self.client.get('/api/v1/admin/actions/?engine=Oracle')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item['engine'] == 'Oracle' for item in response.data['data']))

    def test_retrieve_action_success(self):
        """Test GET /admin/actions/{id} returns action details."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get(f'/api/v1/admin/actions/{self.action.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.action.id)
        self.assertEqual(response.data['data']['name'], 'Test Action')

    def test_retrieve_action_not_found(self):
        """Test GET /admin/actions/{id} returns 404 for non-existent action."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        # DRF wraps Http404 as VALIDATION_ERROR in our exception handler
        self.assertIn(response.data['error']['code'], ('NOT_FOUND', 'VALIDATION_ERROR'))

    def test_update_action_success(self):
        """Test PUT /admin/actions/{id} updates action metadata."""
        self.client.force_authenticate(user=self.dbops_user)
        update_data = {
            'name': 'Updated Action',
            'description': 'Updated Description',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action',
        }
        response = self.client.put(f'/api/v1/admin/actions/{self.action.id}/', update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['name'], 'Updated Action')
        self.assertEqual(response.data['data']['description'], 'Updated Description')

    def test_update_tags_success(self):
        """Test PUT /admin/actions/{id}/tags updates action tags."""
        self.client.force_authenticate(user=self.dbops_user)
        tag_data = {
            'tag_names': ['oracle', 'database']
        }
        response = self.client.put(f'/api/v1/admin/actions/{self.action.id}/tags/', tag_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        tags = response.data['data']['tags']
        self.assertIn('oracle', tags)
        self.assertIn('database', tags)

    def test_update_status_success(self):
        """Test PATCH /admin/actions/{id}/status updates action status."""
        self.client.force_authenticate(user=self.dbops_user)
        status_data = {
            'transition': 'publish'
        }
        response = self.client.patch(f'/api/v1/admin/actions/{self.action.id}/status/', status_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['status'], 'published')

    def test_update_status_invalid_transition(self):
        """Test PATCH /admin/actions/{id}/status returns 400 for invalid transition."""
        self.client.force_authenticate(user=self.dbops_user)
        # Action is draft, can't disable (only published can be disabled)
        status_data = {
            'transition': 'disable'
        }
        response = self.client.patch(f'/api/v1/admin/actions/{self.action.id}/status/', status_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'INVALID_STATE')

    def test_list_eligible_for_workflow(self):
        """Test GET /admin/actions/eligible-for-workflow returns published actions only."""
        # Publish the action
        self.service.update_status(self.action.id, 'publish', self.dbops_user)

        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/actions/eligible-for-workflow/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
        # All returned actions should be published and item_type=action
        for item in response.data['data']:
            self.assertEqual(item['status'], 'published')
            self.assertEqual(item['item_type'], 'action')

    def test_update_remediation_rules_success(self):
        """Test PUT /admin/actions/{id}/remediation-rules updates remediation rules."""
        self.client.force_authenticate(user=self.dbops_user)
        remediation_data = {
            'remediation_rules': {
                'auto_retry': True,
                'max_retries': 3,
                'retry_delay_seconds': 60
            }
        }
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/remediation-rules/',
            remediation_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsNotNone(response.data['data']['remediation_rules'])

    def test_update_remediation_rules_requires_draft_status(self):
        """Test PUT /admin/actions/{id}/remediation-rules requires draft status."""
        # Publish the action first
        self.service.update_status(self.action.id, 'publish', self.dbops_user)

        self.client.force_authenticate(user=self.dbops_user)
        remediation_data = {
            'remediation_rules': {'auto_retry': True}
        }
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/remediation-rules/',
            remediation_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'INVALID_STATE')

    def test_update_remediation_rules_missing_field(self):
        """Test PUT /admin/actions/{id}/remediation-rules returns 400 if field missing."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.put(
            f'/api/v1/admin/actions/{self.action.id}/remediation-rules/',
            {},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
