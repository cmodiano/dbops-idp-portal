"""
Integration tests for pagination contract (Story 22.6).

Validates that all paginated API endpoints return consistent pagination fields:
- page (int)
- page_size (int)
- total (int) — NOT total_count
- total_pages (int)
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from catalog.models import Action, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from profiles.models import Profile
from tests.factories import UserFactory

EXPECTED_PAGINATION_KEYS = {'page', 'page_size', 'total', 'total_pages'}


@pytest.mark.django_db
@pytest.mark.integration
class TestPaginationContract(TestCase):
    """Verify all paginated endpoints use 'total' (not 'total_count')."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='paginationtest', profile='dbops')
        self.client.force_authenticate(user=self.user)

        # Create a published action for catalog endpoint
        service = CatalogService()
        action_data = {
            'name': 'Pagination Test Action',
            'description': 'For pagination contract test',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.action = service.create_action(action_data, self.user)
        service.update_status(self.action.id, 'publish', self.user)

    def _assert_pagination_fields(self, pagination, endpoint_name):
        """Assert pagination dict has exactly the expected keys."""
        self.assertIsInstance(pagination, dict, f"{endpoint_name}: pagination should be a dict")
        self.assertEqual(
            set(pagination.keys()),
            EXPECTED_PAGINATION_KEYS,
            f"{endpoint_name}: pagination keys mismatch. "
            f"Got {set(pagination.keys())}, expected {EXPECTED_PAGINATION_KEYS}"
        )
        # Verify types
        self.assertIsInstance(pagination['page'], int, f"{endpoint_name}: page should be int")
        self.assertIsInstance(pagination['page_size'], int, f"{endpoint_name}: page_size should be int")
        self.assertIsInstance(pagination['total'], int, f"{endpoint_name}: total should be int")
        self.assertIsInstance(pagination['total_pages'], int, f"{endpoint_name}: total_pages should be int")
        # Verify 'total_count' is absent
        self.assertNotIn('total_count', pagination, f"{endpoint_name}: 'total_count' must NOT be present")

    def test_catalog_service_pagination_contract(self):
        """CatalogService.list_all() returns pagination_info with 'total'."""
        service = CatalogService()
        results, pagination_info = service.list_all(page=1, page_size=10)
        self._assert_pagination_fields(pagination_info, 'CatalogService.list_all()')
        self.assertGreaterEqual(pagination_info['total'], 1)

    def test_executions_pagination_contract(self):
        """GET /api/v1/executions/ returns pagination with 'total'."""
        response = self.client.get('/api/v1/executions/?limit=10&offset=0&scope=all')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('pagination', response.data)
        self._assert_pagination_fields(response.data['pagination'], '/executions/')

    def test_audit_pagination_contract(self):
        """GET /api/v1/audit/executions/ returns pagination with 'total'."""
        Profile.objects.create(
            name='auditor_profile',
            ad_group='auditor_profile',
            is_auditor=1,
        )
        auditor = UserFactory(username='auditor_user', profile='auditor_profile')
        self.client.force_authenticate(user=auditor)
        response = self.client.get('/api/v1/audit/executions/?limit=10&offset=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('pagination', response.data)
        self._assert_pagination_fields(response.data['pagination'], '/audit/executions/')

    def test_pagination_total_matches_data_count(self):
        """Verify total >= len(data) for executions endpoint."""
        response = self.client.get('/api/v1/executions/?limit=100&offset=0&scope=all')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pagination = response.data['pagination']
        data = response.data['data']
        self.assertGreaterEqual(pagination['total'], len(data))

    def test_inventory_targets_pagination_contract(self):
        """GET /api/v1/inventory/targets/ returns 'total' (not 'total_count')."""
        response = self.client.get('/api/v1/inventory/targets/?page=1&page_size=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inventory uses flat structure, not nested pagination
        self.assertIn('total', response.data)
        self.assertNotIn('total_count', response.data)
        self.assertIsInstance(response.data['total'], int)
