"""
Story 30.6: Integration tests verifying consistent API response format.
APIFMT-1 to APIFMT-4 — All endpoints must use {"data": ...} wrapper.

Tests verify:
- validate and validate-all endpoints return {"data": {...}}
- reference/engines, reference/platforms, reference/categories return {"data": [...]}
- catalog list returns {"data": [...], "pagination": {...}}
- No compensatory branches needed in frontend (apiFetch extracts .data)
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from reference.models import RefEngine, RefCategory
from integrations.models import Integration, IntegrationTypeCatalogue, IntegrationRole


@pytest.mark.django_db
class TestAPIResponseFormatConsistency(TestCase):
    """Verify {"data": ...} wrapper on all modified endpoints (Story 30.6)."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = User.objects.create(username='dbops_fmt', profile='dbops')
        self.client.force_authenticate(user=self.dbops_user)

        # Reference data
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=10, is_active=1)
        self.integration = Integration.objects.create(
            type='aap', name='Test AAP', base_url='https://aap.example.com',
        )

    # --- APIFMT-1: validateIntegration ---

    def test_validate_integration_returns_data_wrapper(self):
        """APIFMT-1: GET /admin/integrations/{id}/validate/ returns {"data": {...}}."""
        response = self.client.get(
            f'/api/v1/admin/integrations/{self.integration.id}/validate/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        data = response.data['data']
        assert isinstance(data, dict)
        assert 'integration_id' in data
        assert 'current_status' in data
        assert 'validation_details' in data

    # --- APIFMT-2: validateAllIntegrations ---

    def test_validate_all_returns_data_wrapper(self):
        """APIFMT-2: POST /admin/integrations/validate-all/ returns {"data": {...}}."""
        response = self.client.post('/api/v1/admin/integrations/validate-all/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        data = response.data['data']
        assert isinstance(data, dict)
        assert 'valid' in data
        assert 'invalid' in data

    # --- APIFMT-3: reference endpoints ---

    def test_list_engines_returns_data_wrapper(self):
        """APIFMT-3: GET /reference/engines/ returns {"data": [...]}."""
        response = self.client.get('/api/v1/reference/engines/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert isinstance(response.data['data'], list)
        assert len(response.data['data']) == 1

    def test_list_platforms_returns_data_wrapper(self):
        """APIFMT-3: GET /reference/platforms/ returns {"data": [...]}."""
        response = self.client.get('/api/v1/reference/platforms/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert isinstance(response.data['data'], list)
        assert len(response.data['data']) == 1

    def test_list_categories_returns_data_wrapper(self):
        """APIFMT-3: GET /reference/categories/ returns {"data": [...]}."""
        response = self.client.get('/api/v1/reference/categories/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert isinstance(response.data['data'], list)
        assert len(response.data['data']) == 1

    def test_create_category_returns_data_wrapper(self):
        """APIFMT-3: POST /admin/categories/ returns {"data": {...}}."""
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'backup', 'label': 'Sauvegarde', 'display_order': 50, 'is_active': 1,
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'data' in response.data
        assert response.data['data']['code'] == 'backup'

    def test_update_category_returns_data_wrapper(self):
        """APIFMT-3: PATCH /admin/categories/{id}/ returns {"data": {...}}."""
        cat = RefCategory.objects.get(code='patching')
        response = self.client.patch(f'/api/v1/admin/categories/{cat.id}/', {
            'label': 'Patchs',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert response.data['data']['label'] == 'Patchs'

    # --- APIFMT-4: catalog list pagination ---

    def test_catalog_list_includes_pagination(self):
        """APIFMT-4: GET /catalog/actions/ returns {"data": [...], "pagination": {...}}."""
        response = self.client.get('/api/v1/catalog/actions/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert 'pagination' in response.data
        pagination = response.data['pagination']
        assert 'page' in pagination
        assert 'page_size' in pagination
        assert 'total' in pagination
        assert 'total_pages' in pagination

    def test_catalog_list_cache_hit_preserves_format(self):
        """APIFMT-4: Cache hit returns same format as fresh response."""
        # First call - cache miss
        response1 = self.client.get('/api/v1/catalog/actions/')
        assert response1.status_code == status.HTTP_200_OK
        assert 'data' in response1.data
        assert 'pagination' in response1.data

        # Second identical call - cache hit
        response2 = self.client.get('/api/v1/catalog/actions/')
        assert response2.status_code == status.HTTP_200_OK
        assert 'data' in response2.data
        assert 'pagination' in response2.data

        # Format must be identical
        assert response1.data.keys() == response2.data.keys()
        assert 'page' in response2.data['pagination']
        assert 'total' in response2.data['pagination']

    # --- AC#4: No compensatory branches needed ---

    def test_all_endpoints_use_consistent_data_key(self):
        """AC#4: All modified endpoints return 'data' key — frontend apiFetch works uniformly."""
        endpoints = [
            ('GET', '/api/v1/reference/engines/'),
            ('GET', '/api/v1/reference/platforms/'),
            ('GET', '/api/v1/reference/categories/'),
            ('GET', f'/api/v1/admin/integrations/{self.integration.id}/validate/'),
            ('POST', '/api/v1/admin/integrations/validate-all/'),
            ('GET', '/api/v1/catalog/actions/'),
        ]

        for method, url in endpoints:
            if method == 'GET':
                response = self.client.get(url)
            else:
                response = self.client.post(url)

            assert response.status_code == status.HTTP_200_OK, (
                f"{method} {url} returned {response.status_code}"
            )
            assert 'data' in response.data, (
                f"{method} {url} missing 'data' key in response"
            )
