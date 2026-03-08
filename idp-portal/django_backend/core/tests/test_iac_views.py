"""
Tests for core IaC views (feature-flags export/sync, config-sync status).
Story 64.8 — API endpoints for IaC sync (export GET + sync POST).
Story 64.14 — Config sync dashboard endpoint.
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


@pytest.mark.django_db
class TestGetConfigSyncStatus:
    EXPECTED_ENTITY_TYPES = {
        'actions', 'integrations', 'profiles', 'policies',
        'engines', 'categories', 'integration-types', 'feature-flags',
    }

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_css', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_css', profile='dba')

    def test_returns_200_with_correct_structure(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 200
        data = response.json()['data']
        assert 'global' in data
        assert 'entity_types' in data
        assert len(data['entity_types']) == 8
        entity_types_set = {e['entity_type'] for e in data['entity_types']}
        assert entity_types_set == self.EXPECTED_ENTITY_TYPES

    def test_global_fields_present(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 200
        global_data = response.json()['data']['global']
        for field in ('total', 'synced', 'diverged', 'never_synced', 'last_sync_date'):
            assert field in global_data

    def test_entity_type_fields_present(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 200
        for entity in response.json()['data']['entity_types']:
            for field in ('entity_type', 'total', 'synced', 'diverged', 'never_synced', 'last_sync_date'):
                assert field in entity

    def test_feature_flag_counted_as_never_synced(self):
        FeatureFlag.objects.create(flag_key='test-sync-status', enabled=True, last_synced_at=None)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 200
        ff_data = next(
            e for e in response.json()['data']['entity_types']
            if e['entity_type'] == 'feature-flags'
        )
        assert ff_data['never_synced'] >= 1
        assert ff_data['total'] >= 1

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 401

    def test_feature_flag_counted_as_diverged(self):
        """Vérifie que la logique diverged détecte updated_at > last_synced_at."""
        import datetime
        from django.utils import timezone
        past_time = timezone.now() - datetime.timedelta(hours=1)
        FeatureFlag.objects.create(flag_key='test-diverged-ff', enabled=True)
        # Mettre last_synced_at dans le passé sans toucher updated_at (auto_now)
        FeatureFlag.objects.filter(flag_key='test-diverged-ff').update(last_synced_at=past_time)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/config-sync/status/')
        assert response.status_code == 200
        ff_data = next(
            e for e in response.json()['data']['entity_types']
            if e['entity_type'] == 'feature-flags'
        )
        assert ff_data['diverged'] >= 1
