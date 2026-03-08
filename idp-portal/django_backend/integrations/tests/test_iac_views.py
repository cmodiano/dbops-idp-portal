"""
Tests for integrations IaC views (integrations, integration-types export/sync).
Story 64.8 — API endpoints for IaC sync (export GET + sync POST).
"""

import pytest
from rest_framework.test import APIClient

from idp_auth.models import User


@pytest.mark.django_db
class TestIntegrationExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ie', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_ie', profile='dba')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/integrations/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml_content_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/integrations/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/integrations/export/yaml/')
        assert 'integrations.yaml' in response['Content-Disposition']

    def test_export_empty_db_returns_empty_bytes(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/integrations/export/yaml/')
        assert response.status_code == 200
        assert response.content == b''

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/integrations/export/yaml/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestIntegrationSyncView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_is', profile='DBOPS')

    def test_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/integrations/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'

    def test_sync_invalid_mode_returns_400(self):
        YAML = 'apiVersion: idp/v1\nkind: Integration\nmetadata:\n  name: test\nspec:\n  integration_type: aap\n'
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/integrations/sync/?mode=invalid',
            data=YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 400

    def test_sync_requires_admin(self):
        non_admin = User.objects.create(username='user_is', profile='dba')
        self.client.force_authenticate(user=non_admin)
        response = self.client.post('/api/v1/admin/integrations/sync/', data={})
        assert response.status_code == 403


@pytest.mark.django_db
class TestIntegrationTypesSyncView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_it', profile='DBOPS')

    def test_export_integration_types_returns_yaml(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/integration-types/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']
        assert 'integration-types.yaml' in response['Content-Disposition']

    def test_sync_integration_types_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/integration-types/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'
