"""
Story 24.1: Tests for Integration Type Catalogue API endpoints.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status

from tests.factories import (
    UserFactory,
    IntegrationTypeCatalogueFactory,
    IntegrationActionFactory,
)


@pytest.mark.django_db
class TestIntegrationTypeCatalogueListEndpoint:
    """Tests for GET /api/v1/integrations/types/"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v1/integrations/types/'

    def test_list_returns_200(self):
        IntegrationTypeCatalogueFactory(code='aap')
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_response_structure(self):
        IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        response = self.client.get(self.url)
        assert 'data' in response.data
        assert len(response.data['data']) == 1
        assert response.data['data'][0]['code'] == 'aap'
        assert response.data['data'][0]['name'] == 'AAP'

    def test_list_includes_actions(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        response = self.client.get(self.url)
        assert len(response.data['data'][0]['actions']) == 1
        assert response.data['data'][0]['actions'][0]['action_code'] == 'start_job'

    def test_list_excludes_inactive_types(self):
        IntegrationTypeCatalogueFactory(code='active', is_active=True)
        IntegrationTypeCatalogueFactory(code='inactive', is_active=False)
        response = self.client.get(self.url)
        codes = [t['code'] for t in response.data['data']]
        assert 'active' in codes
        assert 'inactive' not in codes

    def test_list_empty_catalogue(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data'] == []

    def test_list_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_multiple_types_with_actions(self):
        t1 = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t1, action_code='start_job')
        IntegrationActionFactory(integration_type=t1, action_code='cancel_job')
        t2 = IntegrationTypeCatalogueFactory(code='sn')
        IntegrationActionFactory(integration_type=t2, action_code='create_change')
        response = self.client.get(self.url)
        assert len(response.data['data']) == 2


@pytest.mark.django_db
class TestIntegrationTypeCatalogueRetrieveEndpoint:
    """Tests for GET /api/v1/integrations/types/{code}/"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_returns_200(self):
        IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        response = self.client.get('/api/v1/integrations/types/aap/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['code'] == 'aap'

    def test_retrieve_includes_actions(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        response = self.client.get('/api/v1/integrations/types/aap/')
        assert len(response.data['data']['actions']) == 1

    def test_retrieve_not_found_returns_404(self):
        response = self.client.get('/api/v1/integrations/types/nonexistent/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_inactive_returns_404(self):
        IntegrationTypeCatalogueFactory(code='old', is_active=False)
        response = self.client.get('/api/v1/integrations/types/old/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_unauthenticated_returns_401(self):
        IntegrationTypeCatalogueFactory(code='aap')
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/integrations/types/aap/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestIntegrationTypeCatalogueActionsEndpoint:
    """Tests for GET /api/v1/integrations/types/{code}/actions/"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_actions_returns_200(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        response = self.client.get('/api/v1/integrations/types/aap/actions/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 1

    def test_actions_excludes_inactive(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='active', is_active=True)
        IntegrationActionFactory(integration_type=t, action_code='inactive', is_active=False)
        response = self.client.get('/api/v1/integrations/types/aap/actions/')
        codes = [a['action_code'] for a in response.data['data']]
        assert 'active' in codes
        assert 'inactive' not in codes

    def test_actions_not_found_type_returns_404(self):
        response = self.client.get('/api/v1/integrations/types/nonexistent/actions/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_actions_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/integrations/types/aap/actions/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_actions_response_structure(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(
            integration_type=t,
            action_code='start_job',
            action_label='Démarrer un job',
        )
        response = self.client.get('/api/v1/integrations/types/aap/actions/')
        action_data = response.data['data'][0]
        assert action_data['action_code'] == 'start_job'
        assert action_data['action_label'] == 'Démarrer un job'
        assert 'required_params' in action_data
        assert 'optional_params' in action_data
        assert 'response_format' in action_data
