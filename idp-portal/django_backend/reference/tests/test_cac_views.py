"""
Tests for reference CaC views (engines, categories export/sync).
Story 64.8 — API endpoints for CaC sync (export GET + sync POST).
"""

import pytest
from rest_framework.test import APIClient

from idp_auth.models import User


@pytest.mark.django_db
class TestRefEnginesExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_re', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_re', profile='dba')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/reference/engines/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml_content_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/reference/engines/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/reference/engines/export/yaml/')
        assert 'reference-engines.yaml' in response['Content-Disposition']

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/reference/engines/export/yaml/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestRefEnginesSyncView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_res', profile='DBOPS')

    def test_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/reference/engines/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'

    def test_sync_invalid_mode_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/reference/engines/sync/?mode=bad',
            data='apiVersion: idp/v1\n',
            content_type='application/x-yaml',
        )
        assert response.status_code == 400

    def test_sync_requires_admin(self):
        non_admin = User.objects.create(username='user_res', profile='dba')
        self.client.force_authenticate(user=non_admin)
        response = self.client.post('/api/v1/admin/reference/engines/sync/', data={})
        assert response.status_code == 403


@pytest.mark.django_db
class TestRefCategoriesSyncView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_rcs', profile='DBOPS')

    def test_export_categories_returns_yaml(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/reference/categories/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']
        assert 'reference-categories.yaml' in response['Content-Disposition']

    def test_sync_categories_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/reference/categories/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'
