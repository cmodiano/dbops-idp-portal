"""
Tests for core IaC views (feature-flags export/sync).
Story 64.8 — API endpoints for IaC sync (export GET + sync POST).
"""

import pytest
import yaml
from rest_framework.test import APIClient

from idp_auth.models import User
from core.models import FeatureFlag


@pytest.mark.django_db
class TestFeatureFlagsExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ff', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_ff', profile='dba')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/feature-flags/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml_content_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/feature-flags/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/feature-flags/export/yaml/')
        assert 'feature-flags.yaml' in response['Content-Disposition']

    def test_export_contains_flag_data(self):
        FeatureFlag.objects.create(flag_key='test-flag', enabled=True, rollout_percent=100)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/feature-flags/export/yaml/')
        assert response.status_code == 200
        parsed = yaml.safe_load(response.content)
        assert parsed['kind'] == 'FeatureFlags'
        assert any(f['flag_key'] == 'test-flag' for f in parsed['spec'])

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/feature-flags/export/yaml/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestFeatureFlagsSyncView:
    VALID_YAML = """\
apiVersion: idp/v1
kind: FeatureFlags
metadata: {}
spec:
  - flag_key: sync-flag-test
    enabled: true
    rollout_percent: 50
    description: Test flag for sync
"""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ffs', profile='DBOPS')

    def test_sync_requires_admin(self):
        non_admin = User.objects.create(username='user_ffs', profile='dba')
        self.client.force_authenticate(user=non_admin)
        response = self.client.post('/api/v1/admin/feature-flags/sync/', data={})
        assert response.status_code == 403

    def test_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/feature-flags/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'

    def test_sync_invalid_mode_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/feature-flags/sync/?mode=invalid',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 400

    def test_sync_creates_flag_returns_201(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/feature-flags/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 201
        data = response.data['data']
        assert data['created'] == 1
        assert data['updated'] == 0
        assert data['mode'] == 'additive'
        assert FeatureFlag.objects.filter(flag_key='sync-flag-test').exists()

    def test_sync_existing_flag_returns_200(self):
        FeatureFlag.objects.create(flag_key='sync-flag-test', enabled=False)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/feature-flags/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['updated'] == 1

    def test_sync_mode_in_response(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/feature-flags/sync/?mode=full',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code in (200, 201)
        assert response.data['data']['mode'] == 'full'
